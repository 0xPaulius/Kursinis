"""
Rinkinio įkėlimas į vertinimo Loki (loki-eval) su originaliomis laiko žymomis.

Kiekvienas įvykis atvaizduojamas lygiai taip, kaip jį pateiktų gyvas konvejeris
(syslog-ng šablonas + Alloy etiketės + job srautai), ir papildomai pažymimas
`dataset` etikete, kad keli rinkiniai galėtų gyventi tame pačiame Loki.
"""
from __future__ import annotations

import datetime
import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from .formatters import render_line, routed_jobs, stream_labels
from .schema import Dataset


def build_streams(ds: Dataset, dataset_label: str) -> dict[tuple, list[tuple[int, str]]]:
    streams: dict[tuple, list[tuple[int, str]]] = defaultdict(list)
    for ev in ds.events:
        ts_ns = int(ev.ts.timestamp() * 1e9)
        # Endpoint (Windows) įvykiai: žalia JSON eilutė su {job, host, channel} etiketėmis —
        # lygiai kaip juos pateiktų Alloy windowsevent + gateway (ne syslog šablonas).
        if ev.extra_labels:
            labels = dict({"job": ev.job, "host": ev.host, "dataset": dataset_label},
                          **ev.extra_labels)
            streams[tuple(sorted(labels.items()))].append((ts_ns, ev.message))
            continue
        line = render_line(ev)
        base = stream_labels(ev)
        for job in routed_jobs(ev):
            labels = dict(base, job=job, dataset=dataset_label)
            if job == "errors":
                labels.pop("facility", None)  # errors job neturi facility etiketės
            streams[tuple(sorted(labels.items()))].append((ts_ns, line))
    for entries in streams.values():
        entries.sort()
    return streams


def _post(session: requests.Session, url: str, payload: dict, retries: int = 6) -> None:
    for attempt in range(retries):
        resp = session.post(url, json=payload, timeout=120)
        if resp.status_code in (200, 204):
            return
        if resp.status_code in (429, 500, 502, 503, 504) and attempt + 1 < retries:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"Loki push klaida {resp.status_code}: {resp.text[:300]}")


def push(ds: Dataset, loki_url: str, dataset_label: str, batch_bytes: int = 2 * 1024 * 1024) -> int:
    """Siunčia srautus laiko tvarka; grąžina išsiųstų įrašų skaičių."""
    url = loki_url.rstrip("/") + "/loki/api/v1/push"
    session = requests.Session()
    sent = 0
    for key, entries in build_streams(ds, dataset_label).items():
        labels = dict(key)
        batch: list[list[str]] = []
        size = 0
        for ts_ns, line in entries:
            batch.append([str(ts_ns), line])
            size += len(line) + 32
            if size >= batch_bytes:
                _post(session, url, {"streams": [{"stream": labels, "values": batch}]})
                sent += len(batch)
                batch, size = [], 0
        if batch:
            _post(session, url, {"streams": [{"stream": labels, "values": batch}]})
            sent += len(batch)
    return sent


def write_meta(ds: Dataset, dataset_label: str, out_dir: Path, sources: list[str],
               dataset_hash: str, sent: int) -> Path:
    """Rinkinio metaduomenys ir ground truth, kurių reikia `run` ir `score` žingsniams."""
    out_dir.mkdir(parents=True, exist_ok=True)
    attack_ts = sorted(e.ts.timestamp() for e in ds.events if e.is_attack)
    meta = {
        "dataset": dataset_label,
        "source_name": ds.name,
        "start": ds.start.isoformat(),
        "end": ds.end.isoformat(),
        "sources": sources,
        "dataset_hash": dataset_hash,
        "events": len(ds.events),
        "attack_events": len(attack_ts),
        "loki_entries": sent,
        "hosts": sorted({e.host for e in ds.events}),
        "attack_intervals": [
            {"name": iv.name, "start": iv.start.isoformat(), "end": iv.end.isoformat(),
             "techniques": iv.techniques}
            for iv in ds.attacks
        ],
        "attack_event_times": attack_ts,
        "ingested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    path = out_dir / "meta.json"
    path.write_text(json.dumps(meta, indent=1))
    return path
