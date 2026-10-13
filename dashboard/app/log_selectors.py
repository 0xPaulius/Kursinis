"""
Bendras žurnalų srautų (job) selektorius dashboard užklausoms.

Į srautą įtraukiami ir syslog (Linux/tinklas), ir windows (endpoint telemetrija),
kad galiniai įrenginiai matytųsi grafikuose, įrenginių žemėlapyje ir būklėje.
"""
from __future__ import annotations

import os

# Reguliarioji job reikšmė; keičiama per env. Apima syslog + endpoint telemetriją.
LOG_JOBS = os.getenv("LOG_JOBS", "syslog|windows|linux_endpoint")


def logs_selector(host: str | None = None) -> str:
    """LogQL srauto selektorius; su `host` — tik to įrenginio srautas."""
    parts = [f'job=~"{LOG_JOBS}"']
    if host:
        parts.append(f'host="{host}"')
    return "{" + ", ".join(parts) + "}"
