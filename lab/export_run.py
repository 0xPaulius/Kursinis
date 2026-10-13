#!/usr/bin/env python3
"""
Eksportuoja gyvo lab paleidimo laiko langą iš veikiančio Loki ir paruošia jį
atkartojamam vertinimui per loki-eval (atkartojamas RQ1/RQ2 scoringas be VM).

Žingsniai:
  1. perskaito ground_truth.json (lab/collect_ground_truth.py);
  2. iš gyvo Loki ištraukia visus {job=~"syslog|security|errors|windows"} įrašus
     lange [min(start)-pad, max(end)+pad] (žingsniuojant, kad apeitų 5000 ribą);
  3. įrašo datasets/lab/<dataset>/events.jsonl (ts_ns, labels, line) — archyvui;
  4. įkelia juos į loki-eval su dataset="<dataset>" etikete;
  5. parašo eval meta.json (attack_intervals + attack_event_times iš intervalų),
     tad `python -m evaluation run/score --dataset <dataset>` veikia iš karto.

  lab/export_run.py --dataset lab-2022 --ground-truth ground_truth.json \
      --live-loki http://localhost:3100 --eval-loki http://localhost:3101

Pastaba: lab duomenys neturi eilučių lygmens žymių, tad „tiesa" cikle yra
intervalo persidengimas — attack_event_times gaunami tolygiai imant intervalą.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from pathlib import Path

import requests

UTC = datetime.timezone.utc
JOBS = '{job=~"syslog|security|errors|windows"}'


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


def fetch_window(loki: str, start: datetime.datetime, end: datetime.datetime,
                 step_minutes: int = 5) -> list[tuple[int, dict, str]]:
    """Ištraukia visus įrašus [start,end] žingsniuojant po `step_minutes` (apeina 5000 ribą)."""
    session = requests.Session()
    url = loki.rstrip("/") + "/loki/api/v1/query_range"
    out: list[tuple[int, dict, str]] = []
    seen: set[tuple[int, str]] = set()
    cur = start
    step = datetime.timedelta(minutes=step_minutes)
    while cur < end:
        upper = min(cur + step, end)
        resp = session.get(url, params={
            "query": JOBS, "start": int(cur.timestamp() * 1e9),
            "end": int(upper.timestamp() * 1e9), "limit": 5000, "direction": "forward",
        }, timeout=60)
        resp.raise_for_status()
        for stream in resp.json().get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for ts_ns, line in stream.get("values", []):
                key = (int(ts_ns), line)
                if key not in seen:
                    seen.add(key)
                    out.append((int(ts_ns), labels, line))
        cur = upper
    out.sort(key=lambda r: r[0])
    return out


def push(eval_loki: str, rows: list[tuple[int, dict, str]], dataset: str,
         batch: int = 2000) -> int:
    url = eval_loki.rstrip("/") + "/loki/api/v1/push"
    session = requests.Session()
    by_stream: dict[tuple, list[list[str]]] = {}
    for ts_ns, labels, line in rows:
        key = tuple(sorted({**labels, "dataset": dataset}.items()))
        by_stream.setdefault(key, []).append([str(ts_ns), line])
    sent = 0
    for key, values in by_stream.items():
        labels = dict(key)
        for i in range(0, len(values), batch):
            chunk = values[i:i + batch]
            for attempt in range(5):
                r = session.post(url, json={"streams": [{"stream": labels, "values": chunk}]}, timeout=120)
                if r.status_code in (200, 204):
                    break
                if r.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"loki-eval push {r.status_code}: {r.text[:200]}")
            sent += len(chunk)
    return sent


def sample_times(intervals: list[dict], every_seconds: int = 30) -> list[float]:
    """Intervalus paverčia atskiromis „atakos" laiko žymomis (tick tiesai metrics.py)."""
    times: list[float] = []
    for iv in intervals:
        start, end = _parse(iv["start"]).timestamp(), _parse(iv["end"]).timestamp()
        t = start
        while t < end:
            times.append(t)
            t += every_seconds
        times.append(end)
    return sorted(set(times))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--live-loki", default=os.getenv("LIVE_LOKI", "http://localhost:3100"))
    ap.add_argument("--eval-loki", default=os.getenv("LOKI_URL", "http://localhost:3101"))
    ap.add_argument("--results", default=os.getenv("EVAL_RESULTS", "eval-results"))
    ap.add_argument("--datasets", default=os.getenv("EVAL_DATASETS", "datasets"))
    ap.add_argument("--pad-minutes", type=int, default=30)
    ap.add_argument("--no-push", action="store_true", help="tik eksportuoti JSONL, neįkelti į loki-eval")
    args = ap.parse_args(argv)

    gt = json.loads(Path(args.ground_truth).read_text())
    intervals = gt.get("intervals", [])
    if not intervals:
        return int(not print("Nėra intervalų ground_truth faile"))
    pad = datetime.timedelta(minutes=args.pad_minutes)
    start = min(_parse(i["start"]) for i in intervals) - pad
    end = max(_parse(i["end"]) for i in intervals) + pad

    rows = fetch_window(args.live_loki, start, end)
    ds_dir = Path(args.datasets) / "lab" / args.dataset
    ds_dir.mkdir(parents=True, exist_ok=True)
    with open(ds_dir / "events.jsonl", "w") as fh:
        for ts_ns, labels, line in rows:
            fh.write(json.dumps({"ts": ts_ns, "labels": labels, "line": line}, ensure_ascii=False) + "\n")

    sent = 0 if args.no_push else push(args.eval_loki, rows, args.dataset)

    attack_intervals = [{"name": i.get("name") or i.get("technique", "?"),
                         "start": _parse(i["start"]).isoformat(), "end": _parse(i["end"]).isoformat(),
                         "techniques": [i["technique"]] if i.get("technique") else []}
                        for i in intervals]
    meta = {
        "dataset": args.dataset,
        "source_name": f"lab live export ({args.ground_truth})",
        "start": start.isoformat(), "end": end.isoformat(),
        "sources": ["live-loki-export"], "dataset_hash": "live-export",
        "events": len(rows), "attack_events": len(sample_times(intervals)),
        "loki_entries": sent,
        "hosts": sorted({lbl.get("host", "") for _, lbl, _ in rows}),
        "attack_intervals": attack_intervals,
        "attack_event_times": sample_times(intervals),
        "ingested_at": datetime.datetime.now(UTC).isoformat(),
    }
    out_dir = Path(args.results) / args.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"{args.dataset}: {len(rows)} įrašų ({sent} į loki-eval), {len(intervals)} intervalai -> "
          f"{out_dir / 'meta.json'}")
    print("Toliau: python -m evaluation run --dataset {0} --run-id lab && "
          "python -m evaluation score --dataset {0} --run-id lab".format(args.dataset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
