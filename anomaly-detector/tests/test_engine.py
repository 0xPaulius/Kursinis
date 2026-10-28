"""
Engine (bendro aptikimo ciklo) testai: virtualus laikrodis, cooldown ir ML dažnis.
"""
from __future__ import annotations

import datetime
import json

from detector import SSH_BRUTE_THRESHOLD, Engine, LokiClient, Selectors

T0 = datetime.datetime(2022, 1, 24, 12, 0, tzinfo=datetime.timezone.utc)


class RecordingLokiClient(LokiClient):
    """Grąžina SSH nesėkmes `Failed password` užklausai ir įsimena užklausas."""

    def __init__(self, failures: int = SSH_BRUTE_THRESHOLD):
        super().__init__("http://fake")
        self.failures = failures
        self.calls: list[tuple[str, datetime.datetime, datetime.datetime]] = []
        self.metric_calls: list[tuple[str, datetime.datetime]] = []

    def query_range(self, query, start=None, end=None, limit=5000):
        self.calls.append((query, start, end))
        if "Failed password" in query:
            return [
                {"timestamp": "0", "line": f"Failed password for root from 10.0.0.5 port {p}",
                 "labels": {"host": "web-1"}}
                for p in range(self.failures)
            ]
        return []

    def instant_query(self, query, at=None):
        self.metric_calls.append((query, at))
        return [{"labels": {}, "value": 10.0}]


class StubML:
    def __init__(self):
        self.calls: list[datetime.datetime] = []

    def detect(self, window_minutes: int = 10, now=None):
        self.calls.append(now)
        return []


def test_alert_timestamp_follows_virtual_clock():
    raw, new = Engine(RecordingLokiClient(), enable_ml=False).run_cycle(T0)
    assert [a.alert_type for a in raw] == ["ssh_bruteforce"]
    assert new[0].timestamp == T0.isoformat()


def test_engine_fills_attack_techniques_from_catalog():
    raw, _ = Engine(RecordingLokiClient(), enable_ml=False).run_cycle(T0)
    ssh = next(a for a in raw if a.alert_type == "ssh_bruteforce")
    assert ssh.attack_techniques == ["T1110.001"]


def test_queries_use_window_ending_at_virtual_now():
    loki = RecordingLokiClient()
    Engine(loki, enable_ml=False).run_cycle(T0)
    query, start, end = next(c for c in loki.calls if "Failed password" in c[0])
    assert end == T0
    assert start == T0 - datetime.timedelta(minutes=5)
    assert loki.metric_calls and all(at == T0 for _, at in loki.metric_calls)


def test_cooldown_uses_virtual_time():
    engine = Engine(RecordingLokiClient(), enable_ml=False, cooldown_seconds=300)
    _, first = engine.run_cycle(T0)
    raw, second = engine.run_cycle(T0 + datetime.timedelta(seconds=60))
    _, third = engine.run_cycle(T0 + datetime.timedelta(seconds=300))

    assert len(first) == 1
    assert len(raw) == 1 and second == []      # aptikta, bet nuslopinta
    assert len(third) == 1                      # cooldown praėjo virtualiu laiku


class AccountsCreatedLoki(RecordingLokiClient):
    """Trys skirtingos Windows paskyros (4720) tame pačiame host'e per vieną langą."""

    def query_range(self, query, start=None, end=None, limit=5000):
        if 'job="windows"' not in query:
            return []
        return [{"timestamp": "0", "labels": {"job": "windows"}, "line": json.dumps({
            "event_id": 4720, "channel": "Security", "computer": "PC-01",
            "event_data": f'<Data Name="TargetUserName">{user}</Data>'})}
            for user in ("backdoor1", "backdoor2", "backdoor3")]


def test_cooldown_keeps_distinct_events_of_same_type_and_host():
    engine = Engine(AccountsCreatedLoki(), enable_ml=False, enable_linux=False, cooldown_seconds=300)
    _, first = engine.run_cycle(T0)
    _, repeat = engine.run_cycle(T0 + datetime.timedelta(seconds=5))

    assert sorted(a.details["key"] for a in first) == ["backdoor1", "backdoor2", "backdoor3"]
    assert repeat == []                         # tie patys įvykiai — nuslopinti


def test_ml_disabled_by_default():
    assert Engine(RecordingLokiClient()).ml_detector is None


def test_ml_runs_every_nth_cycle():
    engine = Engine(RecordingLokiClient(), enable_ml=True, ml_every_n_cycles=2, ml_state_dir=None)
    stub = StubML()
    engine.ml_detector = stub
    for i in range(5):
        engine.run_cycle(T0 + datetime.timedelta(minutes=i))
    assert stub.calls == [T0 + datetime.timedelta(minutes=1), T0 + datetime.timedelta(minutes=3)]


def test_extra_matchers_scope_every_query():
    loki = RecordingLokiClient()
    Engine(loki, selectors=Selectors(extra_matchers='dataset="ait"'), enable_ml=False).run_cycle(T0)
    queries = [q for q, _, _ in loki.calls] + [q for q, _ in loki.metric_calls]
    assert queries
    assert all('dataset="ait"' in query for query in queries)


def test_default_selectors_unchanged():
    sel = Selectors(extra_matchers="")
    assert sel.syslog == '{job="syslog"}'
    assert sel.errors == '{job="errors"}'
    assert sel.stream("windows", 'channel="Security"') == '{job="windows", channel="Security"}'
