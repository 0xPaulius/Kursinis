#!/usr/bin/env bash
# TLS sertifikatai kolektoriui (syslog-ng 6514, Alloy endpoint gateway 3500) ir
# galiniams įrenginiams (mTLS kliento sertifikatai). Rezultatas — ./certs (gitignored).
#
#   tools/gen-certs.sh ca                          # vieną kartą: privati CA
#   tools/gen-certs.sh server 192.168.1.10 [...]   # kolektoriaus sertifikatas (SAN: IP/DNS)
#   tools/gen-certs.sh client win11-lab            # vienam endpoint'ui: certs/clients/win11-lab.{crt,key}
#
# Serverio SAN visada apima localhost, 127.0.0.1, syslog-ng ir alloy-gateway (konteinerių vardai).
# Laboratorijos VM pasiekia host'ą per libvirt tiltą (dažniausiai 192.168.122.1) — jį įtraukite.
set -euo pipefail
CERTS="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$CERTS/clients"
cd "$CERTS"
umask 077

require_ca() {
  [ -f ca.crt ] && [ -f ca.key ] || { echo "Pirma: $0 ca" >&2; exit 1; }
}

sign() {  # sign <csr> <crt> <extensions>
  openssl x509 -req -in "$1" -CA ca.crt -CAkey ca.key -CAcreateserial -days 825 -sha256 \
    -extfile <(printf '%b' "$3") -out "$2" 2>/dev/null
  rm -f "$1"
}

case "${1:-}" in
  ca)
    [ -f ca.key ] && { echo "CA jau yra ($CERTS/ca.crt)"; exit 0; }
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout ca.key -out ca.crt \
      -subj "/CN=Kursinis Log Collector CA" 2>/dev/null
    chmod 644 ca.crt
    echo "CA: $CERTS/ca.crt"
    ;;
  server)
    require_ca
    shift
    san="DNS:localhost,IP:127.0.0.1,DNS:syslog-ng,DNS:alloy-gateway"
    for name in "$@"; do
      if [[ "$name" =~ ^[0-9.]+$ || "$name" == *:* ]]; then san+=",IP:$name"; else san+=",DNS:$name"; fi
    done
    openssl req -newkey rsa:2048 -nodes -keyout collector.key -out collector.csr \
      -subj "/CN=${1:-kursinis-collector}" 2>/dev/null
    sign collector.csr collector.crt \
      "subjectAltName=$san\nextendedKeyUsage=serverAuth\nkeyUsage=digitalSignature,keyEncipherment\n"
    chmod 644 collector.crt
    echo "Kolektorius: $CERTS/collector.crt ($san)"
    ;;
  client)
    require_ca
    name="${2:?kliento vardas, pvz. win11-lab}"
    openssl req -newkey rsa:2048 -nodes -keyout "clients/$name.key" -out "clients/$name.csr" \
      -subj "/CN=$name" 2>/dev/null
    sign "clients/$name.csr" "clients/$name.crt" \
      "extendedKeyUsage=clientAuth\nkeyUsage=digitalSignature,keyEncipherment\n"
    chmod 644 "clients/$name.crt"
    echo "Klientas: $CERTS/clients/$name.crt + .key (+ ca.crt) — nukopijuokite į endpoint'ą"
    ;;
  *)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
