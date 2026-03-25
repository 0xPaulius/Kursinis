"""
Async Loki HTTP API klientas.
Naudoja httpx.AsyncClient neblokuojantiems užklausoms.
"""
from __future__ import annotations

import datetime
import logging

import httpx

logger = logging.getLogger(__name__)

# Nanoseconds per second
_NS = 1_000_000_000


def _to_ns(dt: datetime.datetime) -> int:
    return int(dt.timestamp() * _NS)


class AsyncLokiClient:
    """Async Loki HTTP klientas su graceful degradation."""

    def __init__(self, base_url: str, client: httpx.AsyncClient):
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def query_range(
        self,
        query: str,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        """
        Vykdo LogQL log query per nurodytą laiko langą.
        Grąžina log eilučių sąrašą su timestamp, line, labels.
        Klaidos atveju grąžina tuščią sąrašą (graceful degradation).
        """
        if end is None:
            end = datetime.datetime.now(datetime.timezone.utc)
        if start is None:
            start = end - datetime.timedelta(minutes=5)

        params = {
            "query": query,
            "start": _to_ns(start),
            "end": _to_ns(end),
            "limit": limit,
            "direction": "backward",
        }

        try:
            resp = await self._client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            result = data.get("data", {}).get("result", [])
            lines: list[dict] = []
            for stream in result:
                labels = stream.get("stream", {})
                for entry in stream.get("values", []):
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        lines.append({
                            "timestamp": entry[0],
                            "line": entry[1],
                            "labels": labels,
                        })
            return lines

        except Exception as exc:
            logger.warning("Loki query_range klaida (%s): %s", query[:60], exc)
            return []

    async def query_metric(
        self,
        query: str,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        step: str = "1h",
    ) -> list[dict]:
        """
        Vykdo LogQL metric query (count_over_time ir pan.).
        Grąžina matrix rezultatą: [{metric: {}, values: [[ts, val], ...]}]
        """
        if end is None:
            end = datetime.datetime.now(datetime.timezone.utc)
        if start is None:
            start = end - datetime.timedelta(hours=24)

        params = {
            "query": query,
            "start": _to_ns(start),
            "end": _to_ns(end),
            "step": step,
        }

        try:
            resp = await self._client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("result", [])

        except Exception as exc:
            logger.warning("Loki query_metric klaida (%s): %s", query[:60], exc)
            return []

    async def is_ready(self) -> bool:
        """Tikrina ar Loki yra pasiruošęs."""
        try:
            resp = await self._client.get(
                f"{self.base_url}/ready",
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
