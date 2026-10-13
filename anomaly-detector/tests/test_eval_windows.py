"""
Windows ATT&CK adapterių (EVTX XML, OTRF JSON) ir technikų recall metrikos testai.
"""
from __future__ import annotations

import datetime
import json

from evaluation import metrics
from evaluation.adapters import windows
from windows_rules import parse_event

T0 = datetime.datetime(2022, 1, 24, 4, 0, tzinfo=datetime.timezone.utc)

EVTX_XML = """<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Microsoft-Windows-Security-Auditing"/>
    <EventID>4625</EventID>
    <Channel>Security</Channel>
    <Computer>VICTIM-01</Computer>
  </System>
  <EventData>
    <Data Name="TargetUserName">administrator</Data>
    <Data Name="IpAddress">203.0.113.9</Data>
    <Data Name="LogonType">3</Data>
  </EventData>
</Event>"""


def test_evtx_xml_to_alloy_line_roundtrips_through_parser():
    line = windows.event_xml_to_line(EVTX_XML)
    ev = parse_event(line)
    assert ev.event_id == 4625 and ev.channel == "Security" and ev.computer == "VICTIM-01"
    assert ev.data["IpAddress"] == "203.0.113.9"
    assert ev.data["TargetUserName"] == "administrator"


def test_evtx_invalid_xml_returns_none():
    assert windows.event_xml_to_line("<broken") is None


def test_otrf_jsonl_to_dataset(tmp_path):
    records = [
        {"EventID": 1, "Channel": "Microsoft-Windows-Sysmon/Operational", "Hostname": "H1",
         "Image": "C:\\Windows\\System32\\whoami.exe", "CommandLine": "whoami /all",
         "@timestamp": "2022-01-24T04:00:00Z", "Message": "Process Create"},
        {"EventID": 1, "Channel": "Microsoft-Windows-Sysmon/Operational", "Hostname": "H1",
         "Image": "C:\\Windows\\System32\\net.exe", "CommandLine": "net user"},
    ]
    path = tmp_path / "T1087.001_discovery.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    ds = windows.load("otrf", path)
    assert len(ds.events) == 2
    assert all(e.job == "windows" and e.is_attack for e in ds.events)
    # Technika paimta iš failo pavadinimo, vienas intervalas tai technikai
    assert [iv.techniques for iv in ds.attacks] == [["T1087.001"]]
    # event_data laukai atkuriami, meta laukai (Message, @timestamp) — ne
    ev = parse_event(ds.events[0].message)
    assert ev.data["Image"].endswith("whoami.exe")
    assert "Message" not in ev.data and "@timestamp" not in ev.data


def test_otrf_line_detected_by_windows_rules(tmp_path):
    """Adapterio išvestis turi suveikti tikrose Windows taisyklėse (discovery burst)."""
    from windows_rules import WindowsRuleDetector

    recs = [{"EventID": 1, "Channel": "Microsoft-Windows-Sysmon/Operational", "Hostname": "H1",
             "Image": f"C:\\Windows\\System32\\{p}"} for p in
            ("whoami.exe", "net.exe", "ipconfig.exe", "systeminfo.exe")]
    path = tmp_path / "T1033_recon.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs))
    ds = windows.load("otrf", path)

    class FakeLoki:
        def query_range(self, q, start=None, end=None, limit=5000):
            return [{"timestamp": "0", "line": e.message, "labels": {}} for e in ds.events]

    alerts = WindowsRuleDetector(FakeLoki()).check(now=T0)
    assert any(a.alert_type == "win_discovery_burst" for a in alerts)


def test_technique_recall_counts_detected():
    intervals = [
        {"name": "T1110.001", "start": T0.isoformat(),
         "end": (T0 + datetime.timedelta(minutes=1)).isoformat(), "techniques": ["T1110.001"]},
        {"name": "T1046", "start": (T0 + datetime.timedelta(minutes=30)).isoformat(),
         "end": (T0 + datetime.timedelta(minutes=31)).isoformat(), "techniques": ["T1046"]},
    ]
    ticks = []
    for m in range(40):
        t = (T0 + datetime.timedelta(minutes=m)).isoformat()
        raw = [{"detection_method": "rule", "alert_type": "win_failed_logon_bruteforce"}] if m == 2 else []
        ticks.append({"t": t, "raw": raw, "new": raw})
    tr = metrics.technique_recall(intervals, ticks, window_s=300)
    assert tr["total"] == 2 and tr["detected"] == 1
    detected = {r["technique"]: r["detected"] for r in tr["techniques"]}
    assert detected == {"T1110.001": True, "T1046": False}
