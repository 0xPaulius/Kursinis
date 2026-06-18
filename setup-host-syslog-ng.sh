#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-host-syslog-ng.sh
# Sukonfigūruoja šio host'o syslog-ng persiuntimą į Kursinis kolektorių.
# Installs + configures host syslog-ng to forward ALL system logs (systemd
# journal) to the syslog-ng container, so this machine shows up in the
# dashboard Devices tab / traffic graphs.
#
# Naudojimas / usage:
#   sudo bash setup-host-syslog-ng.sh
#   sudo COLLECTOR_HOST=192.168.1.10 COLLECTOR_PORT=514 bash setup-host-syslog-ng.sh
# ---------------------------------------------------------------------------
set -euo pipefail

COLLECTOR_HOST="${COLLECTOR_HOST:-127.0.0.1}"   # 127.0.0.1 = kolektorius sukasi šiame host'e
COLLECTOR_PORT="${COLLECTOR_PORT:-514}"
CONF="/etc/syslog-ng/syslog-ng.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/config/syslog-ng-host/syslog-ng.conf"

if [[ $EUID -ne 0 ]]; then
  echo "Paleiskite kaip root: sudo bash $0" >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Nerastas šablonas: $TEMPLATE" >&2
  exit 1
fi

# 1. Įdiegti syslog-ng (oficialus repo — AUR nereikia)
if ! command -v syslog-ng >/dev/null 2>&1; then
  echo "[*] Diegiamas syslog-ng..."
  pacman -S --noconfirm --needed syslog-ng
else
  echo "[*] syslog-ng jau įdiegtas."
fi

# 2. Atsarginė pradinės konfigūracijos kopija (tik kartą)
if [[ -f "$CONF" && ! -f "${CONF}.kursinis.bak" ]]; then
  cp -a "$CONF" "${CONF}.kursinis.bak"
  echo "[*] Atsarginė kopija: ${CONF}.kursinis.bak"
fi

# 3. Įrašyti persiuntimo konfigūraciją (įstatomas kolektoriaus adresas)
echo "[*] Rašoma $CONF  ->  ${COLLECTOR_HOST}:${COLLECTOR_PORT}/tcp"
sed -e "s|\"127\.0\.0\.1\"|\"${COLLECTOR_HOST}\"|" \
    -e "s|port(514)|port(${COLLECTOR_PORT})|" \
    "$TEMPLATE" > "$CONF"

# 4. Sintaksės patikra prieš paleidžiant
echo "[*] Tikrinama syslog-ng konfigūracija..."
syslog-ng -s -f "$CONF"

# 5. Nustatyti teisingą systemd unit pavadinimą.
#    Arch/CachyOS pakete yra TIK šablonas syslog-ng@.service, todėl naudojam
#    egzempliorių syslog-ng@default (jis skaito /etc/syslog-ng/syslog-ng.conf).
#    daemon-reload — kad systemd pamatytų ką tik įdiegtus unit failus.
systemctl daemon-reload
if [[ -f /usr/lib/systemd/system/syslog-ng.service || -f /etc/systemd/system/syslog-ng.service ]]; then
  UNIT="syslog-ng.service"
else
  UNIT="syslog-ng@default.service"
fi

# 6. Įjungti + (per)paleisti
echo "[*] Įjungiamas + paleidžiamas ${UNIT}"
systemctl enable --now "$UNIT"
systemctl restart "$UNIT"

# 7. Testinė žinutė (journald -> syslog-ng -> kolektorius)
sleep 3
logger -t kursinis-test "syslog-ng forwarding test from $(hostname)"
echo
echo "[OK] Atlikta. Testinė žinutė išsiųsta kaip host '$(hostname)'."
echo "     Dashboard: http://localhost:8080  ->  Įrenginiai / Devices."
