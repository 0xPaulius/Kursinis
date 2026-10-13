"""
Pranešimų (webhook) nustatymų API maršrutai.

Leidžia per UI sukonfigūruoti webhook kanalą, į kurį dashboard'as siunčia
naujus anomalijų alertus, ir išsiųsti testinį pranešimą.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_notifier, require_admin, require_auth
from app.models.schemas import NotificationSettings
from app.services.notifier import VALID_SEVERITIES, Notifier, is_valid_webhook

# Skaitymas — bet kuriam prisijungusiam; keitimas/testas — tik admin (žr. maršrutus).
router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_auth)],
)


@router.get("/settings", response_model=NotificationSettings)
async def get_settings(
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> NotificationSettings:
    """Dabartiniai pranešimų nustatymai."""
    return NotificationSettings(**notifier.load_settings())


@router.put("/settings", response_model=NotificationSettings, dependencies=[Depends(require_admin)])
async def update_settings(
    payload: NotificationSettings,
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> NotificationSettings:
    """Išsaugo pranešimų nustatymus."""
    if payload.min_severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="Neteisingas sunkumo lygis")
    if payload.webhook_url and not is_valid_webhook(payload.webhook_url):
        raise HTTPException(status_code=400, detail="Neteisingas webhook URL (reikia http/https)")
    if payload.enabled and not payload.webhook_url:
        raise HTTPException(status_code=400, detail="Įjungus pranešimus, webhook URL privalomas")
    notifier.save_settings(payload.model_dump())
    return payload


@router.post("/test", dependencies=[Depends(require_admin)])
async def test_notification(
    payload: NotificationSettings,
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> dict:
    """Išsiunčia testinį pranešimą į nurodytą (arba išsaugotą) webhook."""
    url = payload.webhook_url or notifier.load_settings()["webhook_url"]
    if not url:
        raise HTTPException(status_code=400, detail="Webhook URL nenustatytas")
    try:
        await notifier.send_text("Testas: pranešimų kanalas veikia.", url)
    except Exception as exc:  # noqa: BLE001 — vartotojui grąžiname aiškią klaidą
        raise HTTPException(status_code=502, detail=f"Nepavyko išsiųsti: {exc}")
    return {"detail": "Testinis pranešimas išsiųstas"}
