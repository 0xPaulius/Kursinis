"""
Syslog siuntiklis — generuoja demonstracinį srautą tiesiai į syslog-ng.

Formatas — standartinis BSD syslog per UDP, tad
syslog-ng / Promtail / anomaly-detector apdoroja jį lygiai taip pat:

    <pri>MMM dd HH:MM:SS HOST program: message

- Normalus srautas generuojamas pagal įrenginio OS tipą (macos / windows).
- Demonstracinė ataka (SSH brute-force + ugniasienės DROP banga) siunčiama
  asinchroniškai, kad API atsakytų iškart. Ją aptinka tikras anomaly-detector.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import random
import socket

logger = logging.getLogger(__name__)

SYSLOG_HOST = os.getenv("SYSLOG_HOST", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "514"))

# Syslog facility / severity kodai (BSD syslog)
_FACILITIES = {"kern": 0, "user": 1, "mail": 2, "daemon": 3, "auth": 4, "syslog": 5, "local0": 16}
_SEVERITIES = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7}

_BRUTE_USERS = ["admin", "root", "test", "user", "oracle", "postgres", "deploy", "ubuntu", "pi", "guest"]

# Normalaus srauto šablonai pagal OS: (program, facility, severity, message_template).
# {ip} pakeičiamas įrenginio IP adresu.
_NORMAL_TEMPLATES: dict[str, list[tuple[str, str, str, str]]] = {
    "macos": [
        ("sshd",                 "auth",   "info",   "Accepted publickey for admin from {ip} port 52341 ssh2"),
        ("loginwindow",          "auth",   "info",   "USER_PROCESS: user admin session opened"),
        ("mDNSResponder",        "daemon", "info",   "service registered: _companion-link._tcp"),
        ("kernel",               "kern",   "info",   "en0: link up, 1000 Mbps full-duplex"),
        ("com.apple.xpc.launchd","daemon", "notice", "Service started: com.apple.Spotlight"),
        ("CommCenter",           "daemon", "info",   "Wi-Fi associated with SSID office-net"),
    ],
    "windows": [
        ("Security-Auditing",    "auth",   "info",   "An account was successfully logged on (Event 4624) for admin from {ip}"),
        ("Service-Control-Manager","daemon","info",  "The Windows Update service entered the running state"),
        ("Winlogon",             "auth",   "info",   "User logon notification received for admin"),
        ("Kernel-General",       "kern",   "info",   "The operating system started successfully"),
        ("WindowsUpdateClient",  "daemon", "notice", "Installation Successful: Update KB5034123"),
        ("Defender",             "daemon", "info",   "Antimalware scan completed, no threats found"),
    ],
    "router": [
        ("firewall", "kern",   "info",   "forward: in:ether1 out:ether2, proto TCP, 192.168.1.50:51000->93.184.216.34:443, accepted"),
        ("dhcp",     "daemon", "info",   "assigned 192.168.1.120 to AA:BB:CC:DD:EE:01"),
        ("wireless", "daemon", "info",   "client AA:BB:CC:DD:EE:01 connected to wlan1, signal -62dBm"),
        ("system",   "daemon", "notice", "user admin logged in from 192.168.1.50 via webfig"),
        ("dns",      "daemon", "info",   "query from 192.168.1.50: example.com resolved"),
        ("ntp",      "daemon", "info",   "time synchronized with pool.ntp.org"),
    ],
    "server": [
        ("nginx",    "daemon", "info",   "192.168.1.50 - - \"GET /index.html HTTP/1.1\" 200 1234"),
        ("nginx",    "daemon", "info",   "192.168.1.61 - - \"GET /api/status HTTP/1.1\" 200 56"),
        ("sshd",     "auth",   "info",   "Accepted publickey for deploy from 192.168.1.50 port 51022 ssh2"),
        ("systemd",  "daemon", "info",   "Started Daily apt download activities."),
        ("cron",     "daemon", "info",   "(root) CMD (/usr/lib/sysstat/sa1 1 1)"),
        ("php-fpm",  "daemon", "notice", "pool www: child 2451 started"),
    ],
}


def syslog_priority(facility: str, severity: str) -> int:
    """Apskaičiuoja syslog priority (PRI) reikšmę."""
    return _FACILITIES.get(facility, 1) * 8 + _SEVERITIES.get(severity, 6)


def build_syslog_line(
    host: str,
    facility: str,
    severity: str,
    program: str,
    message: str,
    when: datetime.datetime | None = None,
) -> str:
    """Sudaro vieną BSD syslog eilutę (be PID)."""
    pri = syslog_priority(facility, severity)
    timestamp = (when or datetime.datetime.now()).strftime("%b %d %H:%M:%S")
    return f"<{pri}>{timestamp} {host} {program}: {message}"


class SyslogEmitter:
    """UDP syslog siuntiklis su atskira normaliojo srauto ir atakų logika."""

    def __init__(self, host: str = SYSLOG_HOST, port: int = SYSLOG_PORT) -> None:
        self.host = host
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Saugome nuorodas į fonines užduotis, kad jų nepašalintų GC.
        self._tasks: set[asyncio.Task] = set()

    def _send_line(self, line: str) -> None:
        try:
            self._sock.sendto(line.encode("utf-8"), (self.host, self.port))
        except OSError as exc:
            logger.warning("Syslog siuntimo klaida: %s", exc)

    # -- Normalus srautas -----------------------------------------------------

    def emit_normal_for_device(self, device: dict, count: int = 1) -> int:
        """Išsiunčia `count` normalių logų vienam įrenginiui. Grąžina išsiųstų kiekį."""
        templates = _NORMAL_TEMPLATES.get(device.get("os", ""), _NORMAL_TEMPLATES["macos"])
        host = device.get("hostname", "device")
        ip = device.get("ip", "0.0.0.0")
        sent = 0
        for _ in range(count):
            program, facility, severity, message_tmpl = random.choice(templates)
            self._send_line(build_syslog_line(host, facility, severity, program, message_tmpl.format(ip=ip)))
            sent += 1
        return sent

    # -- Demonstracinis scenarijus --------------------------------------------

    async def _ssh_bruteforce(self, target_host: str, attacker_ip: str, intensity: int) -> None:
        """SSH brute-force banga prieš įrenginį (≥3 skirtingi ir „invalid" vartotojai)."""
        for i in range(intensity):
            user = random.choice(_BRUTE_USERS)
            port = random.randint(40000, 65535)
            # Dalis bandymų su neegzistuojančiu vartotoju → suveikia ir invalid_user_scan.
            prefix = "invalid user " if i % 2 == 0 else ""
            self._send_line(build_syslog_line(
                target_host, "auth", "warning", "sshd",
                f"Failed password for {prefix}{user} from {attacker_ip} port {port} ssh2",
            ))
            await asyncio.sleep(0.05)

    async def _firewall_drop_wave(self, router_host: str, router_ip: str, attacker_ip: str, count: int) -> None:
        """Ugniasienės DROP banga (port scan) ant maršrutizatoriaus."""
        for _ in range(count):
            port = random.randint(1, 65535)
            self._send_line(build_syslog_line(
                router_host, "kern", "warning", "firewall",
                f"input: in:ether1, proto TCP, {attacker_ip}:{random.randint(40000, 65535)}"
                f"->{router_ip}:{port}, DROP",
            ))
            await asyncio.sleep(0.02)

    async def _error_burst(self, host: str, count: int) -> None:
        """Trumpas klaidų šuolis web serveryje (suveikia high_error_rate)."""
        errors = [
            ("nginx",   "connect() failed (111: Connection refused) while connecting to upstream"),
            ("php-fpm", "pool www: server reached max_children setting (10)"),
            ("nginx",   "upstream timed out (110: Connection timed out) while reading response header"),
        ]
        for _ in range(count):
            program, message = random.choice(errors)
            self._send_line(build_syslog_line(host, "daemon", "err", program, message))
            await asyncio.sleep(0.05)

    async def _run_scenario(
        self,
        web_device: dict,
        router_device: dict,
        attacker_ip: str,
        ssh_intensity: int,
        firewall_count: int,
        error_count: int,
    ) -> None:
        """SSH brute-force (web) → ugniasienės DROP banga (router) → klaidų šuolis (web)."""
        web_host = web_device.get("hostname", "web-server-01")
        router_host = router_device.get("hostname", "router-01")
        router_ip = router_device.get("ip", "192.168.1.1")
        await self._ssh_bruteforce(web_host, attacker_ip, ssh_intensity)
        await self._firewall_drop_wave(router_host, router_ip, attacker_ip, firewall_count)
        await self._error_burst(web_host, error_count)
        logger.info("Demonstracinis scenarijus baigtas: %s → SSH:%s, FW:%s", attacker_ip, web_host, router_host)

    def _spawn(self, coro) -> None:
        """Paleidžia foninę užduotį ir saugo jos nuorodą, kad jos nepašalintų GC."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def simulate_attack(
        self,
        attack: str,
        web_device: dict,
        router_device: dict,
        ssh_intensity: int = 15,
        firewall_count: int = 60,
        error_count: int = 12,
    ) -> str:
        """
        Paleidžia pasirinktą demonstracinę ataką fone ir grąžina atakuojantį IP.

        attack:
          - "ssh_bruteforce" — SSH brute-force banga prieš web serverį;
          - "firewall_spike" — ugniasienės DROP banga ant maršrutizatoriaus;
          - "full" (numatyta) — pilnas daugiapakopis scenarijus (visi sluoksniai).
        """
        # 203.0.113.0/24 — dokumentacijai skirtas (TEST-NET-3) išorinis IP.
        attacker_ip = f"203.0.113.{random.randint(1, 254)}"
        web_host = web_device.get("hostname", "web-server-01")
        router_host = router_device.get("hostname", "router-01")
        router_ip = router_device.get("ip", "192.168.1.1")

        if attack == "ssh_bruteforce":
            coro = self._ssh_bruteforce(web_host, attacker_ip, ssh_intensity)
        elif attack == "firewall_spike":
            coro = self._firewall_drop_wave(router_host, router_ip, attacker_ip, firewall_count)
        else:
            coro = self._run_scenario(
                web_device, router_device, attacker_ip, ssh_intensity, firewall_count, error_count
            )

        self._spawn(coro)
        return attacker_ip

    def simulate_scenario(
        self,
        web_device: dict,
        router_device: dict,
        ssh_intensity: int = 15,
        firewall_count: int = 60,
        error_count: int = 12,
    ) -> str:
        """
        Pilnas daugiapakopis demonstracinis scenarijus (SSH brute-force + ugniasienės
        DROP banga + klaidų šuolis). Paliktas suderinamumui — deleguoja į `simulate_attack`.
        """
        return self.simulate_attack(
            "full", web_device, router_device, ssh_intensity, firewall_count, error_count
        )

    def close(self) -> None:
        self._sock.close()
