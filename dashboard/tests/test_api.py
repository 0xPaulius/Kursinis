"""
API ir paslaugų testai: įrenginių registracija, sesijos tikrinimas, teisės,
bandymų ribojimas, detektoriaus būklė, srauto kiekiai ir įspėjimų priskyrimas.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.services.user_store import UserStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Izoliuota būsena: vartotojai, įrenginiai, pranešimai ir alertai laikinajame kataloge."""
    monkeypatch.setenv("USERS_DB_PATH", str(tmp_path / "users.json"))
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD", "admin-pw")
    import app.main as main
    import app.routers.auth as auth
    from app.services import alert_reader, device_registry, health_checker, notifier
    monkeypatch.setattr(main, "SYNTHETIC_TRAFFIC", False)
    monkeypatch.setattr(device_registry, "DEVICES_DB_PATH", str(tmp_path / "devices.json"))
    monkeypatch.setattr(device_registry, "SUPPRESSED_DB_PATH", str(tmp_path / "deleted.json"))
    monkeypatch.setattr(notifier, "NOTIFY_CONFIG_PATH", str(tmp_path / "notify.json"))
    monkeypatch.setattr(alert_reader, "ANOMALY_DB_PATH", str(tmp_path / "anomaly_history.json"))
    monkeypatch.setattr(health_checker, "DETECTOR_HEARTBEAT_PATH", str(tmp_path / "detector.alive"))
    monkeypatch.setattr(auth, "_store", None)
    auth._failures.clear()
    return SimpleNamespace(tmp=tmp_path, app=main.app, auth=auth)


@pytest.fixture
def client(env):
    with TestClient(env.app) as c:
        yield c


