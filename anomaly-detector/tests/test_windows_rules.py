"""
Windows taisyklių testai: WinEvent parseris ir kiekviena taisyklė (teigiamas + neigiamas)
prieš golden fixtures (Alloy loki.source.windowsevent formatas).
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import attack_catalog
from windows_rules import WindowsRuleDetector, parse_event

GOLDEN = {c["name"]: c for c in json.loads(
    (Path(__file__).parent / "fixtures" / "windows" / "windows_golden.json").read_text())["cases"]}
T0 = datetime.datetime(2022, 1, 24, 4, 40, tzinfo=datetime.timezone.utc)


class FakeLoki:
    def __init__(self, lines: list[str]):
        self._lines = [{"timestamp": "0", "line": ln, "labels": {"job": "windows"}} for ln in lines]

    def query_range(self, query, start=None, end=None, limit=5000):
        return self._lines[:limit]


def line(name: str) -> str:
    return GOLDEN[name]["line"]


def alerts_for(names: list[str], **kw):
    det = WindowsRuleDetector(FakeLoki([line(n) for n in names]))
    return det.check(now=T0, **kw)


# -- Parser ------------------------------------------------------------------

def test_parse_eventdata_fields():
    ev = parse_event(line("4625_failed_logon"))
    assert ev.event_id == 4625 and ev.channel == "Security"
    assert ev.data["IpAddress"] == "203.0.113.7"
    assert ev.data["TargetUserName"] == "administrator"


def test_parse_userdata_1102():
    ev = parse_event(line("1102_audit_log_cleared"))
    assert ev.event_id == 1102
    assert ev.data["SubjectUserName"] == "attacker"   # iš UserData, ne EventData


def test_parse_rejects_non_windows():
    assert parse_event("not json") is None
    assert parse_event(json.dumps({"foo": "bar"})) is None


def test_image_name_helper():
    ev = parse_event(line("sysmon1_process_create"))
    assert ev.image_name() == "whoami.exe"


# -- Per-event rules: teigiami ----------------------------------------------

def test_account_created():
    a = alerts_for(["4720_account_created"])
    assert [x.alert_type for x in a] == ["win_account_created"]
    assert a[0].attack_techniques == ["T1136.001"]


def test_account_lockout():
    a = alerts_for(["4740_account_lockout"])
    assert a[0].alert_type == "win_account_lockout"


def test_admin_group_add_detected():
    a = alerts_for(["4732_added_to_administrators"])
    assert a[0].alert_type == "win_admin_group_add"
    assert a[0].attack_techniques == ["T1098"]


def test_audit_log_cleared():
    a = alerts_for(["1102_audit_log_cleared"])
    assert a[0].alert_type == "win_audit_log_cleared"
    assert a[0].attack_techniques == ["T1070.001"]


def test_suspicious_powershell_detected():
    a = alerts_for(["4104_scriptblock_suspicious"])
    assert a[0].alert_type == "win_suspicious_powershell"


def test_startup_persistence_detected():
    a = alerts_for(["sysmon11_file_create_startup"])
    assert a[0].alert_type == "win_startup_persistence"


def test_lolbin_network_detected():
    a = alerts_for(["sysmon3_network_connect"])
    assert a[0].alert_type == "win_lolbin_network"
    assert a[0].source_ip == "203.0.113.7"


# -- Per-event rules: neigiami (jokio alerto) -------------------------------

def test_non_admin_group_add_ignored():
    assert alerts_for(["4732_added_to_users_benign"]) == []


def test_benign_powershell_ignored():
    assert alerts_for(["4104_scriptblock_benign"]) == []


def test_benign_file_create_ignored():
    assert alerts_for(["sysmon11_file_create_benign"]) == []


def test_successful_logon_ignored():
    assert alerts_for(["4624_logon_benign"]) == []


# -- Agregacijos taisyklės ---------------------------------------------------

def _failed_logon(ip: str, user: str) -> str:
    return json.dumps({"event_id": 4625, "channel": "Security", "computer": "WIN11-LAB",
                       "event_data": f'<Data Name="TargetUserName">{user}</Data>'
                                     f'<Data Name="IpAddress">{ip}</Data>'})


def test_failed_logon_bruteforce_threshold():
    lines = [_failed_logon("203.0.113.7", "administrator") for _ in range(5)]
    a = WindowsRuleDetector(FakeLoki(lines)).check(now=T0)
    assert a[0].alert_type == "win_failed_logon_bruteforce"
    assert a[0].source_ip == "203.0.113.7"
    assert a[0].details["attempts"] == 5


def test_failed_logon_below_threshold_silent():
    lines = [_failed_logon("203.0.113.7", "administrator") for _ in range(4)]
    assert WindowsRuleDetector(FakeLoki(lines)).check(now=T0) == []


def test_password_spray_distinct_users():
    lines = [_failed_logon("203.0.113.7", f"user{i}") for i in range(5)]
    a = WindowsRuleDetector(FakeLoki(lines)).check(now=T0)
    assert a[0].alert_type == "win_password_spray"
    assert a[0].details["distinct_users"] == 5


def _sysmon1(image: str) -> str:
    return json.dumps({"event_id": 1, "channel": "Microsoft-Windows-Sysmon/Operational",
                       "computer": "WIN11-LAB", "event_data": f'<Data Name="Image">{image}</Data>'})


def test_discovery_burst_detected():
    lines = [_sysmon1(f"C:\\Windows\\System32\\{p}")
             for p in ("whoami.exe", "net.exe", "ipconfig.exe", "systeminfo.exe")]
    a = WindowsRuleDetector(FakeLoki(lines)).check(now=T0)
    assert a[0].alert_type == "win_discovery_burst"
    assert a[0].details["process_count"] == 4


def test_discovery_burst_below_threshold_silent():
    lines = [_sysmon1("C:\\Windows\\System32\\whoami.exe") for _ in range(3)]
    assert WindowsRuleDetector(FakeLoki(lines)).check(now=T0) == []


# -- Katalogas ---------------------------------------------------------------

def test_query_fetches_only_rule_event_ids():
    class RecordingLoki(FakeLoki):
        def query_range(self, query, start=None, end=None, limit=5000):
            self.query = query
            return super().query_range(query, start, end, limit)

    loki = RecordingLoki([])
    WindowsRuleDetector(loki).check(now=T0)
    assert loki.query.endswith('| json event_id="event_id" | event_id=~"1|3|11|1102|4104|4625|4720|4732|4740"')


def test_every_windows_alert_type_in_catalog():
    win_types = ["win_failed_logon_bruteforce", "win_password_spray", "win_account_lockout",
                 "win_account_created", "win_admin_group_add", "win_audit_log_cleared",
                 "win_suspicious_powershell", "win_discovery_burst", "win_lolbin_network",
                 "win_startup_persistence"]
    for t in win_types:
        assert attack_catalog.techniques_for(t), t


def test_coverage_reports_uncovered_techniques():
    cov = attack_catalog.coverage()
    assert cov["total"] == len(attack_catalog.LAB_TECHNIQUE_SET)
    assert cov["with_rule"] < cov["total"]      # kai kurios technikos sąmoningai be taisyklės
    names = {r["technique"] for r in cov["techniques"] if not r["has_rule"]}
    assert "T1021.001" in names


def test_coverage_detected_from_seen_alert_types():
    cov = attack_catalog.coverage(seen_alert_types={"win_admin_group_add", "ssh_bruteforce"})
    detected = {r["technique"] for r in cov["techniques"] if r["detected"]}
    assert detected == {"T1098", "T1110.001"}
