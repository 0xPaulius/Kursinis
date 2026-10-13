"""
Gyvo atnaujinimo (Server-Sent Events) maršrutas.

Vietoj kliento pollinimo, serveris laiko vieną ilgalaikę HTTP jungtį ir
„pushina" duomenis tik tada, kai jie pasikeičia (change-detection). Naudojami
tie patys duomenų šaltiniai kaip ir REST maršrutuose (sveikata, srautas,
įspėjimai, įrenginiai), tad klientas gauna identišką JSON.

Autentifikacija per `?token=` užklausos parametrą, nes naršyklės `EventSource`
negali siųsti `Authorization` antraštės.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.routers.alerts import get_alerts_recent
from app.routers.auth import verify_token
from app.routers.health import get_health_status
from app.routers.traffic import get_traffic_current

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])

# Bazinis pulso intervalas sekundėmis (kiek dažnai serveris tikrina pokyčius).
STREAM_INTERVAL = float(os.getenv("STREAM_INTERVAL", "5"))


def _sse(event: str, payload: dict, last: dict[str, str]) -> str:
    """Suformuoja SSE įvykį TIK jei duomenys pasikeitė nuo paskutinio karto."""
    data = json.dumps(payload, ensure_ascii=False, default=str)
    if last.get(event) == data:
        return ""
    last[event] = data
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/api/stream")
async def stream(request: Request, token: str = Query(...)) -> StreamingResponse:
    """
    SSE srautas su gyvais atnaujinimais. Įvykiai: `health`, `traffic`, `alerts`,
    `devices`. Kiekvienas siunčiamas tik pasikeitus duomenims; `: ping` palaiko
    jungtį gyvą.
    """
    if verify_token(token) is None:
        raise HTTPException(status_code=401, detail="Neteisingas arba pasibaigęs tokenas")

    app_state = request.app.state

    async def event_generator():
        last: dict[str, str] = {}
        tick = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                tick += 1

                # Sveikata (kešuojama 30s) — pigu tikrinti kas pulsą.
                try:
                    health = (await get_health_status(app_state.health_checker)).model_dump(mode="json")
                    chunk = _sse("health", health, last)
                    if chunk:
                        yield chunk
                except Exception as exc:  # noqa: BLE001 — srautas neturi nukristi
                    logger.debug("stream health klaida: %s", exc)

                # Dabartinis srautas (5 min metrika).
                try:
                    current = (await get_traffic_current(app_state.loki)).model_dump(mode="json")
                    chunk = _sse("traffic", current, last)
                    if chunk:
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    logger.debug("stream traffic klaida: %s", exc)

                # Įspėjimai (AlertReader mtime-kešuotas — pigu).
                try:
                    alerts = (await get_alerts_recent(app_state.alert_reader)).model_dump(mode="json")
                    chunk = _sse("alerts", alerts, last)
                    if chunk:
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    logger.debug("stream alerts klaida: %s", exc)

                # Įrenginių žemėlapis — sunkesnis (kelios Loki užklausos), retsesnis.
                if tick == 1 or tick % 3 == 0:
                    try:
                        devices = await app_state.device_monitor.build_map()
                        chunk = _sse("devices", devices, last)
                        if chunk:
                            yield chunk
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("stream devices klaida: %s", exc)

                # Heartbeat — palaiko jungtį (ir proxy) gyvą net be pokyčių.
                yield ": ping\n\n"
                await asyncio.sleep(STREAM_INTERVAL)
        except asyncio.CancelledError:
            raise

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # išjungia buferinimą (jei prieš tai yra nginx)
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
