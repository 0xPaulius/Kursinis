"""
Vertinimo duomenų rinkinių atsisiuntimas.

AIT-LDS v2.0: iš ~7–27 GB scenarijaus ZIP per HTTP Range ištraukiami tik reikalingi
nariai (dataset.yaml, žymės, atakų tvarkaraštis, auth/syslog/apache žurnalai).
Kiekvienas narys tikrinamas CRC32, o ištrauktiems failams įrašomas sha256 manifestas.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
