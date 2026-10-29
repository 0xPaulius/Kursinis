# Device Detail Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking a device on the Devices tab opens a page with its uptime, CPU, memory, disk, running programs, recent actions, raw logs and alerts.

**Architecture:** This PC sends a one-line JSON status record every minute (bash script + systemd timer → journal → host syslog-ng → collector → Loki, `program="kursinis-status"`). A new dashboard endpoint `GET /api/devices/{key}/details` reads the newest valid record and one hour of history, classifies notable events from the device's logs and attaches its alerts. A new frontend module renders `#devices/<key>` as a Grafana-style page.

**Tech Stack:** bash + awk, systemd, syslog-ng 4.8, Loki LogQL, FastAPI + Pydantic v2, pytest, vanilla JS ES modules, Tailwind runtime, the project's SVG `sparkline()`.

**Spec:** `docs/superpowers/specs/2026-10-29-device-detail-design.md`

**Conventions (from CLAUDE.md):** academic comments in Lithuanian, technical identifiers in English; Python with type hints and docstrings; frontend without inline handlers or scripts, text only via `textContent`; dashboard tests run in `dashboard/.venv` (`cd dashboard && .venv/bin/python -m pytest tests/ -q`, baseline 35 passed). Run `/verify` right before each code commit (not for docs).

---

## File map

| File | Change | Responsibility |
|---|---|---|
| `dashboard/app/log_selectors.py` | modify | + `HOST_RE`, `valid_host()` (moved from `routers/traffic.py`, now `fullmatch`) |
| `dashboard/app/routers/traffic.py` | modify | use `valid_host()` |
| `dashboard/app/services/loki_client.py` | modify | + `ns_to_datetime()` |
| `dashboard/app/services/device_monitor.py` | modify | + `alerts_for_device()`; `alert_summary()` uses it |
| `dashboard/app/models/schemas.py` | modify | + `ProgramUsage`, `HostStatus`, `StatusPoint`, `ActivityItem`, `DeviceDetails` |
| `dashboard/app/services/host_status.py` | create | status record model, line parsing, latest + 1 h history |
| `config/syslog-ng-host/kursinis-status.sh` | create | prints one status record |
| `config/syslog-ng-host/kursinis-status.service` | create | sandboxed oneshot |
| `config/syslog-ng-host/kursinis-status.timer` | create | every 60 s |
| `setup-host-syslog-ng.sh` | modify | installs script + units, starts timer |
| `config/syslog-ng/syslog-ng.conf` | modify | `f_security` skips `program("kursinis-status")` |
| `dashboard/app/services/activity.py` | create | activity rules + `classify()` |
| `dashboard/app/services/device_details.py` | create | Loki queries → `DeviceDetails` |
| `dashboard/app/dependencies.py`, `dashboard/app/main.py`, `dashboard/app/routers/devices.py` | modify | DI + route |
| `dashboard/app/static/js/pages/device-meta.js` | create | OS/source labels, `deviceKey()` |
| `dashboard/app/static/js/pages/device-detail.js` | create | detail page |
| `dashboard/app/static/js/{state,shell,main,format,charts,alert-dialog}.js`, `pages/{devices,anomalies}.js`, `i18n.js` | modify | routing, hooks, helpers, strings |
| `dashboard/app/static/index.html`, `css/theme.css` | modify | detail markup, dialog removed, styles |
| `dashboard/tests/test_host_status.py`, `test_activity.py` | create | unit + contract tests |
| `dashboard/tests/test_api.py`, `test_frontend_static.py` | modify | API + i18n tests |
| `CLAUDE.md` | modify | docs |

---

### Task 1: Shared helpers (host validation, Loki timestamps, device alerts)

**Files:**
- Modify: `dashboard/app/log_selectors.py`, `dashboard/app/routers/traffic.py`, `dashboard/app/services/loki_client.py`, `dashboard/app/services/device_monitor.py`
- Test: `dashboard/tests/test_api.py`

- [ ] **Step 1: Write the failing tests** — append to `dashboard/tests/test_api.py` (after `test_alert_summary_matches_exact_hostnames`):

```python
def test_valid_host_rejects_logql_breakers():
    from app.log_selectors import valid_host
    assert valid_host("web-server-01") and valid_host("PC.local")
    for bad in ("", None, 'a"b', "a}b", "a b", "web\n", "x" * 256):
        assert not valid_host(bad), repr(bad)


def test_alerts_for_device_keeps_order_and_matches_ip_or_host():
    from app.services.device_monitor import alerts_for_device
    a1 = SimpleNamespace(source_ip="10.0.0.5", source_host="", severity="high")
    a2 = SimpleNamespace(source_ip="", source_host="web-1, pc-2", severity="low")
    a3 = SimpleNamespace(source_ip="", source_host="pc-22", severity="low")
    assert alerts_for_device("10.0.0.5", "pc-2", [a1, a2, a3]) == [a1, a2]
    assert alerts_for_device("", "pc-2", [a1, a2, a3]) == [a2]


def test_ns_to_datetime():
    from app.services.loki_client import ns_to_datetime
    assert ns_to_datetime("1793260800000000000").isoformat() == "2026-10-29T08:00:00+00:00"
    assert ns_to_datetime("x") is None and ns_to_datetime(None) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_api.py -q -k "valid_host or alerts_for_device or ns_to_datetime"`
Expected: 3 failed (ImportError: cannot import name ...).

- [ ] **Step 3: Implement**

`dashboard/app/log_selectors.py` — add `import re` and, after `LOG_JOBS`:

```python
# Leistini host etiketės simboliai — apsauga nuo LogQL injekcijos per host reikšmę.
HOST_RE = re.compile(r"[A-Za-z0-9._-]{1,255}")


def valid_host(host: str | None) -> bool:
    """Ar reikšmę saugu įdėti į LogQL kaip host etiketę (visa eilutė: be kabučių ir „\\n")."""
    return bool(host) and HOST_RE.fullmatch(host) is not None
```

`dashboard/app/routers/traffic.py` — delete `import re` and the `_HOST_RE` block (comment + assignment), change the import to `from app.log_selectors import logs_selector, valid_host`, and replace both occurrences of
`selector = logs_selector(host if host and _HOST_RE.match(host) else None)` with
`selector = logs_selector(host if valid_host(host) else None)`.

`dashboard/app/services/loki_client.py` — after `_to_ns()`:

```python
def ns_to_datetime(ts: str | int | None) -> datetime.datetime | None:
    """Loki įrašo laikas (nanosekundės) -> UTC datetime; None, jei reikšmė netinkama."""
    try:
        return datetime.datetime.fromtimestamp(int(ts) / _NS, tz=datetime.timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
```

`dashboard/app/services/device_monitor.py` — replace the whole `alert_summary` function with:

```python
def _matches(alert, ip: str, hostname: str) -> bool:
    # source_host gali būti sąrašas „web-1, web-2" (SSH brute-force keliems host'ams).
    hosts = {h.strip() for h in (alert.source_host or "").split(",")}
    return bool((ip and alert.source_ip == ip) or (hostname and hostname in hosts))


def alerts_for_device(ip: str, hostname: str, alerts: list) -> list:
    """Įrenginio įspėjimai (pagal IP arba tikslų host vardą), ta pačia tvarka kaip `alerts`."""
    return [a for a in alerts if _matches(a, ip, hostname)]


def alert_summary(ip: str, hostname: str, alerts: list) -> tuple[int, str]:
    """Įrenginio įspėjimų skaičius ir blogiausias sunkumas (pagal IP arba tikslų host vardą)."""
    matched = alerts_for_device(ip, hostname, alerts)
    worst = "none"
    for a in matched:
        if _SEV_RANK.get(a.severity, 0) > _SEV_RANK.get(worst, 0):
            worst = a.severity
    return len(matched), worst
```

- [ ] **Step 4: Run the whole suite**

Run: `cd dashboard && .venv/bin/python -m pytest tests/ -q`
Expected: 38 passed.

---

### Task 2: Status record model and parser

**Files:**
- Modify: `dashboard/app/models/schemas.py`
- Create: `dashboard/app/services/host_status.py`
- Test: `dashboard/tests/test_host_status.py`

- [ ] **Step 1: Write the failing tests** — create `dashboard/tests/test_host_status.py`:

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_host_status.py -q`
Expected: collection error (`ModuleNotFoundError: app.services.host_status`).

- [ ] **Step 3: Add the response models** — append to `dashboard/app/models/schemas.py`:

```python
class ProgramUsage(BaseModel):
    """Programa (procesai, sugrupuoti pagal vardą) iš įrenginio būsenos įrašo."""
    name: str
    processes: int
    cpu_pct: float              # visų branduolių dalis per 1 s matavimą
    mem_kb: int                 # suminė RSS


class HostStatus(BaseModel):
    """Naujausias įrenginio būsenos įrašas (status heartbeat)."""
    time: str                   # ISO; kada įrašą gavo kolektorius
    uptime_s: int | None = None
    cpus: int | None = None
    cpu_pct: float | None = None
    load: list[float] = []
    mem_total_kb: int | None = None
    mem_avail_kb: int | None = None
    disk_used_kb: int | None = None
    disk_avail_kb: int | None = None
    procs: int | None = None
    users: list[str] = []
    programs: list[ProgramUsage] = []


class StatusPoint(BaseModel):
    """Vienas CPU / atminties taškas (paskutinės valandos sparkline)."""
    time: str
    cpu_pct: float | None = None
    mem_pct: float | None = None


class ActivityItem(BaseModel):
    """Pastebimas įrenginio veiksmas (prisijungimas, sudo, paskyros pakeitimas, komanda ...)."""
    time: str
    kind: str                   # login | auth_failed | admin | account | command | script | boot | log_cleared | update
    user: str = ""
    text: str


class DeviceDetails(BaseModel):
    """Įrenginio detalių puslapio duomenys."""
    status: HostStatus | None = None
    history: list[StatusPoint] = []
    activity: list[ActivityItem] = []
    alerts: list[AlertItem] = []
