"""
FastAPI priklausomybės (dependency injection).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

from app.routers.auth import verify_session
from app.services.alert_reader import AlertReader
from app.services.device_monitor import DeviceMonitor
from app.services.device_registry import DeviceRegistry
from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker
from app.services.syslog_emitter import SyslogEmitter


def get_loki(request: Request) -> AsyncLokiClient:
    return request.app.state.loki


def get_health_checker(request: Request) -> HealthChecker:
    return request.app.state.health_checker


def get_alert_reader(request: Request) -> AlertReader:
    return request.app.state.alert_reader


def get_device_registry(request: Request) -> DeviceRegistry:
    return request.app.state.device_registry


def get_syslog_emitter(request: Request) -> SyslogEmitter:
    return request.app.state.syslog_emitter


def get_device_monitor(request: Request) -> DeviceMonitor:
    return request.app.state.device_monitor


def get_notifier(request: Request):
    return request.app.state.notifier


def require_auth(authorization: str | None = Header(default=None)) -> dict:
    """
    Tikrina `Authorization: Bearer <token>` antraštę ir grąžina tokeno claims.
    Naudojama API maršrutuose, kuriems reikia prisijungimo.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Reikalingas prisijungimo tokenas")
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    claims = verify_session(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Neteisingas arba pasibaigęs tokenas")
    return claims


def require_admin(claims: dict = Depends(require_auth)) -> dict:
    """Leidžia tik `admin` rolei (įrenginių keitimas, atakos, pranešimai)."""
    if claims.get("r") != "admin":
        raise HTTPException(status_code=403, detail="Reikalingos administratoriaus teisės")
    return claims
