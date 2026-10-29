#!/usr/bin/env bash
# TLS sertifikatai kolektoriui (syslog-ng 6514, Alloy endpoint gateway 3500) ir
# galiniams įrenginiams (mTLS kliento sertifikatai). Rezultatas — ./certs (gitignored).
#
#   tools/gen-certs.sh ca                            # vieną kartą: privati CA
#   tools/gen-certs.sh server 192.168.1.10 [...]     # kolektoriaus sertifikatas (SAN: IP/DNS)
#   tools/gen-certs.sh client win11-lab              # vienam endpoint'ui: certs/clients/win11-lab.{crt,key}
#   tools/gen-certs.sh bundle 192.168.1.10 [vardas]  # diegimo paketai certs/bundles/ (vardas: fleet)
#   tools/gen-certs.sh revoke laptop-07              # atšaukti kliento sertifikatą
#
# Serverio SAN visada apima localhost, 127.0.0.1, syslog-ng ir alloy-gateway (konteinerių vardai).
# Laboratorijos VM pasiekia host'ą per libvirt tiltą (dažniausiai 192.168.122.1) — jį įtraukite.
#
# Konteineriai mato tik certs/server/: ca.crt, collector.crt/.key ir clients.pem — šliuzo
# priimamų kliento sertifikatų sąrašą (be CA rakto). Jį atnaujina kiekviena komanda;
# šliuzas sąrašą perskaito tik po `docker compose restart alloy-gateway`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERTS="$ROOT/certs"
ALLOY_VERSION=v1.20.1
SYSMON_CONFIG_COMMIT=1836897f12fbd6a0a473665ef6abc34a6b497e31   # SwiftOnSecurity/sysmon-config
mkdir -p "$CERTS/clients"
cd "$CERTS"
umask 077
shopt -s nullglob

require_ca() {
  [ -f ca.crt ] && [ -f ca.key ] || { echo "Pirma: $0 ca" >&2; exit 1; }
}

sign() {  # sign <csr> <crt> <extensions>
  openssl x509 -req -in "$1" -CA ca.crt -CAkey ca.key -CAcreateserial -days 825 -sha256 \
    -extfile <(printf '%b' "$3") -out "$2" 2>/dev/null
  rm -f "$1"
}

issue_client() {  # issue_client <vardas>
  openssl req -newkey rsa:2048 -nodes -keyout "clients/$1.key" -out "clients/$1.csr" \
    -subj "/CN=$1" 2>/dev/null
  sign "clients/$1.csr" "clients/$1.crt" \
    "extendedKeyUsage=clientAuth\nkeyUsage=digitalSignature,keyEncipherment\n"
  chmod 644 "clients/$1.crt"
}

fetch() {  # fetch <url> <failas>: atsisiunčiama vieną kartą, vėliau paketai kuriami ir be interneto
  [ -f "$2" ] || { curl -fsSL -o "$2.part" "$1" && mv "$2.part" "$2"; }
}