```

- [ ] **Step 4: Implement the parser** — create `dashboard/app/services/host_status.py`:

```python
"""
Įrenginio būsenos įrašai (status heartbeat): veikimo laikas, CPU, atmintis, diskas, programos.

Įrenginys kas minutę siunčia vieną JSON eilutę įprastu žurnalų keliu
(config/syslog-ng-host/kursinis-status.sh -> journal -> syslog-ng -> Alloy -> Loki,
program="kursinis-status"). Syslog'ą (UDP 514) gali siųsti bet kas, todėl įrašas —
nepatikimi duomenys: tikrinamas griežtai, netinkamas praleidžiamas (netaisomas).
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.models.schemas import HostStatus, ProgramUsage, StatusPoint
from app.services.loki_client import ns_to_datetime

logger = logging.getLogger(__name__)

STATUS_PROGRAM = "kursinis-status"
HISTORY_WINDOW = datetime.timedelta(hours=1)
MAX_LINE_LENGTH = 16_384

_STATUS_RE = re.compile(r"kursinis-status\[\d*\]: (\{.*\})\s*$")

_Pct = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
_Kb = Annotated[int, Field(ge=0, le=2**50)]
_Name = Annotated[str, Field(min_length=1, max_length=64)]
_Load = Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)]


class _Program(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: _Name
    n: Annotated[int, Field(ge=1, le=1_000_000)]
    cpu: _Pct
    mem_kb: _Kb


class StatusRecord(BaseModel):
    """Būsenos įrašas, 1 versija (specifikacijos 4.2 ir 4.6 skyriai)."""
    model_config = ConfigDict(extra="ignore")
    v: Literal[1]
    uptime_s: Annotated[int, Field(ge=0, le=10**10)] | None = None
    cpus: Annotated[int, Field(ge=1, le=4096)] | None = None
    cpu_pct: _Pct | None = None
    load: Annotated[list[_Load], Field(max_length=3)] = []
    mem_total_kb: _Kb | None = None
    mem_avail_kb: _Kb | None = None
    disk_used_kb: _Kb | None = None
    disk_avail_kb: _Kb | None = None
    procs: Annotated[int, Field(ge=0, le=10**7)] | None = None
    users: Annotated[list[_Name], Field(max_length=20)] = []
    top: Annotated[list[_Program], Field(max_length=20)] = []

    @model_validator(mode="after")
    def _memory_consistent(self) -> StatusRecord:
        if (self.mem_total_kb is not None and self.mem_avail_kb is not None
                and self.mem_avail_kb > self.mem_total_kb):
            raise ValueError("mem_avail_kb > mem_total_kb")
        return self

    @property
    def mem_pct(self) -> float | None:
        if not self.mem_total_kb or self.mem_avail_kb is None:
            return None
        return round(100 * (self.mem_total_kb - self.mem_avail_kb) / self.mem_total_kb, 1)


def parse_status_line(line: str) -> StatusRecord | None:
    """Loki eilutė -> StatusRecord; None, jei tai ne būsenos įrašas arba jis netinkamas."""
    if len(line) > MAX_LINE_LENGTH:
        return None
    match = _STATUS_RE.search(line)
    if not match:
        return None
    try:
        return StatusRecord.model_validate_json(match.group(1))
    except ValidationError as exc:
        logger.debug("Netinkamas būsenos įrašas praleistas: %s", exc.errors()[:3])
        return None


def _to_host_status(rec: StatusRecord, when: datetime.datetime) -> HostStatus:
    return HostStatus(
        time=when.isoformat(),
        uptime_s=rec.uptime_s, cpus=rec.cpus, cpu_pct=rec.cpu_pct, load=rec.load,
        mem_total_kb=rec.mem_total_kb, mem_avail_kb=rec.mem_avail_kb,
        disk_used_kb=rec.disk_used_kb, disk_avail_kb=rec.disk_avail_kb,
        procs=rec.procs, users=rec.users,
        programs=[ProgramUsage(name=p.name, processes=p.n, cpu_pct=p.cpu, mem_kb=p.mem_kb) for p in rec.top],
    )


def build_status(entries: list[dict], now: datetime.datetime) -> tuple[HostStatus | None, list[StatusPoint]]:
    """Loki įrašai (bet kokia tvarka) -> naujausia tinkama būsena ir valandos istorija (seniausi pirmi)."""
    parsed: list[tuple[datetime.datetime, StatusRecord]] = []
    for e in entries:
        when = ns_to_datetime(e.get("timestamp"))
        rec = parse_status_line(e.get("line") or "")
        if when is not None and rec is not None:
            parsed.append((when, rec))
    if not parsed:
        return None, []
    parsed.sort(key=lambda p: p[0])
    cutoff = now - HISTORY_WINDOW
    history = [StatusPoint(time=w.isoformat(), cpu_pct=r.cpu_pct, mem_pct=r.mem_pct)
               for w, r in parsed if w >= cutoff]
    latest_when, latest = parsed[-1]
    return _to_host_status(latest, latest_when), history
```

- [ ] **Step 5: Run the tests**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_host_status.py -q`
Expected: all pass except `test_status_script_output_passes_the_parser` (script not created yet → `CalledProcessError`).

---

### Task 3: Status script and systemd units

**Files:**
- Create: `config/syslog-ng-host/kursinis-status.sh`, `config/syslog-ng-host/kursinis-status.service`, `config/syslog-ng-host/kursinis-status.timer`
- Test: `dashboard/tests/test_host_status.py::test_status_script_output_passes_the_parser` (already written)

- [ ] **Step 1: Create the script** `config/syslog-ng-host/kursinis-status.sh` (then `chmod 755`):

```bash
#!/usr/bin/env bash
# Kursinis: vienas šio kompiuterio būsenos įrašas (JSON eilutė) į stdout — veikimo laikas, CPU,
# atmintis, diskas, prisijungę vartotojai ir sunkiausios programos.
#
# Kas minutę paleidžia kursinis-status.timer; stdout patenka į journal (SyslogIdentifier=
# kursinis-status), iš ten per host syslog-ng — į kolektorių. Įrašą tikrina dashboard
# (app/services/host_status.py); formatas — docs/superpowers/specs/2026-10-29-device-detail-design.md.
# Komandų eilučių nesiunčiame (jose gali būti slaptažodžių) — tik procesų vardus.
# Nepavykęs šaltinis praleidžiamas: JSON visada teisingas, trūksta tik to lauko.
set -uo pipefail
export LC_ALL=C

SAMPLE_SECONDS="${SAMPLE_SECONDS:-1}"   # CPU matavimo langas
TOP_N="${TOP_N:-10}"                    # programų pagal CPU ir pagal atmintį (iš viso <= 2*TOP_N)

# JSON eilutė: kabutės ir \ ekranuojami, valdymo ir ne ASCII baitai -> „?".
JS='function js(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/[\001-\037\177-\377]/, "?", s); return "\"" s "\"" }'

# /proc/stat „cpu" eilutė -> "total busy" tick'ai (guest jau įskaičiuotas į user).
cpu_ticks() {
  awk '/^cpu / { t = 0; for (i = 2; i <= 9; i++) t += $i; print t, t - $5 - $6; exit }' /proc/stat
}

# Procesai: pid, sesija, ppid, utime+stime, rss (puslapiais), vardas. Vardas (comm) gali
# turėti tarpų ir „)", todėl laukai skaitomi nuo paskutinio „)".
proc_snapshot() {
  cat /proc/[0-9]*/stat 2>/dev/null | awk '{
    l = index($0, " ("); r = 0
    for (i = length($0); i > l; i--) if (substr($0, i, 1) == ")") { r = i; break }
    if (!l || !r) next
    name = substr($0, l + 2, r - l - 2); gsub(/\t/, " ", name)
    split(substr($0, r + 2), f, " ")
    printf "%s\t%s\t%s\t%d\t%d\t%s\n", substr($0, 1, l - 1), f[4], f[2], f[12] + f[13], f[22], name
  }'
}

read -r t0 b0 < <(cpu_ticks)
snap0=$(proc_snapshot)
sleep "$SAMPLE_SECONDS"
read -r t1 b1 < <(cpu_ticks)
snap1=$(proc_snapshot)
dt=$(( ${t1:-0} - ${t0:-0} ))

self_sid=$(awk '{ for (i = length($0); i > 0; i--) if (substr($0, i, 1) == ")") break
                  split(substr($0, i + 2), f, " "); print f[4] }' /proc/self/stat)
page_kb=$(( $(getconf PAGESIZE 2>/dev/null || echo 4096) / 1024 ))

# Programos: procesai sugrupuoti pagal vardą -> "tick'ai  atmintis_kb  procesai  vardas".
# Praleidžiamos branduolio gijos (PID 2 ir jo vaikai) ir paties skripto procesai (jo sesija).
groups=$(awk -F'\t' -v sid="$self_sid" -v page_kb="$page_kb" '
  FNR == NR { before[$1] = $4; next }
  $1 == 2 || $3 == 2 || $2 == sid { next }
  { d = $4 - (($1 in before) ? before[$1] : 0); if (d < 0) d = 0
    cpu[$6] += d; mem[$6] += $5 * page_kb; cnt[$6]++ }
  END { for (n in cnt) printf "%d\t%d\t%d\t%s\n", cpu[n], mem[n], cnt[n], n }
' <(printf '%s\n' "$snap0") <(printf '%s\n' "$snap1"))

fields=('"v":1')
add() { [[ -n "$2" ]] && fields+=("\"$1\":$2"); }

add uptime_s "$(awk '{ printf "%d", $1 }' /proc/uptime 2>/dev/null)"
add cpus "$(nproc 2>/dev/null)"
if (( dt > 0 )); then
  add cpu_pct "$(awk -v b=$(( b1 - b0 )) -v t="$dt" 'BEGIN { v = 100 * b / t; if (v < 0) v = 0; if (v > 100) v = 100; printf "%.1f", v }')"
fi
add load "$(awk '{ printf "[%s,%s,%s]", $1, $2, $3 }' /proc/loadavg 2>/dev/null)"
add mem_total_kb "$(awk '/^MemTotal:/ { print $2 }' /proc/meminfo 2>/dev/null)"
add mem_avail_kb "$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo 2>/dev/null)"
read -r disk_used disk_avail < <(df -Pk / 2>/dev/null | awk 'NR == 2 { print $3, $4 }')
add disk_used_kb "${disk_used:-}"
add disk_avail_kb "${disk_avail:-}"
add procs "$(printf '%s\n' "$groups" | awk -F'\t' 'NF { s += $3 } END { print s + 0 }')"

users=$(loginctl list-users --no-legend 2>/dev/null | awk '{ print $2 }')
[[ -n "$users" ]] || users=$(who 2>/dev/null | awk '{ print $1 }')
add users "[$(printf '%s\n' "$users" | sort -u | head -n 20 | awk "$JS"' NF { printf "%s%s", (n++ ? "," : ""), js($0) }')]"

if (( dt > 0 )); then
  add top "[$( { printf '%s\n' "$groups" | sort -t $'\t' -k1,1nr -k2,2nr | head -n "$TOP_N"
                 printf '%s\n' "$groups" | sort -t $'\t' -k2,2nr | head -n "$TOP_N"; } |
              awk -F'\t' 'NF && !seen[$4]++' | sort -t $'\t' -k1,1nr -k2,2nr |
              awk -F'\t' -v t="$dt" "$JS"' { c = 100 * $1 / t; if (c > 100) c = 100
                printf "%s{\"name\":%s,\"n\":%d,\"cpu\":%.1f,\"mem_kb\":%d}", (NR > 1 ? "," : ""), js($4), $3, c, $2 }')]"
fi

(IFS=,; printf '{%s}\n' "${fields[*]}")
```

- [ ] **Step 2: Create** `config/syslog-ng-host/kursinis-status.service`:

```ini
# Kursinis: šio kompiuterio būsenos įrašas (veikimo laikas, CPU, atmintis, diskas, programos).
# Įdiegia setup-host-syslog-ng.sh; kas minutę paleidžia kursinis-status.timer.
[Unit]
Description=Kursinis host status record

[Service]
Type=oneshot
ExecStart=/usr/local/libexec/kursinis-status
SyslogIdentifier=kursinis-status
# Tik skaito /proc, df ir loginctl: laikinas neprivilegijuotas vartotojas, be tinklo ir rašymo.
DynamicUser=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateNetwork=yes
```

- [ ] **Step 3: Create** `config/syslog-ng-host/kursinis-status.timer`:

```ini
# Kursinis: būsenos įrašas kas minutę (kursinis-status.service).
[Unit]
Description=Kursinis host status record every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=1s

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Check the script by hand**

Run: `bash -n config/syslog-ng-host/kursinis-status.sh && bash config/syslog-ng-host/kursinis-status.sh | python3 -m json.tool | head -20`
Expected: pretty-printed JSON with `"v": 1`, `uptime_s`, `cpu_pct`, `top` …

Run: `systemd-analyze verify config/syslog-ng-host/kursinis-status.service config/syslog-ng-host/kursinis-status.timer`
Expected: at most a warning that `/usr/local/libexec/kursinis-status` is not installed yet.

- [ ] **Step 5: Run the status tests**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_host_status.py -q`
Expected: all pass (including the contract test).

---

### Task 4: Install step on this PC and the collector filter

**Files:**
- Modify: `setup-host-syslog-ng.sh`, `config/syslog-ng/syslog-ng.conf`

- [ ] **Step 1: Header comment of `setup-host-syslog-ng.sh`** — after the line `# dashboard Devices tab / traffic graphs.` add:

```bash
# Also installs kursinis-status.timer: once a minute a status record (uptime, CPU,
# memory, disk, programs) goes the same way and fills the device detail page.
# Disable: sudo systemctl disable --now kursinis-status.timer
```

- [ ] **Step 2: New step 7** — replace the block that starts with `# 7. Testinė žinutė` with:

```bash
# 7. Būsenos įrašas kas minutę (CPU, atmintis, diskas, programos) -> journal -> kolektorius.
#    Dashboard rodo jį įrenginio puslapyje („Šis serveris").
echo "[*] Diegiamas būsenos įrašas (kursinis-status.timer, kas minutę)"
install -D -m 0755 "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.sh" /usr/local/libexec/kursinis-status
install -m 0644 "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.service" \
                "${SCRIPT_DIR}/config/syslog-ng-host/kursinis-status.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kursinis-status.timer
systemctl start kursinis-status.service   # pirmas įrašas iškart

# 8. Testinė žinutė (journald -> syslog-ng -> kolektorius)
sleep 3
logger -t kursinis-test "syslog-ng forwarding test from $(hostname)"
echo
echo "[OK] Atlikta. Testinė žinutė išsiųsta kaip host '$(hostname)'."
echo "     Būsena kas minutę: systemctl status kursinis-status.timer"
echo "     Dashboard: http://localhost:8080  ->  Įrenginiai / Devices."
```

(The old step 7 body — `sleep 3`, `logger …`, three `echo` lines — is replaced by the new step 8 above.)

- [ ] **Step 3: Collector filter** — in `config/syslog-ng/syslog-ng.conf` replace the `f_security` filter with:

```
# Saugumo filtrai - potencialiai pavojingi įvykiai.
# Būsenos įrašai (kursinis-status) praleidžiami: procesų varduose gali būti „denied", „blocked" ir pan.
filter f_security {
    not program("kursinis-status") and (
    match("Failed password" value("MESSAGE")) or
    match("authentication failure" value("MESSAGE")) or
    match("Invalid user" value("MESSAGE")) or
    match("BREAK-IN ATTEMPT" value("MESSAGE")) or
    match("refused connect" value("MESSAGE")) or
    match("unauthorized" value("MESSAGE")) or
    match("denied" value("MESSAGE")) or
    match("blocked" value("MESSAGE")) or
    match("attack" value("MESSAGE")) or
    match("DROP" value("MESSAGE")) or
    match("REJECT" value("MESSAGE"))
    );
};
```

(Keep the existing comment line above it if it says the same; do not duplicate it.)

- [ ] **Step 4: Verify syntax**

Run: `bash -n setup-host-syslog-ng.sh`
Expected: no output.

Run (throwaway container, same mounts as compose):
```bash
docker run --rm --entrypoint syslog-ng \
  -v "$PWD/config/syslog-ng/syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf:ro" \
  -v "$PWD/config/syslog-ng/conf.d:/etc/syslog-ng/conf.d:ro" \
  -v "$PWD/certs/server:/etc/syslog-ng/tls:ro" \
  balabit/syslog-ng:4.8.3 --syntax-only
```
Expected: exit code 0.

- [ ] **Step 5: Run `/verify`, then commit**

```bash
git add dashboard/app/log_selectors.py dashboard/app/routers/traffic.py dashboard/app/services/loki_client.py \
        dashboard/app/services/device_monitor.py dashboard/app/models/schemas.py dashboard/app/services/host_status.py \
        dashboard/tests/test_api.py dashboard/tests/test_host_status.py config/syslog-ng-host/kursinis-status.* \
        setup-host-syslog-ng.sh config/syslog-ng/syslog-ng.conf
git commit -m "feat(status): status heartbeat from this PC and its parser"
```

---

### Task 5: Activity classifier — syslog rules

**Files:**
- Create: `dashboard/app/services/activity.py`
- Test: `dashboard/tests/test_activity.py`

- [ ] **Step 1: Write the failing tests** — create `dashboard/tests/test_activity.py`:

```python
"""Įrenginio veiksmų klasifikavimas: tikros journal eilutės, demonstraciniai šablonai, Windows įvykiai."""
from __future__ import annotations

import datetime
import json

import pytest

from app.services.activity import TEXT_LIMIT, classify

T = datetime.datetime(2026, 10, 29, 8, 0, tzinfo=datetime.timezone.utc)
TS = str(int(T.timestamp()) * 10**9)


def syslog(program: str, message: str) -> dict:
    """Įrašas taip, kaip jį grąžina Loki: kolektoriaus syslog-ng šablono eilutė."""
    line = f"2026-10-29T08:00:00+00:00 pc auth.info {program}[42]: {message}"
    return {"timestamp": TS, "line": line, "labels": {"job": "syslog", "host": "pc"}}


def found(entry: dict):
    item = classify(entry)
    return None if item is None else (item.kind, item.user, item.text)


@pytest.mark.parametrize("program, message, expected", [
    ("sshd", "Accepted publickey for deploy from 192.168.1.50 port 51022 ssh2: ED25519 SHA256:abc",
     ("login", "deploy", "SSH login from 192.168.1.50 (publickey)")),
    ("sshd", "Failed password for invalid user admin from 203.0.113.7 port 40000 ssh2",
     ("auth_failed", "admin", "SSH login failed from 203.0.113.7")),
    ("sshd", "Failed password for root from 203.0.113.7 port 40001 ssh2",
     ("auth_failed", "root", "SSH login failed from 203.0.113.7")),
    ("systemd-logind", "New session '1' of user 'oxshan' with class 'user' and type 'tty'.",
     ("login", "oxshan", "Session 1 started")),
    ("systemd-logind", "New session 3 of user alice.",
     ("login", "alice", "Session 3 started")),
    ("sudo", "  oxshan : TTY=pts/0 ; PWD=/home/oxshan ; USER=root ; COMMAND=/usr/bin/pacman -S vscode",
     ("admin", "oxshan", "sudo /usr/bin/pacman -S vscode")),
    ("sudo", "  oxshan : a password is required ; PWD=/home/oxshan/Kursinis ; USER=root ; COMMAND=/usr/bin/true",
     ("auth_failed", "oxshan", "sudo: a password is required")),
    ("sudo", "  bob : 3 incorrect password attempts ; TTY=pts/1 ; PWD=/home/bob ; USER=root ; COMMAND=/usr/bin/id",
     ("auth_failed", "bob", "sudo: 3 incorrect password attempts")),
    ("su", "pam_unix(su:session): session opened for user root(uid=0) by oxshan(uid=1000)",
     ("admin", "oxshan", "su to root")),
    ("su", "pam_unix(su:auth): authentication failure; logname=oxshan uid=1000 euid=0 tty=/dev/pts/1 "
           "ruser=oxshan rhost=  user=root",
     ("auth_failed", "root", "su: authentication failure")),
    ("useradd", "new user: name=backdoor, UID=1001, GID=1001, home=/home/backdoor, shell=/bin/bash, from=/dev/pts/0",
     ("account", "backdoor", "User backdoor created")),
    ("groupadd", "new group: name=devs, GID=1002", ("account", "", "Group devs created")),
    ("usermod", "add 'alice' to group 'wheel'", ("account", "alice", "alice added to group wheel")),
    ("userdel", "delete user 'backdoor'", ("account", "backdoor", "User backdoor deleted")),
    ("passwd", "pam_unix(passwd:chauthtok): password changed for alice",
     ("account", "alice", "Password changed for alice")),
    ("kernel", "Linux version 7.3.0-5-cachyos (linux-cachyos@cachyos) (clang version 23.1.3) #1 SMP",
     ("boot", "", "System booted (Linux 7.3.0-5-cachyos)")),
    ("audisp-syslog", 'type=EXECVE msg=audit(1729501400.202:840): argc=3 a0="ls" a1="-la" a2=2F746D7020646972',
     ("command", "", "ls -la /tmp dir")),
], ids=["ssh-ok", "ssh-fail-invalid", "ssh-fail", "logind", "logind-old", "sudo", "sudo-nopass",
        "sudo-wrongpw", "su", "pam-fail", "useradd", "groupadd", "usermod", "userdel", "passwd", "boot", "execve"])
def test_real_syslog_lines(program, message, expected):
    assert found(syslog(program, message)) == expected


@pytest.mark.parametrize("program, message", [
    ("systemd-logind", "New session '2' of user 'oxshan' with class 'manager' and type 'unspecified'."),
    ("sudo", "pam_unix(sudo:session): session opened for user root(uid=0) by oxshan(uid=1000)"),
    ("sudo", "pam_unix(sudo:auth): authentication failure; logname=oxshan uid=1000 euid=0 tty=/dev/pts/1 "
             "ruser=oxshan rhost=  user=oxshan"),
    ("sshd", "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= "
             "rhost=203.0.113.7  user=root"),
    ("sshd", "Invalid user admin from 203.0.113.7 port 40000"),
    ("usermod", "add 'alice' to shadow group 'wheel'"),
    ("CRON", "(root) CMD (/usr/lib/sysstat/sa1 1 1)"),
    ("systemd", "Started Daily apt download activities."),
    ("kursinis-status", '{"v":1,"top":[{"name":"sudo","n":1,"cpu":0.0,"mem_kb":10}]}'),
    ("firewall", "input: in:ether1, proto TCP, 203.0.113.7:40000->192.168.1.1:22, DROP"),
], ids=["logind-manager", "sudo-pam-session", "sudo-pam-fail", "sshd-pam-fail", "ssh-invalid-user",
        "shadow-group", "cron", "systemd", "status-record", "firewall"])
def test_noise_is_not_an_action(program, message):
    assert classify(syslog(program, message)) is None


@pytest.mark.parametrize("program, message, expected", [
    ("loginwindow", "USER_PROCESS: user admin session opened", ("login", "admin", "Session opened")),
    ("Security-Auditing", "An account was successfully logged on (Event 4624) for admin from 192.168.1.60",
     ("login", "admin", "Logon from 192.168.1.60")),
    ("system", "user admin logged in from 192.168.1.50 via webfig",
     ("login", "admin", "Login from 192.168.1.50 via webfig")),
    ("Kernel-General", "The operating system started successfully", ("boot", "", "System started")),
    ("WindowsUpdateClient", "Installation Successful: Update KB5034123",
     ("update", "", "Update installed: Update KB5034123")),
], ids=["mac-login", "win-4624", "router-login", "win-boot", "win-update"])
def test_demo_device_lines(program, message, expected):
    assert found(syslog(program, message)) == expected


def test_raw_audit_line_without_syslog_prefix():
    entry = {"timestamp": TS, "line": 'type=EXECVE msg=audit(1:3): argc=2 a0="bash" a1="-i"',
             "labels": {"job": "linux_endpoint", "host": "lab"}}
    assert found(entry) == ("command", "", "bash -i")


def test_text_is_capped_and_time_is_iso():
    item = classify(syslog("sudo", "  bob : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/echo " + "x" * 500))
    assert item is not None and len(item.text) == TEXT_LIMIT and item.text.endswith("…")
    assert item.time == T.isoformat()


def test_entry_without_valid_timestamp_is_skipped():
    assert classify({**syslog("kernel", "Linux version 7.3.0 (x)"), "timestamp": "?"}) is None
```

- [ ] **Step 2: Run to see them fail**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_activity.py -q`
Expected: collection error (`ModuleNotFoundError: app.services.activity`).

- [ ] **Step 3: Implement** — create `dashboard/app/services/activity.py`:

```python
"""
Įrenginio veiksmų srautas („Paskutiniai veiksmai") iš jo žurnalų.

classify() verčia Loki įrašą į ActivityItem arba None (ne veiksmas). Syslog eilutės
skaidomos pagal kolektoriaus syslog-ng šabloną į programą ir žinutę; Windows įvykiai —
Alloy windowsevent JSON. Taisyklės tikrinamos eilės tvarka, galioja pirmoji tikusi.
Taisyklių pasirinkimas: docs/superpowers/specs/2026-10-29-device-detail-design.md (4.7).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from app.models.schemas import ActivityItem
from app.services.loki_client import ns_to_datetime

TEXT_LIMIT = 200
USER_LIMIT = 64

# Loki užklausų filtrai (device_details.py): syslog — RE2 eilučių filtras, Windows — įvykių ID.
SYSLOG_PREFILTER = "|".join((
    "Accepted ", r"Failed \S+ for ", "New session ", "COMMAND=", "session opened for user root",
    "authentication failure", "new user: ", "new group: ", "to group '", "delete user '",
    "password changed for ", "Linux version ", "type=EXECVE", "USER_PROCESS: ", "successfully logged on",
    "logged in from ", "The operating system started", "Installation Successful",
))
WINDOWS_EVENT_IDS = "4624|4625|4720|4726|4732|4740|1102|4104|1"

# syslog-ng šablonas: <laikas> <host> <facility>.<level> <program>[<pid>]: <žinutė>
_SYSLOG_RE = re.compile(r"^\S+\s+\S+\s+\w+\.\w+\s+(?P<program>[^\[]+)\[\d*\]:\s(?P<message>.*)$", re.DOTALL)
_EXECVE_ARG_RE = re.compile(r'\ba\d+=("[^"]*"|[0-9A-Fa-f]+)')

Found = tuple[str, str, str]   # (kind, user, text)


@dataclass(frozen=True)
class _Rule:
    programs: frozenset[str] | None     # None — bet kuri programa
    pattern: re.Pattern[str]
    kind: str
    build: Callable[[re.Match[str], str], tuple[str, str] | None]   # (user, text); None — ne veiksmas
    exclude: frozenset[str] = frozenset()


def _rule(programs, pattern: str, kind: str, build, exclude=()) -> _Rule:
    return _Rule(frozenset(programs) if programs else None, re.compile(pattern), kind, build, frozenset(exclude))


def _execve_command(args: str) -> str:
    """auditd EXECVE a0..aN -> komanda; reikšmes be kabučių auditd užkoduoja hex."""
    parts = []
    for raw in _EXECVE_ARG_RE.findall(args):
        if raw.startswith('"'):
            parts.append(raw[1:-1])
            continue
        try:
            parts.append(bytes.fromhex(raw).decode("utf-8", "replace"))
        except ValueError:
            parts.append(raw)
    return " ".join(parts)


def _logind(m: re.Match[str], _program: str) -> tuple[str, str] | None:
    # „manager" (vartotojo systemd), „greeter", „background" sesijos — ne prisijungimai.
    if m["cls"] not in (None, "user"):
        return None
    return m["user"], f"Session {m['id']} started"


# Programų vardai mažosiomis (lyginama be raidžių dydžio).
_SYSLOG_RULES: tuple[_Rule, ...] = (
    _rule({"sshd"}, r"^Accepted (\S+) for (\S+) from (\S+)", "login",
          lambda m, p: (m[2], f"SSH login from {m[3]} ({m[1]})")),
    _rule({"sshd"}, r"^Failed \S+ for (?:invalid user )?(\S+) from (\S+)", "auth_failed",
          lambda m, p: (m[1], f"SSH login failed from {m[2]}")),
    _rule({"systemd-logind"},
          r"^New session '?(?P<id>[^' ]+?)'? of user '?(?P<user>[^' ]+?)'?(?: with class '(?P<cls>[^']+)'|\.?$)",
          "login", _logind),
    # sudo: „user : <priežastis> ; ... COMMAND=" — nesėkmė; „user : TTY=... ; COMMAND=" — komanda.
    _rule({"sudo"}, r"^\s*(\S+) : ([^;=]+?)\s*;.*COMMAND=", "auth_failed",
          lambda m, p: (m[1], f"sudo: {m[2]}")),
    _rule({"sudo"}, r"^\s*(\S+) : .*COMMAND=(.+)$", "admin",
          lambda m, p: (m[1], f"sudo {m[2]}")),
    _rule({"su", "su-l"}, r"session opened for user root(?:\(uid=0\))? by ([^\s(]+)", "admin",
          lambda m, p: (m[1], "su to root")),
    # sshd ir sudo nesėkmes aprašo savo eilutės — pam dublikatų nerodome.
    _rule(None, r"authentication failure;.*\buser=(\S+)", "auth_failed",
          lambda m, p: (m[1], f"{p}: authentication failure"), exclude={"sshd", "sudo"}),
    _rule({"useradd"}, r"^new user: name=([^,\s]+)", "account",
          lambda m, p: (m[1], f"User {m[1]} created")),
    _rule({"useradd", "groupadd"}, r"^new group: name=([^,\s]+)", "account",
          lambda m, p: ("", f"Group {m[1]} created")),
    _rule({"usermod", "gpasswd"}, r"add '([^']+)' to group '([^']+)'", "account",
          lambda m, p: (m[1], f"{m[1]} added to group {m[2]}")),
    _rule({"userdel"}, r"^delete user '([^']+)'", "account",
          lambda m, p: (m[1], f"User {m[1]} deleted")),
    _rule({"passwd", "chpasswd"}, r"password changed for (\S+)", "account",
          lambda m, p: (m[1], f"Password changed for {m[1]}")),
    _rule({"kernel"}, r"^Linux version (\S+)", "boot",
          lambda m, p: ("", f"System booted (Linux {m[1]})")),
    _rule(None, r"type=EXECVE\b.*?\bargc=\d+\s(.*)$", "command",
          lambda m, p: ("", _execve_command(m[1]))),
    # Demonstraciniai įrenginiai (services/syslog_emitter.py šablonai)
    _rule({"loginwindow"}, r"USER_PROCESS: user (\S+) session opened", "login",
          lambda m, p: (m[1], "Session opened")),
    _rule({"security-auditing"}, r"successfully logged on \(Event 4624\) for (\S+)(?: from (\S+))?", "login",
          lambda m, p: (m[1], f"Logon from {m[2]}" if m[2] else "Logon")),
    _rule({"system"}, r"^user (\S+) logged in from (\S+) via (\S+)", "login",
          lambda m, p: (m[1], f"Login from {m[2]} via {m[3]}")),
    _rule({"kernel-general"}, r"The operating system started", "boot",
          lambda m, p: ("", "System started")),
    _rule({"windowsupdateclient"}, r"Installation Successful: (.+)$", "update",
          lambda m, p: ("", f"Update installed: {m[1]}")),
)


def _classify_syslog(line: str) -> Found | None:
    m = _SYSLOG_RE.match(line)
    # Be syslog šablono (linux_endpoint: žalias auditd įrašas) tikrinama visa eilutė.
    program, message = (m["program"].strip().lower(), m["message"]) if m else ("", line)
    for rule in _SYSLOG_RULES:
        if (rule.programs is not None and program not in rule.programs) or program in rule.exclude:
            continue
        hit = rule.pattern.search(message)
        if hit:
            built = rule.build(hit, program)
            return None if built is None else (rule.kind, *built)
    return None


def _classify_windows(obj: dict) -> Found | None:
    return None   # Task 6


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT - 1] + "…"


