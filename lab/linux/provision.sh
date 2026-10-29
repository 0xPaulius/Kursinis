#!/usr/bin/env bash
# Paruošia Linux taikinį laboratorijai: sshd (su nesėkmingų bandymų žurnalu), tada
# onboarding/linux/setup.sh — rsyslog + auditd per TLS (6514) į kolektorių. Debian/Ubuntu, RHEL.
#
#   sudo COLLECTOR=192.168.122.1 CA_FILE=/etc/ssl/certs/kursinis-ca.crt ./provision.sh
#
# CA sertifikatą (certs/ca.crt) nukopijuokite į šį VM ir nurodykite CA_FILE. Šalia lab/ turi
# būti ir onboarding/ (kaip repozitorijoje).
set -euo pipefail
COLLECTOR="${COLLECTOR:?Nurodykite COLLECTOR=<kolektoriaus IP>}"
CA_FILE="${CA_FILE:-/etc/ssl/certs/kursinis-ca.crt}"
[[ $EUID -eq 0 ]] || { echo "Paleiskite kaip root"; exit 1; }

if command -v apt-get >/dev/null; then
  apt-get update -qq && apt-get install -y -qq openssh-server
else
  dnf install -y -q openssh-server
fi
systemctl enable --now ssh 2>/dev/null || systemctl enable --now sshd

COLLECTOR="$COLLECTOR" CA_FILE="$CA_FILE" "$(dirname "$0")/../../onboarding/linux/setup.sh"
