"""
Bendras žurnalų srautų (job) selektorius dashboard užklausoms.

Į srautą įtraukiami ir syslog (Linux/tinklas), ir windows (endpoint telemetrija),
kad galiniai įrenginiai matytųsi grafikuose, įrenginių žemėlapyje ir būklėje.
"""
from __future__ import annotations

import os
import re

# Reguliarioji job reikšmė; keičiama per env. Apima syslog + endpoint telemetriją.
LOG_JOBS = os.getenv("LOG_JOBS", "syslog|windows|linux_endpoint")

# Leistini host etiketės simboliai — apsauga nuo LogQL injekcijos per host reikšmę.
HOST_RE = re.compile(r"[A-Za-z0-9._-]{1,255}")


def valid_host(host: str | None) -> bool:
    """Ar reikšmę saugu įdėti į LogQL kaip host etiketę (visa eilutė: be kabučių ir „\\n")."""
    return isinstance(host, str) and HOST_RE.fullmatch(host) is not None


def logs_selector(host: str | None = None) -> str:
    """LogQL srauto selektorius; su `host` — tik to įrenginio srautas."""
    parts = [f'job=~"{LOG_JOBS}"']
    if host:
        parts.append(f'host="{host}"')
    return "{" + ", ".join(parts) + "}"
