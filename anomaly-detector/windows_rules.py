"""
Windows endpoint telemetrijos taisyklės (job="windows"): Security, Sysmon ir
PowerShell įvykiai, susieti su MITRE ATT&CK.

Įvykiai ateina kaip Alloy `loki.source.windowsevent` JSON eilutės (žr.
tests/fixtures/windows/windows_golden.json). `event_data` / `user_data` yra
`<EventData>` / `<UserData>` InnerXML — iš jo išgaunami pavadinti laukai.

Taisyklės skaito tik `event_id` ir laukus (ne lokalizuotą `message`), todėl veikia
nepriklausomai nuo Windows kalbos.
"""
from __future__ import annotations

import datetime
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

import attack_catalog
from common import SAMPLE_LINE_LIMIT, Alert, LokiClient, Selectors, utcnow

# <Data Name="K">V</Data> (EventData) ir <K>V</K> (UserData, pvz. 1102)
_DATA_RE = re.compile(r'<Data Name="([^"]+)">(.*?)</Data>', re.DOTALL)
_USERDATA_RE = re.compile(r"<(\w+)>([^<]*)</\1>")

_PRIVATE_IP = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|169\.254\.|::1|fe80:|f[cd])")
_DISCOVERY_PROCS = {"whoami.exe", "net.exe", "net1.exe", "ipconfig.exe", "systeminfo.exe",
                    "nltest.exe", "quser.exe", "tasklist.exe", "hostname.exe", "arp.exe",
                    "route.exe", "netstat.exe", "wmic.exe"}
_LOLBINS = {"rundll32.exe", "regsvr32.exe", "mshta.exe", "powershell.exe", "pwsh.exe",
            "certutil.exe", "bitsadmin.exe", "cscript.exe", "wscript.exe", "msiexec.exe"}
_SUSPICIOUS_PS = re.compile(
    r"(?i)(IEX|Invoke-Expression|DownloadString|DownloadFile|FromBase64String|"
    r"-enc\b|-encodedcommand|Net\.WebClient|Invoke-WebRequest|Start-BitsTransfer|"
    r"Reflection\.Assembly|-nop\b|-w\s+hidden|hidden)")
_ADMIN_GROUP_SIDS = {"S-1-5-32-544"}  # Administrators (lokalizacijai atsparu)


@dataclass
class WinEvent:
    event_id: int
    channel: str
    computer: str
    data: dict[str, str]
    message: str = ""
    level_text: str = ""
    raw: str = ""

    def image_name(self, key: str = "Image") -> str:
        return self.data.get(key, "").rsplit("\\", 1)[-1].lower()


def parse_event(line: str) -> Optional[WinEvent]:
    """Alloy windowsevent JSON eilutė -> WinEvent (arba None, jei ne JSON / be event_id)."""
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None
    if "event_id" not in obj:
        return None
    data: dict[str, str] = {}
    for key, value in _DATA_RE.findall(obj.get("event_data", "") or ""):
        data[key] = value.strip()
    for key, value in _USERDATA_RE.findall(obj.get("user_data", "") or ""):
        data.setdefault(key, value.strip())
    return WinEvent(
        event_id=int(obj["event_id"]),
        channel=obj.get("channel", ""),
        computer=obj.get("computer", "") or obj.get("host", ""),
        data=data,
        message=obj.get("message", ""),
        level_text=obj.get("levelText", ""),
        raw=line,
    )


# ---------------------------------------------------------------------------
# Taisyklės
# ---------------------------------------------------------------------------

@dataclass
class PerEventRule:
    """Taisyklė, vertinanti vieną įvykį. `match` grąžina (raktas, aprašas) arba None."""
    event_ids: set[int]
    alert_type: str
    severity: str
    match: Callable[[WinEvent], Optional[tuple[str, str]]]
    key_as: str = "detail"   # kur dėti `raktą`: "ip" (source_ip), "host" (source_host) ar "detail"


