"""
Stebėjimo pultas — FastAPI pagrindinė aplikacija.

Autorius: Paulius Turauskas
Kursinis darbas: Centralizuota žurnalų analizės ir anomalijų
                 aptikimo sistema mažoms organizacijoms
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import traffic, alerts, health
from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dashboard")

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Paleidžiamas vienintelis httpx.AsyncClient visai aplikacijai
    async with httpx.AsyncClient() as client:
        loki = AsyncLokiClient(base_url=LOKI_URL, client=client)
        app.state.loki = loki
        app.state.health_checker = HealthChecker(loki=loki)
        logger.info("Dashboard paleistas. Loki URL: %s", LOKI_URL)
        yield
    logger.info("Dashboard sustabdytas.")


app = FastAPI(
    title="Stebėjimo pultas",
    description="Žurnalų analizės sistemos stebėjimo pultas",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# API maršrutai
app.include_router(traffic.router)
app.include_router(alerts.router)
app.include_router(health.router)

# Statiniai failai
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
