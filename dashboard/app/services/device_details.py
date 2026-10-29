"""
Įrenginio detalių puslapio duomenys: būsena (status heartbeat), paskutiniai veiksmai, įspėjimai.

Raktas — „self" (šis serveris; tikras hostname URL'e nerodomas) arba Loki host etiketė.
Trys Loki užklausos vykdomos lygiagrečiai: būsenos srautas, syslog veiksmai, Windows įvykiai.
"""
from __future__ import annotations

import asyncio
import datetime
import logging

from app.log_selectors import valid_host
from app.models.schemas import ActivityItem, DeviceDetails
from app.services.activity import SYSLOG_PREFILTER, WINDOWS_EVENT_IDS, classify
from app.services.alert_reader import AlertReader
from app.services.device_monitor import alerts_for_device
from app.services.device_registry import DeviceRegistry
from app.services.host_info import HostInfo
from app.services.host_status import STATUS_PROGRAM, build_status
from app.services.loki_client import AsyncLokiClient

logger = logging.getLogger(__name__)

SELF_KEY = "self"
LOOKBACK = datetime.timedelta(hours=24)
STATUS_LIMIT = 120           # ~2 val. įrašų (kas minutę)
ACTIVITY_QUERY_LIMIT = 500
ACTIVITY_LIMIT = 50
ALERT_LIMIT = 20


class DeviceNotFound(Exception):
    """Netinkamas raktas arba nežinomas savo serveris."""


def _ns(entry: dict) -> int:
    try:
        return int(entry.get("timestamp", 0))
    except (TypeError, ValueError):
        return 0


def _classify_rows(rows: list[dict]) -> list[ActivityItem]:
    """Naujausi pirmi; ne daugiau ACTIVITY_LIMIT. Eilutė, sugadinusi klasifikavimą, praleidžiama."""
    activity: list[ActivityItem] = []
    failed = 0
    for row in sorted(rows, key=_ns, reverse=True):
        try:
            item = classify(row)
        except Exception:  # noqa: BLE001 — viena keista eilutė neturi sugadinti viso puslapio
            failed += 1
            continue
        if item is not None:
            activity.append(item)
            if len(activity) == ACTIVITY_LIMIT:
                break
    if failed:
        logger.warning("Įrenginio veiksmai: praleista %d eilučių (klasifikavimo klaida)", failed)
    return activity


def _assemble(status_rows: list[dict], activity_rows: list[dict], now: datetime.datetime):
    """Eilučių tikrinimas (JSON, regex) — atskiroje gijoje, kad neužimtų serverio įvykių ciklo."""
    status, history = build_status(status_rows, now)
    return status, history, _classify_rows(activity_rows)


class DeviceDetailsService:
    def __init__(
        self,
        loki: AsyncLokiClient,
        registry: DeviceRegistry,
        alert_reader: AlertReader,
        host_info: HostInfo,
    ) -> None:
        self._loki = loki
        self._registry = registry
        self._alert_reader = alert_reader
        self._host_info = host_info

    def resolve(self, key: str) -> str:
        """Maršruto raktas -> Loki host etiketė. DeviceNotFound, jei raktas netinkamas."""
        if key == SELF_KEY:
            host = self._host_info.get()
            if not host or not valid_host(host.get("hostname")):
                raise DeviceNotFound(key)
            return host["hostname"]
        if not valid_host(key):
            raise DeviceNotFound(key)
        return key

    async def details(self, key: str, now: datetime.datetime | None = None) -> DeviceDetails:
        host = self.resolve(key)
        now = now or datetime.datetime.now(datetime.timezone.utc)
        start = now - LOOKBACK
        status_query = f'{{job="syslog", host="{host}", program="{STATUS_PROGRAM}"}}'
        syslog_query = (f'{{job=~"syslog|linux_endpoint", host="{host}", program!="{STATUS_PROGRAM}"}} '
                        f'|~ `{SYSLOG_PREFILTER}`')
        windows_query = f'{{job="windows", host="{host}"}} | json event_id | event_id=~"{WINDOWS_EVENT_IDS}"'
        status_rows, syslog_rows, windows_rows = await asyncio.gather(
            self._loki.query_range(status_query, start=start, end=now, limit=STATUS_LIMIT),
            self._loki.query_range(syslog_query, start=start, end=now, limit=ACTIVITY_QUERY_LIMIT),
            self._loki.query_range(windows_query, start=start, end=now, limit=ACTIVITY_QUERY_LIMIT),
        )
        status, history, activity = await asyncio.to_thread(_assemble, status_rows, syslog_rows + windows_rows, now)

        ip = next((d.get("ip", "") for d in self._registry.list_all() if d.get("hostname") == host), "")
        alerts = alerts_for_device(ip, host, self._alert_reader.read_all())[:ALERT_LIMIT]
        return DeviceDetails(status=status, history=history, activity=activity, alerts=alerts)
