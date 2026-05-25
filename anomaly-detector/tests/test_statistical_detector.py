"""
Statistinio detektoriaus testai.
"""
from __future__ import annotations

import detector
from detector import StatisticalDetector


class FakeLokiClient:
    """Grąžina iš anksto paruoštą atsakymą kiekvienai užklausai."""

    def __init__(self, lines_by_query: dict[str, list[dict]] | None = None,
                 default_lines: list[dict] | None = None):
        self._by_query = lines_by_query or {}
        self._default = default_lines or []

    def query_range(self, query: str, start=None, end=None, limit: int = 5000) -> list[dict]:
        return self._by_query.get(query, self._default)


def _entry() -> dict:
    return {"timestamp": "0", "line": "test", "labels": {}}


# ---------------------------------------------------------------------------
# Log volume spike
# ---------------------------------------------------------------------------

def test_volume_spike_silent_during_warmup():
    """Pirmi 5 ciklai turi tik kaupti baseline, ne alertinti."""
    det = StatisticalDetector(FakeLokiClient(default_lines=[_entry()] * 10))
    for _ in range(5):
        assert det.check_log_volume_spike() == []
    # Po 5 ciklų baseline užpildyta; 6-as gali tikrinti, bet std=0 todėl tylu.
    assert len(det.baseline_history) == 5


def test_volume_spike_no_alert_on_stable_traffic():
    """Stabilus srautas → jokio z-score viršyto slenksčio."""
    det = StatisticalDetector(FakeLokiClient(default_lines=[_entry()] * 10))
    alerts: list = []
    for _ in range(20):
        alerts.extend(det.check_log_volume_spike())
    assert alerts == []


def test_volume_spike_triggers_on_huge_jump(monkeypatch):
    """Po normalios baseline'os, didelis šuolis turi triggerinti alertą."""
    monkeypatch.setattr(detector, "LOG_SPIKE_MULTIPLIER", 3.0)

    det = StatisticalDetector(FakeLokiClient(default_lines=[]))
    # Įvairi baseline (kitaip std=0 ir z-score neapibrėžtas)
    det.baseline_history = [8.0, 10.0, 12.0, 9.0, 11.0, 10.0, 9.0, 11.0]

    # Simuliuojame šuolį
    det.loki = FakeLokiClient(default_lines=[_entry()] * 1000)
    alerts = det.check_log_volume_spike()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "log_volume_spike"
    assert alerts[0].details["z_score"] > 3.0


def test_volume_spike_no_alert_when_std_is_zero():
    """Jei visi baseline įrašai identiški (std=0), netriggeriname (apsauga nuo dalybos iš 0)."""
    det = StatisticalDetector(FakeLokiClient(default_lines=[_entry()] * 1000))
    det.baseline_history = [10.0] * 10
    assert det.check_log_volume_spike() == []


def test_volume_spike_history_bounded():
    """baseline_history negali augti be ribos."""
    det = StatisticalDetector(FakeLokiClient(default_lines=[_entry()]))
    det.max_history = 5
    for _ in range(20):
        det.check_log_volume_spike()
    assert len(det.baseline_history) <= 5


# ---------------------------------------------------------------------------
# Error rate
# ---------------------------------------------------------------------------

def test_error_rate_triggers_above_30_percent():
    """>30% klaidų santykis turi triggerinti alertą."""
    loki = FakeLokiClient({
        '{job="syslog"}': [_entry()] * 100,
        '{job="errors"}': [_entry()] * 40,
    })
    alerts = StatisticalDetector(loki).check_error_rate()
    assert len(alerts) == 1
    assert alerts[0].alert_type == "high_error_rate"
    assert alerts[0].details["error_rate"] == 0.4


def test_error_rate_silent_on_low_volume():
    """Mažas bendras kiekis (<=10) — netinka statistikai."""
    loki = FakeLokiClient({
        '{job="syslog"}': [_entry()] * 5,
        '{job="errors"}': [_entry()] * 5,
    })
    assert StatisticalDetector(loki).check_error_rate() == []


def test_error_rate_silent_on_normal_ratio():
    loki = FakeLokiClient({
        '{job="syslog"}': [_entry()] * 100,
        '{job="errors"}': [_entry()] * 10,
    })
    assert StatisticalDetector(loki).check_error_rate() == []
