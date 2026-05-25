"""
Žurnalų srauto API maršrutai.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models.schemas import TrafficCurrent, TrafficHistory, TrafficPoint
from app.services.loki_client import AsyncLokiClient
from app.dependencies import get_loki, require_auth

router = APIRouter(prefix="/api/traffic", tags=["traffic"], dependencies=[Depends(require_auth)])


@router.get("/current", response_model=TrafficCurrent)
async def get_traffic_current(
    loki: Annotated[AsyncLokiClient, Depends(get_loki)],
) -> TrafficCurrent:
    """Dabartinis žurnalų srautas per paskutines 5 minutes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(minutes=5)

    lines = await loki.query_range('{job="syslog"}', start=start, end=now)

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
) -> TrafficHistory:
    """
    Valandinis žurnalų skaičius per paskutines N valandų.
    Naudojamas grafikui braižyti.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(hours=hours)

    results = await loki.query_metric(
        f'sum(count_over_time({{job="syslog"}}[1h]))',
        start=start,
        end=now,
        step="1h",
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
            *(loki.query_range('{job="syslog"}', start=s, end=e) for s, e in windows),
            return_exceptions=True,
        )
        for (h_start, _), lines in zip(windows, responses):
            count = len(lines) if isinstance(lines, list) else 0
            points.append(TrafficPoint(time=h_start.isoformat(), count=count))

    points.sort(key=lambda p: p.time)
    return TrafficHistory(points=points)
