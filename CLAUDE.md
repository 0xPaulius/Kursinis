# Log Analysis System

Centralized log analysis and anomaly detection system for small organizations.
Academic coursework (kursinis darbas, Vilnius University ISKS).

## Stack
syslog-ng 4.8 → Grafana Alloy 1.20 → Loki 3.4 → Grafana 11.5 + Python 3.12 anomaly detector + FastAPI dashboard.
Windows/Linux endpoints push to an Alloy gateway over mTLS. Everything containerized in Docker Compose.

## Structure
```
docker-compose.yml — base (syslog-ng, alloy, loki, grafana, dashboard) + profiles: anomaly, endpoints (alloy-gateway), eval (loki-eval, evaluator)
.env / .env.example                  — GF_SECURITY_ADMIN_PASSWORD, DASHBOARD_ADMIN_PASSWORD, DASHBOARD_SECRET_KEY (gitignored)
docs/ARCHITECTURE.md                 — LT architecture overview
config/syslog-ng/syslog-ng.conf      — syslog receiver, filters, destinations (+ conf.d/tls.conf TLS 6514)
config/loki/loki.yml                 — storage, retention (30d), schema
config/loki/loki-eval.yml            — eval Loki (original dataset timestamps, no retention)
config/alloy/collector.alloy         — file tail → Loki (replaces Promtail; alloy convert output)
config/alloy/gateway.alloy           — loki.source.api :3500 endpoint gateway (mTLS + job allowlist)
config/grafana/provisioning/         — auto datasource + dashboard provider
config/grafana/dashboards/           — dashboard JSON files (datasource uid: loki)
anomaly-detector/common.py           — Alert, LokiClient, Selectors, config constants
anomaly-detector/detector.py         — Engine.run_cycle(now): rule, statistical, ML + endpoint layers
anomaly-detector/windows_rules.py    — Windows Event Log / Sysmon rules → ATT&CK
anomaly-detector/linux_rules.py      — Linux auditd rules → ATT&CK
anomaly-detector/attack_catalog.py   — alert_type → ATT&CK techniques, coverage, lab technique set
anomaly-detector/evaluation/         — offline eval harness (fetch/ingest/run/score/report; AIT/OTRF/EVTX adapters)
anomaly-detector/Dockerfile          — base + eval + runtime targets
anomaly-detector/requirements.txt / requirements-eval.txt
anomaly-detector/tests/              — pytest (rule, statistical, ML, engine, windows, linux, eval)
dashboard/app/main.py                — FastAPI app (serves UI + REST API)
dashboard/app/dependencies.py        — DI (get_loki, get_health_checker, get_alert_reader, require_auth, require_admin)
dashboard/app/routers/               — auth, traffic, alerts, health, devices, notifications, stream, attack API routes
dashboard/app/services/user_store.py — scrypt-hashed users (/state/users.json), roles admin/viewer
dashboard/app/manage_users.py        — CLI: python -m app.manage_users (list/add/passwd/delete)
dashboard/app/services/attack_coverage.py — ATT&CK coverage from /data/attack_catalog.json + alert history
dashboard/app/log_selectors.py       — shared {job=~"syslog|windows|linux_endpoint"} selector
dashboard/app/services/              — loki_client, alert_reader (mtime-cached), health_checker
dashboard/app/static/                — HTML, CSS, JS (Tailwind + Chart.js)
dashboard/app/services/device_registry.py — registered demo devices (JSON persistence in /state)
dashboard/app/services/syslog_emitter.py  — sends normal + attack syslog (UDP) to syslog-ng
dashboard/app/services/host_info.py       — reads mounted host files for self-server kernel/OS version
dashboard/app/services/device_monitor.py  — builds device map (per-host Loki stats + registry + self + discovered)
dashboard/app/routers/devices.py     — device CRUD, demo attack scenario, GET /map (node map)
dashboard/app/models/schemas.py      — Pydantic response models
dashboard/Dockerfile                 — Python 3.12-slim + uvicorn
demo_data/anomaly_history.json       — seed alert data for demo/testing
seed_demo.sh                         — loads demo_data into kursinis_anomaly-data volume
```

## Commands
- `docker compose up -d` — base stack (syslog-ng, alloy, loki, grafana, dashboard)
- `docker compose --profile anomaly up -d` — recommended demo: base stack + anomaly detector
- `docker compose --profile endpoints up -d` — add Windows/Linux endpoint gateway (needs `tools/gen-certs.sh`)
- `docker compose --profile eval run --rm evaluator <ingest|run|score|report>` — offline evaluation
- `docker compose down -v` — teardown with volumes
- `docker compose logs -f anomaly-detector` — watch detections
- `docker compose restart dashboard` — apply dashboard code changes (or `up -d --build dashboard`)
- `python -m app.manage_users add <user> --role admin` — manage dashboard users (in dashboard container)
- `./seed_demo.sh` — load demo alert data into dashboard

