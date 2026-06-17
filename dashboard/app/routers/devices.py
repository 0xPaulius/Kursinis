"""
Įrenginių API maršrutai.

Leidžia registruoti demonstracinius įrenginius (pavadinimas + IP + OS),
generuoti jiems normalų srautą (fone) ir paleisti demonstracinę ataką,
kurią aptinka tikras anomaly-detector.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import (
    get_alert_reader,
    get_device_monitor,
    get_device_registry,
    get_syslog_emitter,
    require_auth,
)
from app.models.schemas import Device, DeviceCreate, DeviceList, DeviceMap, SimulateResponse
from app.services.alert_reader import AlertReader
from app.services.device_monitor import DeviceMonitor
from app.services.device_registry import DeviceRegistry
from app.services.syslog_emitter import SyslogEmitter

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_auth)])

_SEV_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _annotate(device: dict, reader: AlertReader) -> Device:
    """Priskiria įrenginiui įspėjimų skaičių ir blogiausią sunkumą iš alertų istorijos."""
    ip = device.get("ip", "")
    hostname = device.get("hostname", "")
    count = 0
    worst = "none"
    for alert in reader.read_all():
        if (ip and alert.source_ip == ip) or (hostname and hostname in (alert.source_host or "")):
            count += 1
            if _SEV_RANK.get(alert.severity, 0) > _SEV_RANK.get(worst, 0):
                worst = alert.severity
    return Device(**device, alert_count=count, worst_severity=worst)


@router.get("", response_model=DeviceList)
async def list_devices(
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
    reader: Annotated[AlertReader, Depends(get_alert_reader)],
) -> DeviceList:
    """Visi registruoti įrenginiai su įspėjimų suvestine."""
    devices = [_annotate(d, reader) for d in registry.list_all()]
    return DeviceList(devices=devices, total=len(devices))


@router.get("/map", response_model=DeviceMap)
async def device_map(
    monitor: Annotated[DeviceMonitor, Depends(get_device_monitor)],
) -> DeviceMap:
    """Įrenginių žemėlapis: registruoti + savas serveris + aptikti, su gyva statistika."""
    return DeviceMap(**await monitor.build_map())


@router.post("", response_model=Device, status_code=201)
async def create_device(
    payload: DeviceCreate,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
    reader: Annotated[AlertReader, Depends(get_alert_reader)],
) -> Device:
    """Registruoja naują įrenginį. Normalus srautas pradedamas generuoti automatiškai."""
    try:
        device = registry.add(
            name=payload.name, ip=payload.ip, os_type=payload.os, os_version=payload.os_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _annotate(device, reader)


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
) -> dict:
    """Pašalina įrenginį pagal ID."""
    if not registry.delete(device_id):
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    return {"detail": "Įrenginys pašalintas"}


@router.post("/{device_id}/simulate", response_model=SimulateResponse)
async def simulate_attack(
    device_id: str,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
    emitter: Annotated[SyslogEmitter, Depends(get_syslog_emitter)],
) -> SimulateResponse:
    """Paleidžia demonstracinę ataką prieš įrenginį (SSH brute-force + ugniasienės banga)."""
    device = registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    attacker_ip = emitter.simulate_attack(device)
    return SimulateResponse(
        detail="Demonstracinė ataka pradėta. Anomalijos pasirodys po kelių akimirkų.",
        target=device["hostname"],
        attacker_ip=attacker_ip,
    )
