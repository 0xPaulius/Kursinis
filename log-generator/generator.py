#!/usr/bin/env python3
"""
Testinių žurnalų generatorius
==============================
Generuoja realistiškus syslog logus kursiniam testavimui.
Simuliuoja:
  - Normalų serverių aktyvumą
  - SSH brute-force atakas
  - Firewall blokavimus
  - Klaidų šuolius (spikes)
  - Tinklo įrenginių logus

Siunčia per syslog protokolą (UDP) į syslog-ng kolektorių.
"""

import os
import sys
import time
import signal
import random
import socket
import datetime
import logging

SYSLOG_HOST = os.getenv("SYSLOG_HOST", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "514"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("log-generator")

# Simuliuojami host'ai (maža organizacija)
HOSTS = {
    "web-server-01": {"programs": ["nginx", "php-fpm", "systemd"], "ip": "192.168.1.10"},
    "db-server-01":  {"programs": ["mariadb", "systemd", "crond"], "ip": "192.168.1.11"},
    "file-server":   {"programs": ["smbd", "nmbd", "systemd"],     "ip": "192.168.1.12"},
    "mikrotik-gw":   {"programs": ["firewall", "dhcp", "wireless"],"ip": "192.168.1.1"},
    "ubiquiti-ap":   {"programs": ["hostapd", "kernel", "syslog"], "ip": "192.168.1.2"},
    "workstation-01":{"programs": ["sshd", "sudo", "systemd"],     "ip": "192.168.1.100"},
    "workstation-02":{"programs": ["sshd", "sudo", "systemd"],     "ip": "192.168.1.101"},
}

# Syslog facility ir severity kodai
FACILITIES = {"kern": 0, "user": 1, "mail": 2, "daemon": 3, "auth": 4, "syslog": 5, "local0": 16}
SEVERITIES = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7}

# Atsitiktiniai vartotojų vardai brute-force simuliacijai
BRUTE_USERS = ["admin", "root", "test", "user", "oracle", "postgres", "deploy", "ubuntu", "pi", "guest"]