### Demo flow (Devices tab)
1. `docker compose --profile anomaly up -d`
2. Open dashboard (8080) → Devices tab → "Add device": name + IP + OS (macOS / Windows 11). A per-OS setup tutorial is shown.
3. Registered devices auto-emit normal syslog (dashboard `syslog_emitter` → syslog-ng) — visible in traffic graphs within ~30s.
4. "Run attack" dropdown → `POST /api/devices/demo/scenario {attack}` runs a single attack: `ssh_bruteforce` (web-server-01) or `firewall_spike` (router-01). The "Test ML detector" button sends `{attack:"full"}` for the combined multi-stage scenario (SSH brute-force + firewall DROP + error burst). The real anomaly-detector raises alerts on the Anomalies tab within ~60s.

### Tests
- `docker compose run --rm anomaly-detector pytest tests/ -v` — detector tests (requires `tests/` mounted or COPYed)
- Detector: 91 pytest tests (rule, statistical, ML, engine, windows, linux, eval harness)
- Dashboard: `dashboard/tests/` — 14 auth tests (UserStore scrypt, tokens, roles, throttling, CLI)

## Ports
- 514/TCP,UDP — syslog input from network
- 1514/TCP — alternative syslog input (non-root)
- 6514/TCP — syslog over TLS (RFC 5425; enable config/syslog-ng/conf.d/tls.conf)
- 3500/TCP — Alloy endpoint gateway: Windows/Linux Loki push (HTTPS + mTLS; profile `endpoints`)
- 3100 — Loki API (internal Docker network only)
- 3000 — Grafana UI (admin / $GF_SECURITY_ADMIN_PASSWORD)
- 8080 — Dashboard web UI (admin / $DASHBOARD_ADMIN_PASSWORD, bootstrap on first run)

## Code Style
- Python: type hints, dataclasses, f-strings, docstrings
- Academic comments in Lithuanian, technical in English
- YAML configs for Loki/Grafana, Alloy river syntax, native syntax for syslog-ng
- Grafana: JSON provisioned dashboards, Europe/Vilnius timezone
- Dashboard: FastAPI + Vanilla JS + Tailwind CSS, i18n (LT/EN)