def classify(entry: dict) -> ActivityItem | None:
    """Loki įrašas ({timestamp, line, labels}) -> ActivityItem; None, jei tai ne veiksmas."""
    when = ns_to_datetime(entry.get("timestamp"))
    line = entry.get("line") or ""
    if when is None or not line:
        return None
    if (entry.get("labels") or {}).get("job") == "windows":
        try:
            obj = json.loads(line)
        except ValueError:
            return None
        hit = _classify_windows(obj) if isinstance(obj, dict) else None
    else:
        hit = _classify_syslog(line)
    if hit is None:
        return None
    kind, user, text = hit
    return ActivityItem(time=when.isoformat(), kind=kind, user=user[:USER_LIMIT], text=_clip(text))
```

- [ ] **Step 4: Run the tests**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_activity.py -q`
Expected: all pass.

---

### Task 6: Activity classifier — Windows events

**Files:**
- Modify: `dashboard/app/services/activity.py`
- Test: `dashboard/tests/test_activity.py`

- [ ] **Step 1: Write the failing tests** — append to `dashboard/tests/test_activity.py`:

```python
def win(event_id: int, data: dict, channel: str = "Security", **extra) -> dict:
    """Alloy windowsevent JSON eilutė (kaip anomaly-detector tests/fixtures/windows)."""
    event_data = "".join(f'<Data Name="{k}">{v}</Data>' for k, v in data.items())
    obj = {"source": "Microsoft-Windows-Security-Auditing", "channel": channel, "computer": "WIN11-LAB",
           "event_id": event_id, "levelText": "Information", "event_data": event_data, **extra}
    return {"timestamp": TS, "line": json.dumps(obj), "labels": {"job": "windows", "host": "WIN11-LAB"}}


@pytest.mark.parametrize("entry, expected", [
    (win(4624, {"TargetUserName": "jdoe", "LogonType": "2", "IpAddress": "-"}),
     ("login", "jdoe", "Logon (interactive)")),
    (win(4624, {"TargetUserName": "jdoe", "LogonType": "10", "IpAddress": "10.0.0.5"}),
     ("login", "jdoe", "Logon (remote) from 10.0.0.5")),
    (win(4625, {"TargetUserName": "administrator", "LogonType": "3", "IpAddress": "203.0.113.7"}),
     ("auth_failed", "administrator", "Logon failed from 203.0.113.7")),
    (win(4720, {"TargetUserName": "backdoor", "SubjectUserName": "admin"}),
     ("account", "backdoor", "User backdoor created by admin")),
    (win(4726, {"TargetUserName": "backdoor", "SubjectUserName": "admin"}),
     ("account", "backdoor", "User backdoor deleted by admin")),
    (win(4732, {"MemberName": "-", "MemberSid": "S-1-5-21-1-2-3-1001", "TargetUserName": "Administrators"}),
     ("account", "S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1001 added to group Administrators")),
    (win(4740, {"TargetUserName": "jdoe"}), ("account", "jdoe", "Account jdoe locked out")),
    (win(1102, {}, user_data="<LogFileCleared><SubjectUserName>admin</SubjectUserName></LogFileCleared>"),
     ("log_cleared", "admin", "Security log cleared")),
    (win(4104, {"ScriptBlockText": "IEX (New-Object Net.WebClient).DownloadString('http://x')"},
         channel="Microsoft-Windows-PowerShell/Operational", levelText="Warning"),
     ("script", "", "Suspicious PowerShell: IEX (New-Object Net.WebClient).DownloadString('http://x')")),
    (win(1, {"Image": "C:\\Windows\\System32\\whoami.exe", "CommandLine": "whoami /all", "User": "LAB\\jdoe"},
         channel="Microsoft-Windows-Sysmon/Operational"),
     ("command", "LAB\\jdoe", "whoami.exe: whoami /all")),
], ids=["4624-interactive", "4624-remote", "4625", "4720", "4726", "4732", "4740", "1102", "4104-warning", "sysmon-1"])
def test_windows_events(entry, expected):
    assert found(entry) == expected


@pytest.mark.parametrize("entry", [
    win(4624, {"TargetUserName": "SYSTEM", "LogonType": "5"}),
    win(4624, {"TargetUserName": "jdoe", "LogonType": "3"}),
    win(4104, {"ScriptBlockText": "Get-Date"}, channel="Microsoft-Windows-PowerShell/Operational"),
    win(1, {"Image": "x.exe"}, channel="Security"),
    win(3, {"Image": "x.exe"}, channel="Microsoft-Windows-Sysmon/Operational"),
    {"timestamp": TS, "line": "not json", "labels": {"job": "windows"}},
], ids=["4624-service", "4624-network", "4104-verbose", "eid1-not-sysmon", "sysmon-3", "bad-json"])
def test_windows_noise(entry):
    assert classify(entry) is None
```

