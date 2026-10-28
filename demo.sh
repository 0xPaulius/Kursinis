#!/usr/bin/env bash
# Pristatymo demonstracija prieš veikiantį stack'ą (docker compose --profile anomaly up -d).
#
#   ./demo.sh health      paslaugų būklė (be tokeno -> 401, su tokenu -> būklė)
#   ./demo.sh log         syslog eilutė -> syslog-ng -> Alloy -> Loki
#   ./demo.sh traffic     srautas per 5 min
#   ./demo.sh attack ssh  SSH brute-force (web-server-01)
#   ./demo.sh attack fw   ugniasienės DROP šuolis (router-01)
#   ./demo.sh attack full kombinuotas scenarijus
#   ./demo.sh alerts      naujausi alertai su ATT&CK technikomis
#   ./demo.sh coverage    ATT&CK aprėptis
#   ./demo.sh roles       viewer rolė: skaito, bet negali paleisti atakos
#
# Prisijungia admin vartotoju iš .env (DASHBOARD_ADMIN_USER / DASHBOARD_ADMIN_PASSWORD).
set -euo pipefail
cd "$(dirname "$0")"
URL="${DASHBOARD_URL:-http://localhost:8080}"
set -a; . ./.env; set +a

login() {
  curl -sf -X POST "$URL/api/auth/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$1\",\"password\":\"$2\"}" | jq -r .token
}
api() { curl -s -H "Authorization: Bearer $TOKEN" "$@"; }
TOKEN=$(login "${DASHBOARD_ADMIN_USER:-admin}" "${DASHBOARD_ADMIN_PASSWORD:?nustatykite .env}")

case "${1:-}" in
  health)
    echo "be tokeno: HTTP $(curl -s -o /dev/null -w '%{http_code}' "$URL/api/health/status")"
    api "$URL/api/health/status" | jq '{overall, services: [.services[] | {name, status}]}' ;;
  log)
    msg="Pristatymo testas $(date +%H:%M:%S)"
    TZ=UTC logger --server 127.0.0.1 --port 514 --udp --rfc3164 --tag demo-app "$msg"
    sleep 5
    docker compose exec -T loki wget -qO- \
      'http://localhost:3100/loki/api/v1/query_range?query=%7Bjob%3D%22syslog%22%2Cprogram%3D%22demo-app%22%7D&limit=3' \
      | jq -r '.data.result[] | "labels: \(.stream | {host, program, severity})\n\(.values[0][1])"' ;;
  traffic)
    api "$URL/api/traffic/current" | jq ;;
  attack)
    case "${2:-}" in ssh) a=ssh_bruteforce ;; fw) a=firewall_spike ;; full) a=full ;;
      *) echo "naudojimas: $0 attack ssh|fw|full" >&2; exit 1 ;; esac
    api -X POST "$URL/api/devices/demo/scenario" -H 'Content-Type: application/json' \
      -d "{\"attack\":\"$a\"}" | jq
    echo "Alertai po ~10 s: ./demo.sh alerts (tas pats alertas kartojamas ne dažniau nei kas 5 min)" ;;
  alerts)
    api "$URL/api/alerts/recent?limit=${2:-8}" \
      | jq -r '.alerts[] | "\(.timestamp[0:19])  \(.severity)  \(.alert_type)  \(.source_ip // "")  ATT&CK=\(.attack_techniques | join(","))"' ;;
  coverage)
    api "$URL/api/attack/coverage" | jq '{total, with_rule, detected}' ;;
  roles)
    pw="Viewer-$(date +%s)"
    docker compose exec -T dashboard python -m app.manage_users add demo-viewer --role viewer --password "$pw" >/dev/null
    VT=$(login demo-viewer "$pw")
    echo "viewer skaito alertus:    HTTP $(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $VT" "$URL/api/alerts/recent")"
    echo "viewer paleidžia ataką:   HTTP $(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $VT" \
      -H 'Content-Type: application/json' -d '{"attack":"ssh_bruteforce"}' "$URL/api/devices/demo/scenario")"
    docker compose exec -T dashboard python -m app.manage_users delete demo-viewer >/dev/null ;;
  *)
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
