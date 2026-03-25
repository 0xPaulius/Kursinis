#!/usr/bin/env python3
"""
Centralizuota anomalijų aptikimo sistema
=========================================
Periodiškai query'ina Loki API ir taiko anomalijų aptikimo metodus:

1. Taisyklėmis pagrįstas (Rule-based):
   - SSH brute-force aptikimas
   - Neleistinų IP prisijungimai
   - Nežinomų vartotojų bandymai

2. Statistinis (Baseline deviation):
   - Log volume spike aptikimas
   - Neįprastų valandų aktyvumas
   - Error rate nukrypimai

3. ML-pagrįstas (Isolation Forest):
   - Daugiamačių požymių anomalijų aptikimas
   - Automatinis baseline mokymasis

Autorius: Paulius Turauskas
Kursinis darbas: Centralizuota žurnalų analizės ir anomalijų
                 aptikimo sistema mažoms organizacijoms
"""

import os
import sys
import json
import time
import logging
import datetime
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import signal

import joblib
import requests
import numpy as np
from sklearn.ensemble import IsolationForest

# ============================================================
# Konfigūracija
# ============================================================

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
SSH_BRUTE_THRESHOLD = int(os.getenv("SSH_BRUTE_THRESHOLD", "5"))
LOG_SPIKE_MULTIPLIER = float(os.getenv("LOG_SPIKE_MULTIPLIER", "3.0"))
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
ANOMALY_DB_PATH = "/data/anomaly_history.json"
MODEL_PATH = "/data/model.pkl"
TRAINING_DATA_PATH = "/data/training_data.pkl"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("anomaly-detector")


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
        }


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
            end = datetime.datetime.now(datetime.timezone.utc)
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

    def is_ready(self) -> bool:
        """Tikrina ar Loki yra pasiruošęs."""
        try:
            resp = self.session.get(f"{self.base_url}/ready", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False


# ============================================================
# 1. TAISYKLĖMIS PAGRĮSTAS APTIKIMAS (Rule-based)
# ============================================================

class RuleBasedDetector:
    """
    Statinių taisyklių variklis anomalijoms aptikti.
    Tikrina žinomus pavojingus pattern'us.
    """

    def __init__(self, loki: LokiClient):
        self.loki = loki

    def check_ssh_bruteforce(self, window_minutes: int = 5) -> list[Alert]:
        """
        Aptinka SSH brute-force atakas.
        Kriterijai: >N nesėkmingų prisijungimų per laiko langą iš to paties IP.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range(
            '{job="syslog"} |= "Failed password"',
            start=start,
            end=now,
        )

        # Skaičiuojame nesėkmes pagal IP
        ip_pattern = re.compile(r"from\s+(\d+\.\d+\.\d+\.\d+)")
        ip_counts: Counter = Counter()
        ip_hosts: dict[str, set] = defaultdict(set)

        for entry in lines:
            match = ip_pattern.search(entry["line"])
            if match:
                ip = match.group(1)
                ip_counts[ip] += 1
                host = entry["labels"].get("host", "unknown")
                ip_hosts[ip].add(host)

        for ip, count in ip_counts.items():
            if count >= SSH_BRUTE_THRESHOLD:
                severity = "high" if count >= SSH_BRUTE_THRESHOLD * 3 else "medium"
                alerts.append(Alert(
                    timestamp=now.isoformat(),
                    severity=severity,
                    detection_method="rule",
                    alert_type="ssh_bruteforce",
                    description=(
                        f"SSH brute-force aptiktas: {count} nesėkmingų bandymų "
                        f"per {window_minutes} min iš IP {ip}"
                    ),
                    source_ip=ip,
                    source_host=", ".join(ip_hosts[ip]),
                    details={
                        "failed_attempts": count,
                        "window_minutes": window_minutes,
                        "threshold": SSH_BRUTE_THRESHOLD,
                        "target_hosts": list(ip_hosts[ip]),
                    },
                ))

        return alerts

    def check_unauthorized_access(self, window_minutes: int = 5) -> list[Alert]:
        """
        Aptinka bandymus prisijungti su neegzistuojančiais vartotojais.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range(
            '{job="syslog"} |= "Invalid user"',
            start=start,
            end=now,
        )

        user_pattern = re.compile(r"Invalid user\s+(\S+)\s+from\s+(\d+\.\d+\.\d+\.\d+)")
        attempts: dict[str, list] = defaultdict(list)

        for entry in lines:
            match = user_pattern.search(entry["line"])
            if match:
                user, ip = match.group(1), match.group(2)
                attempts[ip].append(user)

        for ip, users in attempts.items():
            if len(users) >= 3:
                alerts.append(Alert(
                    timestamp=now.isoformat(),
                    severity="high",
                    detection_method="rule",
                    alert_type="invalid_user_scan",
                    description=(
                        f"Vartotojų skenavimas aptiktas: {len(users)} skirtingi "
                        f"vartotojų vardai iš IP {ip}"
                    ),
                    source_ip=ip,
                    details={
                        "usernames_tried": list(set(users)),
                        "attempt_count": len(users),
                    },
                ))

        return alerts

    def check_firewall_events(self, window_minutes: int = 5) -> list[Alert]:
        """
        Aptinka neįprastai didelį blokuojamų paketų kiekį.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range(
            '{job="syslog"} |~ "DROP|REJECT|blocked"',
            start=start,
            end=now,
        )

        if len(lines) > 50:
            alerts.append(Alert(
                timestamp=now.isoformat(),
                severity="medium",
                detection_method="rule",
                alert_type="firewall_spike",
                description=(
                    f"Neįprastai daug ugniasienės blokavimų: "
                    f"{len(lines)} per {window_minutes} min"
                ),
                details={"blocked_count": len(lines)},
            ))

        return alerts


# ============================================================
# 2. STATISTINIS APTIKIMAS (Baseline deviation)
# ============================================================

class StatisticalDetector:
    """
    Statistinis anomalijų aptikimas pagrįstas baseline'u.
    Skaičiuoja vidurkį ir standartinį nuokrypį,
    alertina kai reikšmė viršija N sigma.
    """

    def __init__(self, loki: LokiClient):
        self.loki = loki
        self.baseline_history: list[float] = []
        self.max_history = 288  # 24 valandų baseline (288 x 60s intervalų)

    def _update_baseline(self, current_value: float):
        """Atnaujina baseline istoriją."""
        self.baseline_history.append(current_value)
        if len(self.baseline_history) > self.max_history:
            self.baseline_history = self.baseline_history[-self.max_history:]

    def check_log_volume_spike(self, window_minutes: int = 5) -> list[Alert]:
        """
        Aptinka staigų logų kiekio šuolį (spike).
        Lygina dabartinį kiekį su istoriniu vidurkiu.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range(
            '{job="syslog"}',
            start=start,
            end=now,
        )
        current_count = float(len(lines))
        self._update_baseline(current_count)

        if len(self.baseline_history) < 5:
            logger.info(
                f"Renkamas baseline: {len(self.baseline_history)}/5 "
                f"(dabartinis: {current_count:.0f})"
            )
            return alerts

        arr = np.array(self.baseline_history[:-1])  # Be dabartinės reikšmės
        mean = np.mean(arr)
        std = np.std(arr)

        if std > 0 and mean > 0:
            z_score = (current_count - mean) / std

            if z_score > LOG_SPIKE_MULTIPLIER:
                severity = "critical" if z_score > 5 else "high" if z_score > 4 else "medium"
                alerts.append(Alert(
                    timestamp=now.isoformat(),
                    severity=severity,
                    detection_method="statistical",
                    alert_type="log_volume_spike",
                    description=(
                        f"Logų kiekio šuolis aptiktas: {current_count:.0f} logų "
                        f"(vidurkis: {mean:.0f}, z-score: {z_score:.2f})"
                    ),
                    details={
                        "current_count": current_count,
                        "baseline_mean": round(mean, 2),
                        "baseline_std": round(std, 2),
                        "z_score": round(z_score, 2),
                        "multiplier_threshold": LOG_SPIKE_MULTIPLIER,
                    },
                ))

        return alerts

    def check_error_rate(self, window_minutes: int = 5) -> list[Alert]:
        """
        Tikrina ar error logų proporcija neviršija normos.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        all_lines = self.loki.query_range('{job="syslog"}', start=start, end=now)
        error_lines = self.loki.query_range('{job="errors"}', start=start, end=now)

        total = len(all_lines)
        errors = len(error_lines)

        if total > 10:
            error_rate = errors / total
            if error_rate > 0.3:  # >30% klaidų
                alerts.append(Alert(
                    timestamp=now.isoformat(),
                    severity="high",
                    detection_method="statistical",
                    alert_type="high_error_rate",
                    description=(
                        f"Aukštas klaidų lygis: {error_rate:.1%} "
                        f"({errors}/{total} per {window_minutes} min)"
                    ),
                    details={
                        "error_count": errors,
                        "total_count": total,
                        "error_rate": round(error_rate, 4),
                    },
                ))

        return alerts


# ============================================================
# 3. ML APTIKIMAS (Isolation Forest)
# ============================================================

class MLDetector:
    """
    Machine Learning anomalijų aptikimas naudojant Isolation Forest.
    Iš logų išgauna požymius (features) ir aptinka anomalijas.
    """

    def __init__(self, loki: LokiClient, contamination: float = 0.05):
        self.loki = loki
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        self.is_trained = False
        self.training_data: list[list[float]] = []
        self.min_training_samples = 20
        self._load_model()

    def _load_model(self):
        """Įkelia išsaugotą modelį ir treniravimo duomenis iš disko."""
        if os.path.exists(TRAINING_DATA_PATH):
            try:
                self.training_data = joblib.load(TRAINING_DATA_PATH)
                logger.info(f"Įkelti {len(self.training_data)} treniravimo įrašai iš disko")
            except Exception as e:
                logger.warning(f"Treniravimo duomenų įkėlimo klaida: {e}")

        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_trained = True
                logger.info("ML modelis įkeltas iš disko")
            except Exception as e:
                logger.warning(f"Modelio įkėlimo klaida: {e}")

    def _save_model(self):
        """Išsaugo treniruotą modelį ir treniravimo duomenis į diską."""
        try:
            joblib.dump(self.model, MODEL_PATH)
            joblib.dump(self.training_data, TRAINING_DATA_PATH)
        except Exception as e:
            logger.warning(f"Modelio išsaugojimo klaida: {e}")

    def _extract_features(self, lines: list[dict], window_minutes: int) -> dict[str, list[float]]:
        """
        Iš log eilučių išgauna požymių vektorius per host.
        Požymiai:
          - Logų kiekis
          - Unikalių programų skaičius
          - Error proporcija
          - Unikalių IP skaičius
          - Vidutinis žinutės ilgis
        """
        host_features: dict[str, dict] = defaultdict(lambda: {
            "count": 0,
            "programs": set(),
            "errors": 0,
            "ips": set(),
            "msg_lengths": [],
        })

        ip_pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)")

        for entry in lines:
            host = entry["labels"].get("host", "unknown")
            severity = entry["labels"].get("severity", "")
            program = entry["labels"].get("program", "")
            line = entry["line"]

            host_features[host]["count"] += 1
            host_features[host]["programs"].add(program)
            host_features[host]["msg_lengths"].append(len(line))

            if severity in ("err", "crit", "alert", "emerg", "error"):
                host_features[host]["errors"] += 1

            ip_match = ip_pattern.search(line)
            if ip_match:
                host_features[host]["ips"].add(ip_match.group(1))

        result = {}
        for host, feats in host_features.items():
            count = feats["count"]
            if count == 0:
                continue
            result[host] = [
                count,                                           # Logų kiekis
                len(feats["programs"]),                           # Unikalios programos
                feats["errors"] / count if count > 0 else 0,     # Error rate
                len(feats["ips"]),                                # Unikalūs IP
                np.mean(feats["msg_lengths"]) if feats["msg_lengths"] else 0,  # Vid. ilgis
            ]

        return result

    def detect(self, window_minutes: int = 10) -> list[Alert]:
        """
        Vykdo ML anomalijų aptikimą.
        Pirma renka training duomenis, po to klasifikuoja.
        """
        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range('{job="syslog"}', start=start, end=now)

        if not lines:
            return alerts

        host_features = self._extract_features(lines, window_minutes)

        if not host_features:
            return alerts

        # Kaupiame training duomenis (immutable replacement)
        new_data = self.training_data + list(host_features.values())
        self.training_data = new_data[-500:]

        # Treniruojame modelį kai turime pakankamai duomenų
        if len(self.training_data) >= self.min_training_samples:
            try:
                X_train = np.array(self.training_data)
                self.model.fit(X_train)
                self.is_trained = True
                self._save_model()
            except Exception as e:
                logger.warning(f"ML modelio treniravimo klaida: {e}")
                return alerts

        # Klasifikuojame dabartinius duomenis
        if self.is_trained:
            for host, features in host_features.items():
                try:
                    X = np.array([features])
                    prediction = self.model.predict(X)
                    score = self.model.score_samples(X)[0]

                    if prediction[0] == -1:  # Anomalija
                        severity = "high" if score < -0.7 else "medium"
                        alerts.append(Alert(
                            timestamp=now.isoformat(),
                            severity=severity,
                            detection_method="ml",
                            alert_type="ml_anomaly",
                            description=(
                                f"ML anomalija aptikta host '{host}': "
                                f"score={score:.3f}"
                            ),
                            source_host=host,
                            details={
                                "anomaly_score": round(score, 4),
                                "features": {
                                    "log_count": features[0],
                                    "unique_programs": features[1],
                                    "error_rate": round(features[2], 4),
                                    "unique_ips": features[3],
                                    "avg_msg_length": round(features[4], 2),
                                },
                                "training_samples": len(self.training_data),
                            },
                        ))
                except Exception as e:
                    logger.warning(f"ML klasifikavimo klaida '{host}': {e}")

        else:
            logger.info(
                f"ML modelis renka duomenis: "
                f"{len(self.training_data)}/{self.min_training_samples}"
            )

        return alerts


# ============================================================
# Alertų siuntimas
# ============================================================

class AlertSender:
    """Siunčia alertus per webhook (Telegram, Slack, etc.)."""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    def send(self, alert: Alert):
        """Logina ir siunčia alertą."""
        # Visada loginame
        icon = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}
        level = icon.get(alert.severity, "❓")
        logger.warning(
            f"{level} [{alert.severity.upper()}] {alert.alert_type}: "
            f"{alert.description}"
        )

        # Siunčiame per webhook jei sukonfigūruotas
        if self.webhook_url:
            try:
                payload = {
                    "text": (
                        f"{level} *{alert.severity.upper()}* — "
                        f"{alert.alert_type}\n{alert.description}"
                    ),
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=10)
                if not resp.ok:
                    logger.error(f"Webhook atsakė klaida: {resp.status_code}")
            except requests.RequestException as e:
                logger.error(f"Webhook siuntimo klaida: {e}")

    def save_history(self, alerts: list[Alert]):
        """Saugo alertų istoriją į failą."""
        history = []
        try:
            if os.path.exists(ANOMALY_DB_PATH):
                with open(ANOMALY_DB_PATH, "r") as f:
                    history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

        for alert in alerts:
            history.append(alert.to_dict())

        # Saugome tik paskutinius 1000 alertų
        history = history[-1000:]

        try:
            os.makedirs(os.path.dirname(ANOMALY_DB_PATH), exist_ok=True)
            with open(ANOMALY_DB_PATH, "w") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Istorijos rašymo klaida: {e}")


# ============================================================
# Pagrindinis ciklas
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("Anomalijų aptikimo sistema paleista")
    logger.info(f"Loki URL: {LOKI_URL}")
    logger.info(f"Tikrinimo intervalas: {CHECK_INTERVAL}s")
    logger.info(f"SSH brute-force slenkstis: {SSH_BRUTE_THRESHOLD}")
    logger.info(f"Log spike daugiklis: {LOG_SPIKE_MULTIPLIER}")
    logger.info("=" * 60)

    loki = LokiClient(LOKI_URL)

    # Laukiame kol Loki bus pasiruošęs (max 5 min)
    logger.info("Laukiama kol Loki bus pasiruošęs...")
    max_wait = 300
    waited = 0
    while not loki.is_ready():
        if waited >= max_wait:
            logger.error(f"Loki nepasiekiamas po {max_wait}s. Stabdoma.")
            sys.exit(1)
        time.sleep(5)
        waited += 5
    logger.info("Loki pasiruošęs!")

    # Inicializuojame detektorius
    rule_detector = RuleBasedDetector(loki)
    stat_detector = StatisticalDetector(loki)
    ml_detector = MLDetector(loki)
    alert_sender = AlertSender(ALERT_WEBHOOK_URL)

    # Alertų cooldown žodynas — slopina pasikartojančius alertus
    alert_cooldown: dict[str, float] = {}

    # Graceful shutdown tvarkyklė
    shutdown_requested = False

    def _handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("SIGTERM/SIGINT gautas, stabdoma...")

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    iteration = 0

    while not shutdown_requested:
        iteration += 1
        logger.info(f"--- Tikrinimo ciklas #{iteration} ---")

        # Heartbeat failas healthcheck'ui
        try:
            open("/tmp/detector.alive", "w").close()
        except OSError:
            pass

        all_alerts: list[Alert] = []

        try:
            # 1. Taisyklėmis pagrįstas tikrinimas
            all_alerts.extend(rule_detector.check_ssh_bruteforce())
            all_alerts.extend(rule_detector.check_unauthorized_access())
            all_alerts.extend(rule_detector.check_firewall_events())

            # 2. Statistinis tikrinimas
            all_alerts.extend(stat_detector.check_log_volume_spike())
            all_alerts.extend(stat_detector.check_error_rate())

            # 3. ML tikrinimas (kas 5-ą iteraciją - resursų taupymas)
            if iteration % 5 == 0:
                all_alerts.extend(ml_detector.detect())

        except Exception as e:
            logger.error(f"Tikrinimo klaida: {e}", exc_info=True)

        # Filtruojame pasikartojančius alertus (cooldown)
        if all_alerts:
            now_ts = time.time()
            new_alerts = []
            suppressed = 0
            for alert in all_alerts:
                key = f"{alert.alert_type}:{alert.source_ip}:{alert.source_host}"
                if now_ts - alert_cooldown.get(key, 0.0) >= ALERT_COOLDOWN_SECONDS:
                    alert_cooldown[key] = now_ts
                    new_alerts.append(alert)
                else:
                    suppressed += 1
            if suppressed:
                logger.info(f"{suppressed} alertų praleista (cooldown {ALERT_COOLDOWN_SECONDS}s)")
            if new_alerts:
                logger.info(f"Siunčiama {len(new_alerts)} naujų alertų")
                for alert in new_alerts:
                    alert_sender.send(alert)
                alert_sender.save_history(new_alerts)
        else:
            logger.info("Anomalijų neaptikta.")

        # Interruptible sleep — leidžia greitai reaguoti į SIGTERM
        for _ in range(CHECK_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Anomalijų aptikimo sistema sustabdyta.")


if __name__ == "__main__":
    main()
