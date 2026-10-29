"""
Įvykių atvaizdavimas į tą patį formatą, kurį gamina gyvas konvejeris.

syslog-ng rašo šabloną `${R_ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`,
o Alloy jį parsina ir prideda etiketes (host, facility, severity, program) bei
`job` iš failo (all-*.log=syslog, errors-*.log=errors, security-*.log=security).
Vertinime gavimo laiką atstoja originali rinkinio laiko žyma.

Vertinime tą patį eventą paduodame į kelis srautus (job), kad detektorius matytų
identišką vaizdą kaip gyvai: visada `syslog`, papildomai `errors` jei severity>=err,
ir `security` jei žinutė atitinka syslog-ng f_security filtrą.
"""
from __future__ import annotations

import re

from .schema import Event

# Atitinka config/alloy/collector.alloy regex ir syslog-ng šabloną.
LINE_TEMPLATE = "{iso} {host} {facility}.{severity} {program}[{pid}]: {message}"

_ERROR_SEVERITIES = {"err", "crit", "alert", "emerg", "error"}

# Atitinka config/syslog-ng/syslog-ng.conf filter f_security match() sąrašą.
_SECURITY_PATTERNS = re.compile(
    r"Failed password|authentication failure|Invalid user|BREAK-IN ATTEMPT|"
    r"refused connect|unauthorized|denied|blocked|attack|DROP|REJECT"
)


def is_endpoint(ev: Event) -> bool:
    """Endpoint telemetrija (Windows/Linux Alloy agentas) — ne syslog šablonas.

    Tokios eilutės į Loki eina žalios (pvz. Windows įvykio JSON), kaip jas pateiktų
    `loki.source.windowsevent`, ir su savo etiketėmis (job, host, channel)."""
    return bool(ev.extra_labels) or ev.job not in ("syslog", "errors", "security")


def render_line(ev: Event) -> str:
    """syslog įvykiui — syslog-ng šablono eilutė; endpoint įvykiui — žalia žinutė (JSON)."""
    if is_endpoint(ev):
        return ev.message
    iso = ev.ts.isoformat()
    return LINE_TEMPLATE.format(
        iso=iso, host=ev.host, facility=ev.facility, severity=ev.severity,
        program=ev.program, pid=ev.pid, message=ev.message,
    )


def stream_labels(ev: Event) -> dict[str, str]:
    """Alloy etiketės srautui: syslog — host/facility/severity/program; endpoint — job/host + extra."""
    if is_endpoint(ev):
        return {"job": ev.job, "host": ev.host, **{k: str(v) for k, v in ev.extra_labels.items()}}
    return {
        "job": ev.job,
        "host": ev.host,
        "facility": ev.facility,
        "severity": ev.severity,
        "program": ev.program.strip(),
    }


def routed_jobs(ev: Event) -> list[str]:
    """Į kuriuos job srautus syslog-ng nukreiptų šį įvykį (be pagrindinio dubliavimo)."""
    if is_endpoint(ev):
        return [ev.job]   # endpoint srautai neina per syslog-ng failų maršrutizaciją
    jobs = [ev.job]
    if ev.severity in _ERROR_SEVERITIES:
        jobs.append("errors")
    if _SECURITY_PATTERNS.search(ev.message):
        jobs.append("security")
    return jobs
