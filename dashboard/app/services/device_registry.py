"""
Įrenginių registras — saugo vartotojo pridėtus įrenginius JSON faile.

Naudojamas demonstraciniam srautui: kiekvienas įrenginys turi hostname
(syslog HOST laukui), IP adresą ir OS tipą (macos / windows). Failas
rašomas atominiu būdu (tmp + os.replace), kad nesugadintų esant gedimui.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)

DEVICES_DB_PATH = os.getenv("DEVICES_DB_PATH", "/state/devices.json")

VALID_OS = {"macos", "windows"}

# Reprezentacinės OS versijos demonstraciniams įrenginiams (galima keisti pridedant)
DEFAULT_OS_VERSION = {
    "macos": "macOS 14 (Sonoma)",
    "windows": "Windows 11 (23H2)",
}

_IP_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def _valid_ip(ip: str) -> bool:
    """Paprastas IPv4 patikrinimas (0-255 kiekvienam oktetui)."""
    m = _IP_RE.match(ip)
    return bool(m) and all(0 <= int(o) <= 255 for o in m.groups())


def _slugify_hostname(name: str) -> str:
    """Paverčia įrenginio pavadinimą į syslog hostname be tarpų."""
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", name.strip().lower()).strip("-")
    return slug or "device"


class DeviceRegistry:
    """
    Įrenginių sąrašo saugykla su persistencija į DEVICES_DB_PATH.

    Laikoma atmintyje (`_devices`) ir sinchronizuojama su failu po kiekvieno
    pakeitimo. Skaitymas vyksta iš atminties, tad pollinimas yra pigus.
    """

    def __init__(self) -> None:
        self._devices: list[dict] = self._load()

    # -- Persistencija --------------------------------------------------------

    def _load(self) -> list[dict]:
        if not os.path.exists(DEVICES_DB_PATH):
            return []
        try:
            with open(DEVICES_DB_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Įrenginių failo skaitymo klaida: %s", exc)
        return []

    def _save(self) -> None:
        try:
            db_dir = os.path.dirname(DEVICES_DB_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            tmp_path = f"{DEVICES_DB_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(self._devices, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, DEVICES_DB_PATH)
        except OSError as exc:
            logger.error("Įrenginių failo rašymo klaida: %s", exc)

    # -- Pagalbinės -----------------------------------------------------------

    def _unique_hostname(self, base: str) -> str:
        existing = {d["hostname"] for d in self._devices}
        if base not in existing:
            return base
        i = 2
        while f"{base}-{i}" in existing:
            i += 1
        return f"{base}-{i}"

    # -- Vieša API ------------------------------------------------------------

    def list_all(self) -> list[dict]:
        return list(self._devices)

    def get(self, device_id: str) -> dict | None:
        return next((d for d in self._devices if d["id"] == device_id), None)

    def add(self, name: str, ip: str, os_type: str, os_version: str | None = None) -> dict:
        """Sukuria ir išsaugo naują įrenginį. Kelia ValueError, jei duomenys netinkami."""
        name = (name or "").strip()
        if not name:
            raise ValueError("Pavadinimas privalomas")
        os_type = (os_type or "").strip().lower()
        if os_type not in VALID_OS:
            raise ValueError("Nepalaikomas OS tipas (macos arba windows)")
        ip = (ip or "").strip()
        if not _valid_ip(ip):
            raise ValueError("Neteisingas IPv4 adresas")

        os_version = (os_version or "").strip() or DEFAULT_OS_VERSION.get(os_type, "")
        device = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "hostname": self._unique_hostname(_slugify_hostname(name)),
            "ip": ip,
            "os": os_type,
            "os_version": os_version,
            "synthetic": True,
            "enabled": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._devices.append(device)
        self._save()
        logger.info("Pridėtas įrenginys: %s (%s, %s)", device["hostname"], ip, os_type)
        return device

    def delete(self, device_id: str) -> bool:
        before = len(self._devices)
        self._devices = [d for d in self._devices if d["id"] != device_id]
        if len(self._devices) == before:
            return False
        self._save()
        logger.info("Pašalintas įrenginys: %s", device_id)
        return True
