"""
Windows ATT&CK rinkinių adapteriai: EVTX-ATTACK-SAMPLES (.evtx) ir OTRF Security
Datasets (JSON-lines). Abu paverčiami į tą pačią Alloy `loki.source.windowsevent`
JSON eilutę, kurią skaito windows_rules.parse_event ir vertinimo įkėlimas.

Šie rinkiniai yra „vien atakos" (be gerybinio fono), todėl naudojami technikų
aptikimui (per-technique recall), o ne klaidingai teigiamų (FPR) matavimui.
Technika imama iš failo/katalogo pavadinimo (pvz. T1059.001) arba `technique` argumento;
OTRF korpuso kataloge — iš manifest.csv (technikos iš OTRF metaduomenų).
Įvykių laikas — originalus (EVTX TimeCreated, OTRF @timestamp).
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
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


def _parse_time(value) -> datetime.datetime | None:
    """ISO 8601 arba EVTX SystemTime -> UTC datetime (be zonos laikoma UTC)."""
    if not value:
        return None
    try:
        ts = datetime.datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _build_line(event_id: int, channel: str, computer: str, data: dict[str, str],
                message: str = "", user_data: str = "",
                time_created: datetime.datetime | None = None) -> str:
    """Suformuoja Alloy windowsevent JSON eilutę iš laukų."""
    event: dict[str, object] = {
        "channel": channel or "Unknown",
        "computer": computer or "unknown",
        "event_id": int(event_id),
        "message": message,
    }
    if time_created:
        event["timeCreated"] = time_created.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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
    event_data, user_data = {}, ""
    channel = computer = ""
    event_id = time_created = None
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
                elif ntag == "TimeCreated":
                    time_created = _parse_time(node.attrib.get("SystemTime"))
        elif tag == "EventData":
            for node in child:
                name = node.attrib.get("Name")
                if name:
                    event_data[name] = (node.text or "").strip()
        elif tag == "UserData":
            user_data = "".join(ET.tostring(node, encoding="unicode") for node in child)
    if event_id is None:
        return None
    return _build_line(event_id, channel, computer, event_data, user_data=user_data,
                       time_created=time_created)


_BASE = datetime.datetime(2022, 1, 1, tzinfo=UTC)


def _timed(lines: list[str]) -> list[tuple[datetime.datetime, str]]:
    """(laikas, eilutė): laikas iš timeCreated; jo nesant — ankstesnio įvykio laikas."""
    out, prev = [], _BASE
    for line in lines:
        ts = _parse_time(json.loads(line).get("timeCreated")) or prev
        out.append((ts, line))
        prev = ts
    return out


def _event(ts: datetime.datetime, line: str, techniques: list[str]) -> Event:
    obj = json.loads(line)
    return Event(ts=ts, host=obj.get("computer", "unknown"), message=line,
                 program=f"win-event-{obj['event_id']}", facility="daemon",
                 job="windows", is_attack=True, attack_labels=list(techniques),
                 extra_labels={"channel": obj.get("channel", "Unknown")})


def _dataset(name: str, lines: list[str], tech: str | None) -> Dataset:
    """Vienas failas -> Dataset su vienu intervalu technikai (visas failo laikotarpis)."""
    events = [_event(ts, line, [tech] if tech else []) for ts, line in _timed(lines)]
    times = [e.ts for e in events]
    attacks = [AttackInterval(name=tech, start=min(times), end=max(times), techniques=[tech])
               ] if tech and events else []
    start = min(times, default=_BASE)
    end = max(times, default=start) + datetime.timedelta(minutes=1)
    return Dataset(name=name, events=events, attacks=attacks, start=start, end=end)


def load_evtx(path: str | Path, technique: str | None = None) -> Dataset:
    """EVTX-ATTACK-SAMPLES: vienas .evtx failas (technika iš kelio arba argumento)."""
    from Evtx.Evtx import Evtx  # python-evtx

    path = Path(path)
    with Evtx(str(path)) as log:
        lines = [line for line in (event_xml_to_line(r.xml()) for r in log.records()) if line]
    return _dataset(path.stem, lines, technique or _technique_from_path(path))


def _read_otrf_file(path: Path) -> list[str]:
    """OTRF failas (.json arba .zip / .tar.gz su JSON-lines viduje) -> neapdorotos eilutės."""
    def wanted(name: str) -> bool:
        return name.endswith(".json") and "__MACOSX" not in name

    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            return [line for name in zf.namelist() if wanted(name)
                    for line in zf.read(name).decode(errors="replace").splitlines()]
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path) as tf:
            return [line for m in tf.getmembers() if m.isfile() and wanted(m.name)
                    for line in tf.extractfile(m).read().decode(errors="replace").splitlines()]
    return path.read_text(errors="replace").splitlines()


def _otrf_event_lines(raw_lines: list[str]) -> list[str]:
    """
    OTRF JSON įrašai (vienas Windows įvykis eilutėje) -> Alloy windowsevent eilutės.
    Du OTRF formatai: NXLog (plokšti laukai, Channel, Hostname) ir Winlogbeat 6
    (log_name, computer_name, laukai po event_data; jo `host` — kolektorius).
    """
    lines = []
    for raw in raw_lines:
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
        if isinstance(rec.get("event_data"), dict):
            fields = rec["event_data"]
        else:
            fields = {k: v for k, v in rec.items() if k not in _OTRF_META and not k.startswith("@")}
        host = rec.get("Hostname") or rec.get("computer_name") or rec.get("host")
        lines.append(_build_line(int(event_id), rec.get("Channel") or rec.get("log_name", ""),
                                 host if isinstance(host, str) else "unknown",
                                 {k: str(v) for k, v in fields.items()},
                                 message=rec.get("Message", "") or "",
                                 time_created=_parse_time(rec.get("@timestamp"))))
    return lines


def load_otrf(path: str | Path, technique: str | None = None) -> Dataset:
    """OTRF Security Datasets: vienas failas (technika iš kelio arba argumento)."""
    path = Path(path)
    return _dataset(path.stem, _otrf_event_lines(_read_otrf_file(path)),
                    technique or _technique_from_path(path))


def load_otrf_corpus(directory: str | Path, gap_minutes: int = 30) -> Dataset:
    """
    OTRF korpusas: manifest.csv (file, techniques, title) ir failai šalia jo.
    Failai sudedami vienas po kito į bendrą laiko ašį (tarpas `gap_minutes` > taisyklių
    langas ir cooldown), failo viduje išlaikant originalius tarpus tarp įvykių; kiekvienas
    failas — vienas atakos intervalas su jo technikomis.
    """
    directory = Path(directory)
    with open(directory / "manifest.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    events, attacks, cursor = [], [], _BASE
    for row in rows:
        techniques = row["techniques"].split()
        timed = _timed(_otrf_event_lines(_read_otrf_file(directory / row["file"])))
        if not timed:
            continue
        shift = cursor - min(ts for ts, _ in timed)
        part = [_event(ts + shift, line, techniques) for ts, line in timed]
        end = max(e.ts for e in part)
        attacks.append(AttackInterval(name=row.get("title") or row["file"], start=cursor,
                                      end=end, techniques=techniques))
        events.extend(part)
        cursor = end + datetime.timedelta(minutes=gap_minutes)
    return Dataset(name=directory.name, events=events, attacks=attacks, start=_BASE, end=cursor)


def load(kind: str, path: str | Path, technique: str | None = None) -> Dataset:
    if kind == "evtx":
        return load_evtx(path, technique)
    if kind == "otrf":
        return load_otrf_corpus(path) if Path(path).is_dir() else load_otrf(path, technique)
    raise ValueError(f"Nežinomas Windows adapterio tipas: {kind}")
