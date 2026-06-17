"""
Syslog siuntiklis — generuoja demonstracinį srautą tiesiai į syslog-ng.

Formatas identiškas log-generator/generator.py (BSD syslog per UDP), tad
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

# Syslog facility / severity kodai (kaip generator.py)
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
    """Sudaro vieną BSD syslog eilutę (be PID, kaip generator.py)."""
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

    # -- Demonstracinė ataka --------------------------------------------------

    async def _run_attack(
        self,
        target_host: str,
        attacker_ip: str,
        ssh_intensity: int,
        firewall_count: int,
    ) -> None:
        """SSH brute-force prieš įrenginį + ugniasienės DROP banga (port scan)."""
        for _ in range(ssh_intensity):
            user = random.choice(_BRUTE_USERS)
            port = random.randint(40000, 65535)
            self._send_line(build_syslog_line(
                target_host, "auth", "warning", "sshd",
                f"Failed password for {user} from {attacker_ip} port {port} ssh2",
            ))
            await asyncio.sleep(0.05)

        for _ in range(firewall_count):
            port = random.randint(1, 65535)
            self._send_line(build_syslog_line(
                "gateway-01", "kern", "warning", "firewall",
                f"input: in:ether1, proto TCP, {attacker_ip}:{random.randint(40000, 65535)}"
                f"->192.168.1.1:{port}, DROP",
            ))
            await asyncio.sleep(0.02)

        logger.info("Demonstracinė ataka baigta: %s -> %s", attacker_ip, target_host)

    def simulate_attack(
        self,
        device: dict,
        ssh_intensity: int = 15,
        firewall_count: int = 60,
    ) -> str:
        """
        Paleidžia foninę demonstracinę ataką prieš `device`.
        Grąžina sugeneruotą atakuojantį IP, kad jį būtų galima parodyti vartotojui.
        """
        # 203.0.113.0/24 — dokumentacijai skirtas (TEST-NET-3) išorinis IP.
        attacker_ip = f"203.0.113.{random.randint(1, 254)}"
        task = asyncio.create_task(
            self._run_attack(device["hostname"], attacker_ip, ssh_intensity, firewall_count)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return attacker_ip

    def close(self) -> None:
        self._sock.close()
