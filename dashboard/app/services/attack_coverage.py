"""
MITRE ATT&CK aprėpties skaičiavimas dashboard'ui.

Vienas šaltinis — anomaly-detector startuojant įrašytas /data/attack_catalog.json
(katalogas, technikų metaduomenys, vertinimo technikų rinkinys). Dashboard jį skaito
iš bendro volume ir sujungia su alertų istorijoje realiai matytais tipais, kad parodytų:
  - kurios technikos turi taisyklę (has_rule),
  - kurios technikos realiai suveikė (detected).
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

ATTACK_CATALOG_PATH = os.getenv(
    "ATTACK_CATALOG_PATH",
    os.path.join(os.path.dirname(os.getenv("ANOMALY_DB_PATH", "/data/anomaly_history.json")),
                 "attack_catalog.json"),
)


def _load_catalog() -> dict:
    try:
        return json.loads(open(ATTACK_CATALOG_PATH).read())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def coverage(seen_alert_types: set[str]) -> dict:
    """
    ATT&CK aprėptis pagal vertinimo technikų rinkinį (lab_technique_set).
    Grąžina matricą pagal taktiką; `detected` — ar techniką iškėlė bent vienas matytas alert_type.
    Jei katalogo failo nėra (detektorius nepaleistas) — grąžina tuščią, su `available=False`.
    """
    cat = _load_catalog()
    catalog: dict[str, list[str]] = cat.get("catalog", {})
    techniques_meta: dict[str, dict] = cat.get("techniques", {})
    lab_set: list[str] = cat.get("lab_technique_set", [])
    if not lab_set:
        return {"available": False, "techniques": [], "by_tactic": {},
                "total": 0, "with_rule": 0, "detected": 0}

    rule_covered = {t for techs in catalog.values() for t in techs}
    seen_covered = {t for at in seen_alert_types for t in catalog.get(at, [])}

    rows = []
    for tech in lab_set:
        meta = techniques_meta.get(tech, {"name": tech, "tactic": "Unknown"})
        rows.append({
            "technique": tech,
            "name": meta.get("name", tech),
            "tactic": meta.get("tactic", "Unknown"),
            "has_rule": tech in rule_covered,
            "detected": tech in seen_covered,
        })

    by_tactic: dict[str, list[dict]] = {}
    for row in rows:
        by_tactic.setdefault(row["tactic"], []).append(row)

    return {
        "available": True,
        "techniques": rows,
        "by_tactic": by_tactic,
        "total": len(rows),
        "with_rule": sum(r["has_rule"] for r in rows),
        "detected": sum(r["detected"] for r in rows),
    }
