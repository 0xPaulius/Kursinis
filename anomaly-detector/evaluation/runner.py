"""
Detektoriaus paleidimas virtualiu laikrodžiu per įkeltą rinkinį.

Naudojamas tas pats `Engine` kaip gyvame režime; skiriasi tik `now` (žingsniuoja per
rinkinio laikotarpį) ir selektoriai (apriboti `dataset` etikete). Kiekvieno ciklo
alertai (prieš ir po cooldown) rašomi į ticks.jsonl.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import common
from detector import Engine
from common import LokiClient, Selectors


def git_sha() -> str:
    if os.getenv("GIT_SHA"):
        return os.environ["GIT_SHA"]
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True,
                                      stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD"],
                           stderr=subprocess.DEVNULL).returncode == 1
    return f"{sha}-dirty" if dirty else sha


def run(meta_path: Path, loki_url: str, run_dir: Path, step_seconds: int = 60,
        enable_ml: bool = False, ml_every: int = 5) -> Path:
    meta = json.loads(Path(meta_path).read_text())
    start = datetime.datetime.fromisoformat(meta["start"])
    end = datetime.datetime.fromisoformat(meta["end"])
    dataset = meta["dataset"]

    logging.getLogger("anomaly-detector").setLevel(logging.WARNING)
    loki = LokiClient(loki_url)
    engine = Engine(
        loki,
        selectors=Selectors(extra_matchers=f'dataset="{dataset}"'),
        enable_ml=enable_ml,
        ml_every_n_cycles=ml_every,
        ml_state_dir=None,
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    ticks_path = run_dir / "ticks.jsonl"
    started = time.time()
    cycles = 0
    t = start + datetime.timedelta(seconds=step_seconds)
    with open(ticks_path, "w") as out:
        while t <= end:
            raw, new = engine.run_cycle(t)
            out.write(json.dumps({
                "t": t.isoformat(),
                "raw": [a.to_dict() for a in raw],
                "new": [a.to_dict() for a in new],
            }, ensure_ascii=False) + "\n")
            cycles += 1
            t += datetime.timedelta(seconds=step_seconds)

    (run_dir / "run.json").write_text(json.dumps({
        "dataset": dataset,
        "dataset_hash": meta.get("dataset_hash"),
        "meta": str(meta_path),
        "loki_url": loki_url,
        "step_seconds": step_seconds,
        "cycles": cycles,
        "enable_ml": enable_ml,
        "ml_every_n_cycles": ml_every,
        "params": {
            "SSH_BRUTE_THRESHOLD": common.SSH_BRUTE_THRESHOLD,
            "LOG_SPIKE_MULTIPLIER": common.LOG_SPIKE_MULTIPLIER,
            "ALERT_COOLDOWN_SECONDS": common.ALERT_COOLDOWN_SECONDS,
            "BASELINE_WINDOW_HOURS": getattr(common, "BASELINE_WINDOW_HOURS", None),
            "ML_TRAINING_MODE": getattr(common, "ML_TRAINING_MODE", None),
            "ML_MAX_TRAINING_SAMPLES": common.ML_MAX_TRAINING_SAMPLES,
            "ENABLE_WINDOWS_RULES": common.ENABLE_WINDOWS_RULES,
            "ENABLE_LINUX_RULES": common.ENABLE_LINUX_RULES,
        },
        "git_sha": git_sha(),
        "duration_seconds": round(time.time() - started, 1),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))
    return ticks_path
