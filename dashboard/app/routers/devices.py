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
    get_device_details,
    get_device_monitor,
    get_device_registry,
    get_syslog_emitter,
    require_admin,
    require_auth,
)
from app.models.schemas import (
    DemoScenarioRequest,
    Device,
    DeviceCreate,
    DeviceDetails,
    DeviceList,
    DeviceMap,
    SimulateResponse,
)
from app.services.alert_reader import AlertReader
from app.services.device_details import DeviceDetailsService, DeviceNotFound
from app.services.device_monitor import DeviceMonitor, alert_summary
from app.services.device_registry import DeviceRegistry
from app.services.syslog_emitter import SyslogEmitter

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_auth)])


def _annotate(device: dict, reader: AlertReader) -> Device:
    """Priskiria įrenginiui įspėjimų skaičių ir blogiausią sunkumą iš alertų istorijos."""
    count, worst = alert_summary(device.get("ip", ""), device.get("hostname", ""), reader.read_all())
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


@router.get("/{key}/details", response_model=DeviceDetails)
async def device_details(
    key: str,
    service: Annotated[DeviceDetailsService, Depends(get_device_details)],
) -> DeviceDetails:
    """Vieno įrenginio detalės: būsena (CPU, atmintis, programos), paskutiniai veiksmai, įspėjimai."""
    try:
        return await service.details(key)
    except DeviceNotFound:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")


@router.post("", response_model=Device, status_code=201, dependencies=[Depends(require_admin)])
async def create_device(
    payload: DeviceCreate,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
    reader: Annotated[AlertReader, Depends(get_alert_reader)],
) -> Device:
    """Registruoja naują įrenginį. Normalus srautas pradedamas generuoti automatiškai."""
    try:
        device = registry.add(
            name=payload.name, ip=payload.ip, os_type=payload.os, os_version=payload.os_version,
            synthetic=payload.synthetic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _annotate(device, reader)


@router.delete("/{device_id}", dependencies=[Depends(require_admin)])
async def delete_device(
    device_id: str,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
) -> dict:
    """Pašalina įrenginį pagal ID."""
    if not registry.delete(device_id):
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    return {"detail": "Įrenginys pašalintas"}


def _resolve_demo_targets(registry: DeviceRegistry) -> tuple[dict | None, dict | None]:
    """Parenka web serverio ir maršrutizatoriaus įrenginius demonstraciniam scenarijui."""
    devices = registry.list_all()

    def pick(hostname: str, os_type: str) -> dict | None:
        return (next((d for d in devices if d.get("hostname") == hostname), None)
                or next((d for d in devices if d.get("os") == os_type), None))

    fallback = devices[0] if devices else None
    web = pick("web-server-01", "server") or fallback
    router = pick("router-01", "router") or web
    return web, router


@router.post("/demo/scenario", response_model=SimulateResponse, dependencies=[Depends(require_admin)])
async def run_demo_scenario(
    payload: DemoScenarioRequest,
    registry: Annotated[DeviceRegistry, Depends(get_device_registry)],
    emitter: Annotated[SyslogEmitter, Depends(get_syslog_emitter)],
) -> SimulateResponse:
    """
    Paleidžia pasirinktą demonstracinę ataką, kurią aptinka tikras anomaly-detector:
    "ssh_bruteforce" (web serveris), "firewall_spike" (maršrutizatorius) arba
    "full" — pilnas daugiapakopis scenarijus (SSH + ugniasienė + klaidų šuolis).
    """
    web, router = _resolve_demo_targets(registry)
    if web is None or router is None:
        raise HTTPException(status_code=400, detail="Nėra registruotų įrenginių demonstracijai")
    attacker_ip = emitter.simulate_attack(payload.attack, web, router)
    target = {
        "ssh_bruteforce": web["hostname"],
        "firewall_spike": router["hostname"],
    }.get(payload.attack, f"{web['hostname']} + {router['hostname']}")
    return SimulateResponse(
        detail="Demonstracinė ataka pradėta. Anomalijos pasirodys po kelių akimirkų.",
        target=target,
        attacker_ip=attacker_ip,
    )