def _login(client, user="admin", password="admin-pw") -> dict:
    token = client.post("/api/auth/login", json={"username": user, "password": password}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# -- Įrenginiai ---------------------------------------------------------------

def test_add_device(client):
    resp = client.post("/api/devices", headers=_login(client),
                       json={"name": "Laptop", "ip": "192.168.1.70", "os": "macos", "synthetic": False})
    assert resp.status_code == 201
    assert resp.json()["hostname"] == "laptop" and resp.json()["synthetic"] is False


def test_deleted_default_device_is_not_seeded_again(env):
    from app.services.device_registry import DeviceRegistry
    DeviceRegistry().delete("default-macbook")
    assert "macbook" not in {d["hostname"] for d in DeviceRegistry().list_all()}


# -- Sesija ir teisės ---------------------------------------------------------

def test_token_of_deleted_user_rejected(client, env):
    users = UserStore(env.tmp / "users.json")          # kaip manage_users CLI
    users.set_user("bob", "pw-bob", "admin")
    headers = _login(client, "bob", "pw-bob")
    assert client.get("/api/alerts/recent", headers=headers).status_code == 200
    users.delete_user("bob")
    assert client.get("/api/alerts/recent", headers=headers).status_code == 401


def test_token_of_demoted_user_rejected(client, env):
    users = UserStore(env.tmp / "users.json")
    users.set_user("eve", "pw-eve", "admin")
    headers = _login(client, "eve", "pw-eve")
    users.set_user("eve", "pw-eve", "viewer")
    assert client.post("/api/devices/demo/scenario", headers=headers,
                       json={"attack": "ssh_bruteforce"}).status_code == 401


def test_webhook_settings_admin_only(client, env):
    UserStore(env.tmp / "users.json").set_user("vic", "pw-vic", "viewer")
    assert client.get("/api/notifications/settings", headers=_login(client, "vic", "pw-vic")).status_code == 403
    assert client.get("/api/notifications/settings", headers=_login(client)).status_code == 200


def test_login_throttled_per_ip_across_usernames(client, env, monkeypatch):
    monkeypatch.setattr(env.auth, "_MAX_FAILURES", 3)
    codes = [client.post("/api/auth/login", json={"username": f"u{i}", "password": "x"}).status_code
             for i in range(4)]
    assert codes == [401, 401, 401, 429]


# -- Detektoriaus būklė --------------------------------------------------------

def test_detector_health_follows_heartbeat(env):
    from app.services.health_checker import HealthChecker
    checker = HealthChecker(loki=None)
    heartbeat = env.tmp / "detector.alive"
    assert checker._check_detector_health()[0] == "critical"     # detektorius nepaleistas
    heartbeat.touch()
    assert checker._check_detector_health()[0] == "ok"
    old = time.time() - 600
    os.utime(heartbeat, (old, old))
    assert checker._check_detector_health()[0] == "critical"     # nustojo veikti


class _EndpointLoki:
    """Netikras Loki: naujausia galinio įrenginio eilutė buvo prieš `age`."""

    def __init__(self, age: datetime.timedelta):
        self.newest = datetime.datetime.now(datetime.timezone.utc) - age
        self.queries: list[tuple[str, int]] = []

    async def query_range(self, query, start=None, end=None, limit=5000):
        self.queries.append((query, limit))
        if not start <= self.newest <= end:
            return []
        return [{"timestamp": str(int(self.newest.timestamp() * 1e9)), "line": "{}", "labels": {}}]


@pytest.mark.parametrize("age, status, message", [
    (datetime.timedelta(minutes=2), "ok", "Galiniai įrenginiai siunčia telemetriją"),
    (datetime.timedelta(minutes=40), "warning", "Telemetrijos negaunama — paskutinė gauta prieš 40 min"),
    (datetime.timedelta(hours=3), "warning", "Telemetrijos negaunama — paskutinė gauta prieš 3 val."),
    (datetime.timedelta(days=2, hours=5), "warning", "Telemetrijos negaunama — paskutinė gauta prieš 2 d."),
    (datetime.timedelta(days=8), None, ""),                     # per 7 d. nieko — eilutės nerodome
], ids=["ok", "warning-min", "warning-h", "warning-d", "hidden"])
def test_endpoint_telemetry_states(age, status, message):
    from app.services.health_checker import HealthChecker
    loki = _EndpointLoki(age)
    assert asyncio.run(HealthChecker(loki)._check_endpoint_telemetry()) == (status, message)
    assert loki.queries and all(q == ('{job=~"windows|linux_endpoint"}', 1) for q in loki.queries)


# -- Srauto kiekiai -------------------------------------------------------------

def test_traffic_current_counts_from_metric_query():
    from app.routers.traffic import get_traffic_current

    class FakeLoki:
        async def query_instant(self, query, at=None):
            assert "count_over_time" in query
            return [{"metric": {"job": "syslog", "severity": "info"}, "value": [0, "9000"]},
                    {"metric": {"job": "syslog", "severity": "err"}, "value": [0, "1000"]},
                    {"metric": {"job": "windows"}, "value": [0, "500"]}]

    current = asyncio.run(get_traffic_current(FakeLoki()))
    assert current.total == 10500 and current.logs_per_minute == 2100.0
    assert current.by_severity == {"info": 9000, "err": 1000, "unknown": 500}
    assert current.by_job == {"syslog": 10000, "windows": 500}


# -- Įspėjimai ------------------------------------------------------------------

def test_alert_summary_matches_exact_hostnames():
    from app.services.device_monitor import alert_summary
    alerts = [SimpleNamespace(source_ip="", source_host="macbook-2", severity="high"),
              SimpleNamespace(source_ip="", source_host="web-1, macbook", severity="medium")]
    assert alert_summary("", "macbook", alerts) == (1, "medium")
    assert alert_summary("", "macbook-2", alerts) == (1, "high")


def test_valid_host_rejects_logql_breakers():
    from app.log_selectors import valid_host
    assert valid_host("web-server-01") and valid_host("PC.local")
    for bad in ("", None, 'a"b', "a}b", "a b", "web\n", "x" * 256):
        assert not valid_host(bad), repr(bad)


def test_alerts_for_device_keeps_order_and_matches_ip_or_host():
    from app.services.device_monitor import alerts_for_device
    a1 = SimpleNamespace(source_ip="10.0.0.5", source_host="", severity="high")
    a2 = SimpleNamespace(source_ip="", source_host="web-1, pc-2", severity="low")
    a3 = SimpleNamespace(source_ip="", source_host="pc-22", severity="low")
    assert alerts_for_device("10.0.0.5", "pc-2", [a1, a2, a3]) == [a1, a2]
    assert alerts_for_device("", "pc-2", [a1, a2, a3]) == [a2]


def test_ns_to_datetime():
    from app.services.loki_client import ns_to_datetime
    assert ns_to_datetime("1793260800000000000").isoformat() == "2026-10-29T08:00:00+00:00"
    assert ns_to_datetime("x") is None and ns_to_datetime(None) is None


def test_alert_id_distinguishes_event_keys_and_keeps_old_ids():
    import hashlib
    from app.services.alert_reader import _alert_id
    base = {"timestamp": "t", "alert_type": "win_account_created", "source_ip": "", "source_host": "PC-01"}
    assert _alert_id({**base, "details": {"key": "a"}}) != _alert_id({**base, "details": {"key": "b"}})
    assert _alert_id({**base, "details": {}}) == hashlib.sha1(b"t|win_account_created||PC-01").hexdigest()[:16]


# -- Frontend'o failai ---------------------------------------------------------

def test_frontend_files_are_revalidated(client):
    for path in ("/", "/login", "/static/js/chart.min.js"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers.get("cache-control") == "no-cache", path
