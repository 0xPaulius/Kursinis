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

# Pašalintų įrenginių hostname'ai — kad ištrynus įrenginį jis nebegrįžtų kaip
# „aptiktas" (jo logai Loki dar lieka ~1 val po pašalinimo).
SUPPRESSED_DB_PATH = os.getenv("SUPPRESSED_DB_PATH", "/state/deleted_hosts.json")

# Ar paleidžiant užtikrinti numatytuosius demonstracinius įrenginius
# (MacBook, Windows 11 PC, maršrutizatorius, web serveris).
SEED_DEFAULT_DEVICES = os.getenv("SEED_DEFAULT_DEVICES", "1").lower() not in {"0", "false", "no"}

VALID_OS = {"macos", "windows"}

# Reprezentacinės OS versijos demonstraciniams įrenginiams (galima keisti pridedant)
DEFAULT_OS_VERSION = {
    "macos": "macOS 14 (Sonoma)",
    "windows": "Windows 11 (23H2)",
    "router": "RouterOS 7.14",
    "server": "Ubuntu Server 22.04 LTS",
}

# Numatytieji demonstraciniai įrenginiai — kad sistema iškart turėtų realistišką
# srautą (žemėlapis + „Paleisti demonstraciją" mygtukas). Dashboard fonis ciklas
# (main.py) generuoja jiems normalų srautą, tad jie matomi kaip aktyvūs. Pridedami
# tik jei jų dar nėra (neperrašo vartotojo pridėtų įrenginių) ir vartotojas jų neištrynė.
DEFAULT_DEVICES = [
    {"id": "default-macbook", "name": "MacBook", "hostname": "macbook",
     "ip": "192.168.1.50", "os": "macos"},
    {"id": "default-win11", "name": "Windows 11 PC", "hostname": "windows-11-pc",
     "ip": "192.168.1.60", "os": "windows"},
    {"id": "default-router", "name": "Maršrutizatorius", "hostname": "router-01",
     "ip": "192.168.1.1", "os": "router"},
    {"id": "default-webserver", "name": "Web serveris", "hostname": "web-server-01",
     "ip": "192.168.1.10", "os": "server"},
]

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
        self._suppressed: set[str] = self._load_suppressed()
        if SEED_DEFAULT_DEVICES:
            self._ensure_defaults()

    # -- Numatytieji įrenginiai ----------------------------------------------

    def _ensure_defaults(self) -> None:
        """Prideda numatytuosius įrenginius, jei jų dar nėra ir vartotojas jų neištrynė."""
        existing = {d.get("hostname") for d in self._devices}
        changed = False
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for d in DEFAULT_DEVICES:
            if d["hostname"] in existing or d["hostname"] in self._suppressed:
                continue
            self._devices.append({
                "id": d["id"],
                "name": d["name"],
                "hostname": d["hostname"],
                "ip": d["ip"],
                "os": d["os"],
                "os_version": DEFAULT_OS_VERSION.get(d["os"], ""),
                "synthetic": True,
                "enabled": True,
                "created_at": now,
            })
            changed = True
        if changed:
            self._save()
            logger.info("Numatytieji demonstraciniai įrenginiai užtikrinti")

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

    def _load_suppressed(self) -> set[str]:
        if not os.path.exists(SUPPRESSED_DB_PATH):
            return set()
        try:
            with open(SUPPRESSED_DB_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return {str(h) for h in data}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Pašalintų įrenginių failo skaitymo klaida: %s", exc)
        return set()

    def _save_suppressed(self) -> None:
        try:
            db_dir = os.path.dirname(SUPPRESSED_DB_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            tmp_path = f"{SUPPRESSED_DB_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(sorted(self._suppressed), fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, SUPPRESSED_DB_PATH)
        except OSError as exc:
            logger.error("Pašalintų įrenginių failo rašymo klaida: %s", exc)

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

    def suppressed_hostnames(self) -> set[str]:
        """Pašalintų įrenginių hostname'ai — nerodomi kaip „aptikti"."""
        return set(self._suppressed)

    def get(self, device_id: str) -> dict | None:
        return next((d for d in self._devices if d["id"] == device_id), None)

    def add(self, name: str, ip: str, os_type: str, os_version: str | None = None,
            synthetic: bool = True) -> dict:
        """
        Sukuria ir išsaugo naują įrenginį. Kelia ValueError, jei duomenys netinkami.
        synthetic=True — demonstracinis įrenginys (automatiškai generuoja normalų srautą);
        synthetic=False — realus įrenginys (siunčia savo tikrus logus, srautas negeneruojamas).
        """
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
            "synthetic": synthetic,
            "enabled": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._devices.append(device)
        self._save()
        if device["hostname"] in self._suppressed:
            self._suppressed.discard(device["hostname"])
            self._save_suppressed()
        logger.info("Pridėtas įrenginys: %s (%s, %s)", device["hostname"], ip, os_type)
        return device

    def delete(self, device_id: str) -> bool:
        device = self.get(device_id)
        if device is None:
            return False
        self._devices = [d for d in self._devices if d["id"] != device_id]
        self._save()
        hostname = device.get("hostname", "")
        if hostname:
            self._suppressed.add(hostname)
            self._save_suppressed()
        logger.info("Pašalintas įrenginys: %s (%s)", device_id, hostname)
        return True
