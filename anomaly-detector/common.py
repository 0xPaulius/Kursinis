"""
Bendri anomalijų detektoriaus komponentai: konfigūracija, Alert, Loki klientas
ir LogQL srautų selektoriai.

Atskirta nuo detector.py, kad papildomi detektorių moduliai ir vertinimo paketas
(evaluation) galėtų juos naudoti be ciklinių importų.
"""
from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import requests

# ============================================================
# Konfigūracija
# ============================================================

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
SSH_BRUTE_THRESHOLD = int(os.getenv("SSH_BRUTE_THRESHOLD", "5"))
LOG_SPIKE_MULTIPLIER = float(os.getenv("LOG_SPIKE_MULTIPLIER", "3.0"))
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
# Kiek žalių log eilučių (įrodymų) saugoti prie kiekvieno alerto.
SAMPLE_LINE_LIMIT = int(os.getenv("SAMPLE_LINE_LIMIT", "15"))
# Statistinio baseline'o langas laiku (ne ciklų skaičiumi), kad nepriklausytų nuo CHECK_INTERVAL.
BASELINE_WINDOW_HOURS = float(os.getenv("BASELINE_WINDOW_HOURS", "24"))
# ML sluoksnis gyvame cikle numatytai išjungtas — kėlė per daug klaidingų teigiamų.
ENABLE_ML = os.getenv("ENABLE_ML", "false").strip().lower() in ("1", "true", "yes")
ML_EVERY_N_CYCLES = int(os.getenv("ML_EVERY_N_CYCLES", "5"))
# online — modelis permokomas kiekvieną kartą su naujausiais pavyzdžiais;
# frozen — apmokomas vieną kartą, kai treniravimo buferis prisipildo, ir nebekeičiamas.
ML_TRAINING_MODE = os.getenv("ML_TRAINING_MODE", "online").strip().lower()
ML_MAX_TRAINING_SAMPLES = int(os.getenv("ML_MAX_TRAINING_SAMPLES", "500"))
# Windows endpoint telemetrijos taisyklės (job="windows"). Numatytai įjungtos —
# be endpoint'ų srautas tiesiog tuščias, tad papildomos apkrovos nėra.
ENABLE_WINDOWS_RULES = os.getenv("ENABLE_WINDOWS_RULES", "true").strip().lower() in ("1", "true", "yes")
ENABLE_LINUX_RULES = os.getenv("ENABLE_LINUX_RULES", "true").strip().lower() in ("1", "true", "yes")
# Papildomi LogQL matcher'iai kiekvienam selektoriui (vertinimui, pvz. dataset="ait-fox").
LOKI_EXTRA_MATCHERS = os.getenv("LOKI_EXTRA_MATCHERS", "")
DATA_DIR = "/data"
ANOMALY_DB_PATH = os.path.join(DATA_DIR, "anomaly_history.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("anomaly-detector")


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ============================================================
# Duomenų struktūros
# ============================================================

@dataclass
class Alert:
    """Vienas aptiktas anomalijos alertas."""
    timestamp: str
    severity: str          # "low", "medium", "high", "critical"
    detection_method: str  # "rule", "statistical", "ml"
    alert_type: str        # "ssh_bruteforce", "log_spike", "ml_anomaly", ...
    description: str
    source_host: str = ""
    source_ip: str = ""
    details: dict = field(default_factory=dict)
    sample_lines: list = field(default_factory=list)  # žali log įrašai, sukėlę alertą
    attack_techniques: list = field(default_factory=list)  # MITRE ATT&CK ID, pvz. "T1110.001"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "severity": self.severity,
            "detection_method": self.detection_method,
            "alert_type": self.alert_type,
            "description": self.description,
            "source_host": self.source_host,
            "source_ip": self.source_ip,
            "details": self.details,
            "sample_lines": self.sample_lines,
            "attack_techniques": self.attack_techniques,
        }


# ============================================================
# LogQL selektoriai
# ============================================================

