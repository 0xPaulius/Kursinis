#!/usr/bin/env python3
"""
Žurnalų siuntėjo (Promtail -> Alloy) atitikties patikra.

  parity_check.py send     --syslog HOST:PORT              # deterministinis įvykių rinkinys
  parity_check.py snapshot --loki URL --since 10m --out a.json
  parity_check.py compare  a.json b.json                   # 0 = identiška, 1 = skiriasi

Procedūra: paleisti konvejerį su Promtail, `send`, `snapshot`; tą patį pakartoti su
Alloy į tuščią Loki; `compare` palygina srautų etikečių rinkinius ir kiekius pagal
(job, host, program, severity). Loki automatiškai pridedamos etiketės
(service_name, detected_level) ignoruojamos — jas prideda pats Loki.
"""
from __future__ import annotations

import argparse
import datetime
import json
import socket
import sys
import time
import urllib.parse
import urllib.request

_LOKI_ADDED = {"service_name", "detected_level"}
_FACILITIES = {"kern": 0, "user": 1, "daemon": 3, "auth": 4, "local0": 16}
_SEVERITIES = {"crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6}

# (host, facility, severity, program, pid, message, kartojimų skaičius)
EVENTS = [
    ("parity-web", "daemon", "info", "nginx", "", '10.0.0.5 - - "GET / HTTP/1.1" 200 512', 40),
    ("parity-web", "auth", "warning", "sshd", "2201", "Failed password for root from 203.0.113.7 port 50022 ssh2", 12),
    ("parity-web", "auth", "info", "sshd", "2201", "Invalid user oracle from 203.0.113.7 port 50023", 6),
    ("parity-web", "daemon", "err", "php-fpm", "", "pool www: server reached max_children setting (10)", 9),
    ("parity-db", "kern", "crit", "kernel", "", "Out of memory: Killed process 4242 (postgres)", 3),
    ("parity-fw", "local0", "notice", "firewall", "", "input: in:ether1, proto TCP, 203.0.113.9:4000->10.0.0.1:22, DROP", 25),
]


def send(target: str) -> int:
    host, port = target.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = 0
    for hostname, facility, severity, program, pid, message, repeat in EVENTS:
        pri = _FACILITIES[facility] * 8 + _SEVERITIES[severity]
        tag = f"{program}[{pid}]" if pid else program
        for i in range(repeat):
            ts = datetime.datetime.now(datetime.timezone.utc)
            line = f"<{pri}>{ts:%b %d %H:%M:%S} {hostname} {tag}: {message} #{i}"
            sock.sendto(line.encode(), (host, int(port)))
            sent += 1
            time.sleep(0.01)
    return sent


def _get(loki: str, path: str, params: dict) -> dict:
    url = f"{loki.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def snapshot(loki: str, since: str) -> dict:
    now = time.time()
    seconds = int(since[:-1]) * {"s": 1, "m": 60, "h": 3600}[since[-1]]
    series = _get(loki, "/loki/api/v1/series", {
        "match[]": '{host=~"parity-.*"}', "start": int((now - seconds) * 1e9), "end": int(now * 1e9)})
    label_sets = sorted(
        json.dumps({k: v for k, v in s.items() if k not in _LOKI_ADDED}, sort_keys=True)
        for s in series.get("data", [])
    )
    counts = _get(loki, "/loki/api/v1/query", {
        "query": f'sum by (job, host, program, severity) (count_over_time({{host=~"parity-.*"}}[{since}]))',
        "time": int(now * 1e9)})
    by_key = {
        "|".join(r["metric"].get(k, "") for k in ("job", "host", "program", "severity")): int(float(r["value"][1]))
        for r in counts["data"]["result"]
    }
    return {"label_sets": label_sets, "counts": dict(sorted(by_key.items()))}


def compare(a: dict, b: dict) -> list[str]:
    diffs = []
    for missing in sorted(set(a["label_sets"]) - set(b["label_sets"])):
        diffs.append(f"tik A: {missing}")
    for extra in sorted(set(b["label_sets"]) - set(a["label_sets"])):
        diffs.append(f"tik B: {extra}")
    for key in sorted(set(a["counts"]) | set(b["counts"])):
        if a["counts"].get(key) != b["counts"].get(key):
            diffs.append(f"kiekis {key}: A={a['counts'].get(key)} B={b['counts'].get(key)}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("send")
    p.add_argument("--syslog", default="127.0.0.1:514")
    p = sub.add_parser("snapshot")
    p.add_argument("--loki", default="http://127.0.0.1:3100")
    p.add_argument("--since", default="10m")
    p.add_argument("--out", required=True)
    p = sub.add_parser("compare")
    p.add_argument("a")
    p.add_argument("b")
    args = parser.parse_args()

    if args.cmd == "send":
        print(f"Išsiųsta {send(args.syslog)} įvykių")
    elif args.cmd == "snapshot":
        snap = snapshot(args.loki, args.since)
        with open(args.out, "w") as fh:
            json.dump(snap, fh, indent=2)
        print(f"{len(snap['label_sets'])} srautai, {sum(snap['counts'].values())} įrašų -> {args.out}")
    else:
        with open(args.a) as fa, open(args.b) as fb:
            diffs = compare(json.load(fa), json.load(fb))
        print("\n".join(diffs) if diffs else "IDENTIŠKA: etikečių rinkiniai ir kiekiai sutampa")
        return 1 if diffs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
