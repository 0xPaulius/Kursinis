"""
Rezultatų ataskaita darbui: LaTeX (booktabs) lentelės ir laiko juostos grafikas.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

_LAYER_NAMES = {"rule": "Taisyklės", "statistical": "Statistinis", "ml": "ML",
                "combined": "Bendras"}


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def layers_table(metrics: dict, caption: str, label: str, key: str = "layers") -> str:
    rows = []
    for layer, name in _LAYER_NAMES.items():
        m = metrics[key][layer]
        lo, hi = m["f1_ci95"]
        rows.append(
            f"{name} & {_fmt(m['precision'])} & {_fmt(m['recall'])} & {_fmt(m['f1'])} "
            f"[{_fmt(lo)}; {_fmt(hi)}] & {_fmt(m['fpr'])} & {m['tp']}/{m['fp']}/{m['fn']} \\\\"
        )
    return "\n".join([
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Sluoksnis & Precision & Recall & F1 [95\,\% CI] & FPR & TP/FP/FN \\",
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def attacks_table(metrics: dict, caption: str, label: str) -> str:
    def cell(entry: dict) -> str:
        if not entry["detected"]:
            return "--"
        return f"{entry['latency_s'] / 60:.1f} min"

    rows = [
        f"{row['name'].replace('_', r'\_')} & {cell(row['rule'])} & {cell(row['statistical'])} "
        f"& {cell(row['ml'])} \\\\"
        for row in metrics["per_attack"]
    ]
    return "\n".join([
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Atakos fazė & Taisyklės & Statistinis & ML \\",
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def technique_table(metrics: dict, caption: str, label: str) -> str:
    """RQ2: ATT&CK technikų aptikimas (tik rinkiniams su technikomis)."""
    tr = metrics.get("technique_recall", {})
    rows = [
        f"{r['technique']} & {'taip' if r.get('has_rule') else '--'} "
        f"& {r.get('detected_mapped', 0)}/{r['intervals']} "
        f"& {', '.join(a.replace('_', r'\_') for a in r['alert_types']) or '--'} \\\\"
        for r in tr.get("techniques", [])
    ]
    header = (rf"\multicolumn{{4}}{{l}}{{Aptikta atitinkama taisykle {tr.get('detected_mapped', 0)}"
              rf"/{tr.get('total', 0)} technikų (taisyklė yra {tr.get('with_rule', 0)})}} \\"
              + "\n" + r"\midrule")
    return "\n".join([
        r"\begin{table}[H]", r"\centering", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
        r"\begin{tabular}{llll}", r"\toprule",
        r"Technika & Taisyklė & Aptikta (intervalai) & Visi alert tipai \\", r"\midrule", header,
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}",
    ])


def timeline_figure(ticks_path: Path, meta_path: Path, out_path: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    meta = json.loads(Path(meta_path).read_text())
    rows = [json.loads(line) for line in open(ticks_path) if line.strip()]
    fig, ax = plt.subplots(figsize=(10, 3.2))
    for iv in meta["attack_intervals"]:
        ax.axvspan(datetime.datetime.fromisoformat(iv["start"]),
                   datetime.datetime.fromisoformat(iv["end"]) + datetime.timedelta(minutes=1),
                   color="tab:red", alpha=0.25)
    for y, (layer, color) in enumerate([("rule", "tab:blue"), ("statistical", "tab:orange"),
                                        ("ml", "tab:green")]):
        xs = [datetime.datetime.fromisoformat(r["t"]) for r in rows
              if any(a["detection_method"] == layer for a in r["raw"])]
        ax.scatter(xs, [y] * len(xs), s=6, color=color, label=_LAYER_NAMES[layer])
    ax.set_yticks([0, 1, 2], [_LAYER_NAMES["rule"], _LAYER_NAMES["statistical"], _LAYER_NAMES["ml"]])
    ax.set_ylim(-0.6, 2.6)
    ax.set_xlabel("Laikas (UTC); raudonai — atakų fazės")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    fig.savefig(out_path.with_suffix(".png"), dpi=130)
    plt.close(fig)
    return out_path


def write_report(metrics_path: Path, ticks_path: Path, meta_path: Path, out_dir: Path) -> list[Path]:
    metrics = json.loads(Path(metrics_path).read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    name = metrics["dataset"]
    safe = name.replace("_", "-")
    written = []
    tables = out_dir / "tables.tex"
    sections = [
        layers_table(metrics, f"Aptikimo sluoksnių tikslumas ({name.replace('_', r'\_')})",
                     f"tab:eval-{safe}"),
    ]
    if "layers_windowed" in metrics:
        sections.append(layers_table(
            metrics, f"Aptikimo sluoksnių tikslumas nepersidengiančiuose "
                     f"{metrics['window_minutes']} min languose ({name.replace('_', r'\_')})",
            f"tab:eval-windowed-{safe}", key="layers_windowed"))
    sections += [
        attacks_table(metrics, f"Atakų fazių aptikimo vėlinimas ({name.replace('_', r'\_')})",
                      f"tab:eval-attacks-{safe}"),
    ]
    if metrics.get("technique_recall", {}).get("total"):
        sections.append(technique_table(
            metrics, f"ATT\\&CK technikų aptikimas ({name.replace('_', r'\_')})",
            f"tab:eval-attack-coverage-{safe}"))
    tables.write_text("\n\n".join(sections) + "\n")
    written.append(tables)
    figure = timeline_figure(ticks_path, meta_path, out_dir / "timeline.pdf")
    if figure:
        written.append(figure)
    return written
