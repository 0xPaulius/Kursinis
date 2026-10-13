"""
Vertinimo duomenų rinkinių atsisiuntimas.

AIT-LDS v2.0: iš ~7–27 GB scenarijaus ZIP per HTTP Range ištraukiami tik reikalingi
nariai (dataset.yaml, žymės, atakų tvarkaraštis, auth/syslog/apache žurnalai).
Kiekvienas narys tikrinamas CRC32, o ištrauktiems failams įrašomas sha256 manifestas.

OTRF Security Datasets: manifests/otrf_windows_host.csv išvardyti Windows host rinkiniai
(technikos iš OTRF metaduomenų, žr. tools/build_otrf_manifest.py) iš fiksuotos revizijos.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import requests

from .remote_zip import RemoteZip

AIT_RECORD = "https://zenodo.org/records/5789064/files/{scenario}.zip?download=1"
AIT_SCENARIOS = ["fox", "harrison", "russellmitchell", "santos", "shaw", "wardbeck", "wheeler", "wilson"]
AIT_LICENSE = "AIT-LDS v2.0 — CC BY-NC-SA 4.0 (Landauer et al., 2022, doi:10.5281/zenodo.5789064)"
AIT_MEMBERS = [
    "dataset.yaml",
    "labels/*",
    "gather/attacker_0/logs/attacks.log",
    "gather/*/logs/auth.log*",
    "gather/*/logs/syslog*",
    "gather/*/logs/apache2/*access.log*",
]
OTRF_COMMIT = "d9d40ef123d2c87d5d3df28c96bcab4f0faccc87"
OTRF_URL = ("https://raw.githubusercontent.com/OTRF/Security-Datasets/"
            "{commit}/datasets/atomic/windows/{file}")
OTRF_LICENSE = "OTRF Security Datasets — MIT License (Open Threat Research Forge)"
OTRF_MANIFEST = Path(__file__).parent / "manifests" / "otrf_windows_host.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(root: Path) -> Path:
    """sha256 kiekvienam failui — vėliau įrašomas į run.json kaip rinkinio maiša."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")
    manifest = root / "MANIFEST.sha256"
    with open(manifest, "w") as out:
        for path in files:
            out.write(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n")
    return manifest


def dataset_hash(root: Path) -> str:
    """Rinkinio maiša: failui — jo sha256; katalogui — sha256(MANIFEST.sha256)."""
    root = Path(root)
    if root.is_file():
        return sha256_file(root)
    manifest = root / "MANIFEST.sha256"
    if not manifest.is_file():
        write_manifest(root)
    return sha256_file(manifest)


def fetch_ait(scenario: str, dest: Path, members: list[str] | None = None) -> Path:
    if scenario not in AIT_SCENARIOS:
        raise ValueError(f"Nežinomas AIT scenarijus: {scenario} (galimi: {', '.join(AIT_SCENARIOS)})")
    target = Path(dest) / scenario
    remote = RemoteZip(AIT_RECORD.format(scenario=scenario))
    wanted = sorted(remote.members(members or AIT_MEMBERS), key=lambda i: i.header_offset)
    print(f"{scenario}: {len(wanted)} failai, {sum(i.file_size for i in wanted) / 1048576:.1f} MB")
    for info in wanted:
        out = target / info.filename
        if out.is_file() and out.stat().st_size == info.file_size:
            continue
        remote.extract(info, target)
    write_manifest(target)
    (target / "SOURCE.json").write_text(json.dumps({
        "url": AIT_RECORD.format(scenario=scenario),
        "license": AIT_LICENSE,
        "members": members or AIT_MEMBERS,
    }, indent=2))
    print(f"Licencija: {AIT_LICENSE}")
    return target


def fetch_otrf(dest: Path) -> Path:
    """OTRF Windows host rinkiniai pagal manifestą; manifest.csv nukopijuojamas šalia jų."""
    target = Path(dest)
    with open(OTRF_MANIFEST, newline="") as fh:
        files = [row["file"] for row in csv.DictReader(fh)]
    for name in files:
        out = target / name
        if out.is_file():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(OTRF_URL.format(commit=OTRF_COMMIT, file=name), timeout=120)
        resp.raise_for_status()
        part = out.with_name(out.name + ".part")
        part.write_bytes(resp.content)
        part.replace(out)
    shutil.copy(OTRF_MANIFEST, target / "manifest.csv")
    (target / "SOURCE.json").write_text(json.dumps({
        "url": OTRF_URL.format(commit=OTRF_COMMIT, file="<file>"),
        "commit": OTRF_COMMIT,
        "license": OTRF_LICENSE,
        "files": len(files),
    }, indent=2))
    write_manifest(target)
    print(f"OTRF: {len(files)} rinkiniai -> {target}\nLicencija: {OTRF_LICENSE}")
    return target
