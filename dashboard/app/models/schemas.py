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
    sample_lines: list[str] = []   # raw log lines that triggered this alert
    attack_techniques: list[str] = []   # MITRE ATT&CK technique IDs (e.g. T1110.001)


class AlertList(BaseModel):
    alerts: list[AlertItem]
    total: int
    page: int
    pages: int


class LogLine(BaseModel):
    """Viena žalia žurnalo eilutė iš Loki (su išgautomis etiketėmis)."""
    time: str           # ISO timestamp (Loki entry time)
    host: str = ""
    program: str = ""
    severity: str = ""
    line: str = ""      # raw, full syslog line


class LogLines(BaseModel):
    lines: list[LogLine]
    total: int


class ServiceHealth(BaseModel):
    name: str           # Internal name
    label: str          # Lithuanian display name
    status: str         # "ok" | "warning" | "critical" | "unknown"
    message: str        # Lithuanian status message


class HealthStatus(BaseModel):
    overall: str        # "ok" | "warning" | "critical"
    services: list[ServiceHealth]
    checked_at: str


class DeviceCreate(BaseModel):
    name: str
    ip: str
    os: str                         # "macos" | "windows"
    os_version: str | None = None   # optional override; defaults per OS
    synthetic: bool = True          # False — real endpoint that sends its own logs


class Device(BaseModel):
    id: str
    name: str
    hostname: str       # syslog HOST label
    ip: str
    os: str             # "macos" | "windows"
    os_version: str = ""
    synthetic: bool = True          # generated-traffic device (vs real, discovered host)
    enabled: bool = True
    created_at: str
    alert_count: int = 0            # Computed from alert history (not persisted)
    worst_severity: str = "none"    # "none" | "low" | "medium" | "high" | "critical"


class DeviceList(BaseModel):
    devices: list[Device]
    total: int


class DemoScenarioRequest(BaseModel):
    """Demonstracinės atakos pasirinkimas (Devices skydelio mygtukai)."""
    attack: str = "full"   # "ssh_bruteforce" | "firewall_spike" | "full"


class SimulateResponse(BaseModel):
    detail: str         # Lithuanian status message
    target: str         # Targeted device hostname
    attacker_ip: str    # Simulated attacker IP


class DeviceNode(BaseModel):
    """Vienas mazgas įrenginių žemėlapyje (registruotas, savas serveris arba aptiktas)."""
    id: str
    name: str
    hostname: str
    ip: str = ""
    os: str = "unknown"             # "macos" | "windows" | "linux" | "unknown"
    os_version: str = ""
    source: str = "discovered"      # "registered" | "self" | "discovered"
    online: bool = False
    logs_5m: int = 0
    logs_1h: int = 0
    last_seen: str | None = None    # ISO timestamp of newest log
    alert_count: int = 0
    worst_severity: str = "none"


class CollectorNode(BaseModel):
    name: str
    online: bool
    logs_5m: int


class DeviceMap(BaseModel):
    collector: CollectorNode
    devices: list[DeviceNode]
    generated_at: str


class NotificationSettings(BaseModel):
    """Pranešimų (webhook) nustatymai — saugomi /state/notify.json."""
    enabled: bool = False
    webhook_url: str = ""
    min_severity: str = "medium"   # "low" | "medium" | "high" | "critical"
