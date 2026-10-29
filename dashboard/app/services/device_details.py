"""
Įrenginio detalių puslapio duomenys: būsena (status heartbeat), paskutiniai veiksmai, įspėjimai.

Raktas — „self" (šis serveris; tikras hostname URL'e nerodomas) arba Loki host etiketė.
Penkios Loki užklausos vykdomos lygiagrečiai: būsenos srautas; syslog veiksmai ir auditd
komandos; Windows saugumo įvykiai ir Sysmon procesai. Dažni procesų paleidimai turi atskiras
užklausas ir ribą sraute, kad neišstumtų retų įvykių (paskyros, žurnalo išvalymas).
"""
from __future__ import annotations

import asyncio
import datetime
import logging

from app.log_selectors import valid_host
from app.models.schemas import ActivityItem, DeviceDetails
from app.services.activity import (
    EXECVE_FILTER,
    SYSLOG_PREFILTER,
    SYSMON_PROCESS_EVENT_ID,
    WINDOWS_EVENT_IDS,
    classify,
)
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
COMMAND_QUERY_LIMIT = 200    # procesų paleidimai (EXECVE, Sysmon 1)
ACTIVITY_LIMIT = 50
KIND_LIMITS = {"command": 25}   # sraute: dažna rūšis neužima visų 50 vietų
ALERT_LIMIT = 20


class DeviceNotFound(Exception):
    """Netinkamas raktas arba nežinomas savo serveris."""


def _ns(entry: dict) -> int:
    try:
        return int(entry.get("timestamp", 0))
    except (TypeError, ValueError):
        return 0


def _classify_rows(rows: list[dict]) -> list[ActivityItem]:
    """
    Naujausi pirmi; ne daugiau ACTIVITY_LIMIT (ir KIND_LIMITS kiekvienai rūšiai). Ta pati eilutė iš
    kelių užklausų skaičiuojama kartą; eilutė, sugadinusi klasifikavimą, praleidžiama.
    """
    activity: list[ActivityItem] = []
    per_kind: dict[str, int] = {}
    seen: set[tuple] = set()
    failed = 0
    for row in sorted(rows, key=_ns, reverse=True):
        identity = (row.get("timestamp"), row.get("line"))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            item = classify(row)
        except Exception:  # noqa: BLE001 — viena keista eilutė neturi sugadinti viso puslapio
            failed += 1
            continue
        if item is None or per_kind.get(item.kind, 0) >= KIND_LIMITS.get(item.kind, ACTIVITY_LIMIT):
            continue
        per_kind[item.kind] = per_kind.get(item.kind, 0) + 1
        activity.append(item)
        if len(activity) == ACTIVITY_LIMIT:
            break
    if failed:
        logger.warning("Įrenginio veiksmai: praleista %d eilučių (klasifikavimo klaida)", failed)
    return activity


def _assemble(status_rows: list[dict], activity_rows: list[dict], now: datetime.datetime):
    """
    Eilučių tikrinimas (JSON, regex) darbo gijoje: tarp eilučių serverio įvykių ciklas gauna GIL.
    Vieno reiškinio trukmės gija nesutrumpina — ją riboja activity.py eilučių ilgio riba.
    """
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
        syslog = f'{{job=~"syslog|linux_endpoint", host="{host}", program!="{STATUS_PROGRAM}"}}'
        windows = f'{{job="windows", host="{host}"}} | json event_id'
        sysmon = f'{{job="windows", host="{host}", channel=~".*Sysmon.*"}} | json event_id'
        queries = [
            (f'{{job="syslog", host="{host}", program="{STATUS_PROGRAM}"}}', STATUS_LIMIT),
            (f"{syslog} |~ `{SYSLOG_PREFILTER}`", ACTIVITY_QUERY_LIMIT),
            (f'{syslog} |= "{EXECVE_FILTER}"', COMMAND_QUERY_LIMIT),
            (f'{windows} | event_id=~"{WINDOWS_EVENT_IDS}"', ACTIVITY_QUERY_LIMIT),
            (f'{sysmon} | event_id="{SYSMON_PROCESS_EVENT_ID}"', COMMAND_QUERY_LIMIT),
        ]
        status_rows, *activity_parts = await asyncio.gather(
            *(self._loki.query_range(query, start=start, end=now, limit=limit) for query, limit in queries))
        activity_rows = [row for part in activity_parts for row in part]
        status, history, activity = await asyncio.to_thread(_assemble, status_rows, activity_rows, now)

        ip = next((d.get("ip", "") for d in self._registry.list_all() if d.get("hostname") == host), "")
        alerts = alerts_for_device(ip, host, self._alert_reader.read_all())[:ALERT_LIMIT]
        return DeviceDetails(status=status, history=history, activity=activity, alerts=alerts)