## Key Architecture Decisions
- syslog-ng writes files → Alloy reads them (shared Docker volume `syslog-ng-logs`); Alloy replaced Promtail (`config/alloy/collector.alloy` = `alloy convert` output), picking up Promtail positions once via `legacy_positions_file`
- Alloy regex must match syslog-ng output template: `${ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`
- Windows/Linux endpoints run their own Alloy agent that pushes to `alloy-gateway` (`loki.source.api` :3500) over TLS with client certs (mTLS); the gateway enforces a job allowlist `{job=~"windows|linux_endpoint"}` and keeps only labels `{job,host,channel}`. Loki stays internal. Certs: `tools/gen-certs.sh`
- Loki: label-based indexing only (no full-text), 30-day retention, datasource uid `loki`
- Anomaly detector runs one shared `Engine.run_cycle(now)` (live = wall clock, eval = virtual clock); counts come from `count_over_time`/metric queries (no 5000-line cap)
- ML detector (IsolationForest) is OFF in the live loop by default (`ENABLE_ML=false`) — it produced too many false positives; it is measured offline (RQ3). `ML_TRAINING_MODE` = online/frozen; training_data is deque(maxlen=`ML_MAX_TRAINING_SAMPLES`)
- Evaluation harness (`anomaly-detector/evaluation/`, profile `eval`): replays labeled datasets (AIT-LDS via HTTP-range zip extract, OTRF/EVTX Windows) through `loki-eval` with original timestamps, runs the Engine on a virtual clock, scores precision/recall/F1/FPR per layer + per-technique ATT&CK recall + McNemar/bootstrap, emits LaTeX tables to `eval-results/`
- Anomaly detector writes alerts atomically (`tmp` + `os.replace`) to `/data/anomaly_history.json`, and `attack_catalog.json` at startup
- Synthetic traffic is dashboard-driven only: 4 demo devices (MacBook, Windows 11, `router-01`, `web-server-01`) are seeded into the registry (`SEED_DEFAULT_DEVICES`) and auto-emit normal traffic; the standalone log-generator has been removed
- Dashboard reads Loki API for live traffic + anomaly_history.json for alerts (shared volume `anomaly-data`)
- Dashboard device registry persists to `/state/devices.json` (rw volume `dashboard-state`); `SyslogEmitter` sends UDP syslog to `syslog-ng:514` using the standard BSD syslog format, so syslog-ng/Alloy/detector treat it identically. `DeviceCreate.synthetic` (default true) marks demo devices that auto-emit; synthetic=false registers a real endpoint that sends its own logs
- Background asyncio task emits per-device normal traffic every `NORMAL_TRAFFIC_INTERVAL` (default 5s) ONLY for `synthetic` registry devices; `POST /api/devices/demo/scenario` takes `{attack}` (`ssh_bruteforce` | `firewall_spike` | `full`) and fires the matching on-demand attack via `SyslogEmitter.simulate_attack` (`full` = SSH brute-force + firewall DROP + error burst), detected by the real anomaly-detector
- Live updates: `GET /api/stream` is a Server-Sent Events (SSE) endpoint (`routers/stream.py`, `StreamingResponse` `text/event-stream`) that pushes `health`/`traffic`/`alerts`/`devices` events only when their JSON changes (`STREAM_INTERVAL`=5s, devices every 3rd tick, `: ping` heartbeat). Frontend opens one `EventSource` in `init()` (replacing the old `setInterval` polling); each `apply*()` (split from `load*()`) re-renders. The traffic-history chart stays client-driven (range/host aware), refreshed on a throttled `maybeRefreshHistory()` when a `traffic` event arrives
- Device node map (`GET /api/devices/map`): merges registered (synthetic) devices + the Docker host itself + any host auto-discovered from Loki `host` labels; each node gets live `logs_5m`/`logs_1h`/`last_seen`/`online` (online = logs in last 5 min) via `sum by (host)(count_over_time(...))`. Discovered hosts that are bare IPs (e.g. the Docker bridge gateway `172.18.0.1` from NAT'd port-published logs) and hostnames in the deleted-suppression list are excluded. The self/host node is shown with a generic name (`SELF_DEVICE_NAME`, default "Šis serveris") and its real hostname is hidden in the UI.
- Deleting a device (`DELETE /api/devices/{id}`) records its hostname in `/state/deleted_hosts.json` (`SUPPRESSED_DB_PATH`) so it won't reappear as a "discovered" node while its logs age out of Loki (~1h); re-adding the same hostname clears the suppression
- Self-host monitoring: point the host's rsyslog at `<host>:514`; its kernel/OS version comes from read-only mounts `/etc/hostname`, `/etc/os-release`, `/proc/version` -> `/host/*` (Linux host only; `HOST_INFO_DIR`)
- Tutorials are frontend i18n (LT/EN); Windows uses Grafana Alloy (Security/Sysmon/PowerShell → gateway :3500 mTLS), macOS uses syslog-ng over TLS 6514. Collector address shown to the user is `window.location.hostname`
- Dashboard auth: real users in `/state/users.json` (scrypt hashes), HMAC-signed expiring tokens carrying a role (`DASHBOARD_SECRET_KEY`, TTL), login throttling; `require_auth` guards all `/api/*` read routes, `require_admin` guards device CRUD / demo scenario / notifications. SSE `/api/stream` authenticates via `?token=` query param, validated with the same `verify_token`. First admin bootstraps from `DASHBOARD_ADMIN_USER/PASSWORD`
- ATT&CK coverage: detector writes `/data/attack_catalog.json`; dashboard `GET /api/attack/coverage` combines it with alert history (has_rule vs detected) for the ATT&CK tab
- AlertReader is mtime-cached and injected via DI; alert IDs are deterministic sha1(ts|type|ip|host)[:16]; `AlertItem.attack_techniques` surfaces ATT&CK IDs in the UI
- Health checker reports syslog-ng/alloy as `unknown` when Loki is down; probes Alloy `/-/ready` directly; adds an endpoint-telemetry check when `{job="windows"}` data exists

## Anomaly Detection Layers (detector.py Engine)
1. `RuleBasedDetector` (job=syslog) — SSH brute-force (≥5 failures/5min/IP), invalid user scanning (≥3 usernames/IP, case-insensitive), firewall spike (>50 DROP)
2. `WindowsRuleDetector` (job=windows) — 4625/4740/4720/4732/1102/4104 + Sysmon 1/3/11, ATT&CK-mapped (`windows_rules.py`)
3. `LinuxEndpointRuleDetector` (job=linux_endpoint) — auditd sudo failures, useradd, suspicious EXECVE, discovery burst (`linux_rules.py`)
4. `StatisticalDetector` — log volume z-score (3σ, time-based baseline `BASELINE_WINDOW_HOURS`), error rate (>30%)
5. `MLDetector` — IsolationForest (LogQL-metric features); off in live loop by default, evaluated offline
- All alert types map to MITRE ATT&CK via `attack_catalog.py`; `Engine` fills `Alert.attack_techniques`
