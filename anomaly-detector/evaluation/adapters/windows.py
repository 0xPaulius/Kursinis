"""
Windows ATT&CK rinkinių adapteriai: EVTX-ATTACK-SAMPLES (.evtx) ir OTRF Security
Datasets (JSON-lines). Abu paverčiami į tą pačią Alloy `loki.source.windowsevent`
JSON eilutę, kurią skaito windows_rules.parse_event ir vertinimo įkėlimas.

Šie rinkiniai yra „vien atakos" (be gerybinio fono), todėl naudojami technikų
aptikimui (per-technique recall), o ne klaidingai teigiamų (FPR) matavimui.
Technika imama iš failo/katalogo pavadinimo (pvz. T1059.001) arba `technique` argumento.
"""
from __future__ import annotations

import datetime
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..schema import AttackInterval, Dataset, Event

UTC = datetime.timezone.utc
_TECHNIQUE_RE = re.compile(r"T\d{4}(?:\.\d{3})?")
# OTRF/Mordor metaduomenų laukai, kurie nėra event_data.
_OTRF_META = {"@timestamp", "@version", "timestamp", "Hostname", "host", "Channel",
              "EventID", "event_id", "Message", "message", "SourceName", "ProviderName",
              "Provider", "Level", "LevelText", "Task", "Opcode", "Keywords",
              "RecordNumber", "EventRecordID", "ProcessID", "ThreadID", "Version",
              "Type", "SourceModuleName", "SourceModuleType", "EventType", "tags",
              "AccountType", "OpcodeValue", "ExecutionProcessID", "ActivityID"}


def _technique_from_path(path: str | Path) -> str | None:
    m = _TECHNIQUE_RE.search(str(path))
    return m.group(0) if m else None


def _build_line(event_id: int, channel: str, computer: str, data: dict[str, str],
                message: str = "", user_data: str = "") -> str:
    """Suformuoja Alloy windowsevent JSON eilutę iš laukų."""
    event: dict[str, object] = {
        "channel": channel or "Unknown",
        "computer": computer or "unknown",
        "event_id": int(event_id),
        "message": message,
    }
    if data:
        event["event_data"] = "".join(
            f'<Data Name="{k}">{v}</Data>' for k, v in data.items() if v not in (None, ""))
    if user_data:
        event["user_data"] = user_data
    return json.dumps(event, ensure_ascii=False)


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def event_xml_to_line(xml_str: str) -> str | None:
    """Vienas EVTX `<Event>` XML -> Alloy windowsevent JSON eilutė."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None
    system, event_data, user_data = {}, {}, ""
    channel = computer = ""
    event_id = None
    for child in root:
        tag = _strip_ns(child.tag)
        if tag == "System":
            for node in child:
                ntag = _strip_ns(node.tag)
                if ntag == "EventID":
                    event_id = int((node.text or "0").strip() or 0)
                elif ntag == "Channel":
                    channel = (node.text or "").strip()
                elif ntag == "Computer":
                    computer = (node.text or "").strip()
        elif tag == "EventData":
            for node in child:
                name = node.attrib.get("Name")
                if name:
                    event_data[name] = (node.text or "").strip()
        elif tag == "UserData":
            user_data = "".join(ET.tostring(node, encoding="unicode") for node in child)
    if event_id is None:
        return None
    return _build_line(event_id, channel, computer, event_data, user_data=user_data)


def _dataset(name: str, lines_with_tech: list[tuple[datetime.datetime, str, str]]) -> Dataset:
    """lines_with_tech: (laikas, Alloy JSON eilutė, technika) -> Dataset su 1 intervalu/techniką."""
    events, by_tech = [], {}
    for ts, line, tech in lines_with_tech:
        obj = json.loads(line)
        events.append(Event(ts=ts, host=obj.get("computer", "unknown"), message=line,
                            program=f"win-event-{obj['event_id']}", facility="daemon",
                            job="windows", is_attack=True,
                            attack_labels=[tech] if tech else [],
                            extra_labels={"channel": obj.get("channel", "Unknown")}))
        if tech:
            by_tech.setdefault(tech, []).append(ts)
    attacks = [AttackInterval(name=t, start=min(ts), end=max(ts), techniques=[t])
               for t, ts in by_tech.items()]
    start = min((e.ts for e in events), default=datetime.datetime(2022, 1, 1, tzinfo=UTC))
    end = max((e.ts for e in events), default=start) + datetime.timedelta(minutes=1)
    return Dataset(name=name, events=events, attacks=attacks, start=start, end=end)


def load_evtx(path: str | Path, technique: str | None = None) -> Dataset:
    """EVTX-ATTACK-SAMPLES: vienas .evtx failas (technika iš kelio arba argumento)."""
    from Evtx.Evtx import Evtx  # python-evtx

    path = Path(path)
    tech = technique or _technique_from_path(path)
    base = datetime.datetime(2022, 1, 1, tzinfo=UTC)
    rows = []
    with Evtx(str(path)) as log:
        for i, record in enumerate(log.records()):
            line = event_xml_to_line(record.xml())
            if line:
                rows.append((base + datetime.timedelta(seconds=i), line, tech))
    return _dataset(path.stem, rows)


def load_otrf(path: str | Path, technique: str | None = None) -> Dataset:
    """OTRF Security Datasets: JSON-lines (vienas Windows įvykis eilutėje)."""
    path = Path(path)
    tech = technique or _technique_from_path(path)
    base = datetime.datetime(2022, 1, 1, tzinfo=UTC)
    rows = []
    for i, raw in enumerate(path.read_text(errors="replace").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        event_id = rec.get("EventID") or rec.get("event_id")
        if event_id is None:
            continue
        data = {k: str(v) for k, v in rec.items() if k not in _OTRF_META and not k.startswith("@")}
        line = _build_line(int(event_id), rec.get("Channel", ""),
                           rec.get("Hostname") or rec.get("host") or "unknown",
                           data, message=rec.get("Message", "") or "")
        ts = base + datetime.timedelta(seconds=i)
        rows.append((ts, line, tech))
    return _dataset(path.stem, rows)


def load(kind: str, path: str | Path, technique: str | None = None) -> Dataset:
    if kind == "evtx":
        return load_evtx(path, technique)
    if kind == "otrf":
        return load_otrf(path, technique)
    raise ValueError(f"Nežinomas Windows adapterio tipas: {kind}")
