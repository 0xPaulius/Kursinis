"""
API maršrutų testai naudojant FastAPI TestClient su mock'ais.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import require_auth
from app.main import app
from app.models.schemas import (
    HealthStatus, ServiceHealth, TrafficCurrent, TrafficHistory, TrafficPoint,
)
from app.services.alert_reader import AlertReader
from app.services.loki_client import AsyncLokiClient
from app.services.health_checker import HealthChecker


@pytest.fixture()
def mock_loki():
    loki = MagicMock(spec=AsyncLokiClient)
    loki.query_range = AsyncMock(return_value=[])
    loki.query_metric = AsyncMock(return_value=[])
    loki.is_ready = AsyncMock(return_value=True)
    return loki


@pytest.fixture()
def mock_health_checker(mock_loki):
    checker = MagicMock(spec=HealthChecker)
    checker.get_status = AsyncMock(return_value=HealthStatus(
        overall="ok",
        services=[
            ServiceHealth(name="loki", label="Žurnalų saugykla (Loki)",
                          status="ok", message="Veikia normaliai"),
        ],
        checked_at="2024-01-01T10:00:00+00:00",
    ))
    return checker


@pytest.fixture()
def mock_alert_reader():
    reader = MagicMock(spec=AlertReader)
    reader.read_recent = MagicMock(return_value=[])
    reader.read_page = MagicMock(return_value=([], 0))
    return reader


@pytest.fixture()
def client(mock_loki, mock_health_checker, mock_alert_reader):
    app.state.loki = mock_loki
    app.state.health_checker = mock_health_checker
    app.state.alert_reader = mock_alert_reader
    # Pakeičiame auth dependency į no-op — testai netikrina autentifikacijos.
    app.dependency_overrides[require_auth] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealthRoute:
    def test_returns_200(self, client):
        resp = client.get("/api/health/status")
        assert resp.status_code == 200

    def test_response_schema(self, client):
        data = client.get("/api/health/status").json()
        assert "overall" in data
        assert "services" in data
        assert "checked_at" in data
        assert data["overall"] in ("ok", "warning", "critical", "unknown")

    def test_services_have_required_fields(self, client):
        services = client.get("/api/health/status").json()["services"]
        assert len(services) > 0
        for svc in services:
            assert "name" in svc
            assert "label" in svc
            assert "status" in svc
            assert "message" in svc


class TestTrafficRoutes:
    def test_current_returns_200(self, client):
        resp = client.get("/api/traffic/current")
        assert resp.status_code == 200

    def test_current_schema(self, client):
        data = client.get("/api/traffic/current").json()
        assert "total" in data
        assert "logs_per_minute" in data
        assert "by_severity" in data
        assert "by_job" in data

    def test_current_empty_loki(self, client, mock_loki):
        mock_loki.query_range.return_value = []
        data = client.get("/api/traffic/current").json()
        assert data["total"] == 0
        assert data["logs_per_minute"] == 0.0

    def test_history_returns_200(self, client):
        resp = client.get("/api/traffic/history")
        assert resp.status_code == 200

    def test_history_schema(self, client):
        data = client.get("/api/traffic/history").json()
        assert "points" in data
        assert isinstance(data["points"], list)

    def test_history_hours_validation(self, client):
        assert client.get("/api/traffic/history?hours=0").status_code == 422
        assert client.get("/api/traffic/history?hours=200").status_code == 422
        assert client.get("/api/traffic/history?hours=24").status_code == 200


class TestAlertsRoutes:
    def test_recent_returns_200(self, client):
        resp = client.get("/api/alerts/recent")
        assert resp.status_code == 200

    def test_recent_schema(self, client):
        data = client.get("/api/alerts/recent").json()
        assert "alerts" in data
        assert "total" in data
        assert isinstance(data["alerts"], list)

    def test_history_returns_200(self, client):
        resp = client.get("/api/alerts/history")
        assert resp.status_code == 200

    def test_history_schema(self, client):
        data = client.get("/api/alerts/history").json()
        assert "alerts" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data

    def test_history_pagination_validation(self, client):
        assert client.get("/api/alerts/history?page=0").status_code == 422
        assert client.get("/api/alerts/history?size=0").status_code == 422
        assert client.get("/api/alerts/history?page=1&size=50").status_code == 200


class TestRootRoute:
    def test_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestAuthEnforcement:
    """API maršrutai turi grąžinti 401 be Authorization antraštės."""

    def test_health_requires_auth(self, mock_loki, mock_health_checker, mock_alert_reader):
        app.state.loki = mock_loki
        app.state.health_checker = mock_health_checker
        app.state.alert_reader = mock_alert_reader
        with TestClient(app) as c:
            assert c.get("/api/health/status").status_code == 401

    def test_traffic_requires_auth(self, mock_loki, mock_health_checker, mock_alert_reader):
        app.state.loki = mock_loki
        app.state.health_checker = mock_health_checker
        app.state.alert_reader = mock_alert_reader
        with TestClient(app) as c:
            assert c.get("/api/traffic/current").status_code == 401
            assert c.get("/api/traffic/history").status_code == 401

    def test_alerts_requires_auth(self, mock_loki, mock_health_checker, mock_alert_reader):
        app.state.loki = mock_loki
        app.state.health_checker = mock_health_checker
        app.state.alert_reader = mock_alert_reader
        with TestClient(app) as c:
            assert c.get("/api/alerts/recent").status_code == 401
            assert c.get("/api/alerts/history").status_code == 401

    def test_valid_token_unlocks_api(self, mock_loki, mock_health_checker, mock_alert_reader):
        from app.routers.auth import _token_for
        app.state.loki = mock_loki
        app.state.health_checker = mock_health_checker
        app.state.alert_reader = mock_alert_reader
        with TestClient(app) as c:
            headers = {"Authorization": f"Bearer {_token_for('admin')}"}
            assert c.get("/api/health/status", headers=headers).status_code == 200

    def test_login_success_and_failure(self, mock_loki, mock_health_checker, mock_alert_reader):
        app.state.loki = mock_loki
        app.state.health_checker = mock_health_checker
        app.state.alert_reader = mock_alert_reader
        with TestClient(app) as c:
            ok = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            assert ok.status_code == 200
            assert ok.json()["token"]

            bad = c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
            assert bad.status_code == 401