@dataclass(frozen=True)
class Selectors:
    """
    LogQL srautų selektoriai, kuriuos naudoja detektoriai.
    `extra_matchers` pridedamas prie kiekvieno selektoriaus — vertinimo metu taip
    apribojamas vienas duomenų rinkinys (pvz. `dataset="ait-fox"`).
    """
    extra_matchers: str = LOKI_EXTRA_MATCHERS

    def stream(self, job: str, *matchers: str) -> str:
        parts = [f'job="{job}"', *matchers]
        if self.extra_matchers:
            parts.append(self.extra_matchers)
        return "{" + ", ".join(parts) + "}"

    @property
    def syslog(self) -> str:
        return self.stream("syslog")

    @property
    def errors(self) -> str:
        return self.stream("errors")

    @property
    def windows(self) -> str:
        return self.stream("windows")

    @property
    def linux_endpoint(self) -> str:
        return self.stream("linux_endpoint")


# ============================================================
# Loki API klientas
# ============================================================

class LokiClient:
    """Paprastas Loki HTTP API klientas."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def query_range(
        self,
        query: str,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        limit: int = 5000,
    ) -> list[dict]:
        """
        Vykdo LogQL query per nurodytą laiko langą.
        Grąžina log eilučių sąrašą.
        """
        if end is None:
            end = utcnow()
        if start is None:
            start = end - datetime.timedelta(minutes=5)

        params = {
            "query": query,
            "start": int(start.timestamp() * 1e9),
            "end": int(end.timestamp() * 1e9),
            "limit": limit,
            "direction": "backward",
        }

        try:
            resp = self.session.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            result = data.get("data", {}).get("result", [])
            if not isinstance(result, list):
                logger.error("Loki atsakymas turi neteisingą struktūrą")
                return []

            lines = []
            for stream in result:
                labels = stream.get("stream", {})
                for entry in stream.get("values", []):
                    if not (isinstance(entry, (list, tuple)) and len(entry) == 2):
                        continue
                    ts_ns, line = entry
                    lines.append({
                        "timestamp": ts_ns,
                        "line": line,
                        "labels": labels,
                    })
            return lines

        except requests.RequestException as e:
            logger.error(f"Loki query klaida: {e}")
            return []

    def instant_query(
        self,
        query: str,
        at: Optional[datetime.datetime] = None,
    ) -> list[dict]:
        """
        Vykdo LogQL metrikos užklausą vienam laiko momentui (pvz. `sum(count_over_time(...))`).
        Grąžina [{"labels": {...}, "value": float}, ...].
        """
        if at is None:
            at = utcnow()
        params = {"query": query, "time": int(at.timestamp() * 1e9)}

        try:
            resp = self.session.get(
                f"{self.base_url}/loki/api/v1/query",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Loki metrikos query klaida: {e}")
            return []

        result = data.get("result", [])
        if data.get("resultType") == "scalar" and isinstance(result, list) and len(result) == 2:
            return [{"labels": {}, "value": float(result[1])}]
        if not isinstance(result, list):
            logger.error("Loki metrikos atsakymas turi neteisingą struktūrą")
            return []

        series = []
        for item in result:
            value = item.get("value")
            if isinstance(value, (list, tuple)) and len(value) == 2:
                series.append({"labels": item.get("metric", {}), "value": float(value[1])})
        return series

    def count(self, query: str, at: Optional[datetime.datetime] = None) -> float:
        """Metrikos užklausos reikšmių suma (pvz. `sum(count_over_time({...}[5m]))`)."""
        return sum(item["value"] for item in self.instant_query(query, at))

    def by_label(
        self, query: str, label: str, at: Optional[datetime.datetime] = None
    ) -> dict[str, float]:
        """Metrikos užklausa, sugrupuota pagal etiketę: {reikšmė: suma}."""
        out: dict[str, float] = {}
        for item in self.instant_query(query, at):
            key = item["labels"].get(label, "unknown")
            out[key] = out.get(key, 0.0) + item["value"]
        return out

    def is_ready(self) -> bool:
        """Tikrina ar Loki yra pasiruošęs."""
        try:
            resp = self.session.get(f"{self.base_url}/ready", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False
