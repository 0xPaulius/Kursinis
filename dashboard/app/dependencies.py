"""
FastAPI priklausomybės (dependency injection).
"""
from __future__ import annotations

from fastapi import Request

from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker


def get_loki(request: Request) -> AsyncLokiClient:
    return request.app.state.loki


def get_health_checker(request: Request) -> HealthChecker:
    return request.app.state.health_checker
