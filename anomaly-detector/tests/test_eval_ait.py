"""
AIT-LDS adapterio testai su miniatiūriniu scenarijumi (tikro rinkinio struktūra).
"""
from __future__ import annotations

import datetime
import json

from evaluation.adapters import ait

UTC = datetime.timezone.utc


def _scenario(tmp_path):
    (tmp_path / "dataset.yaml").write_text(
        "name: processed_mini_scenario\nstart: '2022-01-21T00:00:00'\nend: '2022-01-25T00:00:00'\n")
    logs = tmp_path / "gather" / "intranet_server" / "logs"
    (logs / "apache2").mkdir(parents=True)
    (logs / "auth.log").write_text(
        "Jan 24 04:37:39 intranet-server CRON[1]: pam_unix(cron:session): session opened for user root\n"
        "Jan 24 04:37:40 intranet-server su[27950]: Successful su for jhall by www-data\n"
        "Jan 24 04:37:58 intranet-server sudo:    jhall : TTY=pts/1 ; USER=root ; COMMAND=list\n"
    )
    (logs / "apache2" / "site-access.log").write_text(
        '10.0.0.1 - - [24/Jan/2022:03:56:53 +0000] "GET / HTTP/1.0" 200 17051 "-" "-"\n'
        '10.0.0.1 - - [24/Jan/2022:03:57:01 +0000] "GET /admin HTTP/1.0" 404 120 "-" "-"\n'
    )
    (logs / "dnsmasq.log").write_text("Jan 24 05:00:00 dnsmasq[3468]: query[A] x.example from 10.0.0.9\n")
    labels = tmp_path / "labels" / "intranet_server" / "logs"
    (labels / "apache2").mkdir(parents=True)
    (labels / "auth.log").write_text(
        json.dumps({"line": 2, "labels": ["attacker_change_user", "escalate"], "rules": {}}) + "\n"
        + json.dumps({"line": 3, "labels": ["escalated_command", "escalate"], "rules": {}}) + "\n")
    (labels / "apache2" / "site-access.log").write_text(
        json.dumps({"line": 2, "labels": ["attacker_http", "foothold"], "rules": {}}) + "\n")
    attacker = tmp_path / "gather" / "attacker_0" / "logs"
    attacker.mkdir(parents=True)
    (attacker / "attacks.log").write_text("2022-01-24 03:58:20.020490+00:00 upload_rce_shell\n")
    return tmp_path


def test_events_parsed_with_utc_year_from_dataset(tmp_path):
    ds = ait.load(_scenario(tmp_path))
    auth = [e for e in ds.events if e.program == "su"][0]
    assert auth.ts == datetime.datetime(2022, 1, 24, 4, 37, 40, tzinfo=UTC)
    assert auth.host == "intranet-server" and auth.pid == "27950" and auth.facility == "auth"
    assert [e for e in ds.events if e.program == "sudo"][0].pid == ""


def test_labels_mark_lines_by_number(tmp_path):
    ds = ait.load(_scenario(tmp_path))
    attacks = {(e.program, e.ts.minute) for e in ds.events if e.is_attack}
    assert attacks == {("su", 37), ("sudo", 37), ("apache2", 57)}
    cron = [e for e in ds.events if e.program == "CRON"][0]
    assert not cron.is_attack


def test_apache_host_from_directory(tmp_path):
    apache = [e for e in ait.load(_scenario(tmp_path)).events if e.program == "apache2"]
    assert {e.host for e in apache} == {"intranet-server"}
    assert apache[0].ts == datetime.datetime(2022, 1, 24, 3, 56, 53, tzinfo=UTC)


def test_dnsmasq_only_when_requested(tmp_path):
    root = _scenario(tmp_path)
    assert not [e for e in ait.load(root).events if e.program == "dnsmasq"]
    dns = [e for e in ait.load(root, sources=[ait.DNSMASQ_SOURCE]).events if e.program == "dnsmasq"]
    assert len(dns) == 1 and dns[0].host == "intranet-server"


def test_intervals_cluster_by_phase(tmp_path):
    names = [iv.name for iv in ait.load(_scenario(tmp_path)).attacks]
    assert names == ["attacker_http", "attacker_change_user", "escalated_command"]


def test_attack_schedule(tmp_path):
    steps = ait.attack_schedule(_scenario(tmp_path))
    assert steps[0][1] == "upload_rce_shell"
    assert steps[0][0].tzinfo is not None
