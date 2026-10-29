#!/usr/bin/env bash
# Linux kompiuterio prijungimas be agento: rsyslog + auditd syslog įskiepis -> kolektorius
# (syslog-ng, TLS 6514). Debian/Ubuntu (apt) ir RHEL/Fedora (dnf). Paslapčių nereikia, tik CA.
#
#   tar xzf kursinis-linux.tar.gz && cd kursinis-linux && sudo ./setup.sh
#
# Siunčiami visi vietiniai žurnalai (sshd, sudo ...) ir auditd įrašai (USER_AUTH, ADD_USER,
# interaktyvių vartotojų EXECVE). Kolektoriuje jie matomi kaip job="syslog", host=<hostname>.
set -euo pipefail
COLLECTOR="${COLLECTOR:?nurodykite COLLECTOR=<kolektoriaus IP>}"
CA_FILE="${CA_FILE:-$(dirname "$0")/ca.crt}"
[[ $EUID -eq 0 ]] || { echo "Paleiskite su sudo" >&2; exit 1; }
[[ -f "$CA_FILE" ]] || { echo "Nerastas CA sertifikatas: $CA_FILE" >&2; exit 1; }

if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq rsyslog rsyslog-gnutls auditd audispd-plugins
elif command -v dnf >/dev/null; then
  dnf install -y -q rsyslog rsyslog-gnutls audit audispd-plugins
else
  echo "Reikia apt-get arba dnf" >&2
  exit 1
fi
install -D -m 644 "$CA_FILE" /etc/kursinis/ca.crt

# Komandos tik žmonių sesijose (auid >= 1000), ne tarnybų — kitaip EXECVE srautas per tankus.
cat > /etc/audit/rules.d/kursinis.rules <<'EOF'
-a always,exit -F arch=b64 -S execve -F auid>=1000 -F auid!=unset -k kursinis_exec
-a always,exit -F arch=b32 -S execve -F auid>=1000 -F auid!=unset -k kursinis_exec
EOF
# Fedora numatytai išjungia syscall auditą (-a task,never) — tada EXECVE taisyklės nesuveikia.
sed -i 's/^-a task,never/#&/' /etc/audit/rules.d/*.rules
augenrules --load

plugin=/etc/audit/plugins.d/syslog.conf
[[ -f $plugin ]] || plugin=/etc/audisp/plugins.d/syslog.conf   # auditd 2.x
sed -i 's/^active *=.*/active = yes/' "$plugin"
service auditd restart   # RHEL atsisako `systemctl restart auditd`

cat > /etc/rsyslog.d/90-kursinis.conf <<EOF
# Kursinis: visi žurnalai -> kolektorius per TLS. Serveris tikrinamas pagal CA ir vardą
# syslog-ng (tools/gen-certs.sh jį visada įrašo į kolektoriaus sertifikatą); disko eilė
# išsaugo žurnalus, kol kolektorius nepasiekiamas.
global(DefaultNetstreamDriverCAFile="/etc/kursinis/ca.crt")
action(type="omfwd" target="${COLLECTOR}" port="6514" protocol="tcp"
       StreamDriver="gtls" StreamDriverMode="1"
       StreamDriverAuthMode="x509/name" StreamDriverPermittedPeers="syslog-ng"
       queue.type="LinkedList" queue.filename="kursinis_fwd" queue.maxDiskSpace="1g"
       queue.saveOnShutdown="on" action.resumeRetryCount="-1")
EOF
systemctl restart rsyslog

timeout 3 bash -c "</dev/tcp/${COLLECTOR}/6514" 2>/dev/null \
  || echo "ĮSPĖJIMAS: ${COLLECTOR}:6514 nepasiekiamas; rsyslog kaups žurnalus ir išsiųs vėliau." >&2
logger -t kursinis-setup "linux endpoint connected (${HOSTNAME%%.*})"
echo "[OK] rsyslog + auditd -> ${COLLECTOR}:6514 (TLS). Patikra Loki: {job=\"syslog\", host=\"${HOSTNAME%%.*}\"}"
