"""
Aptikimo kokybės metrikos iš runner.py ticks.jsonl ir ingest meta.json.

Vienetas — detektoriaus ciklas (tick) laiko momentu t. Tick'as yra teigiamas
(ataka), jei lange (t - window, t] yra bent viena atakos žyma pažymėta eilutė;
prognozė teigiama, jei tame cikle sluoksnis iškėlė bent vieną alertą (prieš cooldown).

Kadangi gretimi tick'ai koreliuoti (persidengiantys langai), pasikliautinieji
intervalai skaičiuojami blokiniu bootstrap (blokas = 1 val.). ML sluoksnis veikia tik
kas N-tą ciklą, todėl sluoksniai lyginami nepersidengiančiuose `window` dydžio languose
(`layers_windowed` ir McNemar; langas teigiamas, jei teigiamas bent vienas jo tick'as).
"""
from __future__ import annotations

import bisect
import datetime
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

import attack_catalog

LAYERS: dict[str, set[str]] = {
    "rule": {"rule"},
    "statistical": {"statistical"},
    "ml": {"ml"},
    "combined": {"rule", "statistical", "ml"},
}


def load_ticks(path: Path) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def tick_truth(ticks: list[dict], attack_times: list[float], window_s: float) -> np.ndarray:
    """True, jei (t - window, t] yra bent viena atakos eilutė."""
    truth = np.zeros(len(ticks), dtype=bool)
    for i, tick in enumerate(ticks):
        t = datetime.datetime.fromisoformat(tick["t"]).timestamp()
        lo = bisect.bisect_right(attack_times, t - window_s)
        hi = bisect.bisect_right(attack_times, t)
        truth[i] = hi > lo
    return truth


def layer_predictions(ticks: list[dict], methods: set[str]) -> np.ndarray:
    return np.array([any(a["detection_method"] in methods for a in tick["raw"]) for tick in ticks])


def window_index(ticks: list[dict], window_s: float) -> np.ndarray:
    """Nepersidengiančio `window_s` lango numeris kiekvienam tick'ui."""
    times = np.array([datetime.datetime.fromisoformat(t["t"]).timestamp() for t in ticks])
    if not len(times):
        return np.zeros(0, dtype=int)
    return ((times - times[0]) // window_s).astype(int)


def pool(values: np.ndarray, index: np.ndarray) -> np.ndarray:
    """Langas teigiamas, jei teigiamas bent vienas jo tick'as."""
    out = np.zeros(int(index.max()) + 1 if len(index) else 0, dtype=bool)
    np.logical_or.at(out, index, values)
    return out


def confusion(pred: np.ndarray, truth: np.ndarray) -> dict:
    tp = int(np.sum(pred & truth))
    fp = int(np.sum(pred & ~truth))
    fn = int(np.sum(~pred & truth))
    tn = int(np.sum(~pred & ~truth))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision,
            "recall": recall, "f1": f1, "fpr": fpr}


def block_bootstrap_ci(pred: np.ndarray, truth: np.ndarray, metric: str, block: int = 60,
                       n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    """95 % CI blokiniu bootstrap (persidengiantys langai => tick'ai nėra nepriklausomi)."""
    n = len(pred)
    if n == 0:
        return (0.0, 0.0)
    block = max(1, min(block, n))
    starts = np.arange(0, n - block + 1)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    values = []
    for _ in range(n_boot):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.choice(starts, n_blocks)])[:n]
        values.append(confusion(pred[idx], truth[idx])[metric])
    lo, hi = np.percentile(values, [2.5, 97.5])
    return (float(lo), float(hi))


def mcnemar(pred_a: np.ndarray, pred_b: np.ndarray, truth: np.ndarray) -> dict:
    """Tikslus McNemar testas (binominis) poriniams teisingumams."""
    a_ok, b_ok = pred_a == truth, pred_b == truth
    b = int(np.sum(a_ok & ~b_ok))
    c = int(np.sum(~a_ok & b_ok))
    p = binomtest(min(b, c), b + c, 0.5).pvalue if b + c else 1.0
    return {"a_only_correct": b, "b_only_correct": c, "p_value": float(p)}


def per_attack(intervals: list[dict], ticks: list[dict], window_s: float) -> list[dict]:
    """Kiekvienai atakos fazei: ar aptikta (kuris sluoksnis) ir aptikimo vėlinimas."""
    times = [datetime.datetime.fromisoformat(t["t"]).timestamp() for t in ticks]
    rows = []
    for iv in intervals:
        start = datetime.datetime.fromisoformat(iv["start"]).timestamp()
        end = datetime.datetime.fromisoformat(iv["end"]).timestamp() + window_s
        lo, hi = bisect.bisect_left(times, start), bisect.bisect_right(times, end)
        row = {"name": iv["name"], "start": iv["start"], "end": iv["end"],
               "techniques": iv.get("techniques", [])}
        for layer, methods in LAYERS.items():
            hits = [times[i] for i in range(lo, hi)
                    if any(a["detection_method"] in methods for a in ticks[i]["raw"])]
            row[layer] = {"detected": bool(hits),
                          "latency_s": round(hits[0] - start, 1) if hits else None}
        rows.append(row)
    return rows