- [ ] **Step 2: Run to see them fail**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_activity.py -q -k windows`
Expected: the 10 `test_windows_events` cases fail (`None != (...)`); `test_windows_noise` passes.

- [ ] **Step 3: Implement** — in `dashboard/app/services/activity.py` add after `_EXECVE_ARG_RE`:

```python
_DATA_RE = re.compile(r'<Data Name="([^"]+)">(.*?)</Data>', re.DOTALL)
_USERDATA_RE = re.compile(r"<(\w+)>([^<]*)</\1>")
_LOGON_TYPES = {"2": "interactive", "7": "unlock", "10": "remote", "11": "cached"}
```

and replace the `_classify_windows` stub with:

```python
def _win_fields(obj: dict) -> dict[str, str]:
    """<Data Name="K">V</Data> (EventData) ir <K>V</K> (UserData, pvz. 1102) -> laukai."""
    fields = dict(_DATA_RE.findall(str(obj.get("event_data") or "")))
    fields.update(_USERDATA_RE.findall(str(obj.get("user_data") or "")))
    return fields


def _from(ip: str) -> str:
    return f" from {ip}" if ip and ip not in ("-", "::1", "127.0.0.1") else ""


def _classify_windows(obj: dict) -> Found | None:
    try:
        eid = int(obj.get("event_id"))
    except (TypeError, ValueError):
        return None
    d = _win_fields(obj)
    target, subject = d.get("TargetUserName", ""), d.get("SubjectUserName", "")
    if eid == 1:
        if "sysmon" not in str(obj.get("channel", "")).lower():
            return None
        image = d.get("Image", "").rsplit("\\", 1)[-1]
        return "command", d.get("User", ""), f"{image}: {d.get('CommandLine', '')}"
    if eid == 4624:
        logon = _LOGON_TYPES.get(d.get("LogonType", ""))   # tarnybos (5) ir tinklo (3) — triukšmas
        return ("login", target, f"Logon ({logon}){_from(d.get('IpAddress', ''))}") if logon else None
    if eid == 4625:
        return "auth_failed", target, f"Logon failed{_from(d.get('IpAddress', ''))}"
    if eid in (4720, 4726):
        return "account", target, f"User {target} {'created' if eid == 4720 else 'deleted'} by {subject}"
    if eid == 4732:
        member = d.get("MemberName", "")
        member = d.get("MemberSid", "") if member in ("", "-") else member
        return "account", member, f"{member} added to group {target}"
    if eid == 4740:
        return "account", target, f"Account {target} locked out"
    if eid == 1102:
        return "log_cleared", subject, "Security log cleared"
    # 4104: tik tie, kuriuos pati Windows pažymėjo kaip įtartinus (Warning lygis).
    if eid == 4104 and (str(obj.get("level")) == "3" or obj.get("levelText") == "Warning"):
        return "script", "", f"Suspicious PowerShell: {d.get('ScriptBlockText', '')[:120]}"
    return None
```

- [ ] **Step 4: Run the tests**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_activity.py -q`
Expected: all pass.

- [ ] **Step 5: Run `/verify`, then commit**

```bash
git add dashboard/app/services/activity.py dashboard/tests/test_activity.py
git commit -m "feat(dashboard): classify device activity from its logs"
```

---

### Task 7: Device details service and endpoint

**Files:**
- Create: `dashboard/app/services/device_details.py`
- Modify: `dashboard/app/dependencies.py`, `dashboard/app/main.py`, `dashboard/app/routers/devices.py`
- Test: `dashboard/tests/test_api.py`

- [ ] **Step 1: Write the failing tests** — append to `dashboard/tests/test_api.py`:

