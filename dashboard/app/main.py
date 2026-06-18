"""
Stebėjimo pultas — FastAPI pagrindinė aplikacija.

Autorius: Paulius Turauskas
Kursinis darbas: Centralizuota žurnalų analizės ir anomalijų
                 aptikimo sistema mažoms organizacijoms
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import traffic, alerts, health, auth, devices, stream, notifications
from app.services.alert_reader import AlertReader
from app.services.device_monitor import DeviceMonitor
from app.services.device_registry import DeviceRegistry
from app.services.host_info import HostInfo
from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker
from app.services.notifier import Notifier
from app.services.syslog_emitter import SyslogEmitter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dashboard")

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
STATIC_DIR = Path(__file__).parent / "static"

# Fonis normalaus srauto generavimo intervalas (sekundėmis)
NORMAL_TRAFFIC_INTERVAL = int(os.getenv("NORMAL_TRAFFIC_INTERVAL", "5"))

# Pranešimų (webhook) tikrinimo intervalas (sekundėmis)
NOTIFY_INTERVAL = int(os.getenv("NOTIFY_INTERVAL", "10"))


async def _normal_traffic_loop(registry: DeviceRegistry, emitter: SyslogEmitter) -> None:
    """Periodiškai siunčia normalų srautą už kiekvieną įjungtą įrenginį."""
    while True:
        await asyncio.sleep(NORMAL_TRAFFIC_INTERVAL)
        try:
            for device in registry.list_all():
                # Tik sintetiniai (demonstraciniai) įrenginiai gauna generuotą srautą —
                # realūs aptikti host'ai siunčia savo tikrus logus.
                if device.get("enabled", True) and device.get("synthetic", True):
                    emitter.emit_normal_for_device(device, count=random.randint(1, 3))
        except Exception as exc:  # noqa: BLE001 — fonis ciklas neturi nukristi
            logger.warning("Normalaus srauto generavimo klaida: %s", exc)


async def _notifier_loop(notifier: Notifier, alert_reader: AlertReader) -> None:
    """Periodiškai siunčia naujus alertus į webhook (jei įjungta nustatymuose)."""
    # Pradžioje pažymime esamus alertus „matytais" — nesiunčiame senos istorijos.
    notifier.prime(a.id for a in alert_reader.read_recent(200))
    while True:
        await asyncio.sleep(NOTIFY_INTERVAL)
        try:
            # AlertReader grąžina naujausius pirmus — siuntimui reikia seniausių pirmų.
            recent = list(reversed(alert_reader.read_recent(200)))
            await notifier.process_new(recent)
        except Exception as exc:  # noqa: BLE001 — fonis ciklas neturi nukristi
            logger.warning("Pranešimų ciklo klaida: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Paleidžiamas vienintelis httpx.AsyncClient visai aplikacijai
    async with httpx.AsyncClient() as client:
        loki = AsyncLokiClient(base_url=LOKI_URL, client=client)
        app.state.loki = loki
        app.state.health_checker = HealthChecker(loki=loki)
        app.state.alert_reader = AlertReader()
        app.state.device_registry = DeviceRegistry()
        app.state.syslog_emitter = SyslogEmitter()
        app.state.host_info = HostInfo()
        app.state.device_monitor = DeviceMonitor(
            loki=loki,
            registry=app.state.device_registry,
            alert_reader=app.state.alert_reader,
            host_info=app.state.host_info,
        )
        app.state.notifier = Notifier(client)
        traffic_task = asyncio.create_task(
            _normal_traffic_loop(app.state.device_registry, app.state.syslog_emitter)
        )
        notifier_task = asyncio.create_task(
            _notifier_loop(app.state.notifier, app.state.alert_reader)
        )
        logger.info("Dashboard paleistas. Loki URL: %s", LOKI_URL)
        try:
            yield
        finally:
            traffic_task.cancel()
            notifier_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await traffic_task
            with contextlib.suppress(asyncio.CancelledError):
                await notifier_task
            app.state.syslog_emitter.close()
    logger.info("Dashboard sustabdytas.")


app = FastAPI(
    title="Stebėjimo pultas",
    description="Žurnalų analizės sistemos stebėjimo pultas",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS: dashboard ir API serveriai sutampa (same-origin), tad CORS realiai nereikalingas.
# Paliekame siaurą sąrašą tik vietiniam dev naudojimui (8080, 127.0.0.1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)

# API maršrutai
app.include_router(auth.router)
app.include_router(traffic.router)
app.include_router(alerts.router)
app.include_router(health.router)
app.include_router(devices.router)
app.include_router(stream.router)
app.include_router(notifications.router)

# Statiniai failai
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login", include_in_schema=False)
async def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")
