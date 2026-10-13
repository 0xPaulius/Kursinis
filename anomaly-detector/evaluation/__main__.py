"""
Vertinimo CLI.

  python -m evaluation fetch  ait --scenario russellmitchell
  python -m evaluation fetch  otrf
  python -m evaluation ingest ait --scenario-dir /datasets/ait/russellmitchell --dataset ait-russellmitchell
  python -m evaluation ingest otrf --scenario-dir /datasets/otrf --dataset otrf-windows
  python -m evaluation run    --dataset ait-russellmitchell --run-id baseline
  python -m evaluation score  --dataset ait-russellmitchell --run-id baseline
  python -m evaluation report --dataset ait-russellmitchell --run-id baseline

Rezultatai: <results>/<dataset>/meta.json ir <results>/<dataset>/runs/<run-id>/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_LOKI = os.getenv("LOKI_URL", "http://loki-eval:3100")
DEFAULT_RESULTS = os.getenv("EVAL_RESULTS", "/results")
DEFAULT_DATASETS = os.getenv("EVAL_DATASETS", "/datasets")


def _dataset_dir(args) -> Path:
    return Path(args.results) / args.dataset


def _run_dir(args) -> Path:
    return _dataset_dir(args) / "runs" / args.run_id


def cmd_fetch(args) -> None:
    from .fetch import fetch_ait, fetch_otrf
    dest = Path(args.dest or Path(DEFAULT_DATASETS) / args.source)
    if args.source == "otrf":
        fetch_otrf(dest)
    elif args.scenario:
        fetch_ait(args.scenario, dest)
    else:
        sys.exit("fetch ait: reikia --scenario")


def cmd_ingest(args) -> None:
    from .fetch import dataset_hash
    from .ingest import push, write_meta
    adapter = args.adapter
    if adapter == "ait":
        from .adapters import ait
        sources = args.sources or ait.DEFAULT_SOURCES
        ds = ait.load(args.scenario_dir, sources=sources)
    elif adapter in ("evtx", "otrf"):
        from .adapters import windows
        sources = [adapter]
        ds = windows.load(adapter, args.scenario_dir, technique=args.technique)
    else:
        sys.exit(f"Nežinomas adapteris: {adapter}")
    sent = push(ds, args.loki, args.dataset)
    meta = write_meta(ds, args.dataset, _dataset_dir(args), sources,
                      dataset_hash(Path(args.scenario_dir)), sent)
    print(f"{args.dataset}: {len(ds.events)} įvykių ({sent} Loki įrašų), "
          f"{sum(e.is_attack for e in ds.events)} atakos, {len(ds.attacks)} fazės -> {meta}")


def cmd_run(args) -> None:
    from .runner import run
    ticks = run(_dataset_dir(args) / "meta.json", args.loki, _run_dir(args),
                step_seconds=args.step, enable_ml=args.ml, ml_every=args.ml_every)
    print(f"Ciklai įrašyti: {ticks}")


def cmd_score(args) -> None:
    from .metrics import score
    run_dir = _run_dir(args)
    result = score(run_dir / "ticks.jsonl", _dataset_dir(args) / "meta.json",
                   window_minutes=args.window, bootstrap=args.bootstrap)
    (run_dir / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    for layer, m in result["layers"].items():
        print(f"{layer:12s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
              f"FPR={m['fpr']:.4f} TP/FP/FN={m['tp']}/{m['fp']}/{m['fn']}")


def cmd_report(args) -> None:
    from .report import write_report
    run_dir = _run_dir(args)
    for path in write_report(run_dir / "metrics.json", run_dir / "ticks.jsonl",
                             _dataset_dir(args) / "meta.json", run_dir / "report"):
        print(path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="evaluation")
    parser.add_argument("--loki", default=DEFAULT_LOKI)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch")
    p.add_argument("source", choices=["ait", "otrf"])
    p.add_argument("--scenario", help="AIT scenarijus")
    p.add_argument("--dest", help="Numatyta: <datasets>/<source>")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("ingest")
    p.add_argument("adapter", choices=["ait", "evtx", "otrf"])
    p.add_argument("--scenario-dir", required=True,
                   help="AIT scenarijaus katalogas, .evtx/.json failas arba OTRF korpuso katalogas")
    p.add_argument("--dataset", required=True)
    p.add_argument("--sources", nargs="*", help="AIT failų šablonai (numatyta: auth, syslog, apache)")
    p.add_argument("--technique", help="ATT&CK ID Windows rinkiniams (jei nenustatyta iš kelio)")
    p.set_defaults(func=cmd_ingest)

    for name, func in (("run", cmd_run), ("score", cmd_score), ("report", cmd_report)):
        p = sub.add_parser(name)
        p.add_argument("--dataset", required=True)
        p.add_argument("--run-id", required=True)
        if name == "run":
            p.add_argument("--step", type=int, default=60, help="Ciklo žingsnis sekundėmis")
            p.add_argument("--ml", action="store_true", help="Įjungti ML sluoksnį")
            p.add_argument("--ml-every", type=int, default=5)
        if name == "score":
            p.add_argument("--window", type=int, default=5, help="Tiesos lango dydis minutėmis")
            p.add_argument("--bootstrap", type=int, default=1000)
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
