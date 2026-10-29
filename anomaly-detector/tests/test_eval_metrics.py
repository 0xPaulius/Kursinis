"""
Vertinimo metrikų testai su sintetiniais ciklais.
"""
from __future__ import annotations

import datetime
import json

import numpy as np

from evaluation import metrics

T0 = datetime.datetime(2022, 1, 24, 3, 0, tzinfo=datetime.timezone.utc)


def _tick(minute: int, methods: list[str]) -> dict:
    alerts = [{"detection_method": m, "alert_type": f"{m}_x"} for m in methods]
    return {"t": (T0 + datetime.timedelta(minutes=minute)).isoformat(), "raw": alerts, "new": alerts}


def test_tick_truth_uses_trailing_window():
    ticks = [_tick(m, []) for m in range(0, 20)]
    attack = (T0 + datetime.timedelta(minutes=7, seconds=30)).timestamp()
    truth = metrics.tick_truth(ticks, [attack], window_s=300)
    # Positive for ticks whose window (t-5min, t] contains 07:30 -> minutes 8..12
    assert list(np.nonzero(truth)[0]) == [8, 9, 10, 11, 12]


def test_confusion_and_rates():
    pred = np.array([True, True, False, False, True])
    truth = np.array([True, False, True, False, False])
    m = metrics.confusion(pred, truth)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 2, 1, 1)
    assert m["precision"] == 1 / 3 and m["recall"] == 0.5
    assert m["fpr"] == 2 / 3


def test_mcnemar_counts_discordant_pairs():
    truth = np.array([True, True, False, False])
    a = np.array([True, True, False, True])    # 3 teisingi
    b = np.array([False, True, False, False])  # 3 teisingi, kitur
    result = metrics.mcnemar(a, b, truth)
    assert result["a_only_correct"] == 1 and result["b_only_correct"] == 1
    assert result["p_value"] == 1.0


def test_window_index_and_pool_merge_ticks_into_disjoint_windows():
    ticks = [_tick(m, []) for m in range(12)]
    idx = metrics.window_index(ticks, window_s=300)
    assert list(idx) == [0] * 5 + [1] * 5 + [2] * 2
    values = np.zeros(12, dtype=bool)
    values[6] = True
    assert list(metrics.pool(values, idx)) == [False, True, False]


def test_score_mcnemar_counts_a_false_alarm_burst_once_per_window(tmp_path):
    ticks = [_tick(m, ["ml"] if 20 <= m < 25 else []) for m in range(60)]
    (tmp_path / "ticks.jsonl").write_text("\n".join(json.dumps(t) for t in ticks))
    (tmp_path / "meta.json").write_text(json.dumps(
        {"dataset": "t", "attack_event_times": [], "attack_intervals": []}))
    result = metrics.score(tmp_path / "ticks.jsonl", tmp_path / "meta.json", bootstrap=10)
    assert result["windows"] == 12
    assert result["mcnemar_ml_vs_statistical"]["b_only_correct"] == 1
    assert result["layers"]["ml"]["fp"] == 5 and result["layers_windowed"]["ml"]["fp"] == 1


def test_per_attack_latency_per_layer():
    ticks = [_tick(m, ["statistical"] if m == 12 else []) for m in range(0, 30)]
    interval = {"name": "scan", "start": (T0 + datetime.timedelta(minutes=10)).isoformat(),
                "end": (T0 + datetime.timedelta(minutes=11)).isoformat()}
    row = metrics.per_attack([interval], ticks, window_s=300)[0]
    assert row["statistical"] == {"detected": True, "latency_s": 120.0}
    assert row["rule"] == {"detected": False, "latency_s": None}


def test_bootstrap_ci_bounds_contain_point_estimate():
    rng = np.random.default_rng(0)
    truth = rng.random(600) < 0.2
    pred = truth ^ (rng.random(600) < 0.1)
    point = metrics.confusion(pred, truth)["f1"]
    lo, hi = metrics.block_bootstrap_ci(pred, truth, "f1", block=30, n_boot=200)
    assert lo <= point <= hi
