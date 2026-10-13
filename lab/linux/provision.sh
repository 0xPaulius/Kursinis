#!/usr/bin/env bash
# Paruošia Linux taikinį laboratorijai: sshd (su nesėkmingų bandymų žurnalu) ir
# rsyslog persiuntimas į kolektorių per TLS (6514). Testuota Debian/Ubuntu ir Arch.
#
#   sudo COLLECTOR=192.168.122.1 ./provision.sh            # TLS 6514 (numatyta)
#   sudo COLLECTOR=192.168.122.1 TLS=0 ./provision.sh      # paprastas TCP 514
#
# CA sertifikatą (certs/ca.crt) nukopijuokite į šį VM ir nurodykite CA_FILE.
set -euo pipefail
COLLECTOR="${COLLECTOR:?Nurodykite COLLECTOR=<kolektoriaus IP>}"
TLS="${TLS:-1}"
CA_FILE="${CA_FILE:-/etc/ssl/certs/kursinis-ca.crt}"
[[ $EUID -eq 0 ]] || { echo "Paleiskite kaip root"; exit 1; }

if command -v apt-get >/dev/null; then
  apt-get update -qq && apt-get install -y -qq openssh-server rsyslog rsyslog-gnutls
elif command -v pacman >/dev/null; then
  pacman -Sy --noconfirm --needed openssh rsyslog
fi
systemctl enable --now ssh sshd 2>/dev/null || systemctl enable --now sshd

# auth.log su sshd įvykiais (Debian rašo /var/log/auth.log; Arch per journald).
if [[ "$TLS" == "1" ]]; then
  [[ -f "$CA_FILE" ]] || { echo "Nerastas CA: $CA_FILE (nukopijuokite certs/ca.crt)"; exit 1; }
  cat > /etc/rsyslog.d/90-kursinis.conf <<EOF
\$DefaultNetstreamDriver gtls
\$DefaultNetstreamDriverCAFile ${CA_FILE}
\$ActionSendStreamDriverMode 1
\$ActionSendStreamDriverAuthMode anon
*.* @@(o)${COLLECTOR}:6514
EOF
else
  echo "*.* @@${COLLECTOR}:514" > /etc/rsyslog.d/90-kursinis.conf
fi
systemctl restart rsyslog
logger -t kursinis-test "lab linux provisioned ($(hostname))"
echo "[OK] sshd + rsyslog -> ${COLLECTOR}:$([[ "$TLS" == "1" ]] && echo 6514/TLS || echo 514/TCP)"
