#!/usr/bin/env python3
"""
OTRF Security Datasets manifestas vertinimui (RQ2).

Iš vietinės OTRF repozitorijos metaduomenų užrašų
(docs/notebooks/atomic/windows/**/SDWIN-*.ipynb) paima pavadinimą, ATT&CK technikas
(eilutė „Techniques") ir Host rinkinių nuorodas, ir rašo CSV, kurį naudoja
`python -m evaluation fetch otrf` bei OTRF korpuso adapteris. Technikų žymės yra
OTRF autorių, ne šio darbo.

  python tools/build_otrf_manifest.py <OTRF repo> > anomaly-detector/evaluation/manifests/otrf_windows_host.csv

Repozitorija turi būti toje pačioje revizijoje kaip OTRF_COMMIT (evaluation/fetch.py).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

_TECHNIQUE = re.compile(r"\[(T(?!0000)\d{4}(?:\.\d{3})?)\]")  # T0000 — OTRF vietos žymė
_LINK = re.compile(r"\[(https?://[^\]]+)\]")
_PREFIX = "datasets/atomic/windows/"


def parse(notebook: Path) -> list[dict]:
    cells = json.loads(notebook.read_text())["cells"]
    markdown = ["".join(c["source"]) for c in cells if c["cell_type"] == "markdown"]
    title = next((m[2:].strip() for m in markdown if m.startswith("# ")), notebook.stem)
    lines = "\n".join(markdown).splitlines()
    techniques = sorted({t for line in lines if line.startswith("| Techniques")
                         for t in _TECHNIQUE.findall(line)})
    files = [url.split(_PREFIX, 1)[1] for line in lines if re.match(r"\|\s*Host\s*\|", line)
             for url in _LINK.findall(line) if _PREFIX in url and "/network/" not in url]
    return [{"file": f, "techniques": " ".join(techniques), "title": title, "sdwin": notebook.stem}
            for f in files]


def main(repo: str) -> None:
    rows: dict[str, dict] = {}
    skipped = 0
    for notebook in sorted(Path(repo, "docs/notebooks/atomic/windows").rglob("SDWIN-*.ipynb")):
        for row in parse(notebook):
            if not row["techniques"]:
                skipped += 1
                continue
            rows.setdefault(row["file"], row)
    writer = csv.DictWriter(sys.stdout, fieldnames=["file", "techniques", "title", "sdwin"])
    writer.writeheader()
    writer.writerows(rows[f] for f in sorted(rows))
    print(f"{len(rows)} rinkiniai, praleista be technikų: {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
