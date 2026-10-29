#!/usr/bin/env python3
"""
Sujungia laboratorijos etaloninio žymėjimo (ground truth) failus į vieną ground_truth.json.

Šaltiniai (bet kuris kiekis, bet kuria tvarka):
  - Windows run-atomics.ps1  -> ground_truth-<runId>.json (JSON masyvas)
  - Kali attacks.sh          -> ground_truth.jsonl (JSON eilutės)
  - rankiniai intervalai     -> toks pat {technique,name,start,end,host} formatas

  lab/collect_ground_truth.py OUT.json FILE1 [FILE2 ...]

Rezultatas: {"intervals": [...], "start": ISO, "end": ISO, "techniques": [...]},
kurį naudoja lab/export_run.py (RQ1/RQ2 vertinimui per loki-eval).
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

UTC = datetime.timezone.utc


def _iso(value: str) -> str:
    """Normalizuoja laiko žymą į ISO UTC (priima 'Z', poslinkį arba be juostos)."""
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _records(path: Path) -> list[dict]:
    """Nuskaito JSON masyvą arba JSON eilutes (jsonl)."""
    text = path.read_text(errors="replace").strip()
    if not text:
        return []
    if text[0] == "[":
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def merge(files: list[Path]) -> dict:
    intervals: list[dict] = []
    for path in files:
        for rec in _records(path):
            if "start" not in rec or "end" not in rec:
                continue
            intervals.append({
                "technique": rec.get("technique", ""),
                "name": rec.get("name", rec.get("technique", "")),
                "start": _iso(rec["start"]),
                "end": _iso(rec["end"]),
                "host": rec.get("host", ""),
            })
    intervals.sort(key=lambda r: r["start"])
    techniques = sorted({r["technique"] for r in intervals if r["technique"]})
    return {
        "intervals": intervals,
        "techniques": techniques,
        "start": intervals[0]["start"] if intervals else None,
        "end": max((r["end"] for r in intervals), default=None),
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    out, files = Path(args[0]), [Path(p) for p in args[1:]]
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        sys.exit(f"Nerasti failai: {', '.join(missing)}")
    result = merge(files)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"{len(result['intervals'])} intervalai, {len(result['techniques'])} technikos "
          f"({result['start']} .. {result['end']}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
