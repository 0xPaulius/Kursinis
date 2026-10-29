"""
Alertų tipų susiejimas su MITRE ATT&CK technikomis ir ATT&CK aprėpties skaičiavimas.

Vienas šaltinis (single source of truth): kiekvienas aptikimo alert_type susietas su
viena ar keliomis technikomis. `Engine` užpildo `Alert.attack_techniques`, o dashboard
rodo aprėptį pagal vertinimo technikų rinkinį (LAB_TECHNIQUE_SET), kuris sąmoningai
apima ir technikas be taisyklės — kad aprėptis nebūtų „savaime 100 %".
"""
from __future__ import annotations

# alert_type -> ATT&CK technikų ID sąrašas
CATALOG: dict[str, list[str]] = {
    # Esamos (Linux/tinklo) taisyklės
    "ssh_bruteforce": ["T1110.001"],
    "invalid_user_scan": ["T1110.001"],
    "firewall_spike": ["T1046"],
    # Statistinis / ML — be konkrečios technikos (bendras nukrypimas)
    "log_volume_spike": [],
    "high_error_rate": [],
    "ml_anomaly": [],
    # Windows endpoint taisyklės
    "win_failed_logon_bruteforce": ["T1110.001"],
    "win_password_spray": ["T1110.003"],
    "win_account_lockout": ["T1110"],
    "win_account_created": ["T1136.001"],
    "win_admin_group_add": ["T1098"],
    "win_audit_log_cleared": ["T1070.001"],
    "win_suspicious_powershell": ["T1059.001"],
    "win_discovery_burst": ["T1087.001", "T1033"],
    "win_lolbin_network": ["T1105"],
    "win_startup_persistence": ["T1547.001"],
    # Linux auditd taisyklės (job="linux_endpoint" arba per rsyslog job="syslog")
    "linux_sudo_auth_failure": ["T1548.003"],
    "linux_account_created": ["T1136.001"],
    "linux_suspicious_execve": ["T1059.004"],
    "linux_discovery_burst": ["T1087.001", "T1033"],
}

# Technikų metaduomenys (ID -> pavadinimas, taktika) dashboard matricai.
TECHNIQUES: dict[str, dict[str, str]] = {
    "T1110.001": {"name": "Brute Force: Password Guessing", "tactic": "Credential Access"},
    "T1110.003": {"name": "Brute Force: Password Spraying", "tactic": "Credential Access"},
    "T1110": {"name": "Brute Force", "tactic": "Credential Access"},
    "T1046": {"name": "Network Service Discovery", "tactic": "Discovery"},
    "T1087.001": {"name": "Account Discovery: Local Account", "tactic": "Discovery"},
    "T1033": {"name": "System Owner/User Discovery", "tactic": "Discovery"},
    "T1136.001": {"name": "Create Account: Local Account", "tactic": "Persistence"},
    "T1098": {"name": "Account Manipulation", "tactic": "Persistence"},
    "T1547.001": {"name": "Boot/Logon Autostart: Startup Folder", "tactic": "Persistence"},
    "T1070.001": {"name": "Indicator Removal: Clear Windows Event Logs", "tactic": "Defense Evasion"},
    "T1059.001": {"name": "Command and Scripting Interpreter: PowerShell", "tactic": "Execution"},
    "T1105": {"name": "Ingress Tool Transfer", "tactic": "Command and Control"},
    "T1548.003": {"name": "Abuse Elevation Control: Sudo and Sudo Caching", "tactic": "Privilege Escalation"},
    "T1059.004": {"name": "Command and Scripting Interpreter: Unix Shell", "tactic": "Execution"},
    # Vertinimo rinkinyje, bet (sąmoningai) be taisyklės — rodo aprėpties ribas:
    "T1021.001": {"name": "Remote Services: RDP", "tactic": "Lateral Movement"},
    "T1048": {"name": "Exfiltration Over Alternative Protocol", "tactic": "Exfiltration"},
    "T1053.005": {"name": "Scheduled Task", "tactic": "Persistence"},
    "T1003.001": {"name": "OS Credential Dumping: LSASS Memory", "tactic": "Credential Access"},
}

# Vertinimo technikų rinkinys (pvz. Red Canary Threat Detection Report dažniausios +
# scenarijų technikos). Fiksuojamas PRIEŠ taisyklių derinimą, kad aprėptis būtų sąžininga.
LAB_TECHNIQUE_SET: list[str] = [
    "T1110.001", "T1110.003", "T1136.001", "T1098", "T1070.001", "T1059.001", "T1059.004",
    "T1087.001", "T1033", "T1105", "T1547.001", "T1046", "T1548.003",
    "T1021.001", "T1048", "T1053.005", "T1003.001",  # be taisyklės
]


def techniques_for(alert_type: str) -> list[str]:
    return list(CATALOG.get(alert_type, []))


def covered_techniques() -> set[str]:
    """Technikos, kurioms yra bent viena taisyklė."""
    return {t for techniques in CATALOG.values() for t in techniques}


def coverage(seen_alert_types: set[str] | None = None) -> dict:
    """
    ATT&CK aprėptis pagal LAB_TECHNIQUE_SET.
    `seen_alert_types` (neprivaloma) — alertų istorijoje realiai pasirodę tipai;
    tada technika žymima „detected", jei ją iškėlė bent vienas matytas alert_type.
    """
    rule_covered = covered_techniques()
    seen_covered: set[str] = set()
    if seen_alert_types is not None:
        for alert_type in seen_alert_types:
            seen_covered.update(CATALOG.get(alert_type, []))

    rows = []
    for tech in LAB_TECHNIQUE_SET:
        meta = TECHNIQUES.get(tech, {"name": tech, "tactic": "Unknown"})
        rows.append({
            "technique": tech,
            "name": meta["name"],
            "tactic": meta["tactic"],
            "has_rule": tech in rule_covered,
            "detected": tech in seen_covered,
        })
    total = len(LAB_TECHNIQUE_SET)
    return {
        "techniques": rows,
        "total": total,
        "with_rule": sum(r["has_rule"] for r in rows),
        "detected": sum(r["detected"] for r in rows),
    }
