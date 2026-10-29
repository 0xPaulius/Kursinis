"""Būsenos (status heartbeat) įrašų tikrinimas, naujausias įrašas ir istorija, sutartis su skriptu."""
from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.host_status import build_status, parse_status_line

SCRIPT = Path(__file__).resolve().parents[2] / "config" / "syslog-ng-host" / "kursinis-status.sh"
NOW = datetime.datetime(2026, 10, 29, 12, 0, tzinfo=datetime.timezone.utc)

VALID = {"v": 1, "uptime_s": 3600, "cpus": 8, "cpu_pct": 12.5, "load": [0.5, 0.4, 0.3],
         "mem_total_kb": 1000, "mem_avail_kb": 250, "disk_used_kb": 40, "disk_avail_kb": 60,
         "procs": 120, "users": ["oxshan"],
         "top": [{"name": "firefox", "n": 12, "cpu": 8.1, "mem_kb": 2400000}]}


def line(record) -> str:
    """Eilutė taip, kaip ją įrašo kolektoriaus syslog-ng šablonas."""
    body = record if isinstance(record, str) else json.dumps(record)
    return f"2026-10-29T12:00:00+00:00 pc daemon.info kursinis-status[123]: {body}"


def entry(record, minutes_ago: float) -> dict:
    ts = NOW - datetime.timedelta(minutes=minutes_ago)
    return {"timestamp": str(int(ts.timestamp()) * 10**9), "line": line(record), "labels": {}}


def test_valid_record_is_parsed():
    rec = parse_status_line(line(VALID))
    assert rec is not None and rec.cpu_pct == 12.5 and rec.top[0].name == "firefox" and rec.users == ["oxshan"]


def test_record_with_only_version_is_valid():
    assert parse_status_line(line({"v": 1})) is not None


def test_unknown_fields_are_ignored():
    assert parse_status_line(line({**VALID, "future_field": {"x": 1}})) is not None


@pytest.mark.parametrize("bad", [
    "not json",
    '{"v": 1',
    {**VALID, "v": 2},
    {k: v for k, v in VALID.items() if k != "v"},
    {**VALID, "cpu_pct": 101},
    {**VALID, "cpu_pct": -1},
    {**VALID, "uptime_s": -5},
    {**VALID, "cpus": 0},
    {**VALID, "mem_avail_kb": 2000},
    {**VALID, "load": [1, 2, 3, 4]},
    {**VALID, "users": ["u"] * 21},
    {**VALID, "users": ["x" * 65]},
    {**VALID, "top": [VALID["top"][0]] * 21},
    {**VALID, "top": [{**VALID["top"][0], "name": "x" * 65}]},
    {**VALID, "top": [{**VALID["top"][0], "n": 0}]},
    {**VALID, "top": [{**VALID["top"][0], "cpu": 150}]},
], ids=["text", "truncated", "v2", "no-v", "cpu>100", "cpu<0", "uptime<0", "cpus=0", "avail>total",
        "load4", "users21", "user-long", "top21", "name-long", "n=0", "prog-cpu>100"])
def test_invalid_records_are_rejected(bad):
    assert parse_status_line(line(bad)) is None


def test_nan_is_rejected():
    assert parse_status_line(line('{"v": 1, "cpu_pct": NaN}')) is None


def test_other_programs_and_long_lines_are_ignored():
    assert parse_status_line(line(VALID).replace("kursinis-status[", "sshd[")) is None
    assert parse_status_line(line({**VALID, "pad": "x" * 20000})) is None


def test_build_status_picks_newest_valid_record_and_hour_of_history():
    rows = [entry({**VALID, "cpu_pct": 10.0}, 90),     # per senas istorijai
            entry({**VALID, "cpu_pct": 20.0}, 30),
            entry({**VALID, "cpu_pct": 30.0}, 1),
            entry("garbage", 0.5)]                       # naujesnis, bet netinkamas
    status, history = build_status(list(reversed(rows)), NOW)
    assert status.cpu_pct == 30.0
    assert status.time == (NOW - datetime.timedelta(minutes=1)).isoformat()
    assert status.programs[0].processes == 12 and status.programs[0].mem_kb == 2400000
    assert [p.cpu_pct for p in history] == [20.0, 30.0]
    assert history[0].mem_pct == 75.0


def test_build_status_without_records():
    assert build_status([], NOW) == (None, [])


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bash") is None,
                    reason="skriptas skaito Linux /proc")
def test_status_script_output_passes_the_parser():
    out = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, timeout=30, check=True,
                         env={"PATH": "/usr/bin:/bin", "SAMPLE_SECONDS": "0.2"}).stdout
    lines = out.strip().splitlines()
    assert len(lines) == 1
    rec = parse_status_line(line(lines[0]))
    assert rec is not None
    assert rec.uptime_s > 0 and rec.cpus >= 1 and rec.mem_total_kb > 0 and rec.procs > 0
    assert 0 < len(rec.top) <= 20