refresh_server() {
  # docker compose trūkstamą ./certs/server sukuria kaip root; tuščią katalogą pakeičiame savu.
  [ -w server ] || rmdir server 2>/dev/null || true
  mkdir -p server
  for f in ca.crt collector.crt collector.key; do
    if [ -f "$f" ]; then cp "$f" server/; fi
  done
  cat /dev/null clients/*.crt > server/clients.pem
  # Gamybinė Grafana (uid 472) raktą skaito per šią grupę (docker-compose.prod.yml group_add).
  chmod -R g+rX server
}

case "${1:-}" in
  ca)
    if [ -f ca.key ]; then
      echo "CA jau yra ($CERTS/ca.crt)"
    else
      openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout ca.key -out ca.crt \
        -subj "/CN=Kursinis Log Collector CA" 2>/dev/null
      chmod 644 ca.crt
      echo "CA: $CERTS/ca.crt"
    fi
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
    echo "Pritaikyti: docker compose restart syslog-ng alloy-gateway (gamybiniu režimu ir dashboard grafana)"
    ;;
  client)
    require_ca
    name="${2:?kliento vardas, pvz. win11-lab}"
    issue_client "$name"
    echo "Klientas: $CERTS/clients/$name.crt + .key (+ ca.crt) — nukopijuokite į endpoint'ą"
    echo "Įtrauktas į šliuzo sąrašą: docker compose restart alloy-gateway"
    ;;
  bundle)
    require_ca
    collector="${2:?kolektoriaus IP/DNS, pvz. 192.168.1.10}"
    name="${3:-fleet}"
    [ -f collector.crt ] || { echo "Pirma: $0 server $collector" >&2; exit 1; }
    if [[ "$collector" =~ ^[0-9.]+$ || "$collector" == *:* ]]; then want="IP Address:$collector"; else want="DNS:$collector"; fi
    openssl x509 -in collector.crt -noout -ext subjectAltName | tr ',' '\n' | sed 's/^ *//' \
      | grep -xF "$want" >/dev/null || { echo "$collector nėra kolektoriaus sertifikate: $0 server $collector [...]" >&2; exit 1; }
    [ -f "clients/$name.crt" ] || issue_client "$name"

    cache="bundles/cache"
    alloy="$cache/alloy-$ALLOY_VERSION"
    mkdir -p "$alloy"
    fetch "https://github.com/grafana/alloy/releases/download/$ALLOY_VERSION/SHA256SUMS" "$alloy/SHA256SUMS"
    fetch "https://github.com/grafana/alloy/releases/download/$ALLOY_VERSION/alloy-installer-windows-amd64.exe.zip" \
      "$alloy/alloy-installer-windows-amd64.exe.zip"
    fetch https://download.sysinternals.com/files/Sysmon.zip "$cache/Sysmon.zip"
    fetch "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/$SYSMON_CONFIG_COMMIT/sysmonconfig-export.xml" \
      "$cache/sysmonconfig-$SYSMON_CONFIG_COMMIT.xml"

    stage="$(mktemp -d)"
    trap 'rm -rf "$stage"' EXIT
    win="$stage/kursinis-windows"
    lin="$stage/kursinis-linux"
    mkdir "$win" "$lin"
    (cd "$alloy" && grep ' alloy-installer-windows-amd64.exe.zip$' SHA256SUMS | sha256sum -c --quiet)
    python3 -m zipfile -e "$alloy/alloy-installer-windows-amd64.exe.zip" "$win"
    (cd "$win" && grep ' alloy-installer-windows-amd64.exe$' "$CERTS/$alloy/SHA256SUMS" | sha256sum -c --quiet)
    cp "$ROOT/onboarding/windows/install.ps1" ca.crt "$cache/Sysmon.zip" "$win/"
    cp "$cache/sysmonconfig-$SYSMON_CONFIG_COMMIT.xml" "$win/sysmonconfig.xml"
    cp "clients/$name.crt" "$win/client.crt"
    cp "clients/$name.key" "$win/client.key"
    sed "s/COLLECTOR/$collector/" "$ROOT/onboarding/windows/config.alloy" > "$win/config.alloy"
    (cd "$win" && sha256sum -- * > SHA256SUMS)
    # Intune aptikimo taisyklė lygina šį ID: pasikeitus paketui (sertifikatas, adresas, versijos) jis kitas.
    bundle_id="$name-$(sha256sum < "$win/SHA256SUMS" | cut -c1-12)"
    echo "$bundle_id" > "$win/bundle-id"

    sed "s|^COLLECTOR=.*|COLLECTOR=\"\${COLLECTOR:-$collector}\"|" "$ROOT/onboarding/linux/setup.sh" > "$lin/setup.sh"
    cp ca.crt "$lin/"
    chmod 755 "$lin" "$lin/setup.sh"
    chmod 644 "$lin/ca.crt"

    out=bundles
    [ "$name" = fleet ] || out="bundles/$name"
    mkdir -p "$out"
    python3 -m zipfile -c "$out/kursinis-windows.zip" "$win"
    tar -czf bundles/kursinis-linux.tar.gz --owner=0 --group=0 -C "$stage" kursinis-linux
    echo "Windows: $CERTS/$out/kursinis-windows.zip (bundle-id: $bundle_id)"
    echo "Linux:   $CERTS/bundles/kursinis-linux.tar.gz"
    echo "Įtrauktas į šliuzo sąrašą: docker compose restart alloy-gateway"
    ;;
  revoke)
    name="${2:?kliento vardas}"
    [ -f "clients/$name.crt" ] || { echo "Nėra kliento sertifikato clients/$name.crt" >&2; exit 1; }
    mkdir -p clients/revoked
    mv -f "clients/$name".* clients/revoked/
    if [ "$name" = fleet ]; then rm -f bundles/kursinis-windows.zip; else rm -f "bundles/$name/kursinis-windows.zip"; fi
    echo "Atšauktas: $name (clients/revoked/)"
    echo "Pritaikyti: docker compose restart alloy-gateway"
    ;;
  *)
    sed -n '2,16p' "$ROOT/tools/${0##*/}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
refresh_server
