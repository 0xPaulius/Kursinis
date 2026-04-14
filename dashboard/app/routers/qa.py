"""
Kokybės užtikrinimo API — paleidžia pytest testus ir grąžina rezultatus.

Autorius: Paulius Turauskas
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/qa", tags=["qa"])

# Žinomi atviri defektai
_KNOWN_DEFECTS: list[dict[str, Any]] = [
    {
        "id": "DEF-001",
        "name": "Search result count displayed in Lithuanian regardless of selected UI language",
        "severity": "Minor",
        "priority": "Low",
        "status": "Open",
        "component": "app.js:731 (search count renderer)",
        "steps": [
            "Log in (admin / admin123)",
            "Click the EN button at the bottom of the sidebar",
            "Type any search query (e.g. ssh) in the top search bar",
            "Observe the result count indicator next to the search field",
        ],
        "expected": "Count displayed in English: \"X results\"",
        "actual": "Count displayed in Lithuanian: \"X rezultatų\" — i18n not applied to count string",
    }
]

# Paskutiniai testo rezultatai (saugomi atmintyje tarp užklausų)
_last_results: dict[str, Any] | None = None


def _blocking_pytest_run() -> dict[str, Any]:
    """Sinchroninis pytest paleidimas — turi būti vykdomas atskiroje gijoje."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        report_path = fh.name

    t0 = time.monotonic()
    proc = subprocess.run(
        [
            "pytest", "tests/", "-v",
            "--tb=short",
            "--json-report",
            f"--json-report-file={report_path}",
        ],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    elapsed = round(time.monotonic() - t0, 2)

    try:
        with open(report_path, encoding="utf-8") as fh:
            report = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {
            "tests": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "error": 1, "duration": elapsed},
            "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_error": str(exc),
            "stderr": proc.stderr[:2000] if proc.stderr else "",
        }

    tests: list[dict[str, Any]] = []
    for test in report.get("tests", []):
        node_id: str = test.get("nodeid", "")
        # "tests/test_routes.py::TestHealthRoute::test_returns_200"
        # → "test_routes → TestHealthRoute → test_returns_200"
        name = node_id.replace("tests/", "").replace("::", " → ")
        call_info = test.get("call") or {}
        tests.append({
            "name": name,
            "outcome": test.get("outcome", "unknown"),
            "duration": round(call_info.get("duration", 0), 4),
        })

    raw = report.get("summary", {})
    return {
        "tests": tests,
        "summary": {
            "total": raw.get("total", len(tests)),
            "passed": raw.get("passed", 0),
            "failed": raw.get("failed", 0),
            "error": raw.get("error", 0),
            "duration": elapsed,
        },
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@router.get("/run")
async def run_tests() -> JSONResponse:
    """Paleidžia visus pytest testus ir grąžina rezultatus."""
    global _last_results
    _last_results = await asyncio.to_thread(_blocking_pytest_run)
    return JSONResponse(content=_last_results)


@router.get("/results")
async def get_last_results() -> JSONResponse:
    """Grąžina paskutinius saugotus rezultatus (nenaudojant procesoriaus)."""
    if _last_results is None:
        return JSONResponse(content={"tests": [], "summary": None, "ran_at": None})
    return JSONResponse(content=_last_results)


@router.get("/defects")
async def get_defects() -> JSONResponse:
    """Grąžina žinomų defektų sąrašą."""
    return JSONResponse(content={"defects": _KNOWN_DEFECTS})