def _same_technique(a: str, b: str) -> bool:
    """Ta pati technika arba tėvinė technika ir jos sub-technika (T1110 ~ T1110.001)."""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def technique_recall(intervals: list[dict], ticks: list[dict], window_s: float) -> dict:
    """
    Per-technique aptikimas (RQ2 ATT&CK aprėptis).
    `detected` — bet kuriame technikos intervale iškeltas bet koks alertas;
    `detected_mapped` — kiek intervalų sukėlė alertą, kurio ATT&CK technika atitinka
    intervalo techniką; `has_rule` — kataloge yra taisyklė šiai technikai.
    """
    rule_techniques = attack_catalog.covered_techniques()
    times = [datetime.datetime.fromisoformat(t["t"]).timestamp() for t in ticks]
    by_tech: dict[str, dict] = {}
    for iv in intervals:
        for tech in iv.get("techniques", []):
            by_tech.setdefault(tech, {"technique": tech, "intervals": 0, "detected": False,
                                      "detected_mapped": 0, "alert_types": set()})
    for iv in intervals:
        techs = iv.get("techniques", [])
        if not techs:
            continue
        start = datetime.datetime.fromisoformat(iv["start"]).timestamp()
        end = datetime.datetime.fromisoformat(iv["end"]).timestamp() + window_s
        lo, hi = bisect.bisect_left(times, start), bisect.bisect_right(times, end)
        hits = [a for i in range(lo, hi) for a in ticks[i]["raw"]]
        for tech in techs:
            row = by_tech[tech]
            row["intervals"] += 1
            if hits:
                row["detected"] = True
                row["alert_types"].update(a["alert_type"] for a in hits)
            if any(_same_technique(tech, t) for a in hits for t in a.get("attack_techniques", [])):
                row["detected_mapped"] += 1
    rows = [{**v, "alert_types": sorted(v["alert_types"]),
             "has_rule": any(_same_technique(v["technique"], t) for t in rule_techniques)}
            for v in by_tech.values()]
    rows.sort(key=lambda r: r["technique"])
    return {"techniques": rows, "total": len(rows),
            "detected": sum(r["detected"] for r in rows),
            "detected_mapped": sum(r["detected_mapped"] > 0 for r in rows),
            "with_rule": sum(r["has_rule"] for r in rows)}


def alert_counts(ticks: list[dict]) -> dict:
    """Alertų kiekiai prieš ir po cooldown — operatoriaus apkrovai (alert fatigue)."""
    raw: dict[str, int] = {}
    new: dict[str, int] = {}
    for tick in ticks:
        for a in tick["raw"]:
            raw[a["alert_type"]] = raw.get(a["alert_type"], 0) + 1
        for a in tick["new"]:
            new[a["alert_type"]] = new.get(a["alert_type"], 0) + 1
    return {"raw": raw, "after_cooldown": new}


def score(ticks_path: Path, meta_path: Path, window_minutes: int = 5,
          bootstrap: int = 1000) -> dict:
    ticks = load_ticks(ticks_path)
    meta = json.loads(Path(meta_path).read_text())
    window_s = window_minutes * 60
    truth = tick_truth(ticks, sorted(meta["attack_event_times"]), window_s)

    layers = {}
    preds = {}
    for layer, methods in LAYERS.items():
        pred = layer_predictions(ticks, methods)
        preds[layer] = pred
        result = confusion(pred, truth)
        result["f1_ci95"] = block_bootstrap_ci(pred, truth, "f1", n_boot=bootstrap)
        result["fpr_ci95"] = block_bootstrap_ci(pred, truth, "fpr", n_boot=bootstrap)
        layers[layer] = result

    idx = window_index(ticks, window_s)
    w_truth = pool(truth, idx)
    w_preds = {layer: pool(pred, idx) for layer, pred in preds.items()}
    w_block = max(1, round(3600 / window_s))
    layers_windowed = {}
    for layer, w_pred in w_preds.items():
        result = confusion(w_pred, w_truth)
        result["f1_ci95"] = block_bootstrap_ci(w_pred, w_truth, "f1", block=w_block, n_boot=bootstrap)
        result["fpr_ci95"] = block_bootstrap_ci(w_pred, w_truth, "fpr", block=w_block, n_boot=bootstrap)
        layers_windowed[layer] = result

    return {
        "dataset": meta["dataset"],
        "ticks": len(ticks),
        "attack_ticks": int(truth.sum()),
        "window_minutes": window_minutes,
        "windows": len(w_truth),
        "layers": layers,
        "layers_windowed": layers_windowed,
        "mcnemar_ml_vs_statistical": mcnemar(w_preds["ml"], w_preds["statistical"], w_truth),
        "mcnemar_rule_vs_statistical": mcnemar(w_preds["rule"], w_preds["statistical"], w_truth),
        "per_attack": per_attack(meta["attack_intervals"], ticks, window_s),
        "technique_recall": technique_recall(meta["attack_intervals"], ticks, window_s),
        "alert_counts": alert_counts(ticks),
    }
