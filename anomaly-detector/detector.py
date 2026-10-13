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

Visi tikrinimai priima `now` — gyvame režime tai sieninis laikrodis, vertinimo
režime (evaluation paketas) virtualus laikrodis per istorinį duomenų rinkinį.

Autorius: Paulius Turauskas
Kursinis darbas: Centralizuota žurnalų analizės ir anomalijų
                 aptikimo sistema mažoms organizacijoms
"""

import datetime
import json
import os
import re
import signal
import sys
import time
from collections import Counter, defaultdict, deque
from typing import Optional

import joblib
import numpy as np
import requests
from sklearn.ensemble import IsolationForest

from common import (  # noqa: F401  (re-eksportuojama testams ir evaluation paketui)
    ALERT_COOLDOWN_SECONDS,
    ALERT_WEBHOOK_URL,
    ANOMALY_DB_PATH,
    BASELINE_WINDOW_HOURS,
    CHECK_INTERVAL,
    DATA_DIR,
    ENABLE_ML,
    ENABLE_LINUX_RULES,
    ENABLE_WINDOWS_RULES,
    LOG_SPIKE_MULTIPLIER,
    LOKI_URL,
    ML_EVERY_N_CYCLES,
    ML_MAX_TRAINING_SAMPLES,
    ML_TRAINING_MODE,
    SAMPLE_LINE_LIMIT,
    SSH_BRUTE_THRESHOLD,
    Alert,
    LokiClient,
    Selectors,
    logger,
    utcnow,
)
import attack_catalog
from windows_rules import WindowsRuleDetector
from linux_rules import LinuxEndpointRuleDetector

_ERROR_MATCHER = 'severity=~"err|crit|alert|emerg|error"'
# Pirmas IPv4 eilutėje (kaip re.search); eilutės be IP neskaičiuojamos.
_IP_EXTRACT = r'| regexp `(?P<ip>\d+\.\d+\.\d+\.\d+)` | ip != ""'


# ============================================================
# 1. TAISYKLĖMIS PAGRĮSTAS APTIKIMAS (Rule-based)
# ============================================================

class RuleBasedDetector:
    """
    Statinių taisyklių variklis anomalijoms aptikti.
    Tikrina žinomus pavojingus pattern'us.
    """

    def __init__(self, loki: LokiClient, selectors: Optional[Selectors] = None):
        self.loki = loki
        self.sel = selectors or Selectors()

    def check_ssh_bruteforce(
        self, window_minutes: int = 5, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Aptinka SSH brute-force atakas.
        Kriterijai: >N nesėkmingų prisijungimų per laiko langą iš to paties IP.
        """
        alerts = []
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)

        lines = self.loki.query_range(
            f'{self.sel.syslog} |= "Failed password"',
            start=start,
            end=now,
        )

        # Skaičiuojame nesėkmes pagal IP
        ip_pattern = re.compile(r"from\s+(\d+\.\d+\.\d+\.\d+)")
        ip_counts: Counter = Counter()
        ip_hosts: dict[str, set] = defaultdict(set)
        ip_lines: dict[str, list[str]] = defaultdict(list)

        for entry in lines:
            match = ip_pattern.search(entry["line"])
            if match:
                ip = match.group(1)
                ip_counts[ip] += 1
                host = entry["labels"].get("host", "unknown")
                ip_hosts[ip].add(host)
                if len(ip_lines[ip]) < SAMPLE_LINE_LIMIT:
                    ip_lines[ip].append(entry["line"])

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
                    sample_lines=ip_lines[ip],
                ))

        return alerts

    def check_unauthorized_access(
        self, window_minutes: int = 5, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Aptinka bandymus prisijungti su neegzistuojančiais vartotojais.
        """
        alerts = []
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)

        # OpenSSH rašo abi formas: „Invalid user X from IP" ir
        # „Failed password for invalid user X from IP" — todėl raidžių dydis ignoruojamas.
        lines = self.loki.query_range(
            f'{self.sel.syslog} |~ "(?i)invalid user"',
            start=start,
            end=now,
        )

        user_pattern = re.compile(r"(?i)invalid user\s+(\S+)\s+from\s+(\d+\.\d+\.\d+\.\d+)")
        # Atskiriame unikalius vardus (skenavimas) nuo pakartotinių (brute-force vienam vartotojui)
        users_by_ip: dict[str, set[str]] = defaultdict(set)
        attempts_by_ip: Counter = Counter()
        lines_by_ip: dict[str, list[str]] = defaultdict(list)

        for entry in lines:
            match = user_pattern.search(entry["line"])
            if match:
                user, ip = match.group(1), match.group(2)
                users_by_ip[ip].add(user)
                attempts_by_ip[ip] += 1
                if len(lines_by_ip[ip]) < SAMPLE_LINE_LIMIT:
                    lines_by_ip[ip].append(entry["line"])

        for ip, users in users_by_ip.items():
            unique_user_count = len(users)
            if unique_user_count >= 3:
                alerts.append(Alert(
                    timestamp=now.isoformat(),
                    severity="high",
                    detection_method="rule",
                    alert_type="invalid_user_scan",
                    description=(
                        f"Vartotojų skenavimas aptiktas: {unique_user_count} skirtingi "
                        f"vartotojų vardai iš IP {ip}"
                    ),
                    source_ip=ip,
                    details={
                        "usernames_tried": sorted(users),
                        "unique_username_count": unique_user_count,
                        "attempt_count": attempts_by_ip[ip],
                    },
                    sample_lines=lines_by_ip[ip],
                ))

        return alerts

    def check_firewall_events(
        self, window_minutes: int = 5, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Aptinka neįprastai didelį blokuojamų paketų kiekį.
        """
        alerts = []
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)
        selector = f'{self.sel.syslog} |~ "DROP|REJECT|blocked"'

        # Kiekis skaičiuojamas Loki pusėje — eilučių atsisiuntimas būtų apribotas 5000.
        blocked = int(self.loki.count(
            f"sum(count_over_time({selector} [{window_minutes}m]))", at=now))

        if blocked > 50:
            samples = self.loki.query_range(selector, start=start, end=now, limit=SAMPLE_LINE_LIMIT)
            alerts.append(Alert(
                timestamp=now.isoformat(),
                severity="medium",
                detection_method="rule",
                alert_type="firewall_spike",
                description=(
                    f"Neįprastai daug ugniasienės blokavimų: "
                    f"{blocked} per {window_minutes} min"
                ),
                details={"blocked_count": blocked},
                sample_lines=[e["line"] for e in samples[:SAMPLE_LINE_LIMIT]],
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

    def __init__(self, loki: LokiClient, selectors: Optional[Selectors] = None, job: str = "syslog"):
        self.loki = loki
        self.sel = selectors or Selectors()
        # Srauto šeima (syslog / windows) — RQ3 atskiriems baseline'ams.
        self.job = job
        # (laiko žyma, reikšmė) — baseline'as apribojamas laiku, ne ciklų skaičiumi
        self.baseline_history: deque[tuple[float, float]] = deque()
        self.baseline_window_hours = BASELINE_WINDOW_HOURS

    def _update_baseline(self, now: datetime.datetime, current_value: float):
        """Atnaujina baseline istoriją ir išmeta senesnius nei langas įrašus."""
        self.baseline_history.append((now.timestamp(), current_value))
        cutoff = now.timestamp() - self.baseline_window_hours * 3600
        while self.baseline_history and self.baseline_history[0][0] < cutoff:
            self.baseline_history.popleft()

    def _count(self, selector: str, window_minutes: int, now: datetime.datetime) -> float:
        return self.loki.count(f"sum(count_over_time({selector}[{window_minutes}m]))", at=now)

    def check_log_volume_spike(
        self, window_minutes: int = 5, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Aptinka staigų logų kiekio šuolį (spike).
        Lygina dabartinį kiekį su istoriniu vidurkiu.
        """
        alerts = []
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)
        stream = self.sel.stream(self.job)

        # Kiekis skaičiuojamas Loki pusėje — eilučių atsisiuntimas būtų apribotas 5000.
        current_count = self._count(stream, window_minutes, now)

        # Reikia bent 5 istorinių įrašų PRIEŠ dabartinį tikrinimą — kitaip
        # standartinis nuokrypis neturi prasmės. Baseline atnaujiname po
        # tikrinimo, kad gate'as būtų tikslus.
        if len(self.baseline_history) < 5:
            logger.info(
                f"Renkamas baseline: {len(self.baseline_history)}/5 "
                f"(dabartinis: {current_count:.0f})"
            )
            self._update_baseline(now, current_count)
            return alerts

        arr = np.array([value for _, value in self.baseline_history])
        mean = np.mean(arr)
        std = np.std(arr)

        if std > 0 and mean > 0:
            z_score = (current_count - mean) / std

            if z_score > LOG_SPIKE_MULTIPLIER:
                severity = "critical" if z_score > 5 else "high" if z_score > 4 else "medium"
                samples = self.loki.query_range(
                    stream, start=start, end=now, limit=SAMPLE_LINE_LIMIT)
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
                        "baseline_window_hours": self.baseline_window_hours,
                    },
                    sample_lines=[e["line"] for e in samples[:SAMPLE_LINE_LIMIT]],
                ))

        # Baseline atnaujiname po tikrinimo — current_count netraukiamas į savo paties matavimą.
        self._update_baseline(now, current_count)
        return alerts

    def check_error_rate(
        self, window_minutes: int = 5, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Tikrina ar error logų proporcija neviršija normos.
        """
        alerts = []
        now = now or utcnow()
        start = now - datetime.timedelta(minutes=window_minutes)

        total = int(self._count(self.sel.syslog, window_minutes, now))
        errors = int(self._count(self.sel.errors, window_minutes, now))

        if total > 10:
            error_rate = errors / total
            if error_rate > 0.3:  # >30% klaidų
                error_lines = self.loki.query_range(
                    self.sel.errors, start=start, end=now, limit=SAMPLE_LINE_LIMIT)
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
                    sample_lines=[e["line"] for e in error_lines[:SAMPLE_LINE_LIMIT]],
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

    def __init__(
        self,
        loki: LokiClient,
        contamination: float = 0.05,
        selectors: Optional[Selectors] = None,
        state_dir: Optional[str] = DATA_DIR,
        job: str = "syslog",
    ):
        self.loki = loki
        self.sel = selectors or Selectors()
        self.job = job   # srauto šeima (syslog / windows) — RQ3 variantams
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        self.is_trained = False
        # deque(maxlen=...) automatiškai išmeta seniausius įrašus — nereikia kopijuoti sąrašo.
        self.training_data: deque[list[float]] = deque(maxlen=ML_MAX_TRAINING_SAMPLES)
        self.min_training_samples = 20
        self.training_mode = ML_TRAINING_MODE
        self.frozen = False
        # state_dir=None — modelis nesaugomas diske (vertinimo režimas, kad neperrašytų gyvo modelio).
        self.model_path = os.path.join(state_dir, "model.pkl") if state_dir else None
        self.training_data_path = os.path.join(state_dir, "training_data.pkl") if state_dir else None
        self._load_model()

    def _load_model(self):
        """Įkelia išsaugotą modelį ir treniravimo duomenis iš disko."""
        if self.training_data_path and os.path.exists(self.training_data_path):
            try:
                loaded = joblib.load(self.training_data_path)
                # Diske saugomas list — atkuriame į deque su tuo pačiu maxlen.
                self.training_data = deque(loaded, maxlen=self.training_data.maxlen)
                logger.info(f"Įkelti {len(self.training_data)} treniravimo įrašai iš disko")
            except Exception as e:
                logger.warning(f"Treniravimo duomenų įkėlimo klaida: {e}")

        if self.model_path and os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info("ML modelis įkeltas iš disko")
            except Exception as e:
                logger.warning(f"Modelio įkėlimo klaida: {e}")

        self.frozen = (self.training_mode == "frozen" and self.is_trained
                       and len(self.training_data) >= self.training_data.maxlen)

    def _save_model(self):
        """Išsaugo treniruotą modelį ir treniravimo duomenis į diską."""
        if not (self.model_path and self.training_data_path):
            return
        try:
            joblib.dump(self.model, self.model_path)
            # joblib gali serializuoti ir deque, bet list — portatyvesnis tarp versijų.
            joblib.dump(list(self.training_data), self.training_data_path)
        except Exception as e:
            logger.warning(f"Modelio išsaugojimo klaida: {e}")

    def _metric_features(
        self, now: datetime.datetime, window_minutes: int
    ) -> dict[str, list[float]]:
        """
        Požymių vektoriai per host, apskaičiuoti Loki metrikos užklausomis
        (nėra 5000 eilučių ribos, kurią turi eilučių atsisiuntimas):
          - Logų kiekis              count_over_time
          - Unikalių programų skaičius skirtingos `program` etiketės reikšmės
          - Error proporcija         severity err..emerg
          - Unikalių IP skaičius     pirmas IPv4 eilutėje
          - Vidutinis eilutės ilgis  bytes_over_time / kiekis
        """
        w = f"[{window_minutes}m]"
        sel = self.sel.stream(self.job)
        counts = self.loki.by_label(f"sum by (host) (count_over_time({sel}{w}))", "host", now)
        if not counts:
            return {}
        errors = self.loki.by_label(
            f"sum by (host) (count_over_time({self.sel.stream(self.job, _ERROR_MATCHER)}{w}))",
            "host", now)
        programs = self.loki.by_label(
            f"count by (host) (sum by (host, program) (count_over_time({sel}{w})))", "host", now)
        ips = self.loki.by_label(
            f"count by (host) (sum by (host, ip) (count_over_time({sel} {_IP_EXTRACT} {w})))",
            "host", now)
        size = self.loki.by_label(f"sum by (host) (bytes_over_time({sel}{w}))", "host", now)

        return {
            host: [
                count,                              # Logų kiekis
                programs.get(host, 0.0),            # Unikalios programos
                errors.get(host, 0.0) / count,      # Error rate
                ips.get(host, 0.0),                 # Unikalūs IP
                size.get(host, 0.0) / count,        # Vid. eilutės ilgis
            ]
            for host, count in counts.items() if count > 0
        }

    def _train(self, host_features: dict[str, list[float]]) -> bool:
        """
        online — kaupia pavyzdžius ir permoko kiekvieną kartą;
        frozen — apmoko vieną kartą, kai buferis pilnas, ir daugiau nebekeičia.
        Grąžina False, jei treniravimas nepavyko.
        """
        if self.frozen:
            return True
        # Kaupiame training duomenis — deque automatiškai apriboja iki maxlen.
        self.training_data.extend(host_features.values())
        needed = (self.training_data.maxlen if self.training_mode == "frozen"
                  else self.min_training_samples)
        if len(self.training_data) < needed:
            return True
        try:
            self.model.fit(np.array(list(self.training_data)))
            self.is_trained = True
            self._save_model()
        except Exception as e:
            logger.warning(f"ML modelio treniravimo klaida: {e}")
            return False
        if self.training_mode == "frozen":
            self.frozen = True
            logger.info(f"ML modelis užfiksuotas ({len(self.training_data)} pavyzdžių)")
        return True

    def detect(
        self, window_minutes: int = 10, now: Optional[datetime.datetime] = None
    ) -> list[Alert]:
        """
        Vykdo ML anomalijų aptikimą.
        Pirma renka training duomenis, po to klasifikuoja.
        """
        alerts = []
        now = now or utcnow()

        host_features = self._metric_features(now, window_minutes)

        if not host_features:
            return alerts

        if not self._train(host_features):
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
# Aptikimo ciklas (bendras gyvam režimui ir vertinimui)
# ============================================================

class Engine:
    """
    Vienas aptikimo ciklas: visi detektoriai + alertų cooldown pagal `now`.
    Gyvame režime `now` yra sieninis laikrodis, vertinimo režime — virtualus,
    todėl abu režimai naudoja identišką logiką.
    """

    def __init__(
        self,
        loki: LokiClient,
        selectors: Optional[Selectors] = None,
        enable_ml: bool = ENABLE_ML,
        ml_every_n_cycles: int = ML_EVERY_N_CYCLES,
        ml_state_dir: Optional[str] = DATA_DIR,
        cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
        enable_windows: bool = ENABLE_WINDOWS_RULES,
        enable_linux: bool = ENABLE_LINUX_RULES,
    ):
        self.rule_detector = RuleBasedDetector(loki, selectors)
        self.stat_detector = StatisticalDetector(loki, selectors)
        # Windows endpoint taisyklės (job="windows"). Jei endpoint'ų nėra, srautas tuščias.
        self.windows_detector = WindowsRuleDetector(loki, selectors) if enable_windows else None
        # Linux endpoint taisyklės (job="linux_endpoint", auditd). Jei endpoint'ų nėra, srautas tuščias.
        self.linux_detector = LinuxEndpointRuleDetector(loki, selectors) if enable_linux else None
        # ML sluoksnis gyvame cikle numatytai išjungtas (ENABLE_ML=false) — jis per dažnai
        # keldavo bendrinius „neįprasto elgesio" alertus (per daug klaidingų teigiamų).
        # Vertinimo režime įjungiamas, kad tai būtų išmatuota.
        self.ml_detector = (
            MLDetector(loki, selectors=selectors, state_dir=ml_state_dir) if enable_ml else None
        )
        self.ml_every_n_cycles = max(1, ml_every_n_cycles)
        self.cooldown_seconds = cooldown_seconds
        self.iteration = 0
        # Alertų cooldown žodynas — slopina pasikartojančius alertus
        self._cooldown: dict[str, float] = {}

    def detect(self, now: datetime.datetime) -> list[Alert]:
        """Paleidžia visus detektorius vienam laiko momentui (be cooldown)."""
        alerts: list[Alert] = []
        try:
            # 1. Taisyklėmis pagrįstas tikrinimas
            alerts.extend(self.rule_detector.check_ssh_bruteforce(now=now))
            alerts.extend(self.rule_detector.check_unauthorized_access(now=now))
            alerts.extend(self.rule_detector.check_firewall_events(now=now))

            # 2. Endpoint taisyklės (job="windows" / "linux_endpoint")
            if self.windows_detector is not None:
                alerts.extend(self.windows_detector.check(now=now))
            if self.linux_detector is not None:
                alerts.extend(self.linux_detector.check(now=now))

            # 3. Statistinis tikrinimas
            alerts.extend(self.stat_detector.check_log_volume_spike(now=now))
            alerts.extend(self.stat_detector.check_error_rate(now=now))

            # 4. ML sluoksnis (IsolationForest) — kas N-tą ciklą, jei įjungtas
            if self.ml_detector is not None and self.iteration % self.ml_every_n_cycles == 0:
                alerts.extend(self.ml_detector.detect(now=now))

        except Exception as e:
            logger.error(f"Tikrinimo klaida: {e}", exc_info=True)

        # Užpildome ATT&CK technikas iš katalogo (jei taisyklė jų dar nepriskyrė)
        for alert in alerts:
            if not alert.attack_techniques:
                alert.attack_techniques = attack_catalog.techniques_for(alert.alert_type)
        return alerts

    def apply_cooldown(
        self, alerts: list[Alert], now: datetime.datetime
    ) -> tuple[list[Alert], int]:
        """Filtruoja pasikartojančius alertus. Grąžina (nauji alertai, praleistų skaičius)."""
        now_ts = now.timestamp()
        new_alerts = []
        suppressed = 0
        for alert in alerts:
            key = f"{alert.alert_type}:{alert.source_ip}:{alert.source_host}"
            if now_ts - self._cooldown.get(key, 0.0) >= self.cooldown_seconds:
                self._cooldown[key] = now_ts
                new_alerts.append(alert)
            else:
                suppressed += 1
        return new_alerts, suppressed

    def run_cycle(self, now: datetime.datetime) -> tuple[list[Alert], list[Alert]]:
        """Grąžina (visi aptikti alertai, alertai po cooldown filtro)."""
        self.iteration += 1
        raw_alerts = self.detect(now)
        new_alerts, suppressed = self.apply_cooldown(raw_alerts, now)
        if suppressed:
            logger.info(f"{suppressed} alertų praleista (cooldown {self.cooldown_seconds}s)")
        return raw_alerts, new_alerts


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
        """
        Saugo alertų istoriją į failą atominiu rašymu (temp + os.replace),
        kad SIGKILL ar disko trūkumo metu failas nebūtų sugadintas.
        """
        history: list[dict] = []
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
            db_dir = os.path.dirname(ANOMALY_DB_PATH)
            os.makedirs(db_dir, exist_ok=True)
            tmp_path = f"{ANOMALY_DB_PATH}.tmp"
            with open(tmp_path, "w") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, ANOMALY_DB_PATH)
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
    logger.info(f"ML sluoksnis: {'įjungtas' if ENABLE_ML else 'išjungtas'}")
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

    engine = Engine(loki)
    alert_sender = AlertSender(ALERT_WEBHOOK_URL)

    # ATT&CK katalogą įrašome į /data, kad dashboard galėtų parodyti aprėptį.
    try:
        with open(os.path.join(DATA_DIR, "attack_catalog.json"), "w") as f:
            json.dump({"catalog": attack_catalog.CATALOG, "techniques": attack_catalog.TECHNIQUES,
                       "lab_technique_set": attack_catalog.LAB_TECHNIQUE_SET}, f, ensure_ascii=False)
    except OSError as e:
        logger.warning(f"Nepavyko įrašyti attack_catalog.json: {e}")

    # Graceful shutdown tvarkyklė
    shutdown_requested = False

    def _handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("SIGTERM/SIGINT gautas, stabdoma...")

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while not shutdown_requested:
        logger.info(f"--- Tikrinimo ciklas #{engine.iteration + 1} ---")

        # Heartbeat failas healthcheck'ui
        try:
            with open("/tmp/detector.alive", "w"):
                pass
        except OSError:
            pass

        all_alerts, new_alerts = engine.run_cycle(utcnow())

        if all_alerts:
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
