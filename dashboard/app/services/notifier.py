"""
Pranešimų siuntiklis — siunčia naujus anomalijų alertus į webhook (Slack/Telegram/kt.).

Nustatymai (įjungta / webhook URL / minimalus sunkumas) saugomi JSON faile
`/state/notify.json` (rw volume `dashboard-state`). Fonis ciklas (main.py)
periodiškai tikrina naujus alertus iš AlertReader ir siunčia tuos, kurių dar
nesiuntė ir kurių sunkumas ≥ nustatyto.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

NOTIFY_CONFIG_PATH = os.getenv("NOTIFY_CONFIG_PATH", "/state/notify.json")

_SEV_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_SEV_ICON = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}
VALID_SEVERITIES = set(_SEV_RANK)

_DEFAULTS = {"enabled": False, "webhook_url": "", "min_severity": "medium"}


def is_valid_webhook(url: str) -> bool:
    """Leidžiame tik http/https — paprasta apsauga (admin-only API)."""
    try:
        p = urlparse(url)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except ValueError:
        return False


class Notifier:
    """Webhook pranešimų logika su nustatymų persistencija ir „matytų" alertų seka."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._sent_ids: set[str] = set()

    # -- Nustatymai -----------------------------------------------------------

    def load_settings(self) -> dict:
        if os.path.exists(NOTIFY_CONFIG_PATH):
            try:
                with open(NOTIFY_CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return {
                    "enabled": bool(data.get("enabled", False)),
                    "webhook_url": str(data.get("webhook_url", "")),
                    "min_severity": (str(data.get("min_severity", "medium"))
                                     if data.get("min_severity") in VALID_SEVERITIES else "medium"),
                }
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Pranešimų nustatymų skaitymo klaida: %s", exc)
        return dict(_DEFAULTS)

    def save_settings(self, settings: dict) -> None:
        payload = {
            "enabled": bool(settings.get("enabled", False)),
            "webhook_url": str(settings.get("webhook_url", "")),
            "min_severity": (str(settings.get("min_severity", "medium"))
                             if settings.get("min_severity") in VALID_SEVERITIES else "medium"),
        }
        try:
            db_dir = os.path.dirname(NOTIFY_CONFIG_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            tmp_path = f"{NOTIFY_CONFIG_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, NOTIFY_CONFIG_PATH)
        except OSError as exc:
            logger.error("Pranešimų nustatymų rašymo klaida: %s", exc)

    # -- Siuntimas ------------------------------------------------------------

    async def send_text(self, text: str, webhook_url: str) -> None:
        """Siunčia vieną žinutę į webhook. Kelia klaidą, jei nepavyksta."""
        if not is_valid_webhook(webhook_url):
            raise ValueError("Neteisingas webhook URL (reikia http/https)")
        resp = await self._client.post(webhook_url, json={"text": text}, timeout=10.0)
        resp.raise_for_status()

    def prime(self, alert_ids: Iterable[str]) -> None:
        """Pažymi esamus alertus kaip „matytus" — kad nebūtų siunčiama istorija."""
        self._sent_ids.update(alert_ids)

    async def process_new(self, alerts_oldest_first: list) -> int:
        """
        Siunčia naujus (dar nesiųstus) alertus pagal nustatymus. `alerts` —
        AlertItem sąrašas (seniausi pirmi). Grąžina išsiųstų kiekį.
        """
        settings = self.load_settings()
        if not settings["enabled"] or not settings["webhook_url"]:
            # Pažymime visus esamus kaip matytus, kad įjungus nebūtų išsiųsta sena istorija.
            self.prime(a.id for a in alerts_oldest_first)
            return 0

        min_rank = _SEV_RANK.get(settings["min_severity"], 2)
        sent = 0
        for a in alerts_oldest_first:
            if a.id in self._sent_ids:
                continue
            if _SEV_RANK.get(a.severity, 1) < min_rank:
                self._sent_ids.add(a.id)  # žemo sunkumo — praleidžiam, bet žymim matytu
                continue
            try:
                await self.send_text(self._format(a), settings["webhook_url"])
                self._sent_ids.add(a.id)
                sent += 1
            except Exception as exc:  # noqa: BLE001 — nesustabdom ciklo dėl vieno webhook gedimo
                logger.warning("Pranešimo siuntimo klaida: %s", exc)
                break  # bandysime vėl kitą ciklą
        return sent

    @staticmethod
    def _format(alert) -> str:
        icon = _SEV_ICON.get(alert.severity, "❓")
        src = alert.source_ip or alert.source_host or "—"
        return f"{icon} [{alert.severity.upper()}] {alert.title} — {src}"