def _rule_account_created(ev: WinEvent):
    user = ev.data.get("TargetUserName", "?")
    return (user, f"Sukurta nauja Windows paskyra '{user}' (sukūrė {ev.data.get('SubjectUserName','?')})")


def _rule_account_lockout(ev: WinEvent):
    user = ev.data.get("TargetUserName", "?")
    return (user, f"Windows paskyra '{user}' užrakinta (galimas slaptažodžių spėjimas)")


def _rule_admin_group_add(ev: WinEvent):
    if ev.data.get("TargetSid") not in _ADMIN_GROUP_SIDS:
        return None  # ne administratorių grupė
    member = ev.data.get("MemberSid", ev.data.get("MemberName", "?"))
    return (member, f"Narys {member} įtrauktas į administratorių grupę "
                    f"({ev.data.get('TargetUserName','Administrators')})")


def _rule_audit_cleared(ev: WinEvent):
    who = ev.data.get("SubjectUserName", "?")
    return (who, f"Išvalytas Windows saugumo audito žurnalas (vartotojas {who}) — galimas pėdsakų slėpimas")


def _rule_suspicious_powershell(ev: WinEvent):
    script = ev.data.get("ScriptBlockText", "")
    if not _SUSPICIOUS_PS.search(script):
        return None
    snippet = script[:160]
    return (snippet, f"Įtartinas PowerShell scenarijus: {snippet}")


def _rule_startup_persistence(ev: WinEvent):
    target = ev.data.get("TargetFilename", "")
    if "\\Start Menu\\Programs\\Startup\\" not in target and "\\Startup\\" not in target:
        return None
    return (target, f"Failas įrašytas į paleisties (Startup) aplanką: {target} "
                    f"(procesas {ev.image_name()}) — užsitvirtinimas")


def _rule_lolbin_network(ev: WinEvent):
    if ev.image_name() not in _LOLBINS:
        return None
    dest = ev.data.get("DestinationIp", "")
    if not dest or _PRIVATE_IP.match(dest):
        return None  # vidinis / tuščias adresas — ne eksfiltracija
    return (dest, f"LOLBin {ev.image_name()} jungiasi į išorinį {dest}:"
                  f"{ev.data.get('DestinationPort','?')} — galimas įrankio parsiuntimas")


_PER_EVENT_RULES = [
    PerEventRule({4720}, "win_account_created", "medium", _rule_account_created),
    PerEventRule({4740}, "win_account_lockout", "medium", _rule_account_lockout),
    PerEventRule({4732}, "win_admin_group_add", "high", _rule_admin_group_add),
    PerEventRule({1102}, "win_audit_log_cleared", "high", _rule_audit_cleared),
    PerEventRule({4104}, "win_suspicious_powershell", "high", _rule_suspicious_powershell),
    PerEventRule({11}, "win_startup_persistence", "high", _rule_startup_persistence),
    PerEventRule({3}, "win_lolbin_network", "medium", _rule_lolbin_network, key_as="ip"),
]

# Užklausa grąžina tik taisyklių event ID (1 ir 4625 — agregacijos taisyklės): tankus Sysmon
# srautas kitaip viršija query_range 5000 eilučių ribą ir dalis įvykių taisyklių nepasiekia.
RULE_EVENT_IDS = sorted({eid for rule in _PER_EVENT_RULES for eid in rule.event_ids} | {1, 4625})
_EVENT_ID_FILTER = f'| json event_id="event_id" | event_id=~"{"|".join(map(str, RULE_EVENT_IDS))}"'

# Agregacijos slenksčiai
FAILED_LOGON_THRESHOLD = 5     # 4625 iš to paties IP
SPRAY_DISTINCT_USERS = 5       # 4625: skirtingi vartotojai iš to paties IP
DISCOVERY_BURST_THRESHOLD = 4  # Sysmon 1 discovery procesai per host


