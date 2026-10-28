"""
Statistinio detektoriaus testai.
"""
from __future__ import annotations

import datetime

import detector
from detector import LokiClient, StatisticalDetector

T0 = datetime.datetime(2022, 1, 24, 0, 0, tzinfo=datetime.timezone.utc)


class FakeLokiClient(LokiClient):
    """Grąžina iš anksto paruoštus kiekius pagal srautą (syslog / errors)."""

    def __init__(self, counts: dict[str, float] | None = None, default: float = 0.0):
        super().__init__("http://fake")
        self.counts = counts or {}
        self.default = default

    def instant_query(self, query, at=None):
        for selector, value in self.counts.items():
            if selector in query:
                return [{"labels": {}, "value": value}]
        return [{"labels": {}, "value": self.default}]

    def query_range(self, query, start=None, end=None, limit=5000):
        return [{"timestamp": "0", "line": "test", "labels": {}}] * min(limit, 3)


def _seed(det: StatisticalDetector, values: list[float], start: datetime.datetime = T0,
          step_minutes: int = 10):
    for i, value in enumerate(values):
        det._update_baseline(start + datetime.timedelta(minutes=i * step_minutes), value)


# ---------------------------------------------------------------------------
# Log volume spike
# ---------------------------------------------------------------------------

def test_volume_spike_silent_during_warmup():
    """Pirmi 5 ciklai turi tik kaupti baseline, ne alertinti."""
    det = StatisticalDetector(FakeLokiClient(default=10))
    for i in range(5):
        assert det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=i)) == []
    assert len(det.baseline_history) == 5


def test_volume_spike_silent_until_baseline_spans_an_hour():
    """Kelių minučių istorija (daug įrašų, mažas std) dar nevertinama — net ir esant šuoliui."""
    det = StatisticalDetector(FakeLokiClient(default=1000))
    _seed(det, [8.0, 10.0, 12.0, 9.0, 11.0, 10.0, 9.0, 11.0] * 5, step_minutes=1)  # 39 min
    assert det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=40)) == []


def test_volume_spike_no_alert_on_stable_traffic():
    """Stabilus srautas → jokio z-score viršyto slenksčio."""
    det = StatisticalDetector(FakeLokiClient(default=10))
    alerts: list = []
    for i in range(20):
        alerts.extend(det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=i)))
    assert alerts == []


def test_volume_spike_triggers_on_huge_jump(monkeypatch):
    """Po normalios baseline'os, didelis šuolis turi triggerinti alertą."""
    monkeypatch.setattr(detector, "LOG_SPIKE_MULTIPLIER", 3.0)

    det = StatisticalDetector(FakeLokiClient(default=1000))
    # Įvairi baseline (kitaip std=0 ir z-score neapibrėžtas), 70 min istorijos
    _seed(det, [8.0, 10.0, 12.0, 9.0, 11.0, 10.0, 9.0, 11.0])

    alerts = det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=80))

    assert len(alerts) == 1
    assert alerts[0].alert_type == "log_volume_spike"
    assert alerts[0].details["z_score"] > 3.0
    assert alerts[0].details["current_count"] == 1000


def test_volume_spike_no_alert_when_std_is_zero():
    """Jei visi baseline įrašai identiški (std=0), netriggeriname (apsauga nuo dalybos iš 0)."""
    det = StatisticalDetector(FakeLokiClient(default=1000))
    _seed(det, [10.0] * 10)
    assert det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=100)) == []


def test_volume_spike_history_bounded_by_time():
    """baseline_history laikomas tik BASELINE_WINDOW_HOURS laiko langu."""
    det = StatisticalDetector(FakeLokiClient(default=1))
    det.baseline_window_hours = 1
    for i in range(180):  # 3 val. kas minutę
        det.check_log_volume_spike(now=T0 + datetime.timedelta(minutes=i))
    oldest, newest = det.baseline_history[0][0], det.baseline_history[-1][0]
    assert newest - oldest <= 3600
    assert len(det.baseline_history) == 61


def test_volume_count_comes_from_metric_query():
    """Kiekis neapribotas 5000 eilučių — imamas iš count_over_time."""
    det = StatisticalDetector(FakeLokiClient(default=12000))
    det.check_log_volume_spike(now=T0)
    assert det.baseline_history[-1][1] == 12000


# ---------------------------------------------------------------------------
# Error rate
# ---------------------------------------------------------------------------

def test_error_rate_triggers_above_30_percent():
    """>30% klaidų santykis turi triggerinti alertą."""
    loki = FakeLokiClient({'{job="syslog"}': 100, '{job="errors"}': 40})
    alerts = StatisticalDetector(loki).check_error_rate()
    assert len(alerts) == 1
    assert alerts[0].alert_type == "high_error_rate"
    assert alerts[0].details["error_rate"] == 0.4


def test_error_rate_silent_on_low_volume():
    """Mažas bendras kiekis (<=10) — netinka statistikai."""
    loki = FakeLokiClient({'{job="syslog"}': 5, '{job="errors"}': 5})
    assert StatisticalDetector(loki).check_error_rate() == []


def test_error_rate_silent_on_normal_ratio():
    loki = FakeLokiClient({'{job="syslog"}': 100, '{job="errors"}': 10})
    assert StatisticalDetector(loki).check_error_rate() == []
