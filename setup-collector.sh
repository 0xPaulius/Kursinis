#!/usr/bin/env bash
# Kolektoriaus paruošimas realiam biurui vienu žingsniu (ne demonstracijai):
#
#   ./setup-collector.sh 192.168.1.10        # fiksuotas kolektoriaus IP arba DNS vardas
#
# Sukuria .env su atsitiktiniais slaptažodžiais, CA ir serverio sertifikatą, įjungia TLS 6514,
# paruošia Windows/Linux diegimo paketus ir paleidžia stack'ą gamybiniu režimu
# (docker-compose.prod.yml). .env gauna COMPOSE_FILE ir COMPOSE_PROFILES, todėl ir vėlesnės
# `docker compose ...` komandos naudoja tuos pačius nustatymus. Kartoti saugu.
# Grįžti į demonstracinį režimą: ištrinkite COMPOSE_FILE ir COMPOSE_PROFILES eilutes iš .env.
set -euo pipefail
cd "$(dirname "$0")"
addr="${1:?Nurodykite kolektoriaus IP arba DNS vardą, pvz. $0 192.168.1.10}"

for cmd in docker openssl curl python3; do
  command -v "$cmd" >/dev/null || { echo "Trūksta programos: $cmd" >&2; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "Docker neveikia: sudo systemctl enable --now docker" >&2; exit 1; }

env_get() { sed -n "s/^$1=//p" .env | tail -n 1; }
env_set() {
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else printf '%s=%s\n' "$1" "$2" >> .env; fi
}

echo "[1/5] .env"
[ -f .env ] || cp .env.example .env
generated=()
for key in GF_SECURITY_ADMIN_PASSWORD DASHBOARD_ADMIN_PASSWORD DASHBOARD_SECRET_KEY; do
  case "$(env_get "$key")" in
    ""|CHANGE_ME|admin123) env_set "$key" "$(openssl rand -hex 16)"; generated+=("$key") ;;
  esac
done
env_set COMPOSE_FILE docker-compose.yml:docker-compose.prod.yml
env_set COMPOSE_PROFILES anomaly,endpoints
chmod 600 .env

echo "[2/5] Sertifikatai"
tools/gen-certs.sh ca
if [[ "$addr" =~ ^[0-9.]+$ || "$addr" == *:* ]]; then want="IP Address:$addr"; else want="DNS:$addr"; fi
openssl x509 -in certs/collector.crt -noout -ext subjectAltName 2>/dev/null | tr ',' '\n' \
  | sed 's/^ *//' | grep -xF "$want" >/dev/null || tools/gen-certs.sh server "$addr"
env_set CERTS_GID "$(stat -c %g certs/server/collector.key)"   # Grafana raktą skaito per šią grupę

echo "[3/5] TLS 6514 (Linux, macOS)"
[ -f config/syslog-ng/conf.d/tls.conf ] \
  || cp config/syslog-ng/conf.d/tls.conf.example config/syslog-ng/conf.d/tls.conf

echo "[4/5] Diegimo paketai"
tools/gen-certs.sh bundle "$addr"

echo "[5/5] Paleidimas"
docker compose up -d --build
# up -d nemato sertifikatų ir tls.conf turinio pakeitimų
docker compose restart syslog-ng alloy-gateway dashboard grafana
docker compose ps --format 'table {{.Service}}\t{{.Status}}'

cat <<EOF

Kolektorius paruoštas (gamybinis režimas).
  Dashboard: https://$addr:8080  (vartotojas: $(env_get DASHBOARD_ADMIN_USER))
  Grafana:   https://$addr:3000  (vartotojas: admin)
  Naršyklės įspėjimas dings, kai administratorių kompiuteriuose certs/ca.crt
  įdiegsite kaip patikimą šakninę CA.
EOF
for key in "${generated[@]}"; do
  [ "$key" = DASHBOARD_SECRET_KEY ] || echo "  Naujas slaptažodis (saugomas .env): $key=$(env_get "$key")"
done
cat <<EOF

Įrenginiai (README: „Galinių įrenginių prijungimas"):
  Windows:          certs/bundles/kursinis-windows.zip, administratoriaus PowerShell: install.ps1
  Linux:            certs/bundles/kursinis-linux.tar.gz, sudo ./setup.sh
  Maršrutizatorius: syslog į $addr:514 (UDP)
  Ugniasienėje 514, 6514 ir 3500 leiskite tik iš biuro tinklo.

Jei dashboard jau veikė anksčiau: slaptažodis iš .env galioja tik naujai vartotojų bazei
(docker compose exec dashboard python -m app.manage_users passwd admin), o seni
demonstraciniai įrenginiai lieka, kol jų neištrinsite Įrenginių skiltyje.
EOF
