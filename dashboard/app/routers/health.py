"""
Paslaugų sveikatos API maršrutas.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.schemas import HealthStatus
from app.services.health_checker import HealthChecker
from app.dependencies import get_health_checker, require_auth

router = APIRouter(prefix="/api/health", tags=["health"], dependencies=[Depends(require_auth)])


@router.get("/status", response_model=HealthStatus)
async def get_health_status(
    checker: Annotated[HealthChecker, Depends(get_health_checker)],
) -> HealthStatus:
    """Visų paslaugų būklė (kešuojama 30s)."""
    return await checker.get_status()
