"""
AIT Log Data Set v2.0 adapteris (Landauer et al., 2022; CC BY-NC-SA 4.0).

Struktūra (scenarijaus kataloge):
  dataset.yaml                      — pavadinimas, start, end
  gather/<host>/logs/<failas>       — žali žurnalai
  labels/<host>/logs/<failas>       — JSON eilutės {"line": N, "labels": [...]} į žalią failą
  gather/attacker_0/logs/attacks.log — atakos žingsnių tvarkaraštis (UTC)

Žymės (labels) remiasi eilutės numeriu žaliame faile, todėl žymimos tos eilutės,
kurių (host, kelias, numeris) yra žymių faile. AIT serveriai veikia UTC.

Apribojimas: žali syslog failai neturi facility/severity, todėl severity = "info"
(error-rate taisyklė AIT rinkinyje neįvertinama — tik laboratorijos duomenyse).
"""
from __future__ import annotations

import datetime
import fnmatch
import json
import re
from pathlib import Path

from ..schema import AttackInterval, Dataset, Event

UTC = datetime.timezone.utc

# Žurnalų šaltiniai, kuriuos vertiname (atitinka tai, ką maža org. siųstų per syslog).
DEFAULT_SOURCES = [
    "*/logs/auth.log*",
    "*/logs/syslog*",
    "*/logs/apache2/*access.log*",
]
# dnsmasq numatytai neįtraukiamas: dnsteal eksfiltracija žymima per visą scenarijų
# (nuo pirmos eilutės iki dnsteal_stop), todėl beveik kiekvienas 5 min langas būtų
# „ataka" ir langų metrikos prarastų prasmę. Įjungiama per --sources.
DNSMASQ_SOURCE = "*/logs/dnsmasq.log*"

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

_SYSLOG_RE = re.compile(
    r"^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<prog>[^\s:\[]+)(?:\[(?P<pid>\d+)\])?:\s?(?P<msg>.*)$"
)
_DNSMASQ_RE = re.compile(
    r"^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"dnsmasq\[(?P<pid>\d+)\]:\s?(?P<msg>.*)$"
)
_APACHE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) (?P<size>\S+)'
)
_AUTH_PROGRAMS = {"sshd", "su", "sudo", "login", "passwd", "useradd", "usermod", "systemd-logind",
                  "CRON", "cron", "polkitd", "pkexec"}


def _load_yaml_scalar(path: Path) -> dict[str, str]:
    """dataset.yaml yra plokščias raktas: reikšmė — neverta yaml priklausomybės."""
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        if ":" in raw and not raw.startswith("#"):
            key, _, value = raw.partition(":")
            out[key.strip()] = value.strip().strip("'\"")
    return out


