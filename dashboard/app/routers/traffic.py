"""
Žurnalų srauto API maršrutai.
"""
from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models.schemas import TrafficCurrent, TrafficHistory, TrafficPoint
from app.services.loki_client import AsyncLokiClient
from app.dependencies import get_loki

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


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
        f'count_over_time({{job="syslog"}}[1h])',
        start=start,
        end=now,
        step="1h",
    )

    points: list[TrafficPoint] = []

    if results:
        # Metric query grąžina matrix — imame pirmą stream'ą
        for stream in results:
            for ts_str, val_str in stream.get("values", []):
                try:
                    ts_sec = int(ts_str) / 1e9 if int(ts_str) > 1e12 else int(ts_str)
                    dt = datetime.datetime.fromtimestamp(ts_sec, tz=datetime.timezone.utc)
                    points.append(TrafficPoint(
                        time=dt.isoformat(),
                        count=int(float(val_str)),
                    ))
                except (ValueError, TypeError):
                    continue
    else:
        # Fallback: rankiniu būdu skaitome po valandą (max 24h — vengiame šimtų užklausų)
        for h in range(min(hours, 24), 0, -1):
            h_start = now - datetime.timedelta(hours=h)
            h_end = now - datetime.timedelta(hours=h - 1)
            lines = await loki.query_range('{job="syslog"}', start=h_start, end=h_end)
            points.append(TrafficPoint(
                time=h_start.isoformat(),
                count=len(lines),
            ))

    points.sort(key=lambda p: p.time)
    return TrafficHistory(points=points)