class WindowsRuleDetector:
    """Taisyklėmis pagrįstas aptikimas Windows endpoint telemetrijai (job="windows")."""

    def __init__(self, loki: LokiClient, selectors: Optional[Selectors] = None):
        self.loki = loki
        self.sel = selectors or Selectors()

    def _alert(self, now, alert_type, severity, description, host="", ip="", details=None, sample=""):
        return Alert(
            timestamp=now.isoformat(),
            severity=severity,
            detection_method="rule",
            alert_type=alert_type,
            description=description,
            source_host=host,
            source_ip=ip,
            details=details or {},
            sample_lines=[sample] if sample else [],
            attack_techniques=attack_catalog.techniques_for(alert_type),
        )

    def check(self, window_minutes: int = 5, now: Optional[datetime.datetime] = None) -> list[Alert]:
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)
        lines = self.loki.query_range(f"{self.sel.windows} {_EVENT_ID_FILTER}", start=start, end=now)
        events = [ev for ev in (parse_event(e["line"]) for e in lines) if ev]
        if not events:
            return []

        alerts: list[Alert] = []
        alerts += self._failed_logons(events, now, window_minutes)
        alerts += self._discovery_burst(events, now, window_minutes)

        for ev in events:
            for rule in _PER_EVENT_RULES:
                if ev.event_id not in rule.event_ids:
                    continue
                result = rule.match(ev)
                if result:
                    key, description = result
                    alerts.append(self._alert(
                        now, rule.alert_type, rule.severity, description,
                        host=key if rule.key_as == "host" else ev.computer,
                        ip=key if rule.key_as == "ip" else "",
                        details={"event_id": ev.event_id, "key": key},
                        sample=ev.raw))
        return alerts

    def _failed_logons(self, events, now, window_minutes) -> list[Alert]:
        by_ip_count: Counter = Counter()
        by_ip_users: dict[str, set[str]] = defaultdict(set)
        sample: dict[str, str] = {}
        for ev in events:
            if ev.event_id != 4625:
                continue
            ip = ev.data.get("IpAddress", "").strip() or "unknown"
            by_ip_count[ip] += 1
            by_ip_users[ip].add(ev.data.get("TargetUserName", "?"))
            sample.setdefault(ip, ev.raw)

        alerts = []
        for ip, count in by_ip_count.items():
            users = by_ip_users[ip]
            if len(users) >= SPRAY_DISTINCT_USERS:
                alerts.append(self._alert(
                    now, "win_password_spray", "high",
                    f"Windows slaptažodžių purškimas: {len(users)} skirtingų vartotojų iš {ip} "
                    f"({count} nesėkmingų prisijungimų per {window_minutes} min)",
                    ip=ip, details={"distinct_users": len(users), "attempts": count},
                    sample=sample[ip]))
            elif count >= FAILED_LOGON_THRESHOLD:
                alerts.append(self._alert(
                    now, "win_failed_logon_bruteforce",
                    "high" if count >= FAILED_LOGON_THRESHOLD * 3 else "medium",
                    f"Windows prisijungimo ataka: {count} nesėkmingų bandymų iš {ip} "
                    f"per {window_minutes} min",
                    ip=ip, details={"attempts": count, "users": sorted(users)[:SAMPLE_LINE_LIMIT]},
                    sample=sample[ip]))
        return alerts

    def _discovery_burst(self, events, now, window_minutes) -> list[Alert]:
        by_host: dict[str, list[str]] = defaultdict(list)
        sample: dict[str, str] = {}
        for ev in events:
            if ev.event_id == 1 and ev.image_name() in _DISCOVERY_PROCS:
                by_host[ev.computer].append(ev.image_name())
                sample.setdefault(ev.computer, ev.raw)

        alerts = []
        for host, procs in by_host.items():
            if len(procs) >= DISCOVERY_BURST_THRESHOLD:
                alerts.append(self._alert(
                    now, "win_discovery_burst", "medium",
                    f"Žvalgybos komandų serija host'e {host}: {len(procs)} procesų "
                    f"({', '.join(sorted(set(procs)))}) per {window_minutes} min",
                    host=host, details={"process_count": len(procs),
                                        "processes": sorted(set(procs))},
                    sample=sample[host]))
        return alerts
