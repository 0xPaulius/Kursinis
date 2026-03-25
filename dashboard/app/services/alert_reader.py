"""
Alertų istorijos skaitymas iš anomaly-detector išvesties failo.
Verčia techninius alert tipus į paprastą lietuvių kalbą.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from app.models.schemas import AlertItem

logger = logging.getLogger(__name__)

ANOMALY_DB_PATH = os.getenv("ANOMALY_DB_PATH", "/data/anomaly_history.json")

# ---------------------------------------------------------------------------
# Vertimų žodynas: techninis tipas → vartotojui suprantama informacija
# ---------------------------------------------------------------------------

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ssh_bruteforce": {
        "title": "Bandymas įsilaužti per SSH",
        "explanation": (
            "Aptikta daug nesėkmingų bandymų prisijungti prie serverio. "
            "Tai gali būti bandymas atspėti slaptažodį."
        ),
        "recommendation": (
            "Rekomenduojama: peržiūrėkite, ar prisijungimas iš nurodyto IP yra leistinas. "
            "Jei ne — blokuokite jį ugniasienėje ir pakeiskite slaptažodžius."
        ),
    },
    "invalid_user_scan": {
        "title": "Nežinomi vartotojai bando jungtis",
        "explanation": (
            "Aptikti bandymai prisijungti su neegzistuojančiais vartotojų vardais. "
            "Tai gali reikšti, kad kas nors ieško silpnų vietų jūsų sistemoje."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar nurodyta IP priklausanti jūsų organizacijai. "
            "Jei ne — blokuokite ir informuokite IT specialistą."
        ),
    },
    "firewall_spike": {
        "title": "Padidėjęs blokuojamų jungčių kiekis",
        "explanation": (
            "Ugniasienė blokavo neįprastai daug jungčių. "
            "Gali būti tinklo ataka arba konfigūracijos problema."
        ),
        "recommendation": (
            "Rekomenduojama: informuokite IT specialistą. "
            "Jei sistema dirba lėtai — tai gali būti susiję."
        ),
    },
    "log_volume_spike": {
        "title": "Neįprastai daug sistemos žinučių",
        "explanation": (
            "Sistema generuoja žymiai daugiau žinučių nei įprastai. "
            "Tai gali reikšti problemą arba padidėjusį apkrovimą."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar sistema veikia normaliai. "
            "Jei lėta ar kyla klaidų — kreipkitės į IT specialistą."
        ),
    },
    "high_error_rate": {
        "title": "Daug sistemos klaidų",
        "explanation": (
            "Klaidų kiekis viršija normalų lygį. "
            "Kai kurios paslaugos gali veikti netinkamai."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar visos programos ir paslaugos veikia. "
            "Esant problemoms — kreipkitės į IT specialistą."
        ),
    },
    "ml_anomaly": {
        "title": "Neįprastas sistemos elgesys",
        "explanation": (
            "Dirbtinis intelektas aptiko neįprastus sistemos veiklos pokyčius. "
            "Tai gali būti ataka, gedimas arba neįprastas naudojimas."
        ),
        "recommendation": (
            "Rekomenduojama: peržiūrėkite kitus šio laikotarpio įspėjimus. "
            "Jei jų daug — nedelsiant informuokite IT specialistą."
        ),
    },
}

_DEFAULT_TRANSLATION = {
    "title": "Sistemos įspėjimas",
    "explanation": "Aptikta neįprasta sistemos veikla.",
    "recommendation": "Rekomenduojama: kreipkitės į IT specialistą dėl papildomo patikrinimo.",
}


def _translate(alert_type: str) -> tuple[str, str, str]:
    t = _TRANSLATIONS.get(alert_type, _DEFAULT_TRANSLATION)
    return t["title"], t["explanation"], t["recommendation"]


def _make_alert_item(raw: dict[str, Any]) -> AlertItem:
    alert_type = raw.get("alert_type", "unknown")
    title, explanation, recommendation = _translate(alert_type)
    return AlertItem(
        id=str(uuid.uuid4()),
        timestamp=raw.get("timestamp", ""),
        severity=raw.get("severity", "low"),
        alert_type=alert_type,
        title=title,
        explanation=explanation,
        recommendation=recommendation,
        source_ip=raw.get("source_ip", ""),
        source_host=raw.get("source_host", ""),
        detection_method=raw.get("detection_method", ""),
        details=raw.get("details", {}),
    )


class AlertReader:
    """
    Skaito alertų istoriją iš /data/anomaly_history.json.
    Failas tvarkomas anomaly-detector, montuojamas per Docker volume.
    """

    def read_all(self) -> list[AlertItem]:
        """Grąžina visus alertus (naujesni pirmi). Klaidos atveju — tuščias sąrašas."""
        if not os.path.exists(ANOMALY_DB_PATH):
            return []
        try:
            with open(ANOMALY_DB_PATH, "r", encoding="utf-8") as fh:
                raw_list: list[dict] = json.load(fh)
            # Naujesni pirmi
            alerts = [_make_alert_item(r) for r in reversed(raw_list)]
            return alerts
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Alertų failo skaitymo klaida: %s", exc)
            return []

    def read_recent(self, limit: int = 20) -> list[AlertItem]:
        return self.read_all()[:limit]

    def read_page(self, page: int, size: int = 50) -> tuple[list[AlertItem], int]:
        """Grąžina (puslapis, visas_kiekis)."""
        all_alerts = self.read_all()
        total = len(all_alerts)
        start = (page - 1) * size
        end = start + size
        return all_alerts[start:end], total
