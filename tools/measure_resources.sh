#!/usr/bin/env bash
# RQ4: stack'o išteklių matavimas per `docker stats` -> CSV.
# Matuoja RAM/CPU kiekvienam konteineriui + Loki srautų skaičių laikui bėgant,
# kad būtų galima palyginti bazinį stack'ą su Windows/Sysmon telemetrija (pilna vs apkarpyta).
#
#   tools/measure_resources.sh                         # 60 x 10s = 10 min į resources-<ts>.csv
#   DURATION=1800 INTERVAL=15 OUT=full.csv tools/measure_resources.sh
#
# Palyginimui: paleiskite be endpoint'ų, po to su `--profile endpoints` ir Windows VM.
set -euo pipefail
INTERVAL="${INTERVAL:-10}"
DURATION="${DURATION:-600}"
OUT="${OUT:-resources-$(date +%Y%m%d-%H%M%S).csv}"
LOKI="${LOKI:-http://localhost:3100}"
PROJECT="${COMPOSE_PROJECT_NAME:-kursinis}"

echo "timestamp,container,cpu_pct,mem_used_mb,mem_pct,loki_streams" > "$OUT"
end=$(( $(date +%s) + DURATION ))
echo "[*] Matuojama kas ${INTERVAL}s iki $(date -d "@$end" 2>/dev/null || echo "+${DURATION}s") -> $OUT"

while [ "$(date +%s)" -lt "$end" ]; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # Loki aktyvių srautų skaičius (indekso kardinalumas — RAM pagrindinis veiksnys).
  streams=$(curl -s "${LOKI}/metrics" 2>/dev/null \
    | awk -F' ' '/^loki_ingester_memory_streams / {sum+=$2} END {printf "%d", sum}')
  streams="${streams:-NA}"
  # Vienkartinis docker stats momentas visiems projekto konteineriams.
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' \
    | grep -E "^(${PROJECT}[-_]|syslog-ng|loki|grafana|alloy|anomaly-detector|dashboard|loki-eval)" \
    | while IFS=',' read -r name cpu memusage mempct; do
        mem_mb=$(echo "$memusage" | awk '{
          v=$1; unit=$1;
          sub(/[0-9.]+/,"",unit); sub(/[A-Za-z]+/,"",v);
          if (unit ~ /GiB/) v*=1024; else if (unit ~ /KiB/) v/=1024;
          printf "%.1f", v }')
        echo "${ts},${name},${cpu//%/},${mem_mb},${mempct//%/},${streams}" >> "$OUT"
      done
  sleep "$INTERVAL"
done
echo "[OK] $OUT"
echo "Vidurkis MB pagal konteinerį:"
awk -F',' 'NR>1 {s[$2]+=$4; n[$2]++} END {for (c in s) printf "  %-22s %8.1f MB\n", c, s[c]/n[c]}' "$OUT" | sort