```python
# -- Įrenginio detalės ------------------------------------------------------------

class _DetailsLoki:
    """Netikras Loki detalių užklausoms: atsakymas pagal užklausos srautą."""

    def __init__(self):
        self.rows = {"status": [], "syslog": [], "windows": []}
        self.queries: list[str] = []

    async def query_range(self, query, start=None, end=None, limit=5000):
        self.queries.append(query)
        if 'program="kursinis-status"' in query:
            return self.rows["status"]
        return self.rows["windows" if 'job="windows"' in query else "syslog"]


def _row(line: str, minutes_ago: float = 1) -> dict:
    ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return {"timestamp": str(int(ts.timestamp()) * 10**9), "line": line, "labels": {"job": "syslog"}}


@pytest.fixture
def details(env, tmp_path):
    """Detalių paslauga su netikru Loki; šio serverio vardas — „testhost"."""
    from app.dependencies import get_device_details
    from app.services.alert_reader import AlertReader
    from app.services.device_details import DeviceDetailsService
    from app.services.device_registry import DeviceRegistry
    from app.services.host_info import HostInfo

    host_dir = tmp_path / "host"
    host_dir.mkdir()
    (host_dir / "hostname").write_text("testhost\n")
    loki = _DetailsLoki()
    service = DeviceDetailsService(loki, DeviceRegistry(), AlertReader(), HostInfo(str(host_dir)))
    env.app.dependency_overrides[get_device_details] = lambda: service
    yield loki
    env.app.dependency_overrides.clear()


def test_device_details_for_this_server(client, details):
    record = ('{"v":1,"cpu_pct":12.5,"mem_total_kb":1000,"mem_avail_kb":250,'
              '"top":[{"name":"firefox","n":3,"cpu":4.5,"mem_kb":5000}]}')
    details.rows["status"] = [_row(f"2026-10-29T12:00:00+00:00 testhost daemon.info kursinis-status[7]: {record}")]
    details.rows["syslog"] = [
        _row("2026-10-29T12:00:00+00:00 testhost auth.notice sudo[9]:   oxshan : TTY=pts/0 ; PWD=/ ; "
             "USER=root ; COMMAND=/usr/bin/id", 2),
        _row("2026-10-29T12:00:00+00:00 testhost daemon.info systemd[1]: Started Daily apt download activities.", 3),
    ]
    resp = client.get("/api/devices/self/details", headers=_login(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"]["cpu_pct"] == 12.5 and body["status"]["programs"][0]["name"] == "firefox"
    assert [p["mem_pct"] for p in body["history"]] == [75.0]
    assert [(a["kind"], a["user"]) for a in body["activity"]] == [("admin", "oxshan")]
    assert len(details.queries) == 3 and all('host="testhost"' in q for q in details.queries)


def test_device_details_alerts_match_hostname(client, details, env):
    (env.tmp / "anomaly_history.json").write_text(json.dumps([
        {"timestamp": "2026-10-29T10:00:00+00:00", "alert_type": "ssh_bruteforce", "severity": "high",
         "source_ip": "203.0.113.7", "source_host": "web-server-01", "detection_method": "rule", "details": {}},
        {"timestamp": "2026-10-29T11:00:00+00:00", "alert_type": "firewall_spike", "severity": "medium",
         "source_ip": "203.0.113.7", "source_host": "router-01", "detection_method": "rule", "details": {}},
    ]))
    body = client.get("/api/devices/web-server-01/details", headers=_login(client)).json()
    assert body["status"] is None and body["history"] == [] and body["activity"] == []
    assert [a["alert_type"] for a in body["alerts"]] == ["ssh_bruteforce"]


@pytest.mark.parametrize("key", ["bad host", 'x"y', "a" * 256])
def test_device_details_rejects_bad_keys(client, details, key):
    from urllib.parse import quote
    assert client.get(f"/api/devices/{quote(key, safe='')}/details", headers=_login(client)).status_code == 404
    assert details.queries == []


def test_device_details_self_needs_host_info(tmp_path):
    from app.services.device_details import DeviceDetailsService, DeviceNotFound
    from app.services.host_info import HostInfo
    service = DeviceDetailsService(_DetailsLoki(), registry=None, alert_reader=None, host_info=HostInfo(str(tmp_path)))
    with pytest.raises(DeviceNotFound):
        service.resolve("self")


def test_device_details_requires_login(client):
    assert client.get("/api/devices/self/details").status_code == 401
```

Also add `import json` to the imports at the top of `test_api.py`.

- [ ] **Step 2: Run to see them fail**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_api.py -q -k details`
Expected: failures (`ImportError: cannot import name 'get_device_details'` / module not found).

- [ ] **Step 3: Implement the service** — create `dashboard/app/services/device_details.py`:

```python
"""
Įrenginio detalių puslapio duomenys: būsena (status heartbeat), paskutiniai veiksmai, įspėjimai.

Raktas — „self" (šis serveris; tikras hostname URL'e nerodomas) arba Loki host etiketė.
Trys Loki užklausos vykdomos lygiagrečiai: būsenos srautas, syslog veiksmai, Windows įvykiai.
"""
from __future__ import annotations

import asyncio
import datetime

from app.log_selectors import valid_host
from app.models.schemas import ActivityItem, DeviceDetails
from app.services.activity import SYSLOG_PREFILTER, WINDOWS_EVENT_IDS, classify
from app.services.alert_reader import AlertReader
from app.services.device_monitor import alerts_for_device
from app.services.device_registry import DeviceRegistry
from app.services.host_info import HostInfo
from app.services.host_status import STATUS_PROGRAM, build_status
from app.services.loki_client import AsyncLokiClient

SELF_KEY = "self"
LOOKBACK = datetime.timedelta(hours=24)
STATUS_LIMIT = 120           # ~2 val. įrašų (kas minutę)
ACTIVITY_QUERY_LIMIT = 500
ACTIVITY_LIMIT = 50
ALERT_LIMIT = 20


class DeviceNotFound(Exception):
    """Netinkamas raktas arba nežinomas savo serveris."""


def _ns(entry: dict) -> int:
    try:
        return int(entry.get("timestamp", 0))
    except (TypeError, ValueError):
        return 0


class DeviceDetailsService:
    def __init__(
        self,
        loki: AsyncLokiClient,
        registry: DeviceRegistry,
        alert_reader: AlertReader,
        host_info: HostInfo,
    ) -> None:
        self._loki = loki
        self._registry = registry
        self._alert_reader = alert_reader
        self._host_info = host_info

    def resolve(self, key: str) -> str:
        """Maršruto raktas -> Loki host etiketė. DeviceNotFound, jei raktas netinkamas."""
        if key == SELF_KEY:
            host = self._host_info.get()
            if not host or not valid_host(host.get("hostname")):
                raise DeviceNotFound(key)
            return host["hostname"]
        if not valid_host(key):
            raise DeviceNotFound(key)
        return key

    async def details(self, key: str, now: datetime.datetime | None = None) -> DeviceDetails:
        host = self.resolve(key)
        now = now or datetime.datetime.now(datetime.timezone.utc)
        start = now - LOOKBACK
        status_query = f'{{job="syslog", host="{host}", program="{STATUS_PROGRAM}"}}'
        syslog_query = (f'{{job=~"syslog|linux_endpoint", host="{host}", program!="{STATUS_PROGRAM}"}} '
                        f'|~ `{SYSLOG_PREFILTER}`')
        windows_query = f'{{job="windows", host="{host}"}} | json event_id | event_id=~"{WINDOWS_EVENT_IDS}"'
        status_rows, syslog_rows, windows_rows = await asyncio.gather(
            self._loki.query_range(status_query, start=start, end=now, limit=STATUS_LIMIT),
            self._loki.query_range(syslog_query, start=start, end=now, limit=ACTIVITY_QUERY_LIMIT),
            self._loki.query_range(windows_query, start=start, end=now, limit=ACTIVITY_QUERY_LIMIT),
        )
        status, history = build_status(status_rows, now)

        activity: list[ActivityItem] = []
        for row in sorted(syslog_rows + windows_rows, key=_ns, reverse=True):
            item = classify(row)
            if item is not None:
                activity.append(item)
                if len(activity) == ACTIVITY_LIMIT:
                    break

        ip = next((d.get("ip", "") for d in self._registry.list_all() if d.get("hostname") == host), "")
        alerts = alerts_for_device(ip, host, self._alert_reader.read_all())[:ALERT_LIMIT]
        return DeviceDetails(status=status, history=history, activity=activity, alerts=alerts)
```

- [ ] **Step 4: Wire it up**

`dashboard/app/dependencies.py` — add the import `from app.services.device_details import DeviceDetailsService` and, after `get_device_monitor`:

```python
def get_device_details(request: Request) -> DeviceDetailsService:
    return request.app.state.device_details
```

`dashboard/app/main.py` — add `from app.services.device_details import DeviceDetailsService` to the imports and, right after the `app.state.device_monitor = DeviceMonitor(...)` block:

```python
        app.state.device_details = DeviceDetailsService(
            loki=loki,
            registry=app.state.device_registry,
            alert_reader=app.state.alert_reader,
            host_info=app.state.host_info,
        )
```

`dashboard/app/routers/devices.py` — add `get_device_details` to the `app.dependencies` import, `DeviceDetails` to the `app.models.schemas` import, `from app.services.device_details import DeviceDetailsService, DeviceNotFound`, and after `device_map`:

```python
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
```

- [ ] **Step 5: Run the whole suite**

Run: `cd dashboard && .venv/bin/python -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Run `/verify`, then commit**

```bash
git add dashboard/app/services/device_details.py dashboard/app/dependencies.py dashboard/app/main.py \
        dashboard/app/routers/devices.py dashboard/tests/test_api.py
git commit -m "feat(dashboard): device details API"
```

---

### Task 8: Frontend plumbing (state, routing, helpers)

**Files:**
- Modify: `dashboard/app/static/js/state.js`, `shell.js`, `format.js`, `charts.js`, `alert-dialog.js`, `pages/anomalies.js`
- Create: `dashboard/app/static/js/pages/device-meta.js`

- [ ] **Step 1: `state.js`** — add before `_lastHistory`:

```js
  devicesLoaded:false,   // ar įrenginių žemėlapis jau gautas (detalių puslapio „nerastas")
  deviceKey:    "",      // atidarytas įrenginys (#devices/<raktas>): "self" arba hostname
  deviceDetail: null,    // /api/devices/<raktas>/details atsakymas
  deviceDetailKey: "",   // kuriam raktui priklauso deviceDetail
  deviceLogs:   null,    // „Visi logai" skirtukas (null — dar nekrauta)
  deviceSort:   "cpu",   // programų rikiavimas: cpu | mem
  deviceTab:    "actions", // veiksmų skydelio skirtukas: actions | logs
  _lastDeviceDetail: 0,  // detalių atnaujinimo throttle žyma
```

- [ ] **Step 2: `shell.js` routing** — replace `initNavigation`, `navigate`, `pageFromHash` and `showPage` with:

```js
export function initNavigation(enter) {
  onEnter = enter;
  document.querySelectorAll("[data-nav]").forEach(btn =>
    btn.addEventListener("click", () => navigate(btn.dataset.nav)));
  window.addEventListener("hashchange", () => showPage(routeFromHash()));
  showPage(routeFromHash());
}

// route — puslapis („devices") arba įrenginys („devices/self").
export function navigate(route) {
  if (location.hash === "#" + route) showPage(routeFromHash());
  else location.hash = route;
}

// #puslapis arba #devices/<įrenginio raktas>.
function routeFromHash() {
  const [page, ...rest] = location.hash.slice(1).split("/");
  if (!PAGES.includes(page)) return { page: "dashboard", sub: "" };
  let sub = "";
  if (page === "devices" && rest.length) {
    try { sub = decodeURIComponent(rest.join("/")); } catch (_) { sub = ""; }
  }
  return { page, sub };
}

function showPage({ page, sub }) {
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  PAGES.forEach(p => { const b = el("nav-" + p); if (b) b.classList.toggle("active", p === page); });
  state.page = page;
  state.deviceKey = sub;
  setCrumb(t("nav_" + page));
  onEnter(page);
}

// Viršutinės juostos kelias („Įrenginiai" arba „Įrenginiai › MacBook").
export function setCrumb(text) {
  setText("crumb-page", text);
}
```

and in `refreshFrameLabels()` replace `setText("crumb-page", t("nav_" + state.page));` with `setCrumb(t("nav_" + state.page));`.

- [ ] **Step 3: `format.js`** — append:

```js
const locale = () => (state.lang === "lt" ? "lt-LT" : "en-GB");

function oneDecimal(n) {
  return Number(n).toLocaleString(locale(), { maximumFractionDigits: 1 });
}

// Procentai su viena dešimtaine („12,5 %").
export function pctFmt(v) {
  return v == null || !isFinite(v) ? "—" : `${oneDecimal(v)} %`;
}

// Kilobaitai -> „1,5 GB" / „812 MB" / „64 KB".
export function sizeFmt(kb) {
  if (kb == null || !isFinite(kb)) return "—";
  if (kb >= 1048576) return `${oneDecimal(kb / 1048576)} GB`;
  if (kb >= 1024) return `${Math.round(kb / 1024)} MB`;
  return `${Math.round(kb)} KB`;
}

// Trukmė sekundėmis -> „3 d. 4 val." / „4 val. 12 min." / „12 min.".
export function durationFmt(sec) {
  if (sec == null || !isFinite(sec)) return "—";
  const u = t("dur_units");
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d) return `${d} ${u.d} ${h} ${u.h}`;
  if (h) return `${h} ${u.h} ${m} ${u.m}`;
  return `${m} ${u.m}`;
}

// Apkrovos vidurkis su dviem dešimtainėmis („0,52").
export function loadFmt(v) {
  return v == null || !isFinite(v) ? "—"
    : Number(v).toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Žurnalo eilutės kairės juostos spalva pagal lygį (anomalijų ir įrenginio „Visi logai").
export const LOG_SEV_COLOR = {
  emerg: "var(--crit)", alert: "var(--crit)", crit: "var(--crit)", err: "var(--crit)", error: "var(--crit)",
  warning: "var(--warn)", warn: "var(--warn)",
  notice: "var(--ok)", info: "var(--ok)", debug: "var(--text-dim)",
};
```

