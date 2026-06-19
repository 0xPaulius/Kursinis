# Log Analysis System

Centralized log analysis and anomaly detection system for small organizations.
Academic coursework (kursinis darbas, Vilnius University ISKS).

## Stack
syslog-ng 4.8 → Promtail 3.4 → Loki 3.4 → Grafana 11.5 + Python 3.12 anomaly detector + FastAPI dashboard.
Everything containerized in Docker Compose.

## Structure
```
docker-compose.yml — 6 services (syslog-ng, promtail, loki, grafana, anomaly-detector, dashboard)
.env / .env.example                  — GF_SECURITY_ADMIN_PASSWORD (gitignored)
docs/ARCHITECTURE.md                 — LT architecture overview
config/syslog-ng/syslog-ng.conf      — syslog receiver, filters, destinations
config/loki/loki.yml                 — storage, retention (30d), schema
config/promtail/promtail.yml         — regex parsing, label extraction
config/grafana/provisioning/         — auto datasource + dashboard provider
config/grafana/dashboards/           — dashboard JSON files (datasource uid: loki)
anomaly-detector/detector.py         — 3-layer detection (rule, statistical, ML)
anomaly-detector/Dockerfile
anomaly-detector/requirements.txt    — requests, numpy, scikit-learn, joblib
anomaly-detector/tests/              — pytest tests (rule, statistical, ML feature extraction)
dashboard/app/main.py                — FastAPI app (serves UI + REST API)
dashboard/app/dependencies.py        — DI (get_loki, get_health_checker, get_alert_reader, require_auth)
dashboard/app/routers/               — auth, traffic, alerts, health API routes
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
- `docker compose up -d` — base stack (syslog-ng, promtail, loki, grafana, dashboard)
- `docker compose --profile anomaly up -d` — recommended demo: base stack + anomaly detector
- `docker compose down -v` — teardown with volumes
- `docker compose logs -f anomaly-detector` — watch detections
- `docker compose restart dashboard` — apply dashboard code changes (or `up -d --build dashboard`)
- `./seed_demo.sh` — load demo alert data into dashboard

### Demo flow (Devices tab)
1. `docker compose --profile anomaly up -d`
2. Open dashboard (8080) → Devices tab → "Add device": name + IP + OS (macOS / Windows 11). A per-OS setup tutorial is shown.
3. Registered devices auto-emit normal syslog (dashboard `syslog_emitter` → syslog-ng) — visible in traffic graphs within ~30s.
4. "Run attack" dropdown → `POST /api/devices/demo/scenario {attack}` runs a single attack: `ssh_bruteforce` (web-server-01) or `firewall_spike` (router-01). The "Test ML detector" button sends `{attack:"full"}` for the combined multi-stage scenario (SSH brute-force + firewall DROP + error burst). The real anomaly-detector raises alerts on the Anomalies tab within ~60s.

### Tests
- `docker compose run --rm anomaly-detector pytest tests/ -v` — detector tests (requires `tests/` mounted or COPYed)

## Ports
- 514/TCP,UDP — syslog input from network
- 1514/TCP — alternative syslog input (non-root)
- 3100 — Loki API (internal Docker network only)
- 3000 — Grafana UI (admin / $GF_SECURITY_ADMIN_PASSWORD)
- 8080 — Dashboard web UI (admin / admin123)

## Code Style
- Python: type hints, dataclasses, f-strings, docstrings
- Academic comments in Lithuanian, technical in English
- YAML configs for Loki/Promtail/Grafana, native syntax for syslog-ng
- Grafana: JSON provisioned dashboards, Europe/Vilnius timezone
- Dashboard: FastAPI + Vanilla JS + Tailwind CSS, i18n (LT/EN)

## Key Architecture Decisions
- syslog-ng writes files → Promtail reads them (shared Docker volume `syslog-ng-logs`)
- Promtail regex must match syslog-ng output template: `${ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`
- Loki: label-based indexing only (no full-text), 30-day retention, datasource uid `loki`
- Anomaly detector queries Loki HTTP API (`/loki/api/v1/query_range`)
- ML detector (IsolationForest) trains after ≥20 samples, runs every 5th cycle; training_data is deque(maxlen=500)
- Anomaly detector writes alerts atomically (`tmp` + `os.replace`) to `/data/anomaly_history.json`
- Synthetic traffic is dashboard-driven only: 4 demo devices (MacBook, Windows 11, `router-01`, `web-server-01`) are seeded into the registry (`SEED_DEFAULT_DEVICES`) and auto-emit normal traffic; the standalone log-generator has been removed
- Dashboard reads Loki API for live traffic + anomaly_history.json for alerts (shared volume `anomaly-data`)
- Dashboard device registry persists to `/state/devices.json` (rw volume `dashboard-state`); `SyslogEmitter` sends UDP syslog to `syslog-ng:514` using the standard BSD syslog format, so syslog-ng/Promtail/detector treat it identically
- Background asyncio task emits per-device normal traffic every `NORMAL_TRAFFIC_INTERVAL` (default 5s) ONLY for `synthetic` registry devices; `POST /api/devices/demo/scenario` takes `{attack}` (`ssh_bruteforce` | `firewall_spike` | `full`) and fires the matching on-demand attack via `SyslogEmitter.simulate_attack` (`full` = SSH brute-force + firewall DROP + error burst), detected by the real anomaly-detector
- Live updates: `GET /api/stream` is a Server-Sent Events (SSE) endpoint (`routers/stream.py`, `StreamingResponse` `text/event-stream`) that pushes `health`/`traffic`/`alerts`/`devices` events only when their JSON changes (`STREAM_INTERVAL`=5s, devices every 3rd tick, `: ping` heartbeat). Frontend opens one `EventSource` in `init()` (replacing the old `setInterval` polling); each `apply*()` (split from `load*()`) re-renders. The traffic-history chart stays client-driven (range/host aware), refreshed on a throttled `maybeRefreshHistory()` when a `traffic` event arrives
- Device node map (`GET /api/devices/map`): merges registered (synthetic) devices + the Docker host itself + any host auto-discovered from Loki `host` labels; each node gets live `logs_5m`/`logs_1h`/`last_seen`/`online` (online = logs in last 5 min) via `sum by (host)(count_over_time(...))`. Discovered hosts that are bare IPs (e.g. the Docker bridge gateway `172.18.0.1` from NAT'd port-published logs) and hostnames in the deleted-suppression list are excluded. The self/host node is shown with a generic name (`SELF_DEVICE_NAME`, default "Šis serveris") and its real hostname is hidden in the UI.
- Deleting a device (`DELETE /api/devices/{id}`) records its hostname in `/state/deleted_hosts.json` (`SUPPRESSED_DB_PATH`) so it won't reappear as a "discovered" node while its logs age out of Loki (~1h); re-adding the same hostname clears the suppression
- Self-host monitoring: point the host's rsyslog at `<host>:514`; its kernel/OS version comes from read-only mounts `/etc/hostname`, `/etc/os-release`, `/proc/version` -> `/host/*` (Linux host only; `HOST_INFO_DIR`)
- Tutorials are frontend i18n (LT/EN); collector address shown to the user is `window.location.hostname:514`
- Dashboard auth: demo Bearer token (sha256(username:salt)[:32]) enforced on all `/api/{traffic,alerts,health,devices}` routes via `Depends(require_auth)`; client sends `Authorization: Bearer <token>` after login. The SSE `/api/stream` authenticates via `?token=` query param (browsers' `EventSource` can't set headers), validated with the same `verify_demo_token`
- AlertReader is mtime-cached and injected via DI; alert IDs are deterministic sha1(ts|type|ip|host)[:16]
- Health checker reports syslog-ng/promtail as `unknown` when Loki is down (cannot infer freshness without Loki)

## Anomaly Detection Layers (detector.py)
1. `RuleBasedDetector` — SSH brute-force (≥5 failures/5min/IP), invalid user scanning (≥3 usernames/IP), firewall spike (>50 DROP)
2. `StatisticalDetector` — log volume z-score (threshold 3σ), error rate (>30%)
3. `MLDetector` — IsolationForest on features: log_count, unique_programs, error_rate, unique_ips, avg_msg_length
