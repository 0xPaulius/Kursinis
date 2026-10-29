"""
Įrenginio būsenos įrašai (status heartbeat): veikimo laikas, CPU, atmintis, diskas, programos.

Įrenginys kas minutę siunčia vieną JSON eilutę įprastu žurnalų keliu
(config/syslog-ng-host/kursinis-status.sh -> journal -> syslog-ng -> Alloy -> Loki,
program="kursinis-status"). Syslog'ą (UDP 514) gali siųsti bet kas, todėl įrašas —
nepatikimi duomenys: tikrinamas griežtai, netinkamas praleidžiamas (netaisomas).
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.models.schemas import HostStatus, ProgramUsage, StatusPoint
from app.services.loki_client import ns_to_datetime

logger = logging.getLogger(__name__)

STATUS_PROGRAM = "kursinis-status"
HISTORY_WINDOW = datetime.timedelta(hours=1)
MAX_LINE_LENGTH = 8192   # tikras įrašas ~1–3 KB

# Visa syslog-ng šablono eilutė: <laikas> <host> <facility>.<level> kursinis-status[<pid>]: {JSON}
_STATUS_RE = re.compile(r"^\S+\s+\S+\s+\S+\s+kursinis-status\[\d*\]: (\{.*\})\s*$")

_Pct = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
_Kb = Annotated[int, Field(ge=0, le=2**50)]
# Skriptas siunčia tik spausdinamą ASCII (kita -> „?"): bidi ar valdymo simboliai — suklastota.
_Name = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[\x20-\x7e]+$")]
_Load = Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)]


class _Program(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: _Name
    n: Annotated[int, Field(ge=1, le=1_000_000)]
    cpu: _Pct
    mem_kb: _Kb


class StatusRecord(BaseModel):
    """Būsenos įrašas, 1 versija (specifikacijos 4.2 ir 4.6 skyriai)."""
    model_config = ConfigDict(extra="ignore")
    v: Literal[1]
    uptime_s: Annotated[int, Field(ge=0, le=10**10)] | None = None
    cpus: Annotated[int, Field(ge=1, le=4096)] | None = None
    cpu_pct: _Pct | None = None
    load: Annotated[list[_Load], Field(max_length=3)] = []
    mem_total_kb: _Kb | None = None
    mem_avail_kb: _Kb | None = None
    disk_used_kb: _Kb | None = None
    disk_avail_kb: _Kb | None = None
    procs: Annotated[int, Field(ge=0, le=10**7)] | None = None
    users: Annotated[list[_Name], Field(max_length=20)] = []
    top: Annotated[list[_Program], Field(max_length=20)] = []

    @model_validator(mode="after")
    def _memory_consistent(self) -> StatusRecord:
        if (self.mem_total_kb is not None and self.mem_avail_kb is not None
                and self.mem_avail_kb > self.mem_total_kb):
            raise ValueError("mem_avail_kb > mem_total_kb")
        return self

    @property
    def mem_pct(self) -> float | None:
        if not self.mem_total_kb or self.mem_avail_kb is None:
            return None
        return round(100 * (self.mem_total_kb - self.mem_avail_kb) / self.mem_total_kb, 1)


def parse_status_line(line: str) -> StatusRecord | None:
    """Loki eilutė -> StatusRecord; None, jei tai ne būsenos įrašas arba jis netinkamas."""
    if len(line) > MAX_LINE_LENGTH:
        return None
    match = _STATUS_RE.match(line)
    if not match:
        return None
    try:
        return StatusRecord.model_validate_json(match.group(1))
    except ValidationError as exc:
        logger.debug("Netinkamas būsenos įrašas praleistas: %s", exc.errors()[:3])
        return None


def _to_host_status(rec: StatusRecord, when: datetime.datetime) -> HostStatus:
    return HostStatus(
        time=when.isoformat(),
        uptime_s=rec.uptime_s, cpus=rec.cpus, cpu_pct=rec.cpu_pct, load=rec.load,
        mem_total_kb=rec.mem_total_kb, mem_avail_kb=rec.mem_avail_kb,
        disk_used_kb=rec.disk_used_kb, disk_avail_kb=rec.disk_avail_kb,
        procs=rec.procs, users=rec.users,
        programs=[ProgramUsage(name=p.name, processes=p.n, cpu_pct=p.cpu, mem_kb=p.mem_kb) for p in rec.top],
    )


def build_status(entries: list[dict], now: datetime.datetime) -> tuple[HostStatus | None, list[StatusPoint]]:
    """Loki įrašai (bet kokia tvarka) -> naujausia tinkama būsena ir valandos istorija (seniausi pirmi)."""
    parsed: list[tuple[datetime.datetime, StatusRecord]] = []
    for e in entries:
        when = ns_to_datetime(e.get("timestamp"))
        rec = parse_status_line(e.get("line") or "")
        if when is not None and rec is not None:
            parsed.append((when, rec))
    if not parsed:
        return None, []
    parsed.sort(key=lambda p: p[0])
    cutoff = now - HISTORY_WINDOW
    history = [StatusPoint(time=w.isoformat(), cpu_pct=r.cpu_pct, mem_pct=r.mem_pct)
               for w, r in parsed if w >= cutoff]
    latest_when, latest = parsed[-1]
    return _to_host_status(latest, latest_when), history
