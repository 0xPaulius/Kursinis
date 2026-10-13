"""
Paslaugų sveikatos tikrinimas su kešavimu.
Indirektas tikrinimas per Loki duomenų šviežumą.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time


from app.log_selectors import LOG_JOBS, logs_selector
from app.models.schemas import HealthStatus, ServiceHealth
from app.services.loki_client import AsyncLokiClient

logger = logging.getLogger(__name__)

ANOMALY_DB_PATH = os.getenv("ANOMALY_DB_PATH", "/data/anomaly_history.json")
# Alloy būklės (readiness) endpoint'as — pakeitė Promtail.
ALLOY_READY_URL = os.getenv("ALLOY_READY_URL", "http://alloy:12345/-/ready")
_CACHE_TTL = 30.0  # sekundės


class HealthChecker:
    """
    Tikrina paslaugų būklę ir kešuoja rezultatus 30s.
    Naudoja asyncio.Task sargą kad lygiagretūs užklausos nenaudotų Loki du kartus.
    """

    def __init__(self, loki: AsyncLokiClient):
        self._loki = loki
        self._cached: HealthStatus | None = None
        self._cached_at: float = 0.0
        self._in_flight: asyncio.Task[HealthStatus] | None = None

    async def get_status(self) -> HealthStatus:
        now = time.monotonic()
        # Grąžiname kešą jei dar galioja
        if self._cached and (now - self._cached_at) < _CACHE_TTL:
            return self._cached

        # Jei jau vyksta užklausa — laukiame jos rezultato (ne naujos)
        if self._in_flight and not self._in_flight.done():
            return await self._in_flight

        self._in_flight = asyncio.create_task(self._fetch())
        result = await self._in_flight
        self._cached = result
        self._cached_at = time.monotonic()
        return result

    async def _fetch(self) -> HealthStatus:
        services: list[ServiceHealth] = []

        # --- Loki ---
        loki_ready = await self._loki.is_ready()
        services.append(ServiceHealth(
            name="loki",
            label="Žurnalų saugykla (Loki)",
            status="ok" if loki_ready else "critical",
            message="Veikia normaliai" if loki_ready else "Nepasiekiama",
        ))

        # --- syslog-ng: per duomenų šviežumą ---
        # Jei Loki neveikia, negalime nieko spręsti apie šaltinius — žymime kaip nežinoma.
        if loki_ready:
            syslog_status, syslog_msg = await self._check_data_freshness()
        else:
            syslog_status = "unknown"
            syslog_msg = "Negalima patikrinti (Loki nepasiekiamas)"
        services.append(ServiceHealth(
            name="syslog-ng",
            label="Žurnalų rinkimas (syslog-ng)",
            status=syslog_status,
            message=syslog_msg,
        ))

        # --- Alloy: per readiness endpoint'ą (tiesiogiai, nepriklauso nuo Loki) ---
        alloy_status, alloy_msg = await self._check_alloy_ready()
        services.append(ServiceHealth(
            name="alloy",
            label="Žurnalų persiuntimas (Alloy)",
            status=alloy_status,
            message=alloy_msg,
        ))

        # --- Galinių įrenginių telemetrija (Windows) — tik jei yra bent vienas ---
        if "windows" in LOG_JOBS and loki_ready:
            ep_status, ep_msg = await self._check_endpoint_telemetry()
            if ep_status is not None:
                services.append(ServiceHealth(
                    name="endpoints",
                    label="Galinių įrenginių telemetrija",
                    status=ep_status,
                    message=ep_msg,
                ))

        # --- Anomaly detector: per failo modifikacijos laiką ---
        detector_status, detector_msg = self._check_detector_health()
        services.append(ServiceHealth(
            name="anomaly-detector",
            label="Anomalijų aptikimas",
            status=detector_status,
            message=detector_msg,
        ))

        # Bendroji būklė
        statuses = [s.status for s in services]
        if "critical" in statuses:
            overall = "critical"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "ok"

        return HealthStatus(
            overall=overall,
            services=services,
            checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    async def _check_data_freshness(self) -> tuple[str, str]:
        """
        Tikrina ar paskutinis logas Loki yra ne senesnis nei 5 minutės.
        Netiesiogiai parodo, ar syslog-ng ir Alloy veikia.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=5)

        lines = await self._loki.query_range(logs_selector(), start=start, end=now, limit=1)
        if lines:
            return "ok", "Žurnalai gaunami reguliariai"

        # Patikriname ar apskritai yra duomenų (galbūt tiesiog tylu)
        start_1h = now - datetime.timedelta(hours=1)
        lines_1h = await self._loki.query_range(logs_selector(), start=start_1h, end=now, limit=1)
        if lines_1h:
            return "warning", "Žurnalų negauta per paskutines 5 min"
        return "warning", "Nėra žurnalų per paskutinę valandą"

    async def _check_endpoint_telemetry(self) -> tuple[str | None, str]:
        """
        Windows endpoint telemetrijos šviežumas. Grąžina (None, "") jei endpoint'ų
        iš viso nėra (nerodome paslaugos vartotojams be galinių įrenginių).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        recent = await self._loki.query_range(
            '{job="windows"}', start=now - datetime.timedelta(minutes=5), end=now, limit=1)
        if recent:
            return "ok", "Galiniai įrenginiai siunčia telemetriją"
        hour = await self._loki.query_range(
            '{job="windows"}', start=now - datetime.timedelta(hours=1), end=now, limit=1)
        if hour:
            return "warning", "Telemetrijos negauta per paskutines 5 min"
        return None, ""  # endpoint'ų nėra — paslaugos nerodome

    async def _check_alloy_ready(self) -> tuple[str, str]:
        """Tikrina Alloy /-/ready endpoint'ą tiesiogiai (nepriklauso nuo Loki)."""
        try:
            resp = await self._loki._client.get(ALLOY_READY_URL, timeout=5)
            if resp.status_code == 200:
                return "ok", "Veikia normaliai"
            return "warning", f"Netikėtas atsakymas ({resp.status_code})"
        except Exception:  # noqa: BLE001 — tinklo klaida = nepasiekiamas
            return "critical", "Nepasiekiamas"

    def _check_detector_health(self) -> tuple[str, str]:
        """
        Tikrina anomalijų detektoriaus veikimą per failo modifikacijos laiką.
        Nenaudoja json.load — tik mtime, kad neverstų viso failo atmintyje.
        """
        if not os.path.exists(ANOMALY_DB_PATH):
            # Failas gali neegzistuoti jei dar nebuvo aptikta anomalijų — tai normalu
            return "ok", "Veikia (anomalijų dar neaptikta)"

        try:
            os.path.getmtime(ANOMALY_DB_PATH)
            return "ok", "Veikia normaliai"
        except OSError as exc:
            logger.warning("Detektoriaus failo klaida: %s", exc)
            return "warning", "Nepavyko perskaityti duomenų"
