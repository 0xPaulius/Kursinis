"""
Windows ATT&CK adapterių (EVTX XML, OTRF JSON) ir technikų recall metrikos testai.
"""
from __future__ import annotations

import datetime
import json
import zipfile

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


def test_evtx_line_keeps_original_event_time():
    xml = EVTX_XML.replace(
        "<Channel>", '<TimeCreated SystemTime="2019-03-19 23:34:25.123456"/>\n    <Channel>')
    assert json.loads(windows.event_xml_to_line(xml))["timeCreated"] == "2019-03-19T23:34:25.123456Z"


def test_otrf_events_use_timestamp_and_inherit_when_missing(tmp_path):
    recs = [{"EventID": 4720, "Channel": "Security", "Hostname": "H1", "@timestamp": "2020-09-21T23:18:52.372Z"},
            {"EventID": 4732, "Channel": "Security", "Hostname": "H1"}]
    path = tmp_path / "T1136.001_add_user.json"
    path.write_text("\n".join(json.dumps(r) for r in recs))
    ds = windows.load("otrf", path)
    expected = datetime.datetime(2020, 9, 21, 23, 18, 52, 372000, tzinfo=datetime.timezone.utc)
    assert [e.ts for e in ds.events] == [expected, expected]


def test_otrf_winlogbeat6_record_uses_nested_event_data(tmp_path):
    rec = {"@timestamp": "2019-05-18T20:36:46.254Z", "event_id": 11,
           "log_name": "Microsoft-Windows-Sysmon/Operational", "computer_name": "HFDC01.shire.com",
           "host": {"name": "WECserver"},
           "event_data": {"Image": "C:\\Windows\\System32\\cmd.exe", "TargetFilename":
                          "C:\\Users\\a\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\x.bat"}}
    path = tmp_path / "T1547.001_startup.json"
    path.write_text(json.dumps(rec))
    ev = parse_event(windows.load("otrf", path).events[0].message)
    assert (ev.event_id, ev.channel, ev.computer) == (11, "Microsoft-Windows-Sysmon/Operational",
                                                      "HFDC01.shire.com")
    assert ev.data["TargetFilename"].endswith("\\Startup\\x.bat")


def test_otrf_corpus_places_captures_on_one_timeline(tmp_path):
    def capture(name, stamps):
        recs = [{"EventID": 4720, "Channel": "Security", "Hostname": "H1", "@timestamp": s}
                for s in stamps]
        with zipfile.ZipFile(tmp_path / name, "w") as zf:
            zf.writestr(name.replace(".zip", ".json"), "\n".join(json.dumps(r) for r in recs))

    capture("a.zip", ["2020-09-21T10:00:00Z", "2020-09-21T10:00:30Z"])
    capture("b.zip", ["2019-05-01T08:00:00Z"])
    (tmp_path / "manifest.csv").write_text(
        "file,techniques,title\na.zip,T1136.001,Add user\nb.zip,T1098 T1136.001,Admin add\n")
    ds = windows.load("otrf", tmp_path)
    a, b = ds.attacks
    assert (a.name, a.techniques) == ("Add user", ["T1136.001"])
    assert b.techniques == ["T1098", "T1136.001"]
    assert (a.end - a.start).total_seconds() == 30
    assert b.start == a.end + datetime.timedelta(minutes=30)
    assert [e.attack_labels for e in ds.events][-1] == ["T1098", "T1136.001"]


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


def test_technique_recall_credits_only_alerts_mapped_to_the_technique():
    def interval(tech, minute):
        return {"name": tech, "start": (T0 + datetime.timedelta(minutes=minute)).isoformat(),
                "end": (T0 + datetime.timedelta(minutes=minute + 1)).isoformat(), "techniques": [tech]}

    alerts = {2: ["T1110"], 32: ["T1059.003"]}
    ticks = []
    for m in range(40):
        raw = [{"detection_method": "rule", "alert_type": "x", "attack_techniques": alerts[m]}
               ] if m in alerts else []
        ticks.append({"t": (T0 + datetime.timedelta(minutes=m)).isoformat(), "raw": raw, "new": raw})
    tr = metrics.technique_recall([interval("T1110.003", 0), interval("T1059.001", 30)], ticks, 300)
    rows = {r["technique"]: r for r in tr["techniques"]}
    assert rows["T1110.003"]["detected_mapped"] == 1 and rows["T1110.003"]["has_rule"]
    assert rows["T1059.001"]["detected"] and rows["T1059.001"]["detected_mapped"] == 0
    assert tr["detected_mapped"] == 1
