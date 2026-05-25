"""
FastAPI priklausomybės (dependency injection).
"""
from __future__ import annotations

from fastapi import Header, HTTPException, Request

from app.routers.auth import verify_demo_token
from app.services.alert_reader import AlertReader
from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker


def get_loki(request: Request) -> AsyncLokiClient:
    return request.app.state.loki


def get_health_checker(request: Request) -> HealthChecker:
    return request.app.state.health_checker


def get_alert_reader(request: Request) -> AlertReader:
    return request.app.state.alert_reader


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """
    Tikrina `Authorization: Bearer <token>` antraštę.
    Naudojama API maršrutuose, kuriems reikia prisijungimo.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Reikalingas prisijungimo tokenas")
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not verify_demo_token(token):
        raise HTTPException(status_code=401, detail="Neteisingas arba pasibaigęs tokenas")
