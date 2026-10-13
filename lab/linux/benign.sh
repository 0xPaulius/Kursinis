#!/usr/bin/env bash
# Gerybinė Linux veikla be atakų — klaidingai teigiamų (FPR) matavimui.
# Generuoja normalius sshd/sudo/cron/paslaugų įvykius, kurie per rsyslog patenka
# į kolektorių. Paleisti taikinyje LYGIAGREČIAI su ataka-laisvu langu (24–48 val.).
#
#   DURATION=3600 ./benign.sh            # 1 val. normalios veiklos
#
# Svarbu: jokių nesėkmingų prisijungimų ar skenavimų — tik teisėta veikla.
set -uo pipefail
DURATION="${DURATION:-3600}"
INTERVAL="${INTERVAL:-15}"
USERS=("alice" "bob" "deploy")
end=$(( $(date +%s) + DURATION ))
echo "[*] Gerybinė veikla ${DURATION}s (kas ~${INTERVAL}s)"

while [ "$(date +%s)" -lt "$end" ]; do
  u="${USERS[$RANDOM % ${#USERS[@]}]}"
  case $((RANDOM % 5)) in
    0) logger -p auth.info -t sshd "Accepted publickey for ${u} from 192.168.122.$((RANDOM%40+10)) port $((RANDOM%20000+40000)) ssh2" ;;
    1) logger -p auth.info -t sudo  "${u} : TTY=pts/0 ; PWD=/home/${u} ; USER=root ; COMMAND=/usr/bin/apt update" ;;
    2) logger -p cron.info -t CRON  "(${u}) CMD (/usr/lib/sysstat/sa1 1 1)" ;;
    3) logger -p daemon.info -t systemd "Started Session $((RANDOM%999)) of user ${u}." ;;
    4) logger -p daemon.info -t nginx "192.168.122.$((RANDOM%40+10)) - - \"GET /index.html HTTP/1.1\" 200 $((RANDOM%4000+200))" ;;
  esac
  sleep $((RANDOM % INTERVAL + 1))
done
echo "[OK] Gerybinės veiklos langas baigtas."