# Atsitiktiniai atakuojantys IP
ATTACKER_IPS = [f"10.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(5)]

# Žinutių šablonai pagal programą
_PROGRAM_MESSAGES: dict[str, list[str]] = {
    "nginx": [
        '192.168.1.50 - - "GET /index.html HTTP/1.1" 200 1234',
        '192.168.1.51 - - "GET /api/status HTTP/1.1" 200 56',
        '192.168.1.52 - - "POST /api/login HTTP/1.1" 200 89',
        '192.168.1.50 - - "GET /static/style.css HTTP/1.1" 304 0',
    ],
    "php-fpm": [
        "pool www: child 1234 started",
        "pool www: server reached max_children setting (5)",
    ],
    "mariadb": [
        "Note: Aborted connection 42 to db: 'app_db' user: 'webapp'",
        "Note: Sort aborted: Query execution was interrupted",
        "Slow query: SELECT * FROM orders WHERE date > '2024-01-01'",
    ],
    "systemd": [
        "Started Session 42 of user admin.",
        "Starting Daily apt download activities...",
        "Finished Daily apt download activities.",
        "Started Daily Cleanup of Temporary Directories.",
        "session-42.scope: Deactivated successfully.",
    ],
    "smbd": [
        "connect to service shared from 192.168.1.100",
        "closed connection to service shared",
    ],
    "sshd": [
        "Accepted publickey for admin from 192.168.1.100 port 52341 ssh2",
        "pam_unix(sshd:session): session opened for user admin",
        "Received disconnect from 192.168.1.100 port 52341",
    ],
    "sudo": [
        "admin : TTY=pts/0 ; PWD=/home/admin ; COMMAND=/bin/systemctl restart nginx",
    ],
    "crond": [
        "CMD (/usr/lib64/sa/sa1 1 1)",
        "CMD (run-parts /etc/cron.hourly)",
    ],
    "firewall": [
        "forward: in:ether1 out:ether2, proto TCP, 192.168.1.100:43210->93.184.216.34:443, accepted",
        "input: in:ether1, proto UDP, 192.168.1.50:53421->192.168.1.1:53, accepted",
    ],
    "dhcp": [
        "assigned 192.168.1.100 to AA:BB:CC:DD:EE:FF",
        "lease renewed for 192.168.1.101",
    ],
    "wireless": [
        "client AA:BB:CC:DD:EE:FF connected to wlan1",
        "signal strength for AA:BB:CC:DD:EE:FF: -65dBm",
    ],
    "hostapd": [
        "wlan0: STA aa:bb:cc:dd:ee:ff IEEE 802.11: authenticated",
        "wlan0: STA aa:bb:cc:dd:ee:ff WPA: pairwise key handshake completed",
    ],
    "kernel": [
        "device wlan0 entered promiscuous mode",
        "br0: port 1(eth0) entered forwarding state",
    ],
    "nmbd": [
        "register_name_response: success",
    ],
    "syslog": [
        "message repeated 3 times",
    ],
}


def syslog_priority(facility: str, severity: str) -> int:
    """Apskaičiuoja syslog priority reikšmę."""
    return FACILITIES.get(facility, 1) * 8 + SEVERITIES.get(severity, 6)


def send_syslog(sock: socket.socket, host: str, facility: str, severity: str, program: str, message: str):
    """Siunčia syslog žinutę per UDP."""
    pri = syslog_priority(facility, severity)
    timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    msg = f"<{pri}>{timestamp} {host} {program}: {message}"
    try:
        sock.sendto(msg.encode("utf-8"), (SYSLOG_HOST, SYSLOG_PORT))
    except OSError as e:
        logger.error(f"Siuntimo klaida: {e}")


def generate_normal_log(sock: socket.socket):
    """Generuoja normalų kasdienį logą."""
    host = random.choice(list(HOSTS.keys()))
    program = random.choice(HOSTS[host]["programs"])
    msg_list = _PROGRAM_MESSAGES.get(program, ["operational status: normal"])
    message = random.choice(msg_list)
    severity = random.choices(
        ["info", "notice", "warning", "debug"],
        weights=[60, 20, 10, 10],
    )[0]
    facility = "auth" if program in ("sshd", "sudo") else "daemon"
    send_syslog(sock, host, facility, severity, program, message)


def generate_ssh_bruteforce(sock: socket.socket, intensity: int = 10):
    """Simuliuoja SSH brute-force ataką."""
    target_host = random.choice(["web-server-01", "db-server-01", "workstation-01"])
    attacker_ip = random.choice(ATTACKER_IPS)

    logger.info(f"Simuliuojama SSH brute-force ataka: {attacker_ip} -> {target_host}")

    for _ in range(intensity):
        user = random.choice(BRUTE_USERS)
        port = random.randint(40000, 65535)
        send_syslog(
            sock, target_host, "auth", "warning", "sshd",
            f"Failed password for {'invalid user ' if random.random() > 0.5 else ''}"
            f"{user} from {attacker_ip} port {port} ssh2"
        )
        time.sleep(random.uniform(0.1, 0.5))

    # Kartais ataka pavyksta
    if random.random() > 0.8:
        send_syslog(
            sock, target_host, "auth", "notice", "sshd",
            f"Accepted password for root from {attacker_ip} port 55555 ssh2"
        )


def generate_firewall_block_spike(sock: socket.socket, count: int = 30):
    """Simuliuoja port scan / DDoS bandymą (daug DROP)."""
    attacker_ip = random.choice(ATTACKER_IPS)
    logger.info(f"Simuliuojamas port scan: {attacker_ip}")

    for _ in range(count):
        port = random.randint(1, 65535)
        send_syslog(
            sock, "mikrotik-gw", "kern", "warning", "firewall",
            f"input: in:ether1, proto TCP, {attacker_ip}:{random.randint(40000,65535)}"
            f"->192.168.1.1:{port}, DROP"
        )
        time.sleep(random.uniform(0.05, 0.2))


def generate_error_spike(sock: socket.socket, count: int = 15):
    """Simuliuoja staigų klaidų šuolį (pvz. DB crash)."""
    logger.info("Simuliuojamas klaidų šuolis (DB problema)")

    errors = [
        ("mariadb", "ERROR: Too many connections"),
        ("mariadb", "ERROR: Can't connect to local MySQL server through socket"),
        ("mariadb", "ERROR: Deadlock found when trying to get lock"),
        ("php-fpm", "ERROR: pool www: server reached max_children setting"),
        ("nginx", "connect() failed (111: Connection refused) while connecting to upstream"),
    ]

    for _ in range(count):
        program, message = random.choice(errors)
        send_syslog(sock, "web-server-01", "daemon", "err", program, message)
        send_syslog(sock, "db-server-01", "daemon", "err", program, message)
        time.sleep(random.uniform(0.1, 0.3))


def main():
    logger.info(f"Log generatorius paleistas -> {SYSLOG_HOST}:{SYSLOG_PORT}")
    logger.info("Laukiama kol syslog-ng bus pasiruošęs...")
    time.sleep(10)

    shutdown_requested = False

    def _handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("SIGTERM gautas, stabdoma...")

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    cycle = 0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while not shutdown_requested:
            cycle += 1

            # Normalus fonas: 5-15 logų per ciklą
            normal_count = random.randint(5, 15)
            for _ in range(normal_count):
                generate_normal_log(sock)
                time.sleep(random.uniform(0.1, 0.5))

            # Atsitiktiniai saugumo įvykiai
            # SSH brute-force (~10% tikimybė kiekviename cikle)
            if random.random() < 0.10:
                generate_ssh_bruteforce(sock, intensity=random.randint(5, 20))

            # Firewall spike (~5% tikimybė)
            if random.random() < 0.05:
                generate_firewall_block_spike(sock, count=random.randint(20, 50))

            # Error spike (~3% tikimybė)
            if random.random() < 0.03:
                generate_error_spike(sock, count=random.randint(10, 25))

            # Miegame 3-10 sekundžių tarp ciklų
            sleep_time = random.uniform(3, 10)

            if cycle % 20 == 0:
                logger.info(f"Ciklas #{cycle}: išsiųsta ~{normal_count} normalių logų")

            time.sleep(sleep_time)

    logger.info("Log generatorius sustabdytas.")


if __name__ == "__main__":
    main()
