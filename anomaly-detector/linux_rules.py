"""
Linux endpoint telemetrijos taisyklės (job="linux_endpoint"): auditd įrašai,
surinkti Alloy agento (lab/linux/config.alloy), susieti su MITRE ATT&CK.

auditd eilutės yra key=value formato, pvz.:
  type=USER_AUTH msg=audit(1699...:42): pid=1 uid=1000 acct="root" exe="/usr/bin/sudo" res=failed
  type=ADD_USER  msg=audit(...): ... acct="backdoor" exe="/usr/sbin/useradd" res=success
  type=EXECVE    msg=audit(...): argc=2 a0="bash" a1="-i"

host imamas iš Loki etiketės (auditd eilutėje jo nėra). Taisyklės skaito tik
laukus (ne lokalizuotą tekstą), todėl nepriklauso nuo kalbos.
"""
from __future__ import annotations

import datetime
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import attack_catalog
from common import SAMPLE_LINE_LIMIT, Alert, LokiClient, Selectors, utcnow

_KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
_SUDO_EXES = ("sudo", "su", "pkexec")
_DISCOVERY = {"whoami", "id", "uname", "hostname", "netstat", "ss", "ip", "ifconfig",
              "arp", "last", "w", "who", "ps", "lsof", "getent"}
# Reverse shell / įtartini vykdymo šablonai (T1059.004)
_SUSPICIOUS_EXEC = re.compile(
    r"(?i)(-i\b.*(bash|sh|zsh)|(bash|sh|zsh)\b.*-i|/dev/tcp/|nc\b.*-e|ncat\b.*-e|"
    r"socket\.socket|pty\.spawn|base64\s+-d|curl\b.*\|\s*(bash|sh)|wget\b.*\|\s*(bash|sh))")

SUDO_FAILURE_THRESHOLD = 3     # nesėkmingi sudo/su per host+user
DISCOVERY_BURST_THRESHOLD = 4  # skirtingos žvalgybos komandos per host


@dataclass
class AuditEvent:
    type: str
    fields: dict[str, str]
    command: str = ""
    host: str = "unknown"
    raw: str = ""


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_audit(line: str, host: str = "unknown") -> Optional[AuditEvent]:
    """auditd key=value eilutė -> AuditEvent (arba None, jei nėra `type=`)."""
    pairs = {k: _unquote(v) for k, v in _KV_RE.findall(line)}
    etype = pairs.get("type")
    if not etype:
        return None
    # EXECVE: a0, a1, ... -> viena komanda
    args = [pairs[f"a{i}"] for i in range(0, 64) if f"a{i}" in pairs]
    command = " ".join(args)
    return AuditEvent(type=etype, fields=pairs, command=command, host=host, raw=line)


class LinuxEndpointRuleDetector:
    """Taisyklėmis pagrįstas aptikimas Linux endpoint telemetrijai (job="linux_endpoint")."""

    def __init__(self, loki: LokiClient, selectors: Optional[Selectors] = None):
        self.loki = loki
        self.sel = selectors or Selectors()

    def _alert(self, now, alert_type, severity, description, host="", ip="", details=None, sample=""):
        return Alert(
            timestamp=now.isoformat(), severity=severity, detection_method="rule",
            alert_type=alert_type, description=description, source_host=host, source_ip=ip,
            details=details or {}, sample_lines=[sample] if sample else [],
            attack_techniques=attack_catalog.techniques_for(alert_type),
        )

    def check(self, window_minutes: int = 5, now: Optional[datetime.datetime] = None) -> list[Alert]:
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)
        entries = self.loki.query_range(self.sel.linux_endpoint, start=start, end=now)
        events = []
        for e in entries:
            ev = parse_audit(e["line"], e.get("labels", {}).get("host", "unknown"))
            if ev:
                events.append(ev)
        if not events:
            return []

        alerts: list[Alert] = []
        alerts += self._sudo_failures(events, now, window_minutes)
        alerts += self._discovery_burst(events, now, window_minutes)
        for ev in events:
            alerts += self._per_event(ev, now)
        return alerts

    def _per_event(self, ev: AuditEvent, now) -> list[Alert]:
        out = []
        if ev.type in ("ADD_USER", "USER_MGMT") and ev.fields.get("res") == "success" \
                and "useradd" in ev.fields.get("exe", ""):
            acct = ev.fields.get("acct", "?")
            out.append(self._alert(now, "linux_account_created", "medium",
                f"Sukurta nauja Linux paskyra '{acct}' ({ev.host})",
                host=ev.host, details={"acct": acct}, sample=ev.raw))
        if ev.type == "EXECVE" and ev.command and _SUSPICIOUS_EXEC.search(ev.command):
            out.append(self._alert(now, "linux_suspicious_execve", "high",
                f"Įtartina komanda host'e {ev.host}: {ev.command[:160]}",
                host=ev.host, details={"command": ev.command[:400]}, sample=ev.raw))
        return out

    def _sudo_failures(self, events, now, window_minutes) -> list[Alert]:
        by_key: Counter = Counter()
        sample: dict[tuple, str] = {}
        for ev in events:
            exe = ev.fields.get("exe", "")
            if ev.type in ("USER_AUTH", "USER_LOGIN") and ev.fields.get("res") == "failed" \
                    and any(s in exe for s in _SUDO_EXES):
                key = (ev.host, ev.fields.get("acct", "?"))
                by_key[key] += 1
                sample.setdefault(key, ev.raw)
        alerts = []
        for (host, acct), count in by_key.items():
            if count >= SUDO_FAILURE_THRESHOLD:
                alerts.append(self._alert(now, "linux_sudo_auth_failure",
                    "high" if count >= SUDO_FAILURE_THRESHOLD * 3 else "medium",
                    f"Nesėkmingi teisių kėlimo bandymai (sudo/su): {count} vartotojui '{acct}' "
                    f"host'e {host} per {window_minutes} min",
                    host=host, details={"attempts": count, "account": acct}, sample=sample[(host, acct)]))
        return alerts

    def _discovery_burst(self, events, now, window_minutes) -> list[Alert]:
        by_host: dict[str, set[str]] = defaultdict(set)
        sample: dict[str, str] = {}
        for ev in events:
            if ev.type == "EXECVE" and ev.command:
                cmd = ev.command.split(" ", 1)[0].rsplit("/", 1)[-1]
                if cmd in _DISCOVERY:
                    by_host[ev.host].add(cmd)
                    sample.setdefault(ev.host, ev.raw)
        alerts = []
        for host, cmds in by_host.items():
            if len(cmds) >= DISCOVERY_BURST_THRESHOLD:
                alerts.append(self._alert(now, "linux_discovery_burst", "medium",
                    f"Žvalgybos komandų serija host'e {host}: {len(cmds)} komandų "
                    f"({', '.join(sorted(cmds))}) per {window_minutes} min",
                    host=host, details={"commands": sorted(cmds)}, sample=sample[host]))
        return alerts