- [ ] **Step 4: `pages/anomalies.js`** — delete its local `const LOG_SEV_COLOR = {…};` block and add `LOG_SEV_COLOR` to its `../format.js` import.

- [ ] **Step 5: `charts.js`** — change the `sparkline` signature and the `max` line:

```js
export function sparkline(svg, values, color, max = Math.max(...values) || 1) {
```

and delete the line `const max = Math.max(...values) || 1;` inside it.

- [ ] **Step 6: `alert-dialog.js`** — `function sevBadge(severity) {` → `export function sevBadge(severity) {`.

- [ ] **Step 7: Create `pages/device-meta.js`:**

```js
// Įrenginių OS ir šaltinio užrašai bei maršruto raktas (sąrašas ir detalių puslapis).

import { t } from "../i18n.js";

export const OS_META = {
  macos:   { icon: "laptop_mac",     label: () => t("dev_os_macos") },
  windows: { icon: "laptop_windows", label: () => t("dev_os_windows") },
  linux:   { icon: "dns",            label: () => t("dev_os_linux") },
  router:  { icon: "router",         label: () => t("dev_os_router") },
  server:  { icon: "dns",            label: () => t("dev_os_server") },
  unknown: { icon: "devices_other",  label: () => t("dev_os_unknown") },
};

const SRC_LABEL = {
  self:       () => t("src_self"),
  registered: () => t("src_registered"),
  discovered: () => t("src_discovered"),
};

export function osLabel(d) {
  return (OS_META[d.os] || OS_META.unknown).label();
}

export function sourceLabel(d) {
  return (SRC_LABEL[d.source] || (() => d.source))();
}

// #devices/<raktas>: savo serveris — „self" (tikras hostname URL'e nerodomas), kiti — hostname.
export function deviceKey(d) {
  return d.source === "self" ? "self" : d.hostname;
}
```

- [ ] **Step 8: Static checks**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_frontend_static.py -q`
Expected: pass.

---

### Task 9: Markup, styles and strings

**Files:**
- Modify: `dashboard/app/static/index.html`, `dashboard/app/static/css/theme.css`, `dashboard/app/static/js/i18n.js`
- Test: `dashboard/tests/test_frontend_static.py`

- [ ] **Step 1: Write the failing i18n test** — append to `dashboard/tests/test_frontend_static.py`:

```python
I18N_JS = STATIC / "js" / "i18n.js"
DATA_I18N = re.compile(r'data-i18n(?:-title|-placeholder)?="([^"]+)"')


def test_static_labels_exist_in_both_languages():
    lt, en = I18N_JS.read_text(encoding="utf-8").split("\n  en: {", 1)
    for key in set(DATA_I18N.findall((STATIC / "index.html").read_text(encoding="utf-8"))):
        key_re = re.compile(rf"^\s+{re.escape(key)}:", re.MULTILINE)
        assert key_re.search(lt) and key_re.search(en), key
```

- [ ] **Step 2: Wrap the device list and add the detail view** in `index.html`.

Replace `<section id="page-devices" class="page">` + the blank line after it with:

```html
  <section id="page-devices" class="page">
   <div id="devices-list">
