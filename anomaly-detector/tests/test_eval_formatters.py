"""
Vertinimo formatavimo atitiktis gyvam konvejeriui.

syslog_golden.json užfiksuotas paleidus repo konfigūracijas (syslog-ng -> promtail ->
loki) ir išsiuntus žinomus įvykius; vertinimo įkėlimas turi atkurti tas pačias
eilutes ir etiketes kiekvienam job srautui.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from evaluation.ingest import build_streams
from evaluation.schema import Dataset, Event

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "syslog_golden.json").read_text())


def _streams_for(case: dict) -> list[dict]:
    ev = case["event"]
    ts = datetime.datetime.fromisoformat(ev["ts"])
    event = Event(ts=ts, host=ev["host"], message=ev["message"], program=ev["program"],
                  pid=ev["pid"], facility=ev["facility"], severity=ev["severity"])
    ds = Dataset(name="golden", events=[event], attacks=[], start=ts, end=ts)
    out = []
    for key, entries in build_streams(ds, "golden").items():
        labels = dict(key)
        labels.pop("dataset")
        out.extend({"line": line, "labels": labels} for _, line in entries)
    return sorted(out, key=lambda s: s["labels"]["job"])


def test_golden_cases_cover_all_routes():
    jobs = {s["labels"]["job"] for case in GOLDEN["cases"] for s in case["streams"]}
    assert jobs == {"syslog", "security", "errors"}


def test_replayed_streams_match_live_pipeline():
    for case in GOLDEN["cases"]:
        assert _streams_for(case) == case["streams"], case["event"]["host"]
