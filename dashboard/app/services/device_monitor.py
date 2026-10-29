"""
Įrenginių žemėlapio duomenys.

Sujungia tris šaltinius į vieną mazgų sąrašą:
  1. Registruoti (demonstraciniai) įrenginiai — iš DeviceRegistry.
  2. Savas serveris (Docker host) — iš HostInfo (branduolio/OS versija).
  3. Aptikti host'ai — iš Loki `host` etiketės (bet kas, kas siunčia logus).

Kiekvienam mazgui priskiriama gyva statistika iš Loki (logų kiekis per 5 min
ir 1 val, paskutinio logo laikas) bei įspėjimų suvestinė iš AlertReader.
"""
from __future__ import annotations

import datetime
import logging
import os
import re

from app.log_selectors import logs_selector
from app.services.alert_reader import AlertReader
from app.services.device_registry import DEFAULT_OS_VERSION, DeviceRegistry
from app.services.host_info import HostInfo
from app.services.loki_client import AsyncLokiClient

logger = logging.getLogger(__name__)

_SEV_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Savo serverio (host) rodomas vardas — be realaus hostname (pvz. „bombiteris").
SELF_DEVICE_NAME = os.getenv("SELF_DEVICE_NAME", "Šis serveris")
# Gryni IP kaip host (pvz. 172.18.0.1 — Docker tinklo šliuzas) — tai ne įrenginys.
_IP_ONLY = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _matches(alert, ip: str, hostname: str) -> bool:
    # source_host gali būti sąrašas „web-1, web-2" (SSH brute-force keliems host'ams).
    hosts = {h.strip() for h in (alert.source_host or "").split(",")}
    return bool((ip and alert.source_ip == ip) or (hostname and hostname in hosts))


def alerts_for_device(ip: str, hostname: str, alerts: list) -> list:
    """Įrenginio įspėjimai (pagal IP arba tikslų host vardą), ta pačia tvarka kaip `alerts`."""
    return [a for a in alerts if _matches(a, ip, hostname)]


def alert_summary(ip: str, hostname: str, alerts: list) -> tuple[int, str]:
    """Įrenginio įspėjimų skaičius ir blogiausias sunkumas (pagal IP arba tikslų host vardą)."""
    matched = alerts_for_device(ip, hostname, alerts)
    worst = "none"
    for a in matched:
        if _SEV_RANK.get(a.severity, 0) > _SEV_RANK.get(worst, 0):
            worst = a.severity
    return len(matched), worst


class DeviceMonitor:
    def __init__(
        self,
        loki: AsyncLokiClient,
        registry: DeviceRegistry,
        alert_reader: AlertReader,
        host_info: HostInfo,
    ) -> None:
        self._loki = loki
        self._registry = registry
        self._alert_reader = alert_reader
        self._host_info = host_info

    # -- Loki statistika ------------------------------------------------------

    async def _per_host_stats(self) -> dict[str, dict]:
        now = datetime.datetime.now(datetime.timezone.utc)
        stats: dict[str, dict] = {}

        def _ensure(host: str) -> dict:
            return stats.setdefault(host, {"logs_5m": 0, "logs_1h": 0, "last_seen": None})

        # Kiekiai per metric užklausas (neribojama 5000 eilučių riba)
        m5 = await self._loki.query_metric(
            f'sum by (host)(count_over_time({logs_selector()}[5m]))',
            start=now - datetime.timedelta(minutes=5), end=now, step="5m",
        )
        m1h = await self._loki.query_metric(
            f'sum by (host)(count_over_time({logs_selector()}[1h]))',
            start=now - datetime.timedelta(hours=1), end=now, step="1h",
        )
        for series in m5:
            host = series.get("metric", {}).get("host")
            if host:
                _ensure(host)["logs_5m"] = _last_value(series)
        for series in m1h:
            host = series.get("metric", {}).get("host")
            if host:
                _ensure(host)["logs_1h"] = _last_value(series)

        # Paskutinio logo laikas — paskutinė netuščia minutė per 1 val (metric query, ±1 min;
        # eilučių atsisiuntimas apribotas 5000 ir tylesnių host'ų nepasiektų)
        recent = await self._loki.query_metric(
            f'sum by (host)(count_over_time({logs_selector()}[1m]))',
            start=now - datetime.timedelta(hours=1), end=now, step="1m",
        )
        for series in recent:
            host = series.get("metric", {}).get("host")
            stamps = [float(ts) for ts, _val in series.get("values", [])]
            if host and stamps:
                _ensure(host)["last_seen"] = datetime.datetime.fromtimestamp(
                    max(stamps), tz=datetime.timezone.utc).isoformat()

        return stats

    # -- Mazgų sudarymas ------------------------------------------------------

    async def build_map(self) -> dict:
        stats = await self._per_host_stats()
        nodes: dict[str, dict] = {}

        # 1. Registruoti įrenginiai
        for d in self._registry.list_all():
            nodes[d["hostname"]] = {
                "id": d["id"],
                "name": d["name"],
                "hostname": d["hostname"],
                "ip": d.get("ip", ""),
                "os": d.get("os", "unknown"),
                "os_version": d.get("os_version") or DEFAULT_OS_VERSION.get(d.get("os", ""), ""),
                "source": "registered",
            }

        # 2. Savas serveris (Docker host) — vardas bendrinis (be realaus hostname).
        host = self._host_info.get()
        if host and host.get("hostname"):
            h = host["hostname"]
            node = nodes.get(h, {"id": f"host:{h}", "name": SELF_DEVICE_NAME, "hostname": h, "ip": ""})
            node["source"] = "self"
            node["os"] = host.get("os", "linux")
            node["os_version"] = host.get("os_version", "")
            nodes[h] = node

        # 3. Aptikti host'ai (siunčia logus, bet nėra registre).
        #    Praleidžiame grynus IP (Docker šliuzas, pvz. 172.18.0.1 — NAT'inti logai
        #    be hostname) ir pašalintus įrenginius (kad ištrynus negrįžtų).
        suppressed = self._registry.suppressed_hostnames()
        for h in stats:
            if h in nodes:
                continue
            if _IP_ONLY.match(h) or h in suppressed:
                continue
            nodes[h] = {
                "id": f"host:{h}", "name": h, "hostname": h,
                "ip": "", "os": "unknown", "os_version": "", "source": "discovered",
            }

        # Statistika + įspėjimai
        alerts = self._alert_reader.read_all()
        result: list[dict] = []
        for h, node in nodes.items():
            st = stats.get(h, {})
            node["logs_5m"] = int(st.get("logs_5m", 0))
            node["logs_1h"] = int(st.get("logs_1h", 0))
            node["last_seen"] = st.get("last_seen")
            node["online"] = node["logs_5m"] > 0
            ac, ws = alert_summary(node.get("ip", ""), node["hostname"], alerts)
            node["alert_count"] = ac
            node["worst_severity"] = ws
            result.append(node)

        result.sort(key=lambda n: (-n["logs_5m"], n["name"].lower()))

        loki_ok = await self._loki.is_ready()
        collector_logs = sum(n["logs_5m"] for n in result)
        return {
            "collector": {
                "name": "Kolektorius (syslog-ng)",
                "online": loki_ok,
                "logs_5m": collector_logs,
            },
            "devices": result,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def _last_value(series: dict) -> int:
    """Grąžina paskutinę (naujausią) metric reikšmę iš Loki matrix serijos."""
    values = series.get("values", [])
    best = 0
    for _ts, val in values:
        try:
            best = max(best, int(float(val)))
        except (ValueError, TypeError):
            continue
    return best
