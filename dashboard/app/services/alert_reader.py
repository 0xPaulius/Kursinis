"""
Alertų istorijos skaitymas iš anomaly-detector išvesties failo.
Verčia techninius alert tipus į paprastą lietuvių kalbą.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from app.models.schemas import AlertItem

logger = logging.getLogger(__name__)

ANOMALY_DB_PATH = os.getenv("ANOMALY_DB_PATH", "/data/anomaly_history.json")

# Alert tipai, kurių nerodome vartotojui. `ml_anomaly` (ML „neįprastas elgesys")
# išjungtas — kėlė per daug klaidingų teigiamų ir buvo per dažnas, kad būtų naudingas.
_EXCLUDED_ALERT_TYPES = {"ml_anomaly"}

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
    # --- Windows galinių įrenginių (endpoint) įspėjimai ---
    "win_failed_logon_bruteforce": {
        "title": "Windows: slaptažodžių spėjimo ataka",
        "explanation": (
            "Iš vieno adreso daug nesėkmingų Windows prisijungimų (įvykis 4625). "
            "Tai gali būti bandymas atspėti slaptažodį."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite nurodytą IP ir, jei jis nepatikimas, "
            "blokuokite jį ir peržiūrėkite paskyrų saugumą."
        ),
    },
    "win_password_spray": {
        "title": "Windows: slaptažodžių purškimas",
        "explanation": (
            "Iš vieno adreso bandyta jungtis prie daugelio skirtingų paskyrų. "
            "Būdinga slaptažodžių purškimo (password spraying) atakai."
        ),
        "recommendation": (
            "Rekomenduojama: blokuokite šaltinį ir įjunkite paskyrų užrakinimo politiką."
        ),
    },
    "win_account_lockout": {
        "title": "Windows: paskyra užrakinta",
        "explanation": (
            "Windows paskyra užrakinta dėl daugkartinių nesėkmingų bandymų (įvykis 4740)."
        ),
        "recommendation": (
            "Rekomenduojama: išsiaiškinkite, ar tai teisėtas vartotojas, ar ataka."
        ),
    },
    "win_account_created": {
        "title": "Windows: sukurta nauja paskyra",
        "explanation": (
            "Sukurta nauja vietinė Windows paskyra (įvykis 4720). "
            "Jei to nedarė administratorius — gali būti įsilaužimo pėdsakas."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar paskyra sukurta teisėtai."
        ),
    },
    "win_admin_group_add": {
        "title": "Windows: narys įtrauktas į administratorius",
        "explanation": (
            "Vartotojas įtrauktas į lokalių administratorių grupę (įvykis 4732). "
            "Tai teisių eskalavimo požymis."
        ),
        "recommendation": (
            "Rekomenduojama: skubiai patikrinkite, ar pakeitimas autorizuotas."
        ),
    },
    "win_audit_log_cleared": {
        "title": "Windows: išvalytas saugumo žurnalas",
        "explanation": (
            "Išvalytas Windows saugumo audito žurnalas (įvykis 1102). "
            "Užpuolikai taip slepia pėdsakus."
        ),
        "recommendation": (
            "Rekomenduojama: traktuokite kaip galimą incidentą ir ištirkite įrenginį."
        ),
    },
    "win_suspicious_powershell": {
        "title": "Windows: įtartinas PowerShell scenarijus",
        "explanation": (
            "Įvykdytas PowerShell scenarijus su įtartinais požymiais (įvykis 4104), "
            "pvz. kodo parsisiuntimas ar užmaskavimas."
        ),
        "recommendation": (
            "Rekomenduojama: peržiūrėkite scenarijų ir izoliuokite įrenginį, jei kenkėjiškas."
        ),
    },
    "win_discovery_burst": {
        "title": "Windows: žvalgybos komandų serija",
        "explanation": (
            "Per trumpą laiką paleista daug sistemos žvalgybos komandų "
            "(whoami, net, ipconfig ir pan.) — būdinga po įsilaužimo."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, kas vykdė komandas šiame įrenginyje."
        ),
    },
    "win_lolbin_network": {
        "title": "Windows: sistemos įrankis jungiasi į internetą",
        "explanation": (
            "Legitimus Windows įrankis (pvz. rundll32, certutil) jungėsi į išorinį adresą. "
            "Taip dažnai parsiunčiami kenkėjiški įrankiai."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite paskirties adresą ir procesą."
        ),
    },
    "win_startup_persistence": {
        "title": "Windows: failas įrašytas į paleisties aplanką",
        "explanation": (
            "Į automatinės paleisties (Startup) aplanką įrašytas failas — "
            "taip kenkėjiška programa užsitikrina paleidimą po perkrovimo."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite failą ir pašalinkite, jei neatpažįstamas."
        ),
    },
    # --- Linux galinių įrenginių (auditd) įspėjimai ---
    "linux_sudo_auth_failure": {
        "title": "Linux: nesėkmingi sudo bandymai",
        "explanation": (
            "Kelis kartus nepavyko gauti administratoriaus teisių (sudo/su). "
            "Gali būti bandymas išsikelti teises."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar tai darė pats vartotojas."
        ),
    },
    "linux_account_created": {
        "title": "Linux: sukurta nauja paskyra",
        "explanation": (
            "Serveryje sukurta nauja vietinė paskyra. "
            "Jei to nedarė administratorius — gali būti įsilaužimo pėdsakas."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, ar paskyra sukurta teisėtai."
        ),
    },
    "linux_suspicious_execve": {
        "title": "Linux: įtartina komanda",
        "explanation": (
            "Paleista komanda, būdinga nuotoliniam valdymui (pvz. interaktyvus shell "
            "ar nc -e) — dažnas įsilaužėlio žingsnis."
        ),
        "recommendation": (
            "Rekomenduojama: peržiūrėkite komandą ir izoliuokite serverį, jei ji neatpažįstama."
        ),
    },
    "linux_discovery_burst": {
        "title": "Linux: žvalgybos komandų serija",
        "explanation": (
            "Per trumpą laiką paleista daug sistemos žvalgybos komandų "
            "(whoami, id, uname ir pan.) — būdinga po įsilaužimo."
        ),
        "recommendation": (
            "Rekomenduojama: patikrinkite, kas vykdė komandas šiame serveryje."
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


def _alert_id(raw: dict[str, Any]) -> str:
    """
    Deterministinis ID iš pagrindinių laukų — leidžia klientui sekti "matytus"
    įspėjimus, nesikeičia tarp užklausų.
    """
    parts = [
        str(raw.get("timestamp", "")),
        str(raw.get("alert_type", "")),
        str(raw.get("source_ip", "")),
        str(raw.get("source_host", "")),
    ]
    # Vieno įvykio tapatybė (pvz. paskyra): keli to paties tipo įvykiai tame pačiame cikle.
    # Pridedama tik esant — kitų alertų ID nesikeičia.
    event_key = (raw.get("details") or {}).get("key")
    if event_key:
        parts.append(str(event_key))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _make_alert_item(raw: dict[str, Any]) -> AlertItem:
    alert_type = raw.get("alert_type", "unknown")
    title, explanation, recommendation = _translate(alert_type)
    return AlertItem(
        id=_alert_id(raw),
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
        sample_lines=raw.get("sample_lines", []) or [],
        attack_techniques=raw.get("attack_techniques", []) or [],
    )


class AlertReader:
    """
    Skaito alertų istoriją iš /data/anomaly_history.json.
    Failas tvarkomas anomaly-detector, montuojamas per Docker volume.

    Kešavimas pagal mtime: dashboard'as pollina /api/alerts/recent kas 15s.
    Pakartotinai neparsuojame failo, jei jis nepasikeitė.
    """

    def __init__(self) -> None:
        self._cached: list[AlertItem] | None = None
        self._cached_mtime: float | None = None

    def _load(self) -> list[AlertItem]:
        """Grąžina alertus iš failo arba kešo (jei mtime nepasikeitė)."""
        if not os.path.exists(ANOMALY_DB_PATH):
            self._cached = []
            self._cached_mtime = None
            return self._cached

        try:
            mtime = os.path.getmtime(ANOMALY_DB_PATH)
        except OSError as exc:
            logger.warning("Alertų failo mtime klaida: %s", exc)
            return self._cached or []

        if self._cached is not None and self._cached_mtime == mtime:
            return self._cached

        try:
            with open(ANOMALY_DB_PATH, "r", encoding="utf-8") as fh:
                raw_list: list[dict] = json.load(fh)
            # Naujesni pirmi; išfiltruojame išjungtus alert tipus (pvz. ml_anomaly).
            self._cached = [
                _make_alert_item(r)
                for r in reversed(raw_list)
                if r.get("alert_type") not in _EXCLUDED_ALERT_TYPES
            ]
            self._cached_mtime = mtime
            return self._cached
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Alertų failo skaitymo klaida: %s", exc)
            return []

    def read_all(self) -> list[AlertItem]:
        """Grąžina visus alertus (naujesni pirmi). Klaidos atveju — tuščias sąrašas."""
        return list(self._load())

    def read_recent(self, limit: int = 20) -> list[AlertItem]:
        return self._load()[:limit]

    def read_page(self, page: int, size: int = 50) -> tuple[list[AlertItem], int]:
        """Grąžina (puslapis, visas_kiekis)."""
        all_alerts = self._load()
        total = len(all_alerts)
        start = (page - 1) * size
        end = start + size
        return all_alerts[start:end], total
