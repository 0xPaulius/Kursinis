"""
ML detektoriaus požymių (Loki metrikos užklausos) ir treniravimo režimų testai.
"""
from __future__ import annotations

import datetime

from detector import LokiClient, MLDetector

T0 = datetime.datetime(2022, 1, 24, 0, 0, tzinfo=datetime.timezone.utc)


class FakeMetricLoki(LokiClient):
    """Atsako į kiekvieną požymio užklausą pagal jos turinį."""

    def __init__(self, per_host: dict[str, dict[str, float]]):
        super().__init__("http://fake")
        self.per_host = per_host
        self.queries: list[str] = []

    def instant_query(self, query, at=None):
        self.queries.append(query)
        if "bytes_over_time" in query:
            key = "bytes"
        elif "regexp" in query:
            key = "ips"
        elif "sum by (host, program)" in query:
            key = "programs"
        elif "severity=~" in query:
            key = "errors"
        else:
            key = "count"
        return [{"labels": {"host": h}, "value": v[key]} for h, v in self.per_host.items() if key in v]


def _host(count, programs=1, errors=0, ips=0, size=None):
    return {"count": count, "programs": programs, "errors": errors, "ips": ips,
            "bytes": size if size is not None else count * 50}


def test_feature_vector_shape():
    """Kiekvienam host'ui turi būti grąžinti 5 požymiai."""
    feats = MLDetector(FakeMetricLoki({"srv-1": _host(2)}), state_dir=None)._metric_features(T0, 10)
    assert "srv-1" in feats
    assert len(feats["srv-1"]) == 5


def test_feature_error_rate_and_avg_length():
    feats = MLDetector(FakeMetricLoki({"srv-1": _host(4, errors=2, size=400)}),
                       state_dir=None)._metric_features(T0, 10)
    assert feats["srv-1"][2] == 0.5   # error_rate
    assert feats["srv-1"][4] == 100   # bytes / count


def test_feature_unique_ip_count():
    feats = MLDetector(FakeMetricLoki({"srv-1": _host(4, ips=2)}), state_dir=None)._metric_features(T0, 10)
    assert feats["srv-1"][3] == 2


def test_feature_per_host_separation():
    loki = FakeMetricLoki({"srv-1": _host(1), "srv-2": _host(2)})
    feats = MLDetector(loki, state_dir=None)._metric_features(T0, 10)
    assert feats["srv-1"][0] == 1
    assert feats["srv-2"][0] == 2


def test_ip_feature_query_filters_lines_without_ip():
    loki = FakeMetricLoki({"srv-1": _host(1)})
    MLDetector(loki, state_dir=None)._metric_features(T0, 10)
    ip_query = next(q for q in loki.queries if "regexp" in q)
    assert '| ip != ""' in ip_query and "[10m]" in ip_query


def test_online_mode_retrains_every_call():
    det = MLDetector(FakeMetricLoki({"srv-1": _host(5)}), state_dir=None)
    det.training_mode = "online"
    for i in range(25):
        det.detect(now=T0 + datetime.timedelta(minutes=5 * i))
    assert det.is_trained and not det.frozen
    assert len(det.training_data) == 25


def test_frozen_mode_stops_learning_when_buffer_full():
    from collections import deque

    det = MLDetector(FakeMetricLoki({"srv-1": _host(5), "srv-2": _host(7)}), state_dir=None)
    det.training_mode = "frozen"
    det.training_data = deque(maxlen=20)
    for i in range(9):
        det.detect(now=T0 + datetime.timedelta(minutes=5 * i))
    assert not det.is_trained                    # 18 < 20 — dar renkama
    det.detect(now=T0 + datetime.timedelta(minutes=45))
    assert det.is_trained and det.frozen
    snapshot = list(det.training_data)
    det.detect(now=T0 + datetime.timedelta(minutes=50))
    assert list(det.training_data) == snapshot   # užfiksuotas — nebekaupia