def _parse_iso(value: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _host_from_dir(name: str) -> str:
    return name.replace("_", "-")


def _facility_for(source_rel: str, program: str) -> str:
    if "auth.log" in source_rel or program in _AUTH_PROGRAMS:
        return "auth"
    if program == "kernel":
        return "kern"
    return "daemon"


def _load_labels(root: Path) -> dict[tuple[str, int], list[str]]:
    """(host/logs/kelias, eilutės nr.) -> žymių sąrašas."""
    labels: dict[tuple[str, int], list[str]] = {}
    base = root / "labels"
    if not base.is_dir():
        return labels
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        for raw in path.read_text(errors="replace").splitlines():
            if not raw.strip():
                continue
            entry = json.loads(raw)
            labels[(rel, int(entry["line"]))] = list(entry.get("labels", []))
    return labels


def _parse_syslog(line: str, year: int) -> tuple[datetime.datetime, str, str, str, str] | None:
    m = _SYSLOG_RE.match(line)
    if not m or m["mon"] not in _MONTHS:
        return None
    hh, mm, ss = (int(x) for x in m["time"].split(":"))
    ts = datetime.datetime(year, _MONTHS[m["mon"]], int(m["day"]), hh, mm, ss, tzinfo=UTC)
    return ts, m["host"], m["prog"], m["pid"] or "", m["msg"]


def _parse_apache(line: str) -> datetime.datetime | None:
    m = _APACHE_RE.match(line)
    if not m:
        return None
    return datetime.datetime.strptime(m["ts"], "%d/%b/%Y:%H:%M:%S %z").astimezone(UTC)


def _cluster_intervals(events: list[Event], gap: datetime.timedelta) -> list[AttackInterval]:
    """Atakos intervalai pagal pirmą žymę (fazę); artimos žymės sujungiamos per `gap`."""
    by_phase: dict[str, list[datetime.datetime]] = {}
    for ev in events:
        if ev.is_attack and ev.attack_labels:
            by_phase.setdefault(ev.attack_labels[0], []).append(ev.ts)

    intervals: list[AttackInterval] = []
    for phase, stamps in by_phase.items():
        stamps.sort()
        start = prev = stamps[0]
        for ts in stamps[1:]:
            if ts - prev > gap:
                intervals.append(AttackInterval(phase, start, prev))
                start = ts
            prev = ts
        intervals.append(AttackInterval(phase, start, prev))
    return sorted(intervals, key=lambda i: i.start)


def load(scenario_dir: str | Path, sources: list[str] | None = None,
         gap_minutes: int = 10) -> Dataset:
    root = Path(scenario_dir)
    meta = _load_yaml_scalar(root / "dataset.yaml")
    start, end = _parse_iso(meta["start"]), _parse_iso(meta["end"])
    year = start.year
    patterns = sources or DEFAULT_SOURCES
    labels = _load_labels(root)

    events: list[Event] = []
    gather = root / "gather"
    for path in sorted(gather.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(gather).as_posix()          # <host>/logs/...
        if not any(fnmatch.fnmatch(rel, p) for p in patterns):
            continue
        host_dir = rel.split("/", 1)[0]
        is_apache = "/apache2/" in rel
        is_dnsmasq = "dnsmasq.log" in rel
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            if is_dnsmasq:
                m = _DNSMASQ_RE.match(line)
                if not m or m["mon"] not in _MONTHS:
                    continue
                hh, mm, ss = (int(x) for x in m["time"].split(":"))
                ts = datetime.datetime(year, _MONTHS[m["mon"]], int(m["day"]), hh, mm, ss, tzinfo=UTC)
                ev = Event(ts=ts, host=_host_from_dir(host_dir), message=m["msg"],
                           program="dnsmasq", pid=m["pid"], facility="daemon")
            elif is_apache:
                ts = _parse_apache(line)
                if ts is None:
                    continue
                ev = Event(ts=ts, host=_host_from_dir(host_dir), message=line,
                           program="apache2", facility="daemon")
            else:
                parsed = _parse_syslog(line, year)
                if parsed is None:
                    continue
                ts, host, prog, pid, msg = parsed
                ev = Event(ts=ts, host=host, message=msg, program=prog, pid=pid,
                           facility=_facility_for(rel, prog))
            attack = labels.get((rel, lineno))
            if attack:
                ev.is_attack = True
                ev.attack_labels = attack
            events.append(ev)

    events = [e for e in events if start <= e.ts < end]
    attacks = _cluster_intervals(events, datetime.timedelta(minutes=gap_minutes))
    return Dataset(name=meta.get("name", root.name), events=events, attacks=attacks,
                   start=start, end=end)


def attack_schedule(scenario_dir: str | Path) -> list[tuple[datetime.datetime, str]]:
    """attacks.log žingsniai (laikas, pavadinimas) — kontekstui ir grafikams."""
    path = Path(scenario_dir) / "gather" / "attacker_0" / "logs" / "attacks.log"
    if not path.is_file():
        return []
    steps = []
    for raw in path.read_text().splitlines():
        stamp, _, name = raw.rpartition(" ")
        if stamp:
            steps.append((_parse_iso(stamp.replace(" ", "T", 1)), name))
    return steps
