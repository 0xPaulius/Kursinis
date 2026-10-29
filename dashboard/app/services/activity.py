"""
Įrenginio veiksmų srautas („Paskutiniai veiksmai") iš jo žurnalų.

classify() verčia Loki įrašą į ActivityItem arba None (ne veiksmas). Syslog eilutės
skaidomos pagal kolektoriaus syslog-ng šabloną į programą ir žinutę; Windows įvykiai —
Alloy windowsevent JSON. Taisyklės tikrinamos eilės tvarka, galioja pirmoji tikusi.
Taisyklių pasirinkimas: docs/superpowers/specs/2026-10-29-device-detail-design.md (4.7).

Eilutes gali siųsti bet kas (syslog be autentifikacijos): per ilgos praleidžiamos, o
reguliarieji reiškiniai parašyti be kvadratinio „backtracking" (tik vienas pradžios taškas
arba ribotas fragmentas).
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.models.schemas import ActivityItem
from app.services.loki_client import ns_to_datetime

TEXT_LIMIT = 200
USER_LIMIT = 64
MAX_LINE_LENGTH = 4096              # syslog: ilgesnės eilutės — ne veiksmai (ir regex darbo riba)
MAX_WINDOWS_LINE_LENGTH = 131_072   # Windows JSON (scenarijų blokai, užkoduotos komandos); JSON ir regex tiesiniai

# Loki užklausų filtrai (device_details.py). Procesų paleidimai (auditd EXECVE, Sysmon 1) — atskiros
# užklausos, kad dažni įvykiai neišstumtų retų (paskyros, žurnalo išvalymas) iš eilučių ribos.
SYSLOG_PREFILTER = "|".join((  # noqa: FLY002 — po vieną alternatyvą, kad būtų skaitoma
    "Accepted ", r"Failed \S+ for ", "New session ", "COMMAND=", "session opened for user root",
    "authentication failure", "new user: ", "new group: ", "to group ", "delete user '",
    "password changed for ", "Linux version ", "USER_PROCESS: ", "successfully logged on",
    "logged in from ", "The operating system started", "Installation Successful",
))
EXECVE_FILTER = "type=EXECVE"
WINDOWS_EVENT_IDS = "4624|4625|4720|4726|4732|4740|1102|4104"
SYSMON_PROCESS_EVENT_ID = "1"

# OpenSSH ≥ 9.8 žurnale — „sshd-session" / „sshd-auth", ne „sshd".
_SSHD = {"sshd", "sshd-session", "sshd-auth"}

# syslog-ng šablonas: <laikas> <host> <facility>.<level> <program>[<pid>]: <žinutė>
_SYSLOG_RE = re.compile(r"^\S+\s+\S+\s+\w+\.\w+\s+(?P<program>[^\[]+)\[\d*\]:\s(?P<message>.*)$", re.DOTALL)
_EXECVE_ARG_RE = re.compile(r'\ba\d+=("[^"]*"|[0-9A-Fa-f]+)')
# XML tekste „<" visada užkoduotas (&lt;), tad reikšmė baigiasi ties pirmu „<" — tiesinis reiškinys.
_DATA_RE = re.compile(r'<Data Name="([^"]+)">([^<]*)</Data>')
_USERDATA_RE = re.compile(r"<(\w+)>([^<]*)</\1>")
_LOGON_TYPES = {"2": "interactive", "7": "unlock", "10": "remote", "11": "cached"}

Found = tuple[str, str, str]   # (kind, user, text)


@dataclass(frozen=True)
class _Rule:
    programs: frozenset[str] | None     # None — bet kuri programa
    pattern: re.Pattern[str]
    kind: str
    build: Callable[[re.Match[str], str], tuple[str, str] | None]   # (user, text); None — ne veiksmas
    exclude: frozenset[str] = frozenset()


def _rule(programs, pattern: str, kind: str, build, exclude=()) -> _Rule:
    return _Rule(frozenset(programs) if programs else None, re.compile(pattern), kind, build, frozenset(exclude))


def _execve_command(args: str) -> str:
    """auditd EXECVE a0..aN -> komanda; reikšmes be kabučių auditd užkoduoja hex."""
    parts = []
    for raw in _EXECVE_ARG_RE.findall(args):
        if raw.startswith('"'):
            parts.append(raw[1:-1])
            continue
        try:
            parts.append(bytes.fromhex(raw).decode("utf-8", "replace"))
        except ValueError:
            parts.append(raw)
    return " ".join(parts)


def _logind(m: re.Match[str], _program: str) -> tuple[str, str] | None:
    # „manager" (vartotojo systemd), „greeter", „background" sesijos — ne prisijungimai.
    if m["cls"] not in (None, "user"):
        return None
    return m["user"], f"Session {m['id']} started"


# Programų vardai mažosiomis (lyginama be raidžių dydžio).
_SYSLOG_RULES: tuple[_Rule, ...] = (
    _rule(_SSHD, r"^Accepted (\S+) for (\S+) from (\S+)", "login",
          lambda m, p: (m[2], f"SSH login from {m[3]} ({m[1]})")),
    _rule(_SSHD, r"^Failed \S+ for (?:invalid user )?(\S+) from (\S+)", "auth_failed",
          lambda m, p: (m[1], f"SSH login failed from {m[2]}")),
    _rule({"systemd-logind"},
          r"^New session '?(?P<id>[^' ]+?)'? of user '?(?P<user>[^' ]+?)'?(?: with class '(?P<cls>[^']+)'|\.?$)",
          "login", _logind),
    # sudo: „user : <priežastis> ; ... COMMAND=" — nesėkmė; „user : TTY=... ; COMMAND=" — komanda.
    # Priežastis baigiasi ne tarpu prieš „ ;" — taip reiškinys lieka tiesinis.
    _rule({"sudo"}, r"^\s*(\S+) : ([^;=]*[^;=\s]) ;.*COMMAND=", "auth_failed",
          lambda m, p: (m[1], f"sudo: {m[2]}")),
    _rule({"sudo"}, r"^\s*(\S+) : .*COMMAND=(.+)$", "admin",
          lambda m, p: (m[1], f"sudo {m[2]}")),
    _rule({"su", "su-l"}, r"session opened for user root(?:\(uid=0\))? by ([^\s(]+)", "admin",
          lambda m, p: (m[1], "su to root")),
    # sshd ir sudo nesėkmes aprašo savo eilutės — pam dublikatų nerodome.
    # „user=" ieškoma tik iki kito „;" (kitaip kiekvienas pakartojimas skenuotų iki galo).
    _rule(None, r"authentication failure;[^;]*\buser=(\S+)", "auth_failed",
          lambda m, p: (m[1], f"{p}: authentication failure"), exclude=_SSHD | {"sudo"}),
    _rule({"useradd"}, r"^new user: name=([^,\s]+)", "account",
          lambda m, p: (m[1], f"User {m[1]} created")),
    _rule({"useradd", "groupadd"}, r"^new group: name=([^,\s]+)", "account",
          lambda m, p: ("", f"Group {m[1]} created")),
    # Narystė grupėje (wheel, sudo ...) — svarbiausias teisių išplėtimo ženklas.
    _rule({"useradd", "usermod", "gpasswd"}, r"add '([^']+)' to group '([^']+)'", "account",
          lambda m, p: (m[1], f"{m[1]} added to group {m[2]}")),
    _rule({"gpasswd"}, r"^user (\S+) added by (\S+) to group (\S+)", "account",
          lambda m, p: (m[1], f"{m[1]} added to group {m[3]} by {m[2]}")),
    _rule({"userdel"}, r"^delete user '([^']+)'", "account",
          lambda m, p: (m[1], f"User {m[1]} deleted")),
    _rule({"passwd", "chpasswd"}, r"password changed for (\S+)", "account",
          lambda m, p: (m[1], f"Password changed for {m[1]}")),
    _rule({"kernel"}, r"^Linux version (\S+)", "boot",
          lambda m, p: ("", f"System booted (Linux {m[1]})")),
    # auditd įrašas žinutės pradžioje (audisp-syslog arba žalias linux_endpoint įrašas).
    _rule(None, r"^(?:node=\S+ )?type=EXECVE msg=audit\([^)]*\): argc=\d+ (.*)$", "command",
          lambda m, p: ("", _execve_command(m[1]))),
    # Demonstraciniai įrenginiai (services/syslog_emitter.py šablonai)
    _rule({"loginwindow"}, r"USER_PROCESS: user (\S+) session opened", "login",
          lambda m, p: (m[1], "Session opened")),
    _rule({"security-auditing"}, r"successfully logged on \(Event 4624\) for (\S+)(?: from (\S+))?", "login",
          lambda m, p: (m[1], f"Logon from {m[2]}" if m[2] else "Logon")),
    _rule({"system"}, r"^user (\S+) logged in from (\S+) via (\S+)", "login",
          lambda m, p: (m[1], f"Login from {m[2]} via {m[3]}")),
    _rule({"kernel-general"}, r"The operating system started", "boot",
          lambda m, p: ("", "System started")),
    _rule({"windowsupdateclient"}, r"Installation Successful: (.+)$", "update",
          lambda m, p: ("", f"Update installed: {m[1]}")),
)


def _classify_syslog(line: str) -> Found | None:
    m = _SYSLOG_RE.match(line)
    # Be syslog šablono (linux_endpoint: žalias auditd įrašas) tikrinama visa eilutė.
    program, message = (m["program"].strip().lower(), m["message"]) if m else ("", line)
    for rule in _SYSLOG_RULES:
        if (rule.programs is not None and program not in rule.programs) or program in rule.exclude:
            continue
        hit = rule.pattern.search(message)
        if hit:
            built = rule.build(hit, program)
            return None if built is None else (rule.kind, *built)
    return None


def _win_fields(obj: dict) -> dict[str, str]:
    """<Data Name="K">V</Data> (EventData) ir <K>V</K> (UserData, pvz. 1102) -> laukai."""
    fields = dict(_DATA_RE.findall(str(obj.get("event_data") or "")))
    fields.update(_USERDATA_RE.findall(str(obj.get("user_data") or "")))
    return fields


def _from(ip: str) -> str:
    return f" from {ip}" if ip and ip not in ("-", "::1", "127.0.0.1") else ""


def _classify_windows(obj: dict) -> Found | None:
    try:
        eid = int(obj["event_id"])
    except (KeyError, TypeError, ValueError):
        return None
    d = _win_fields(obj)
    target, subject = d.get("TargetUserName", ""), d.get("SubjectUserName", "")
    if eid == 1:
        if "sysmon" not in str(obj.get("channel", "")).lower():
            return None
        image = d.get("Image", "").rsplit("\\", 1)[-1]
        return "command", d.get("User", ""), f"{image}: {d.get('CommandLine', '')}"
    if eid == 4624:
        logon = _LOGON_TYPES.get(d.get("LogonType", ""))   # tarnybos (5) ir tinklo (3) — triukšmas
        return ("login", target, f"Logon ({logon}){_from(d.get('IpAddress', ''))}") if logon else None
    if eid == 4625:
        return "auth_failed", target, f"Logon failed{_from(d.get('IpAddress', ''))}"
    if eid in (4720, 4726):
        return "account", target, f"User {target} {'created' if eid == 4720 else 'deleted'} by {subject}"
    if eid == 4732:
        member = d.get("MemberName", "")
        member = d.get("MemberSid", "") if member in ("", "-") else member
        return "account", member, f"{member} added to group {target}"
    if eid == 4740:
        return "account", target, f"Account {target} locked out"
    if eid == 1102:
        return "log_cleared", subject, "Security log cleared"
    # 4104: tik tie, kuriuos pati Windows pažymėjo kaip įtartinus (Warning lygis).
    if eid == 4104 and (str(obj.get("level")) == "3" or obj.get("levelText") == "Warning"):
        return "script", "", f"Suspicious PowerShell: {d.get('ScriptBlockText', '')[:120]}"
    return None


def _clean(text: str, limit: int) -> str:
    """Valdymo ir formatavimo (pvz. bidi) simboliai -> tarpai, tarpai suspaudžiami, ilgis ribojamas."""
    text = "".join(" " if unicodedata.category(ch) in ("Cc", "Cf") else ch for ch in text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def classify(entry: dict) -> ActivityItem | None:
    """Loki įrašas ({timestamp, line, labels}) -> ActivityItem; None, jei tai ne veiksmas."""
    when = ns_to_datetime(entry.get("timestamp"))
    line = entry.get("line") or ""
    if when is None or not line:
        return None
    if (entry.get("labels") or {}).get("job") == "windows":
        if len(line) > MAX_WINDOWS_LINE_LENGTH:
            return None
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError):
            return None
        hit = _classify_windows(obj) if isinstance(obj, dict) else None
    else:
        if len(line) > MAX_LINE_LENGTH:
            return None
        hit = _classify_syslog(line)
    if hit is None:
        return None
    kind, user, text = hit
    return ActivityItem(time=when.isoformat(), kind=kind,
                        user=_clean(user, USER_LIMIT), text=_clean(text, TEXT_LIMIT))
