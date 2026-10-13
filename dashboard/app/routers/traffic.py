"""
Žurnalų srauto API maršrutai.
"""
from __future__ import annotations

import asyncio
import datetime
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models.schemas import LogLine, LogLines, TrafficCurrent, TrafficHistory, TrafficPoint
from app.services.loki_client import AsyncLokiClient
from app.dependencies import get_loki, require_auth
from app.log_selectors import logs_selector

router = APIRouter(prefix="/api/traffic", tags=["traffic"], dependencies=[Depends(require_auth)])

# Leistini host etiketės simboliai — apsauga nuo LogQL injekcijos per `host` parametrą.
_HOST_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")


def _ns_to_iso(ts_ns: str | int) -> str:
    """Loki įrašo laiką (nanosekundėmis) verčia į ISO formatą."""
    try:
        sec = int(ts_ns) / 1e9
        return datetime.datetime.fromtimestamp(sec, tz=datetime.timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


def _auto_step(hours: int) -> str:
    """
    Parenka Loki agregavimo žingsnį (ir count_over_time langą) pagal pasirinktą
    intervalą, kad grafikas turėtų ~24-72 taškus nepriklausomai nuo lango ilgio.
    Grafana stiliaus laiko parinkiklis siunčia skirtingus `hours`, tad žingsnis
    turi prisitaikyti (1 val intervalui per valandinį žingsnį būtų vos 1 taškas).
    """
    if hours <= 1:
        return "2m"
    if hours <= 6:
        return "10m"
    if hours <= 12:
        return "30m"
    if hours <= 24:
        return "1h"
    if hours <= 48:
        return "2h"
    return "6h"


@router.get("/current", response_model=TrafficCurrent)
async def get_traffic_current(
    loki: Annotated[AsyncLokiClient, Depends(get_loki)],
) -> TrafficCurrent:
    """Dabartinis žurnalų srautas per paskutines 5 minutes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(minutes=5)

    lines = await loki.query_range(logs_selector(), start=start, end=now)

    by_severity: dict[str, int] = {}
    by_job: dict[str, int] = {}

    for entry in lines:
        labels = entry.get("labels", {})
        sev = labels.get("severity", "unknown")
        job = labels.get("job", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_job[job] = by_job.get(job, 0) + 1

    total = len(lines)
    lpm = round(total / 5.0, 1)

    return TrafficCurrent(
        total=total,
        logs_per_minute=lpm,
        by_severity=by_severity,
        by_job=by_job,
    )


@router.get("/history", response_model=TrafficHistory)
async def get_traffic_history(
    loki: Annotated[AsyncLokiClient, Depends(get_loki)],
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    host: Annotated[str | None, Query(max_length=255)] = None,
) -> TrafficHistory:
    """
    Valandinis žurnalų skaičius per paskutines N valandų.
    Naudojamas grafikui braižyti. Pateikus `host` parametrą, rodomas tik
    nurodyto įrenginio (syslog `host` etiketės) srautas.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(hours=hours)

    # Žingsnis prisitaiko prie lango — trumpiems intervalams smulkesnis skiriamumas.
    step = _auto_step(hours)

    # Jei nurodytas validus host — filtruojame pagal jį; kitaip imame visą srautą.
    selector = logs_selector(host if host and _HOST_RE.match(host) else None)

    results = await loki.query_metric(
        f'sum(count_over_time({selector}[{step}]))',
        start=start,
        end=now,
        step=step,
    )

    points: list[TrafficPoint] = []

    if results:
        # Metric query grąžina matrix [{metric: {...}, values: [[ts_sec_float, val_str], ...]}].
        # Naudojame `sum(...)` LogQL apvalkalą — grįžta tik vienas stream'as su jau sudėtais šeimininkais.
        # Loki visada grąžina sekundes float formatu, todėl nebereikia ns/sec konversijos.
        bucket: dict[str, int] = {}
        for stream in results:
            for ts_val, val_str in stream.get("values", []):
                try:
                    ts_sec = float(ts_val)
                    dt = datetime.datetime.fromtimestamp(ts_sec, tz=datetime.timezone.utc)
                    iso = dt.isoformat()
                    bucket[iso] = bucket.get(iso, 0) + int(float(val_str))
                except (ValueError, TypeError):
                    continue
        points = [TrafficPoint(time=t, count=c) for t, c in bucket.items()]
    else:
        # Fallback: lygiagrečios užklausos po valandą (max 24h — vengiame šimtų užklausų).
        capped = min(hours, 24)
        windows = [
            (now - datetime.timedelta(hours=h), now - datetime.timedelta(hours=h - 1))
            for h in range(capped, 0, -1)
        ]
        responses = await asyncio.gather(
            *(loki.query_range(selector, start=s, end=e) for s, e in windows),
            return_exceptions=True,
        )
        for (h_start, _), lines in zip(windows, responses):
            count = len(lines) if isinstance(lines, list) else 0
            points.append(TrafficPoint(time=h_start.isoformat(), count=count))

    points.sort(key=lambda p: p.time)
    return TrafficHistory(points=points)


@router.get("/logs", response_model=LogLines)
async def get_traffic_logs(
    loki: Annotated[AsyncLokiClient, Depends(get_loki)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    host: Annotated[str | None, Query(max_length=255)] = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> LogLines:
    """
    Naujausios žalios žurnalo eilutės (visi aptikti logai). Pateikus `host`
    parametrą — tik nurodyto įrenginio logai. Naudojama „Visi logai" rodiniui.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(hours=hours)

    selector = logs_selector(host if host and _HOST_RE.match(host) else None)

    entries = await loki.query_range(selector, start=start, end=now, limit=limit)

    # query_range grąžina naujausius pirmus (direction=backward).
    lines = [
        LogLine(
            time=_ns_to_iso(e.get("timestamp", "")),
            host=e.get("labels", {}).get("host", ""),
            program=e.get("labels", {}).get("program", ""),
            severity=e.get("labels", {}).get("severity", ""),
            line=e.get("line", ""),
        )
        for e in entries[:limit]
    ]
    return LogLines(lines=lines, total=len(lines))
