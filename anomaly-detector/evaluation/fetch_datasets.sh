#!/usr/bin/env bash
# Vertinimo rinkinių atsisiuntimas į ./datasets (evaluator konteineriu).
#
#   anomaly-detector/evaluation/fetch_datasets.sh [ait-scenarijus ...]   (numatyta: russellmitchell)
#
# AIT-LDS v2.0 (CC BY-NC-SA 4.0, doi:10.5281/zenodo.5789064): iš scenarijaus ZIP per
# HTTP Range ištraukiami tik reikalingi failai (~45 MB vietoj 7–27 GB), kiekvienas
# tikrinamas CRC32, o rezultatui sukuriamas MANIFEST.sha256 (patikrinamas žemiau).
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p datasets eval-results

scenarios=("$@")
[ ${#scenarios[@]} -eq 0 ] && scenarios=(russellmitchell)

for scenario in "${scenarios[@]}"; do
  docker compose --profile eval run --rm --no-deps evaluator fetch ait --scenario "$scenario"
  (cd "datasets/ait/$scenario" && sha256sum --quiet -c MANIFEST.sha256) \
    && echo "$scenario: MANIFEST.sha256 OK"
done

# Windows ATT&CK rinkiniai (neprivaloma: WINDOWS=1). „Vien atakos" — per-technique recall,
# ne FPR. OTRF korpusas (manifests/otrf_windows_host.csv, ~55 MB):
#   python -m evaluation ingest otrf --scenario-dir /datasets/otrf --dataset otrf-windows
# Pavieniai EVTX failai: python -m evaluation ingest evtx --scenario-dir <failas> --dataset <vardas>
if [ "${WINDOWS:-0}" = "1" ]; then
  docker compose --profile eval run --rm --no-deps evaluator fetch otrf
  (cd datasets/otrf && sha256sum --quiet -c MANIFEST.sha256) && echo "otrf: MANIFEST.sha256 OK"
  git -C datasets clone --depth 1 https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES.git 2>/dev/null \
    || git -C datasets/EVTX-ATTACK-SAMPLES pull --ff-only
fi

echo
echo "Licencijos:"
echo "  AIT-LDS v2.0 — CC BY-NC-SA 4.0: naudojimas tik nekomerciniais tikslais, su autorystės nuoroda"
echo "  (M. Landauer et al., 'Maintainable Log Datasets for Evaluation of Intrusion Detection Systems', 2022)."
echo "  OTRF Security-Datasets — MIT License (Open Threat Research Forge)."
echo "  EVTX-ATTACK-SAMPLES (sbousseaden) — žr. jo LICENSE prieš naudojimą."
