"""
ML detektoriaus požymių išgavimo testai.
Tikrų IsolationForest treniravimo testų vengiame — nestabilūs ir lėti.
"""
from __future__ import annotations

from detector import MLDetector


class FakeLokiClient:
    def __init__(self, lines: list[dict]):
        self._lines = lines

    def query_range(self, query: str, start=None, end=None, limit: int = 5000) -> list[dict]:
        return self._lines


def _entry(line: str, host: str = "srv-1", severity: str = "info",
           program: str = "sshd") -> dict:
    return {
        "timestamp": "0",
        "line": line,
        "labels": {"host": host, "severity": severity, "program": program},
    }


def test_feature_vector_shape():
    """Kiekvienam host'ui turi būti grąžinti 5 požymiai."""
    lines = [
        _entry("hello from 1.2.3.4"),
        _entry("hello from 5.6.7.8"),
    ]
    feats = MLDetector(FakeLokiClient(lines))._extract_features(lines, window_minutes=5)

    assert "srv-1" in feats
    assert len(feats["srv-1"]) == 5


def test_feature_error_rate():
    lines = [
        _entry("ok", severity="info"),
        _entry("ok", severity="info"),
        _entry("oops", severity="err"),
        _entry("oops", severity="crit"),
    ]
    feats = MLDetector(FakeLokiClient(lines))._extract_features(lines, window_minutes=5)
    # error_rate yra trečias požymis (index 2)
    assert feats["srv-1"][2] == 0.5


def test_feature_unique_ip_count():
    lines = [
        _entry("from 1.1.1.1"),
        _entry("from 1.1.1.1"),
        _entry("from 2.2.2.2"),
        _entry("no ip here"),
    ]
    feats = MLDetector(FakeLokiClient(lines))._extract_features(lines, window_minutes=5)
    # unique_ips yra ketvirtas požymis (index 3)
    assert feats["srv-1"][3] == 2


def test_feature_per_host_separation():
    lines = [
        _entry("a", host="srv-1"),
        _entry("b", host="srv-2"),
        _entry("c", host="srv-2"),
    ]
    feats = MLDetector(FakeLokiClient(lines))._extract_features(lines, window_minutes=5)
    # log_count yra pirmas požymis (index 0)
    assert feats["srv-1"][0] == 1
    assert feats["srv-2"][0] == 2
