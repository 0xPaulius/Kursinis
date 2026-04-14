"""
Įspėjimų API maršrutai.
"""
from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Query

from app.models.schemas import AlertList
from app.services.alert_reader import AlertReader

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_reader = AlertReader()


@router.get("/recent", response_model=AlertList)
async def get_alerts_recent(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AlertList:
    """Paskutiniai N įspėjimai (naujesni pirmi)."""
    alerts = _reader.read_recent(limit=limit)
    return AlertList(alerts=alerts, total=len(alerts), page=1, pages=1)


@router.get("/history", response_model=AlertList)
async def get_alerts_history(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertList:
    """Visa įspėjimų istorija su puslapiavimų."""
    alerts, total = _reader.read_page(page=page, size=size)
    pages = max(1, math.ceil(total / size))
    return AlertList(alerts=alerts, total=total, page=page, pages=pages)