```

Then replace the end of the section (the grid's closing `</div>` followed by the blank line and `</section>`) so that it reads:

```html
    </div>
   </div>

    <!-- Vieno įrenginio puslapis (#devices/<raktas>) -->
    <div id="device-detail" class="hidden">
      <div class="ctl-row">
        <button data-dd-back class="btn">
          <span class="material-symbols-outlined">arrow_back</span>
          <span data-i18n="dd_back">Įrenginiai</span>
        </button>
        <span id="dd-dot" class="app-dot"></span>
        <h2 id="dd-name" class="dd-title">—</h2>
        <span id="dd-meta" class="text-muted text-[12px]"></span>
        <span id="dd-updated" class="ml-auto text-[12px] text-muted"></span>
      </div>

      <div id="dd-notfound" class="hidden panel">
        <p class="empty" data-i18n="dd_not_found">Įrenginys nerastas.</p>
        <div class="flex justify-center pb-4">
          <button data-dd-back class="btn"><span class="material-symbols-outlined">arrow_back</span><span data-i18n="dd_back">Įrenginiai</span></button>
        </div>
      </div>

      <div id="dd-body" class="grid grid-cols-12 gap-2">
        <div id="dd-nostatus" class="hidden banner is-info col-span-12">
          <span class="material-symbols-outlined text-[17px] text-accent">info</span>
          <span id="dd-nostatus-text"></span>
        </div>

        <div class="panel stat dd-tile col-span-12 sm:col-span-6 xl:col-span-3">
          <div class="panel-h"><span data-i18n="dd_uptime">Veikia</span></div>
          <div id="dd-uptime" class="stat-v">—</div>
        </div>
        <div class="panel stat dd-tile col-span-12 sm:col-span-6 xl:col-span-3">
          <div class="panel-h"><span data-i18n="dd_cpu">CPU</span><small id="dd-cpu-sub"></small></div>
          <div id="dd-cpu" class="stat-v">—</div>
          <svg id="dd-cpu-spark" class="stat-spark" viewBox="0 0 300 44" preserveAspectRatio="none"></svg>
        </div>
        <div class="panel stat dd-tile col-span-12 sm:col-span-6 xl:col-span-3">
          <div class="panel-h"><span data-i18n="dd_memory">Atmintis</span><small id="dd-mem-sub"></small></div>
          <div id="dd-mem" class="stat-v">—</div>
          <svg id="dd-mem-spark" class="stat-spark" viewBox="0 0 300 44" preserveAspectRatio="none"></svg>
        </div>
        <div class="panel stat dd-tile col-span-12 sm:col-span-6 xl:col-span-3">
          <div class="panel-h"><span data-i18n="dd_disk">Diskas (/)</span><small id="dd-disk-sub"></small></div>
          <div id="dd-disk" class="stat-v">—</div>
        </div>

        <div class="panel col-span-12 xl:col-span-7">
          <div class="panel-h"><span data-i18n="dd_programs">Veikiančios programos</span><small id="dd-programs-foot"></small></div>
          <div class="panel-b overflow-x-auto">
            <table class="tbl">
              <thead><tr>
                <th data-i18n="dd_program">Programa</th>
                <th class="text-right" data-i18n="dd_processes">Procesai</th>
                <th class="text-right"><button id="dd-sort-cpu" class="link-btn" data-i18n="dd_cpu">CPU</button></th>
                <th class="text-right"><button id="dd-sort-mem" class="link-btn" data-i18n="dd_memory">Atmintis</button></th>
              </tr></thead>
              <tbody id="dd-programs-tbody"></tbody>
            </table>
          </div>
        </div>

        <div class="panel col-span-12 xl:col-span-5">
          <div class="panel-h"><span data-i18n="dd_info">Įrenginio informacija</span></div>
          <dl id="dd-info" class="panel-b kv"></dl>
        </div>

        <div class="panel col-span-12 xl:col-span-7">
          <div class="panel-h">
            <span class="flex items-center gap-1">
              <button id="dd-tab-actions" class="dd-tab is-active" data-i18n="dd_tab_actions">Veiksmai</button>
              <button id="dd-tab-logs" class="dd-tab" data-i18n="dd_tab_logs">Visi logai</button>
            </span>
            <small data-i18n="dd_last_24h">Paskutinės 24 val.</small>
          </div>
          <div class="panel-b">
            <div id="dd-activity" class="dd-feed"></div>
            <div id="dd-logs" class="hidden logs"></div>
          </div>
        </div>

        <div class="panel col-span-12 xl:col-span-5">
          <div class="panel-h"><span data-i18n="dd_alerts">Šio įrenginio įspėjimai</span></div>
          <div class="panel-b overflow-x-auto">
            <table class="tbl"><tbody id="dd-alerts-tbody"></tbody></table>
          </div>
        </div>
      </div>
    </div>

  </section>
```

- [ ] **Step 3: Remove the info dialog** — delete the whole block from `<!-- ======================== ĮRENGINIO INFORMACIJOS MODALAS ======================== -->` through the closing `</div>` of `#device-info-modal` (two closing `</div>` lines after `</dl>`).

- [ ] **Step 4: Styles** — append to `dashboard/app/static/css/theme.css`:

```css
/* ===== Įrenginio detalės (#devices/<raktas>) ===== */
.dd-title { font-size: 15px; font-weight: 600; color: var(--text-strong); }
.dd-tab { height: 24px; padding: 0 8px; border-radius: 3px; border: 0; background: none; color: var(--text-muted);
  font-size: 12.5px; font-weight: 500; cursor: pointer; }
.dd-tab:hover { color: var(--text-strong); }
.dd-tab.is-active { background: var(--hover); color: var(--text-strong); }
.dd-feed { max-height: 420px; overflow: auto; }
.dd-item { display: grid; grid-template-columns: 86px 20px minmax(0, 1fr); gap: 8px; padding: 6px 2px;
  border-bottom: 1px solid var(--line-weak); font-size: 12.5px; }
.dd-item:last-child { border-bottom: 0; }
.dd-item .material-symbols-outlined { font-size: 17px; color: var(--text-muted); }
.dd-item.is-crit .material-symbols-outlined, .dd-item.is-crit .dd-kind { color: var(--crit); }
.dd-text { min-width: 0; overflow-wrap: anywhere; }
.dd-stale .stat-v { color: var(--text-muted); }
.link-btn.is-sorted { color: var(--text-strong); font-weight: 600; }
.link-btn.is-sorted::after { content: "↓"; margin-left: 2px; }
```

- [ ] **Step 5: Strings** — in `i18n.js`, after `info_alerts_label` in the **lt** block add:

```js
    dd_back:            "Įrenginiai",
    dd_not_found:       "Įrenginys nerastas — galbūt jis pašalintas arba dar nesiuntė logų.",
    dd_uptime:          "Veikia",
    dd_cpu:             "CPU",
    dd_memory:          "Atmintis",
    dd_disk:            "Diskas (/)",
    dd_programs:        "Veikiančios programos",
    dd_program:         "Programa",
    dd_processes:       "Procesai",
    dd_info:            "Įrenginio informacija",
    dd_tab_actions:     "Veiksmai",
    dd_tab_logs:        "Visi logai",
    dd_last_24h:        "Paskutinės 24 val.",
    dd_alerts:          "Šio įrenginio įspėjimai",
    dd_no_alerts:       "Įspėjimų nėra",
    dd_no_activity:     "Per 24 val. veiksmų neužfiksuota",
    dd_no_programs:     "Programų sąrašo nėra",
    dd_nostatus_self:   "Šis serveris dar nesiunčia būsenos (CPU, atminties, programų). Paleiskite: sudo bash setup-host-syslog-ng.sh",
    dd_nostatus_other:  "Šis įrenginys nesiunčia sistemos būsenos (CPU, atminties, programų).",
    dd_updated:         s => `Būsena atnaujinta ${s}`,
    dd_stale:           s => `Paskutinė būsena gauta ${s}`,
    dd_cpu_sub:         n => `branduoliai: ${n}`,
    dd_used_of:         (used, total) => `${used} iš ${total}`,
    dd_programs_foot:   (procs, users) => `procesų: ${procs} · prisijungę: ${users}`,
    dd_cores:           "CPU branduoliai",
    dd_load:            "Apkrova (1 / 5 / 15 min)",
    dd_procs:           "Procesai",
    dd_users:           "Prisijungę vartotojai",
    dd_kind: {
      login:       "Prisijungimas",
      auth_failed: "Nesėkmingas prisijungimas",
      admin:       "Administratoriaus veiksmas",
      account:     "Paskyros pakeitimas",
      command:     "Komanda",
      script:      "PowerShell scenarijus",
      boot:        "Sistemos paleidimas",
      log_cleared: "Žurnalas išvalytas",
      update:      "Atnaujinimas",
    },
    dur_units:          { d: "d.", h: "val.", m: "min." },
```

and after `info_alerts_label` in the **en** block:

```js
    dd_back:            "Devices",
    dd_not_found:       "Device not found — it may have been removed or hasn't sent logs yet.",
    dd_uptime:          "Uptime",
    dd_cpu:             "CPU",
    dd_memory:          "Memory",
    dd_disk:            "Disk (/)",
    dd_programs:        "Running programs",
    dd_program:         "Program",
    dd_processes:       "Processes",
    dd_info:            "Device info",
    dd_tab_actions:     "Actions",
    dd_tab_logs:        "All logs",
    dd_last_24h:        "Last 24 h",
    dd_alerts:          "Alerts for this device",
    dd_no_alerts:       "No alerts",
    dd_no_activity:     "No actions in the last 24 h",
    dd_no_programs:     "No program list",
    dd_nostatus_self:   "This server isn't sending its status (CPU, memory, programs) yet. Run: sudo bash setup-host-syslog-ng.sh",
    dd_nostatus_other:  "This device doesn't send system status (CPU, memory, programs).",
    dd_updated:         s => `Status updated ${s}`,
    dd_stale:           s => `Last status received ${s}`,
    dd_cpu_sub:         n => `cores: ${n}`,
    dd_used_of:         (used, total) => `${used} of ${total}`,
    dd_programs_foot:   (procs, users) => `processes: ${procs} · logged in: ${users}`,
    dd_cores:           "CPU cores",
    dd_load:            "Load (1 / 5 / 15 min)",
    dd_procs:           "Processes",
    dd_users:           "Logged-in users",
    dd_kind: {
      login:       "Login",
      auth_failed: "Failed login",
      admin:       "Admin action",
      account:     "Account change",
      command:     "Command",
      script:      "PowerShell script",
      boot:        "System start",
      log_cleared: "Log cleared",
      update:      "Update",
    },
    dur_units:          { d: "d", h: "h", m: "min" },
```

- [ ] **Step 6: Run the static tests**

Run: `cd dashboard && .venv/bin/python -m pytest tests/test_frontend_static.py -q`
Expected: pass.

---

### Task 10: Detail page module and wiring

**Files:**
- Create: `dashboard/app/static/js/pages/device-detail.js`
- Modify: `dashboard/app/static/js/pages/devices.js`, `dashboard/app/static/js/main.js`

- [ ] **Step 1: Create `pages/device-detail.js`:**

```js
// Įrenginio detalių puslapis (#devices/<raktas>): būsena, programos, informacija, veiksmai ir įspėjimai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { fetchJSON } from "../api.js";
import { alertTitle, t } from "../i18n.js";
import { durationFmt, fullTime, loadFmt, LOG_SEV_COLOR, numFmt, pctFmt, relTime, shortTime, sizeFmt } from "../format.js";
import { navigate, setCrumb } from "../shell.js";
import { sparkline, token } from "../charts.js";
import { openAlertInfo, sevBadge } from "../alert-dialog.js";
import { deviceKey, osLabel, sourceLabel } from "./device-meta.js";

// main.js funkcijos (klaidų juosta); puslapiai main.js neimportuoja.
let ctx = {};

const STALE_MS = 3 * 60 * 1000;   // senesnė būsena rodoma kaip pasenusi
const REFRESH_MS = 12000;         // SSE „devices" įvykiai detalių neperkrauna dažniau
const LOG_LIMIT = 100;

// Veiksmo rūšis -> ikona; crit — raudona eilutė.
const KIND_META = {
  login:       { icon: "login" },
  auth_failed: { icon: "lock", crit: true },
  admin:       { icon: "admin_panel_settings" },
  account:     { icon: "manage_accounts" },
  command:     { icon: "terminal" },
  script:      { icon: "code" },
  boot:        { icon: "power_settings_new" },
  log_cleared: { icon: "delete_history", crit: true },
  update:      { icon: "system_update" },
};

function currentDevice() {
  return state.devices.find(d => deviceKey(d) === state.deviceKey) || null;
}

// Detalės rodomos tik to įrenginio, kurio raktas dabar URL'e.
function currentDetail() {
  return state.deviceDetailKey === state.deviceKey ? state.deviceDetail : null;
}

function isStale(status) {
  return Date.now() - new Date(status.time).getTime() > STALE_MS;
}

// -- Duomenys -------------------------------------------------------------------

// Atidarius įrenginį (ar perėjus prie kito) — iš naujo ir nuo viršaus.
export function openDeviceDetail() {
  if (state.deviceDetailKey !== state.deviceKey) {
    state.deviceDetail = null;
    state.deviceDetailKey = "";
    state.deviceLogs = null;
    state.deviceTab = "actions";
    window.scrollTo(0, 0);
  }
  loadDeviceDetail();
}

export async function loadDeviceDetail() {
  const key = state.deviceKey;
  if (!key) return;
  state._lastDeviceDetail = Date.now();
  try {
    const data = await fetchJSON(`/api/devices/${encodeURIComponent(key)}/details`);
    if (state.deviceKey !== key) return;    // kol laukėme, atidarytas kitas puslapis
    state.deviceDetail = data;
    state.deviceDetailKey = key;
  } catch (e) {
    if (state.deviceKey === key) ctx.loadFailed("Device detail:", e);
  }
  if (state.deviceKey === key && state.deviceTab === "logs") await loadDeviceLogs();
  if (state.page === "devices" && state.deviceKey === key) renderDeviceDetail();
}

async function loadDeviceLogs() {
  const d = currentDevice();
  if (!d) return;
  try {
    const data = await fetchJSON(`/api/traffic/logs?limit=${LOG_LIMIT}&host=${encodeURIComponent(d.hostname)}`);
    if (deviceKey(d) === state.deviceKey) state.deviceLogs = data.lines || [];
  } catch (e) {
    ctx.loadFailed("Device logs:", e);
  }
}

// SSE „devices" įvykis (~kas 15 s): detalės perkraunamos ne dažniau nei kas REFRESH_MS.
export function maybeRefreshDeviceDetail() {
  if (state.page !== "devices" || !state.deviceKey) return;
  if (Date.now() - state._lastDeviceDetail >= REFRESH_MS) loadDeviceDetail();
}

function selectTab(tab) {
  if (state.deviceTab === tab) return;
  state.deviceTab = tab;
  renderDeviceDetail();
  if (tab === "logs") loadDeviceLogs().then(renderDeviceDetail);
}

function sortPrograms(by) {
  state.deviceSort = by;
  renderDeviceDetail();
}

// -- Piešimas -------------------------------------------------------------------

export function renderDeviceDetail() {
  const d = currentDevice();
  const missing = state.devicesLoaded && !d;
  el("dd-notfound")?.classList.toggle("hidden", !missing);
  el("dd-body")?.classList.toggle("hidden", missing);
  setCrumb(d ? `${t("nav_devices")} › ${d.name}` : t("nav_devices"));
  const detail = currentDetail();
  renderHeader(d, detail);
  if (!d) return;
  renderTiles(d, detail);
  renderPrograms(detail);
  renderInfo(d, detail);
  renderActivity(detail);
  renderAlerts(detail);
}

function renderHeader(d, detail) {
  setText("dd-name", d ? d.name : "—");
  const dot = el("dd-dot");
  if (dot) dot.className = "app-dot" + (d && d.alert_count > 0 ? " bg-crit" : d && d.online ? " bg-ok" : "");
  setText("dd-meta", d ? [osLabel(d), d.os_version, d.ip].filter(Boolean).join(" · ") : "");
  const status = detail && detail.status;
  const updated = el("dd-updated");
  if (!updated) return;
  const stale = !!status && isStale(status);
  updated.textContent = status ? t(stale ? "dd_stale" : "dd_updated")(relTime(status.time)) : "";
  updated.classList.toggle("text-warn", stale);
}

function renderTiles(d, detail) {
  const status = detail && detail.status;
  const showTiles = !detail || !!status;          // kol kraunama — tušti langeliai
  document.querySelectorAll("#device-detail .dd-tile").forEach(n => {
    n.classList.toggle("hidden", !showTiles);
    n.classList.toggle("dd-stale", !!status && isStale(status));
  });
  el("dd-nostatus")?.classList.toggle("hidden", showTiles);
  if (!showTiles) {
    setText("dd-nostatus-text", t(d.source === "self" ? "dd_nostatus_self" : "dd_nostatus_other"));
    return;
  }
  const s = status || {};
  // Veikimo laikas „bėga" ir tarp įrašų.
  const age = status ? Math.max(0, (Date.now() - new Date(status.time).getTime()) / 1000) : 0;
  setText("dd-uptime", s.uptime_s != null ? durationFmt(s.uptime_s + age) : "—");
  setText("dd-cpu", pctFmt(s.cpu_pct));
  setText("dd-cpu-sub", s.cpus ? t("dd_cpu_sub")(s.cpus) : "");
  const memUsed = s.mem_total_kb != null && s.mem_avail_kb != null ? s.mem_total_kb - s.mem_avail_kb : null;
  setText("dd-mem", memUsed != null && s.mem_total_kb ? pctFmt(100 * memUsed / s.mem_total_kb) : "—");
  setText("dd-mem-sub", memUsed != null ? t("dd_used_of")(sizeFmt(memUsed), sizeFmt(s.mem_total_kb)) : "");
  const diskTotal = s.disk_used_kb != null && s.disk_avail_kb != null ? s.disk_used_kb + s.disk_avail_kb : 0;
  setText("dd-disk", diskTotal ? pctFmt(100 * s.disk_used_kb / diskTotal) : "—");
  setText("dd-disk-sub", diskTotal ? t("dd_used_of")(sizeFmt(s.disk_used_kb), sizeFmt(diskTotal)) : "");
  const history = (detail && detail.history) || [];
  spark("dd-cpu-spark", history.map(p => p.cpu_pct), "--accent");
  spark("dd-mem-spark", history.map(p => p.mem_pct), "--ok");
}

function spark(id, values, color) {
  const svg = el(id);
  if (svg) sparkline(svg, values.filter(v => v != null), token(color), 100);   // skalė 0–100 %
}

function cell(tr, text, cls) {
  const td = document.createElement("td");
  if (cls) td.className = cls;
  td.textContent = text;
  tr.appendChild(td);
  return td;
}

function emptyRow(tbody, cols, text) {
  const tr = document.createElement("tr");
  cell(tr, text, "empty").colSpan = cols;
  tbody.appendChild(tr);
}

function renderPrograms(detail) {
  const tbody = el("dd-programs-tbody");
  if (!tbody) return;
  ["cpu", "mem"].forEach(k => el(`dd-sort-${k}`)?.classList.toggle("is-sorted", state.deviceSort === k));
  tbody.textContent = "";
  const status = detail && detail.status;
  setText("dd-programs-foot", status && status.procs != null
    ? t("dd_programs_foot")(numFmt(status.procs), status.users.join(", ") || "—") : "");
  if (!detail) return;
  const by = state.deviceSort === "mem" ? "mem_kb" : "cpu_pct";
  const programs = status ? [...status.programs].sort((a, b) => b[by] - a[by] || b.mem_kb - a.mem_kb) : [];
  if (!programs.length) {
    emptyRow(tbody, 4, t("dd_no_programs"));
    return;
  }
  programs.forEach(p => {
    const tr = document.createElement("tr");
    cell(tr, p.name, "mono text-strong");
    cell(tr, numFmt(p.processes), "mono text-muted text-right");
    cell(tr, pctFmt(p.cpu_pct), "mono text-right");
    cell(tr, sizeFmt(p.mem_kb), "mono text-right");
    tbody.appendChild(tr);
  });
}

function renderInfo(d, detail) {
  const dl = el("dd-info");
  if (!dl) return;
  const rows = [
    [t("info_status_label"),   d.online ? t("dev_status_online") : t("dev_status_offline")],
    [t("info_source_label"),   sourceLabel(d)],
    [t("info_ip_label"),       d.ip || "—", "mono"],
    // Savo serverio realaus hostname nerodome (privatumas).
    [t("info_hostname_label"), d.source === "self" ? "—" : d.hostname, "mono"],
    [t("info_os_label"),       osLabel(d)],
    [t("info_version_label"),  d.os_version || "—"],
    [t("info_lastseen_label"), d.last_seen ? relTime(d.last_seen) : t("dev_never")],
    [t("info_logs5m_label"),   numFmt(d.logs_5m || 0), "mono"],
    [t("info_logs1h_label"),   numFmt(d.logs_1h || 0), "mono"],
    [t("info_alerts_label"),   numFmt(d.alert_count || 0), "mono"],
  ];
  const s = detail && detail.status;
  if (s) {
    if (s.cpus != null) rows.push([t("dd_cores"), numFmt(s.cpus), "mono"]);
    if (s.load.length) rows.push([t("dd_load"), s.load.map(loadFmt).join(" / "), "mono"]);
    if (s.procs != null) rows.push([t("dd_procs"), numFmt(s.procs), "mono"]);
    rows.push([t("dd_users"), s.users.join(", ") || "—"]);
  }
  dl.textContent = "";
  rows.forEach(([label, value, cls]) => {
    const row = document.createElement("div");
    row.className = "flex justify-between gap-4";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    if (cls) dd.className = cls;
    dd.textContent = value;
    row.append(dt, dd);
    dl.appendChild(row);
  });
}

function emptyBox(text) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = text;
  return p;
}

function skeleton() {
  const div = document.createElement("div");
  div.className = "skeleton h-4 w-1/2 mx-auto my-4";
  return div;
}

function renderActivity(detail) {
  el("dd-tab-actions")?.classList.toggle("is-active", state.deviceTab === "actions");
  el("dd-tab-logs")?.classList.toggle("is-active", state.deviceTab === "logs");
  const feed = el("dd-activity");
  const logs = el("dd-logs");
  if (!feed || !logs) return;
  feed.classList.toggle("hidden", state.deviceTab !== "actions");
  logs.classList.toggle("hidden", state.deviceTab !== "logs");
  if (state.deviceTab === "logs") renderLogs(logs);
  else renderFeed(feed, detail ? detail.activity : null);
}

function renderFeed(feed, items) {
  feed.textContent = "";
  if (!items) {
    feed.appendChild(skeleton());
    return;
  }
  if (!items.length) {
    feed.appendChild(emptyBox(t("dd_no_activity")));
    return;
  }
  const kinds = t("dd_kind");
  items.forEach(a => {
    const meta = KIND_META[a.kind] || { icon: "info" };
    const row = document.createElement("div");
    row.className = "dd-item" + (meta.crit ? " is-crit" : "");
    const time = document.createElement("span");
    time.className = "mono text-muted";
    time.textContent = shortTime(a.time);
    time.title = fullTime(a.time);
    const icon = document.createElement("span");
    icon.className = "material-symbols-outlined";
    icon.textContent = meta.icon;
    const body = document.createElement("div");
    body.className = "dd-text";
    const head = document.createElement("div");
    head.className = "dd-kind font-medium text-strong";
    const label = kinds[a.kind] || a.kind;
    head.textContent = a.user ? `${label} · ${a.user}` : label;
    const text = document.createElement("div");
    text.className = "text-muted";
    text.textContent = a.text;
    body.append(head, text);
    row.append(time, icon, body);
    feed.appendChild(row);
  });
}

function renderLogs(box) {
  box.textContent = "";
  if (state.deviceLogs === null) {
    box.appendChild(skeleton());
    return;
  }
  if (!state.deviceLogs.length) {
    box.appendChild(emptyBox(t("logs_empty")));
    return;
  }
  state.deviceLogs.forEach(l => {
    const row = document.createElement("div");
    row.className = "ln";
    row.style.borderLeftColor = LOG_SEV_COLOR[l.severity] || "var(--text-dim)";
    row.textContent = l.line || "";
    box.appendChild(row);
  });
}

function renderAlerts(detail) {
  const tbody = el("dd-alerts-tbody");
  if (!tbody) return;
  tbody.textContent = "";
  if (!detail) return;
  if (!detail.alerts.length) {
    emptyRow(tbody, 3, t("dd_no_alerts"));
    return;
  }
  detail.alerts.forEach(a => {
    const tr = document.createElement("tr");
    tr.className = "is-click";
    tr.addEventListener("click", () => openAlertInfo(a));
    cell(tr, shortTime(a.timestamp), "mono text-muted whitespace-nowrap");
    cell(tr, "").appendChild(sevBadge(a.severity));
    cell(tr, alertTitle(a.alert_type, a.title));
    tbody.appendChild(tr);
  });
}

export function init(context) {
  ctx = context;
  document.querySelectorAll("[data-dd-back]").forEach(b => b.addEventListener("click", () => navigate("devices")));
  el("dd-tab-actions")?.addEventListener("click", () => selectTab("actions"));
  el("dd-tab-logs")?.addEventListener("click", () => selectTab("logs"));
  el("dd-sort-cpu")?.addEventListener("click", () => sortPrograms("cpu"));
  el("dd-sort-mem")?.addEventListener("click", () => sortPrograms("mem"));
}
```

- [ ] **Step 2: `pages/devices.js`**

1. After the `../charts.js` import add:
   ```js
   import { openDeviceDetail, renderDeviceDetail } from "./device-detail.js";
   import { deviceKey, OS_META, sourceLabel } from "./device-meta.js";
   ```
2. Delete the local `OS_META` and `SRC_LABEL` constants.
3. At the top of `renderDevicesPage()` insert:
   ```js
     // #devices/<raktas> — vieno įrenginio puslapis vietoje sąrašo.
     const detail = !!state.deviceKey;
     el("devices-list")?.classList.toggle("hidden", detail);
     el("device-detail")?.classList.toggle("hidden", !detail);
     if (detail) {
       renderDeviceDetail();
       return;
     }
   ```
4. In `renderDeviceTable()` replace `src.textContent = (SRC_LABEL[d.source] || (() => d.source))();` with `src.textContent = sourceLabel(d);`.
5. Replace all three `openDeviceInfo(d)` calls (map node, table row, info button) with `openDevice(d)`.
6. Replace the functions `openDeviceInfo`, `closeDeviceInfo` and `onDeviceInfoBackdrop` with:
   ```js
   function openDevice(d) {
     navigate(`devices/${encodeURIComponent(deviceKey(d))}`);
   }

   // Atidarius puslapį (main.js enterPage): įrenginio detalės kraunamos iš naujo.
   export function enterDevicesPage() {
     if (state.deviceKey) openDeviceDetail();
     renderDevicesPage();
   }
   ```
7. In `init()` delete the two lines that wire `device-info-modal` (`el("device-info-modal")?.addEventListener(...)` and the `[data-close="device-info-modal"]` loop).

- [ ] **Step 3: `main.js`**

1. Imports:
   ```js
   import { closeAttackMenu, enterDevicesPage, init as initDevices, renderDevicesPage } from "./pages/devices.js";
   import { init as initDeviceDetail, loadDeviceDetail, maybeRefreshDeviceDetail } from "./pages/device-detail.js";
   ```
2. `retryAll()`:
   ```js
   async function retryAll() {
     const detail = state.page === "devices" && state.deviceKey ? loadDeviceDetail() : null;
     await Promise.allSettled([loadHealth(), loadTrafficCurrent(), loadTrafficHistory(), loadAlerts(), loadDevices(), detail]);
   }
   ```
3. `applyDevices()` — add `state.devicesLoaded = true;` after `state.collector = …`, and replace `if (state.page === "devices") renderDevicesPage();` with:
   ```js
     if (state.page === "devices") { renderDevicesPage(); maybeRefreshDeviceDetail(); }
   ```
4. `applyI18n()` — delete the ten `setText("info-…-label", …)` lines (their elements are gone; the page uses the same keys through `t()`).
5. `enterPage()` — `if (page === "devices")   renderDevicesPage();` → `if (page === "devices")   enterDevicesPage();`
6. `init()` — `const ctx = { loadTrafficHistory, loadTrafficCurrent, loadAlerts, loadAllAlerts, loadRawLogs, loadDevices, loadFailed };` and add `initDeviceDetail(ctx);` after `initDevices(ctx);`.
7. Search input handler — replace `} else if (state.page === "devices") {\n        renderDevicesPage();` with:
   ```js
         } else if (state.page === "devices") {
           if (state.deviceKey) navigate("devices");   // paieška — sąraše
           else renderDevicesPage();
   ```
8. `visibilitychange` handler — after `loadTrafficHistory();` add:
   ```js
       if (state.page === "devices" && state.deviceKey) loadDeviceDetail();
   ```

- [ ] **Step 4: Static checks and full suite**

Run: `cd dashboard && .venv/bin/python -m pytest tests/ -q`
Expected: all pass.

Run: `grep -rn "device-info\|openDeviceInfo\|SRC_LABEL\[" dashboard/app/static/ || echo clean`
Expected: `clean`.

- [ ] **Step 5: Run `/verify`, then commit**

```bash
git add dashboard/app/static/
git commit -m "feat(dashboard): device detail page"
```

---

### Task 11: End-to-end verification

- [ ] **Step 1: Deploy**

```bash
docker compose restart syslog-ng
docker compose up -d --build dashboard
```

- [ ] **Step 2: Send one status record through the real pipeline (no root needed)**

Run: `systemd-cat -t kursinis-status bash config/syslog-ng-host/kursinis-status.sh`
Then (after ~10 s):
`docker exec dashboard python -c 'import httpx,sys; print(httpx.get("http://loki:3100/loki/api/v1/query", params={"query": sys.argv[1]}).text[:600])' 'count_over_time({job="syslog", program="kursinis-status"}[5m])'`
Expected: a series for this PC's host with value ≥ 1.

- [ ] **Step 3: API check** (admin password from `.env`, never printed)

```bash
set -a; . ./.env; set +a
TOKEN=$(curl -s localhost:8080/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"${DASHBOARD_ADMIN_USER:-admin}\",\"password\":\"${DASHBOARD_ADMIN_PASSWORD}\"}" | jq -r .token)
curl -s localhost:8080/api/devices/self/details -H "Authorization: Bearer $TOKEN" | jq '{status: .status.cpu_pct, programs: (.status.programs|length), history: (.history|length), activity: [.activity[:3][]|{kind,user,text}], alerts: (.alerts|length)}'
curl -s localhost:8080/api/devices/web-server-01/details -H "Authorization: Bearer $TOKEN" | jq '{status, activity: (.activity|length), alerts: (.alerts|length)}'
```
Expected: this PC has a status with programs and activity (sudo, sessions, boot); the demo web server has `status: null`, activity (SSH logins) and alerts.

- [ ] **Step 4: Browser check** (Playwright): log in, open Devices → click "Šis serveris" → URL `#devices/self`; check tiles, sparklines (after ≥ 2 records), programs (sort by memory), info, activity, "All logs" tab, alert click opens the dialog, Back. Then a demo device (no-status banner), dark/light theme, EN, 400 px width, browser console free of errors.

- [ ] **Step 5: Ask the user** to run `sudo bash setup-host-syslog-ng.sh` once (installs the timer), then confirm records arrive every minute: `systemctl list-timers kursinis-status.timer` and the page's "Status updated …" text.

---

### Task 12: Coverage, review and docs

- [ ] **Step 1: Coverage of the new modules**

```bash
cd dashboard && uv pip install pytest-cov && .venv/bin/python -m pytest tests/ -q \
  --cov=app.services.host_status --cov=app.services.activity --cov=app.services.device_details --cov-report=term-missing
```
Expected: each ≥ 80 %.

- [ ] **Step 2: Code review** — dispatch `code-reviewer` and `security-reviewer` agents in parallel over `git diff a966901..HEAD`; fix CRITICAL/HIGH findings (with a test first when it's a bug), re-run the suite.

- [ ] **Step 3: CLAUDE.md**
  - Structure: add `config/syslog-ng-host/kursinis-status.sh` (+ `.service`/`.timer`), `dashboard/app/services/host_status.py`, `activity.py`, `device_details.py`, `static/js/pages/device-meta.js`, `device-detail.js`; mention the info dialog is gone (index.html now has 2 dialogs).
  - Commands: the `setup-host-syslog-ng.sh` line also installs `kursinis-status.timer` (disable: `sudo systemctl disable --now kursinis-status.timer`).
  - Key Architecture Decisions: one bullet — status heartbeat (format, transport, `program="kursinis-status"` stream, strict validation, `f_security` exclusion), `GET /api/devices/{key}/details` (`self` key, 3 parallel queries, activity rules), `#devices/<key>` page refreshed on `devices` SSE events.
  - Tests: update the dashboard count and the list of what they cover.

- [ ] **Step 4: Commit docs**

```bash
git add CLAUDE.md docs/superpowers/plans/2026-10-29-device-detail.md
git commit -m "docs: device detail page (CLAUDE.md, implementation plan)"
```

---

## Self-review against the spec

| Spec section | Task |
|---|---|
| 4.2 record format | 2 (model), 3 (script) |
| 4.3 collector on this PC (script, units, install) | 3, 4 |
| 4.4 transport + `f_security` change | 4, 11 |
| 4.5 API, key resolution, queries | 1 (`valid_host`), 7 |
| 4.6 validation limits | 2 |
| 4.7 activity rules, prefilter, exclusions | 5, 6 |
| 4.8 alerts helper | 1, 7 |
| 4.9 routing, layout, refresh, edge cases | 8, 9, 10 |
| 5 error handling | 7 (`[]` from Loki → empty sections), 10 (`loadFailed`, stale) |
| 6 security | 1, 2, 3 (unit hardening), 10 (`textContent`) |
| 7 testing | 1, 2, 5, 6, 7, 9, 11, 12 |
| 8 documentation | 12 |
