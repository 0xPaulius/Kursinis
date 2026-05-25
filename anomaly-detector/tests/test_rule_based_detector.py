"""
Taisyklėmis pagrįsto detektoriaus testai.
"""
from __future__ import annotations

from detector import RuleBasedDetector, SSH_BRUTE_THRESHOLD


class FakeLokiClient:
    """Pakeičia tikrą LokiClient — grąžina iš anksto paruoštas log eilutes."""

    def __init__(self, lines: list[dict]):
        self._lines = lines

    def query_range(self, query: str, start=None, end=None, limit: int = 5000) -> list[dict]:
        return self._lines


def _entry(line: str, host: str = "srv-1") -> dict:
    return {"timestamp": "0", "line": line, "labels": {"host": host}}


# ---------------------------------------------------------------------------
# SSH brute-force
# ---------------------------------------------------------------------------

def test_ssh_bruteforce_triggers_above_threshold():
    lines = [
        _entry(f"Failed password for user from 10.0.0.5 port {p}")
        for p in range(SSH_BRUTE_THRESHOLD)
    ]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_ssh_bruteforce()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "ssh_bruteforce"
    assert alerts[0].source_ip == "10.0.0.5"
    assert alerts[0].details["failed_attempts"] == SSH_BRUTE_THRESHOLD


def test_ssh_bruteforce_below_threshold_no_alert():
    lines = [
        _entry(f"Failed password for user from 10.0.0.5 port {p}")
        for p in range(SSH_BRUTE_THRESHOLD - 1)
    ]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_ssh_bruteforce()
    assert alerts == []


def test_ssh_bruteforce_high_severity_at_3x_threshold():
    lines = [
        _entry(f"Failed password for user from 10.0.0.5 port {p}")
        for p in range(SSH_BRUTE_THRESHOLD * 3)
    ]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_ssh_bruteforce()
    assert len(alerts) == 1
    assert alerts[0].severity == "high"


def test_ssh_bruteforce_per_ip_aggregation():
    """Kiekvienas IP turi būti suskaičiuotas atskirai."""
    lines = (
        [_entry(f"Failed password from 10.0.0.5 port {p}") for p in range(SSH_BRUTE_THRESHOLD)]
        + [_entry(f"Failed password from 10.0.0.6 port {p}") for p in range(SSH_BRUTE_THRESHOLD)]
    )
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_ssh_bruteforce()
    ips = {a.source_ip for a in alerts}
    assert ips == {"10.0.0.5", "10.0.0.6"}


# ---------------------------------------------------------------------------
# Invalid user scan — buvęs false-positive
# ---------------------------------------------------------------------------

def test_invalid_user_scan_triggers_on_distinct_usernames():
    lines = [
        _entry("Invalid user root from 10.0.0.5 port 22"),
        _entry("Invalid user admin from 10.0.0.5 port 22"),
        _entry("Invalid user test from 10.0.0.5 port 22"),
    ]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_unauthorized_access()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "invalid_user_scan"
    assert alerts[0].details["unique_username_count"] == 3
    assert alerts[0].details["attempt_count"] == 3


def test_invalid_user_scan_ignores_repeated_single_username():
    """Regression: pakartotinai tas pats vartotojas neturi triggerinti skenavimo."""
    lines = [_entry("Invalid user root from 10.0.0.5 port 22")] * 4
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_unauthorized_access()
    assert alerts == []


def test_invalid_user_scan_per_ip():
    lines = [
        _entry("Invalid user root from 10.0.0.5 port 22"),
        _entry("Invalid user admin from 10.0.0.5 port 22"),
        _entry("Invalid user test from 10.0.0.5 port 22"),
        _entry("Invalid user oracle from 10.0.0.6 port 22"),  # vienas IP — netriggerina
    ]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_unauthorized_access()
    assert len(alerts) == 1
    assert alerts[0].source_ip == "10.0.0.5"


# ---------------------------------------------------------------------------
# Firewall spike
# ---------------------------------------------------------------------------

def test_firewall_spike_triggers_above_50():
    lines = [_entry("DROP packet") for _ in range(51)]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_firewall_events()
    assert len(alerts) == 1
    assert alerts[0].alert_type == "firewall_spike"
    assert alerts[0].details["blocked_count"] == 51


def test_firewall_spike_no_alert_below_threshold():
    lines = [_entry("DROP packet") for _ in range(50)]
    alerts = RuleBasedDetector(FakeLokiClient(lines)).check_firewall_events()
    assert alerts == []
