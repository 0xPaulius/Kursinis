"""
MITRE ATT&CK aprėpties API maršrutas.

Sujungia detektoriaus attack_catalog.json su alertų istorijoje matytais tipais —
rodo, kurios technikos padengtos taisyklėmis ir kurios realiai suveikė.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_alert_reader, require_auth
from app.services.alert_reader import AlertReader
from app.services.attack_coverage import coverage

router = APIRouter(prefix="/api/attack", tags=["attack"], dependencies=[Depends(require_auth)])


@router.get("/coverage")
async def get_attack_coverage(
    reader: Annotated[AlertReader, Depends(get_alert_reader)],
) -> dict:
    """ATT&CK technikų aprėptis (has_rule) ir realus aptikimas (detected) pagal istoriją."""
    seen = {a.alert_type for a in reader.read_recent(1000)}
    return coverage(seen)
