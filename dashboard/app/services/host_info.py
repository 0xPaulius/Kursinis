"""
Savo serverio (Docker host'o) informacijos skaitymas.

Dashboard veikia konteineryje, tad host'o branduolio/OS versiją sužinome
per read-only primontuotus failus (docker-compose):
    /etc/hostname   -> {HOST_INFO_DIR}/hostname
    /etc/os-release -> {HOST_INFO_DIR}/os-release
    /proc/version   -> {HOST_INFO_DIR}/version

Jei failai neprimontuoti, `get()` grąžina None (savo įrenginys tiesiog
nerodomas su versija — bet vis tiek aptinkamas per Loki host label).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

HOST_INFO_DIR = os.getenv("HOST_INFO_DIR", "/host")


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _parse_pretty_name(os_release: str) -> str:
    """Ištraukia PRETTY_NAME iš /etc/os-release turinio."""
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def _parse_kernel(proc_version: str) -> str:
    """Iš „Linux version 6.12.1-... (...)" palieka „Linux 6.12.1-...""."""
    parts = proc_version.split()
    # Formatas: "Linux version <kernel> (...)"
    if len(parts) >= 3 and parts[0] == "Linux" and parts[1] == "version":
        return f"Linux {parts[2]}"
    return proc_version[:80] if proc_version else ""


class HostInfo:
    """Skaito ir kešuoja host'o tapatybę bei OS/branduolio versiją."""

    def __init__(self, base_dir: str = HOST_INFO_DIR) -> None:
        self._base_dir = base_dir
        self._cached: dict | None = None

    def get(self) -> dict | None:
        """
        Grąžina {hostname, os, os_version} arba None, jei host'o hostname nežinomas.
        Rezultatas kešuojamas (host'o duomenys keičiasi retai).
        """
        if self._cached is not None:
            return self._cached or None

        hostname = _read(os.path.join(self._base_dir, "hostname"))
        if not hostname:
            self._cached = {}
            return None

        pretty = _parse_pretty_name(_read(os.path.join(self._base_dir, "os-release")))
        kernel = _parse_kernel(_read(os.path.join(self._base_dir, "version")))
        version = " · ".join(p for p in (pretty, kernel) if p) or "Linux"

        self._cached = {"hostname": hostname, "os": "linux", "os_version": version}
        logger.info("Savo serveris atpažintas: %s (%s)", hostname, version)
        return self._cached
