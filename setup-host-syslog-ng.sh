#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-host-syslog-ng.sh
# Sukonfigūruoja šio host'o syslog-ng persiuntimą į Kursinis kolektorių.
# Installs + configures host syslog-ng to forward ALL system logs (systemd
# journal) to the syslog-ng container, so this machine shows up in the
# dashboard Devices tab / traffic graphs.
# Taip pat įdiegia kursinis-status.timer: kas minutę būsenos įrašas (veikimo laikas,
# CPU, atmintis, diskas, programos) keliauja tuo pačiu keliu į įrenginio puslapį.
# Išjungti / disable: sudo systemctl disable --now kursinis-status.timer
#
# Naudojimas / usage:
#   sudo bash setup-host-syslog-ng.sh
#   sudo COLLECTOR_HOST=192.168.1.10 COLLECTOR_PORT=514 bash setup-host-syslog-ng.sh
#   sudo COLLECTOR_TLS=1 bash setup-host-syslog-ng.sh        # TLS 6514, CA iš ./certs/ca.crt
# ---------------------------------------------------------------------------
set -euo pipefail

COLLECTOR_HOST="${COLLECTOR_HOST:-127.0.0.1}"   # 127.0.0.1 = kolektorius sukasi šiame host'e
COLLECTOR_TLS="${COLLECTOR_TLS:-0}"
CONF="/etc/syslog-ng/syslog-ng.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/config/syslog-ng-host/syslog-ng.conf"
COLLECTOR_CA="${COLLECTOR_CA:-${SCRIPT_DIR}/certs/ca.crt}"
HOST_CA="/etc/syslog-ng/kursinis-ca.crt"
if [[ "$COLLECTOR_TLS" == "1" ]]; then
  COLLECTOR_PORT="${COLLECTOR_PORT:-6514}"
  TRANSPORT="transport(\"tls\") tls(ca-file(\"${HOST_CA}\") peer-verify(required-trusted))"
else
  COLLECTOR_PORT="${COLLECTOR_PORT:-514}"
  TRANSPORT='transport("tcp")'
fi

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
if [[ "$COLLECTOR_TLS" == "1" ]]; then
  if [[ ! -f "$COLLECTOR_CA" ]]; then
    echo "Nerastas CA sertifikatas: $COLLECTOR_CA (tools/gen-certs.sh ca)" >&2
    exit 1
  fi
  install -m 0644 "$COLLECTOR_CA" "$HOST_CA"
fi
echo "[*] Rašoma $CONF  ->  ${COLLECTOR_HOST}:${COLLECTOR_PORT} ($([[ "$COLLECTOR_TLS" == "1" ]] && echo tls || echo tcp))"
sed -e "s|\"127\.0\.0\.1\"|\"${COLLECTOR_HOST}\"|" \
    -e "s|port(514)|port(${COLLECTOR_PORT})|" \
    -e "s|transport(\"tcp\")|${TRANSPORT}|" \
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

# 7. Būsenos įrašas kas minutę (CPU, atmintis, diskas, programos) -> journal -> kolektorius.
#    Dashboard rodo jį įrenginio puslapyje („Šis serveris").
echo "[*] Diegiamas būsenos įrašas (kursinis-status.timer, kas minutę)"
install -D -m 0755 "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.sh" /usr/local/libexec/kursinis-status
install -m 0644 "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.service" \
                "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kursinis-status.timer
systemctl start kursinis-status.service   # pirmas įrašas iškart

# 8. Testinė žinutė (journald -> syslog-ng -> kolektorius)
sleep 3
logger -t kursinis-test "syslog-ng forwarding test from $(hostname)"
echo
echo "[OK] Atlikta. Testinė žinutė išsiųsta kaip host '$(hostname)'."
echo "     Būsena kas minutę: systemctl status kursinis-status.timer"
echo "     Dashboard: http://localhost:8080  ->  Įrenginiai / Devices."
