"""
Pydantic atsakymų modeliai dashboard API.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class TrafficPoint(BaseModel):
    time: str          # ISO timestamp
    count: int


class TrafficCurrent(BaseModel):
    total: int
    logs_per_minute: float
    by_severity: dict[str, int]
    by_job: dict[str, int]


class TrafficHistory(BaseModel):
    points: list[TrafficPoint]


class AlertItem(BaseModel):
    id: str
    timestamp: str
    severity: str           # "low" | "medium" | "high" | "critical"
    alert_type: str
    title: str              # Plain Lithuanian title
    explanation: str        # Plain Lithuanian explanation
    recommendation: str     # Plain Lithuanian recommendation
    source_ip: str
    source_host: str
    detection_method: str
    details: dict[str, Any]


class AlertList(BaseModel):
    alerts: list[AlertItem]
    total: int
    page: int
    pages: int


class ServiceHealth(BaseModel):
    name: str           # Internal name
    label: str          # Lithuanian display name
    status: str         # "ok" | "warning" | "critical" | "unknown"
    message: str        # Lithuanian status message


class HealthStatus(BaseModel):
    overall: str        # "ok" | "warning" | "critical"
    services: list[ServiceHealth]
    checked_at: str
