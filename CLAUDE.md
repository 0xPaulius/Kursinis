# Log Analysis System

Centralized log analysis and anomaly detection system for small organizations.
Academic coursework (kursinis darbas, Vilnius University ISKS).

## Stack
syslog-ng 4.8 → Grafana Alloy 1.20 → Loki 3.4 → Grafana 11.5 + Python 3.12 anomaly detector + FastAPI dashboard.
Windows/Linux endpoints push to an Alloy gateway over mTLS. Everything containerized in Docker Compose.

## Structure
```
docker-compose.yml — base (syslog-ng, alloy, loki, grafana, dashboard) + profiles: anomaly, endpoints (alloy-gateway), eval (loki-eval, evaluator)
docker-compose.prod.yml              — production overrides (CHECK_INTERVAL=60, no synthetic traffic/demo devices, Grafana/Alloy telemetry off, dashboard + Grafana over HTTPS); on via COMPOSE_FILE in .env
.env / .env.example                  — COMPOSE_PROJECT_NAME=kursinis (volumes `kursinis_*`), GF_SECURITY_ADMIN_PASSWORD, DASHBOARD_ADMIN_USER/PASSWORD, DASHBOARD_SECRET_KEY (.env gitignored)
config/syslog-ng/syslog-ng.conf      — syslog receiver, filters, weekday files all-/security-/errors-<Day>.log (+ conf.d/tls.conf TLS 6514)
config/syslog-ng-host/syslog-ng.conf — this host's own syslog-ng → collector (template for setup-host-syslog-ng.sh)
config/loki/loki.yml                 — storage, retention (30d), schema
config/loki/loki-eval.yml            — eval Loki (original dataset timestamps, no retention)
config/alloy/collector.alloy         — file tail → Loki (replaces Promtail; alloy convert output)
config/alloy/gateway.alloy           — loki.source.api :3500 endpoint gateway (mTLS against pinned client certs clients.pem + job allowlist)
config/grafana/provisioning/         — auto datasource + dashboard provider + alerting/alerts.yml (per-IP SSH brute-force, firewall spike)
config/grafana/dashboards/           — dashboard JSON files (datasource uid: loki)
anomaly-detector/common.py           — Alert, LokiClient, Selectors, config constants
anomaly-detector/detector.py         — Engine.run_cycle(now): rule, statistical, ML + endpoint layers
anomaly-detector/windows_rules.py    — Windows Event Log / Sysmon rules → ATT&CK
anomaly-detector/linux_rules.py      — Linux auditd rules → ATT&CK
anomaly-detector/attack_catalog.py   — alert_type → ATT&CK techniques, coverage, lab technique set
anomaly-detector/evaluation/         — offline eval harness (fetch/ingest/run/score/report; AIT/OTRF/EVTX adapters; manifests/)
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
dashboard/app/services/              — loki_client, alert_reader (mtime-cached), health_checker, notifier (webhook, /state/notify.json)
dashboard/app/static/index.html      — page frame (top bar, menu), 5 page sections, 3 dialogs; no inline scripts or handlers (login.html too)
dashboard/app/static/css/theme.css   — Grafana-style theme: CSS variables (dark default, light) + component classes (panel, stat, tbl, btn, dlg…)
dashboard/app/static/js/             — ES modules, no build step: main.js (entry: auth, loaders, SSE dispatch, language) + state, dom, i18n, format, api, charts, shell (menu, hash routing, top bar, search, Esc), alert-dialog, pages/{overview,anomalies,devices,attack,notifications}.js; login.js; classic theme-boot.js + tailwind.config.js; vendored tailwind.min.js, chart.min.js
dashboard/app/services/device_registry.py — registered demo devices (JSON persistence in /state)
dashboard/app/services/syslog_emitter.py  — sends normal + attack syslog (UDP) to syslog-ng
dashboard/app/services/host_info.py       — reads mounted host files for self-server kernel/OS version
dashboard/app/services/device_monitor.py  — builds device map (per-host Loki stats + registry + self + discovered)
dashboard/app/routers/devices.py     — device CRUD, demo attack scenario, GET /map (node map)
dashboard/app/models/schemas.py      — Pydantic response models
dashboard/Dockerfile                 — Python 3.12-slim + uvicorn
dashboard/tests/                     — pytest: auth + API (TestClient with isolated tmp state) + static frontend checks
demo_data/anomaly_history.json       — seed alert data for demo/testing
seed_demo.sh                         — loads demo_data into kursinis_anomaly-data volume
demo.sh                              — presentation CLI against the running stack (needs curl, jq; admin creds from .env)
setup-host-syslog-ng.sh              — forwards this host's journal to the collector (Arch/pacman; COLLECTOR_TLS=1 → 6514)
setup-collector.sh                   — one-command production collector: .env secrets, certs, TLS 6514, bundles, COMPOSE_FILE/COMPOSE_PROFILES, start
onboarding/windows/                  — install.ps1 (Sysmon, audit policy, Alloy; idempotent, -NoSysmon/-Uninstall) + config.alloy, shipped in the Windows bundle
onboarding/linux/setup.sh            — agentless Linux: rsyslog + auditd syslog plugin → syslog-ng TLS 6514 (apt/dnf)
lab/                                 — VM lab: windows/ linux/ kali/ provisioning (reuses onboarding/) + attack/benign runners, collect_ground_truth.py, export_run.py (live Loki window → loki-eval)
tools/                               — gen-certs.sh (ca/server/client, `bundle <ip> [name]` → certs/bundles/, `revoke <name>`; refreshes certs/server/), parity_check.py, measure_resources.sh, build_otrf_manifest.py
```

## Commands
- `docker compose up -d` — base stack (syslog-ng, alloy, loki, grafana, dashboard)
- `docker compose --profile anomaly up -d` — recommended demo: base stack + anomaly detector
- `docker compose --profile endpoints up -d` — add the Windows endpoint gateway (needs certs: `tools/gen-certs.sh ca`, `server <ip>`, `bundle <ip>`)
- `./setup-collector.sh <ip>` — real office in one step (re-runnable); back to demo: delete `COMPOSE_FILE`/`COMPOSE_PROFILES` from `.env`
- `tools/gen-certs.sh bundle <ip> [name]` / `tools/gen-certs.sh revoke <name>`, then `docker compose restart alloy-gateway` — onboarding bundles, per-PC certs, revocation
- `docker compose --profile eval run --rm evaluator <fetch|ingest|run|score|report> ...` — offline evaluation (usage in `anomaly-detector/evaluation/__main__.py` docstring)
- `docker compose down -v` — teardown with volumes
- `docker compose logs -f anomaly-detector` — watch detections
- `docker compose up -d --build dashboard` — apply dashboard code changes (code is baked into the image; `restart` is not enough)
- `docker compose restart anomaly-detector` — apply detector code changes (`./anomaly-detector` is bind-mounted)
- `docker compose restart syslog-ng alloy grafana` — apply config file edits (bind-mounted files; `up -d` does not notice content changes)
- `docker compose exec dashboard python -m app.manage_users add <user> --role admin|viewer` — manage dashboard users (`list|add|passwd|delete`)
- `./seed_demo.sh` — load demo alert data into dashboard
- `./demo.sh health|log|traffic|alerts|coverage|roles`, `./demo.sh attack ssh|fw|full` — scripted presentation steps
- `sudo bash setup-host-syslog-ng.sh` — make this host send its own logs (map node "Šis serveris")
- `docker exec dashboard python -c 'import httpx,sys; print(httpx.get("http://loki:3100/loki/api/v1/query", params={"query": sys.argv[1]}).text)' '<LogQL>'` — ad-hoc LogQL (Loki has no host port)

### Demo flow (Devices tab)
1. `docker compose --profile anomaly up -d`
2. Open dashboard (8080) → Devices tab → "Add device": name + IP + OS (macOS / Windows 11). A per-OS setup tutorial is shown.
3. Registered devices auto-emit normal syslog (dashboard `syslog_emitter` → syslog-ng) — visible in traffic graphs within ~30s.
4. "Run attack" dropdown → `POST /api/devices/demo/scenario {attack}` runs a single attack: `ssh_bruteforce` (web-server-01) or `firewall_spike` (router-01). The "Test ML detector" button sends `{attack:"full"}` for the combined multi-stage scenario (SSH brute-force + firewall DROP + error burst). The real anomaly-detector raises alerts on the Anomalies tab within ~10–15 s (`CHECK_INTERVAL=5`); `log_volume_spike` only after the 1 h warm-up (see Gotchas).

### Tests
Runtime images contain no pytest — run tests in local uv venvs (Python 3.12, `.venv/` gitignored):
- One-time: `cd anomaly-detector && uv venv --python 3.12 && uv pip install -r requirements-eval.txt`; `cd dashboard && uv venv --python 3.12 && uv pip install -r requirements.txt pytest`
- `cd anomaly-detector && .venv/bin/python -m pytest tests/ -q` — 120 tests (rule, statistical, ML, engine, windows, linux incl. real/syslog-forwarded auditd records, eval harness)
- `cd dashboard && .venv/bin/python -m pytest tests/ -q` — 35 tests (auth: UserStore scrypt, tokens, roles, throttling, CLI; API: devices, sessions, permissions, detector + endpoint health, traffic counts, alert matching, no-cache headers; frontend: no inline handlers/scripts, module imports resolve)

## Ports
- 514/TCP,UDP — syslog input from network
- 1514/TCP — alternative syslog input (non-root)
- 6514/TCP — syslog over TLS (RFC 5425; Linux setup.sh, macOS; enable config/syslog-ng/conf.d/tls.conf)
- 3500/TCP — Alloy endpoint gateway: Windows agent Loki push (HTTPS + mTLS, pinned client certs; profile `endpoints`)
- 3100 — Loki API (internal Docker network only)
- 3000 — Grafana UI (admin / $GF_SECURITY_ADMIN_PASSWORD); HTTPS in production mode
- 8080 — Dashboard web UI (admin / $DASHBOARD_ADMIN_PASSWORD, bootstrap on first run); HTTPS in production mode

## Code Style
- Python: type hints, dataclasses, f-strings, docstrings
- Academic comments in Lithuanian, technical in English
- YAML configs for Loki/Grafana, Alloy river syntax, native syntax for syslog-ng
- Grafana: JSON provisioned dashboards, Europe/Vilnius timezone
- Dashboard: FastAPI + vanilla JS ES modules (no bundler) + Tailwind runtime + Chart.js, Grafana-style dark/light theme, i18n (LT/EN)

## Key Architecture Decisions
- syslog-ng writes files → Alloy reads them (shared Docker volume `syslog-ng-logs`); Alloy replaced Promtail (`config/alloy/collector.alloy` = `alloy convert` output). Files are per weekday (`all-Thu.log`, `security-*`, `errors-*`) with `overwrite-if-older(518000)`, so at most 7 days stay on disk; Alloy globs `all-*.log` and drops the `filename` label (eval ingest/golden fixture match)
- Alloy regex must match syslog-ng output template: `${R_ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}` — receive time, because RFC3164 stamps carry no time zone and the container runs UTC (senders on local time would land 2–3 h in the future and Loki rejects them)
- Windows PCs get one bundle (`tools/gen-certs.sh bundle` → `onboarding/windows/install.ps1`: Sysmon + audit policy + Alloy; shared `fleet` client cert by default, per-PC cert by name) and push to `alloy-gateway` (`loki.source.api` :3500, mTLS). The gateway pins client certs: `client_ca_file` = `certs/server/clients.pem` (rebuilt from `certs/clients/*.crt`) instead of the CA, so an unlisted CA-signed cert is rejected (verified with Alloy v1.20.1). List edits need `docker compose restart alloy-gateway` (`/-/reload` doesn't re-read it); pinned CNs are visible in the TLS handshake, so use neutral names. Job allowlist `{job=~"windows|linux_endpoint"}`, labels kept `{job,host,channel}`; Loki stays internal. Containers mount only `certs/server/` (never `ca.key` or bundles)
- The Windows agent's `loki.write` uses `max_backoff_retries = 0` = retry until delivered (verified); a revoked agent retries silently, so the gateway's `TLS handshake error` lines are the signal
- Linux PCs are agentless: `onboarding/linux/setup.sh` sets up rsyslog + auditd's syslog plugin over TLS 6514 (`x509/name` with PermittedPeers `syslog-ng` from the server SAN, disk queue), arriving as `job="syslog"` so the SSH rules keep working. The Linux rules read `{job=~"linux_endpoint|syslog"}` (`Selectors.linux_audit`) with the record-type filter, and the parser handles the `msg='...'` wrapper of real USER_AUTH/ADD_USER records (`res=failed'`)
- Production mode: `setup-collector.sh` writes `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` and `COMPOSE_PROFILES=anomaly,endpoints` into `.env`; the override sets CHECK_INTERVAL=60, SYNTHETIC_TRAFFIC=false, SEED_DEFAULT_DEVICES=0 and turns off Grafana/Alloy usage reporting. It also serves the dashboard (`UVICORN_SSL_CERTFILE/KEYFILE`, uvicorn reads `UVICORN_*` env) and Grafana (`GF_SERVER_PROTOCOL=https`) over HTTPS with `certs/server/collector.{crt,key}`; browsers warn until admin PCs trust `certs/ca.crt`. Grafana runs as uid 472, so gen-certs makes `certs/server` group-readable (0750/0640) and the override adds the owner's gid via `group_add` (`CERTS_GID`, written to `.env` by setup-collector.sh). Compose file-based secrets can't replace this: they are bind mounts that ignore uid/gid/mode (checked on Compose 5.6)
- Loki: label-based indexing only (no full-text), 30-day retention, datasource uid `loki`
- Anomaly detector runs one shared `Engine.run_cycle(now)` (live = wall clock, eval = virtual clock); firewall, statistical and ML counts come from `count_over_time`/metric queries (no 5000-line cap); SSH/invalid-user and endpoint rules read filtered log lines (`query_range`, 5000-line cap per query)
- ML detector (IsolationForest) is OFF in the live loop by default (`ENABLE_ML=false`) — it produced too many false positives; it is measured offline (RQ3). `ML_TRAINING_MODE` = online/frozen; training_data is deque(maxlen=`ML_MAX_TRAINING_SAMPLES`)
- Evaluation harness (`anomaly-detector/evaluation/`, profile `eval`): replays labeled datasets (AIT-LDS via HTTP-range zip extract, OTRF/EVTX Windows) through `loki-eval` with original timestamps, runs the Engine on a virtual clock, scores precision/recall/F1/FPR per layer (per tick and per non-overlapping window — ML runs every Nth cycle, so layers are compared per window) + per-technique ATT&CK recall + McNemar/bootstrap, emits LaTeX tables to `eval-results/`
- OTRF corpus: `evaluation/manifests/otrf_windows_host.csv` (107 Windows host captures, techniques from OTRF metadata, built by `tools/build_otrf_manifest.py`) at a pinned OTRF commit; `fetch otrf` downloads it, the adapter lays captures on one timeline with original in-capture timing. Technique credit is strict: only an alert mapped to the capture's technique counts. `run.json` git SHA gets `-dirty` for uncommitted code
- Windows rules query only their event IDs (`| json event_id | event_id=~...`) and Linux rules only their auditd record types (`|~ "type=(USER_AUTH|...|EXECVE) "`): unfiltered, dense Sysmon / journal+auditd streams exceed the 5000-line query cap
- Alert cooldown (300 s, `ALERT_COOLDOWN_SECONDS`) key is `type:ip:host:details.key`; per-event rules (Windows/Linux) put the event identity (account, command...) in `details.key`, so distinct events of one type on one host are not muted
- Anomaly detector writes alerts atomically (`tmp` + `os.replace`) to `/data/anomaly_history.json`, and `attack_catalog.json` at startup
- Two webhook paths: detector `ALERT_WEBHOOK_URL` (env; the one the thesis documents) and the dashboard notifier (UI → `/state/notify.json`, admin-only). Configure one — with both set every alert is sent twice
- Synthetic traffic is dashboard-driven only: 4 demo devices (MacBook, Windows 11, `router-01`, `web-server-01`) are seeded into the registry (`SEED_DEFAULT_DEVICES`) and auto-emit normal traffic; the standalone log-generator has been removed
- Dashboard reads Loki API for live traffic + anomaly_history.json for alerts (shared volume `anomaly-data`)
- Dashboard device registry persists to `/state/devices.json` (rw volume `dashboard-state`); `SyslogEmitter` sends UDP syslog to `syslog-ng:514` using the standard BSD syslog format, so syslog-ng/Alloy/detector treat it identically. `DeviceCreate.synthetic` (default true) marks demo devices that auto-emit; synthetic=false registers a real endpoint that sends its own logs
- Background asyncio task emits per-device normal traffic every `NORMAL_TRAFFIC_INTERVAL` (default 5s) ONLY for `synthetic` registry devices; `POST /api/devices/demo/scenario` takes `{attack}` (`ssh_bruteforce` | `firewall_spike` | `full`) and fires the matching on-demand attack via `SyslogEmitter.simulate_attack` (`full` = SSH brute-force + firewall DROP + error burst), detected by the real anomaly-detector
- Live updates: `GET /api/stream` is a Server-Sent Events (SSE) endpoint (`routers/stream.py`, `StreamingResponse` `text/event-stream`) that pushes `health`/`traffic`/`alerts`/`devices` events only when their JSON changes (`STREAM_INTERVAL`=5s, devices every 3rd tick, `: ping` heartbeat). Frontend opens one `EventSource` in `init()`; each `apply*()` re-renders. The traffic-history chart stays client-driven (range/host aware), refreshed on a throttled `maybeRefreshHistory()` when a `traffic` event arrives
- Device node map (`GET /api/devices/map`): merges registered (synthetic) devices + the Docker host itself + any host auto-discovered from Loki `host` labels; each node gets live `logs_5m`/`logs_1h`/`last_seen`/`online` (online = logs in last 5 min) via `sum by (host)(count_over_time(...))` (`last_seen` = newest non-empty 1-minute bucket in the last hour). Discovered hosts that are bare IPs (e.g. the Docker bridge gateway `172.18.0.1` from NAT'd port-published logs) and hostnames in the deleted-suppression list are excluded. The self/host node is shown with a generic name (`SELF_DEVICE_NAME`, default "Šis serveris") and its real hostname is hidden in the UI.
- Deleting a device (`DELETE /api/devices/{id}`) records its hostname in `/state/deleted_hosts.json` (`SUPPRESSED_DB_PATH`) so it won't reappear as a "discovered" node while its logs age out of Loki (~1h), and a deleted default demo device is not re-seeded on restart; re-adding the same hostname clears the suppression
- Self-host monitoring: `setup-host-syslog-ng.sh` installs host syslog-ng (template `config/syslog-ng-host/syslog-ng.conf`) forwarding the journal to `127.0.0.1:514`; its kernel/OS version comes from read-only mounts `/etc/hostname`, `/etc/os-release`, `/proc/version` -> `/host/*` (Linux host only; `HOST_INFO_DIR`)
- Tutorials are frontend i18n (LT/EN): Windows = `install.ps1` from the bundle, Linux = `sudo ./setup.sh` from the tarball, macOS = syslog-ng over TLS 6514 config. The Devices tab's "Connect a computer" button opens them with an OS selector without registering a device (real PCs appear as discovered nodes); "Add device" stays the demo feature. Collector address shown to the user is `window.location.hostname`
- Dashboard auth: real users in `/state/users.json` (scrypt hashes), HMAC-signed expiring tokens carrying a role (`DASHBOARD_SECRET_KEY`, TTL), login throttling per client IP; `require_auth` guards all `/api/*` read routes, `require_admin` guards device CRUD / demo scenario / notifications (incl. reading the webhook URL). Requests are checked with `verify_session` = signature + expiry + the user still exists with the same role (deleted/demoted users are cut off at once). SSE `/api/stream` authenticates via `?token=` query param with the same check, repeated every tick. First admin bootstraps from `DASHBOARD_ADMIN_USER/PASSWORD`
- ATT&CK coverage: detector writes `/data/attack_catalog.json`; dashboard `GET /api/attack/coverage` combines it with alert history (has_rule vs detected) for the ATT&CK tab
- AlertReader is mtime-cached and injected via DI; alert IDs are deterministic sha1(ts|type|ip|host[|details.key])[:16]; `AlertItem.attack_techniques` surfaces ATT&CK IDs in the UI
- Health checker reports syslog-ng/alloy as `unknown` when Loki is down; probes Alloy `/-/ready` directly; endpoint-telemetry check over `{job=~"windows|linux_endpoint"}` is ok with data in the last 5 min, a warning with the silence age if data was seen within 7 days, hidden otherwise (agentless Linux is `job="syslog"`, covered only by the general freshness check); anomaly-detector is `critical` when its heartbeat `/data/detector.alive` (touched every cycle) is missing or older than 2 min
- Dashboard traffic counts (`/api/traffic/current`) come from a Loki instant metric query, not downloaded lines
- Dashboard frontend (Grafana-style, no build step): colors are CSS variables in `css/theme.css` (dark default, light via `<html data-theme="light">`, choice in localStorage); `theme-boot.js` applies it before first paint, `tailwind.config.js` maps Tailwind colors to the variables (so opacity modifiers like `bg-panel/50` don't work), and charts read the variables and recolor on switch (`charts.js` `track()`/`applyTheme()`). Pages are ES modules (`pages/*.js`, `init(ctx)`/`render()`; loaders come from `main.js` via `ctx`, so pages never import `main.js`) with hash routing (`#dashboard|anomalies|devices|attack|messages`, reload keeps the page). No inline handlers or scripts (pytest checks). `/`, `/login`, `/static/*` are sent with `Cache-Control: no-cache`, so browsers revalidate after an upgrade

## Gotchas
- A browser that cached the pre-redesign dashboard (`app.js`, no `no-cache` header yet) needs one hard refresh (Ctrl+Shift+R) after the upgrade; later updates revalidate on their own
- After a detector restart `log_volume_spike` stays silent for 1 h (in-memory baseline warm-up); rule alerts and `high_error_rate` fire at once — restart well before a demo
- Loki `align_queries_with_step: true` floors range-metric queries to step boundaries, so the newest partial step is missing: use `AsyncLokiClient.query_instant` for "last N minutes" numbers. The traffic-history chart keeps its raw-line fallback because a fresh stack would otherwise show nothing for up to one step (1 h on the 24 h view). Known gap: device-map `logs_5m`/`logs_1h` still use aligned range queries, so a new device can look offline for up to 5 min
- Every service has a fixed `container_name`, so a second stack (`-p other`) collides; for throwaway end-to-end tests use a separate compose file without container names or host ports
- With `COMPOSE_FILE` in `.env` (production mode) every plain `docker compose` command uses the prod override (no demo traffic, 60 s detector, HTTPS-only dashboard/Grafana); delete `COMPOSE_FILE`/`COMPOSE_PROFILES` from `.env` for demos
- Run `tools/gen-certs.sh` before `docker compose up` on a fresh clone: Docker creates a missing `certs/server` mount root-owned (gen-certs replaces an empty one)
- Busybox `wget` in the Loki container returns 400 for LogQL with backticks; use the `docker exec dashboard python ...` one-liner from Commands
- Known detection gap: auditd hex-encodes EXECVE arguments containing spaces or quotes, and `linux_rules.py` doesn't decode them, so `bash -c "..."` / `python3 -c '...'` one-liners aren't matched (an inner `bash -i` exec still is)
- `LaTex/` (gitignored) holds the thesis; `kursinis_final/kursinis_galutinis.tex` documents `ALERT_WEBHOOK_URL`, the Grafana alert rules, the heartbeat path and the syslog template — check it before removing or renaming a documented feature (it still describes Promtail and `/tmp/detector.alive`)

## Anomaly Detection Layers (detector.py Engine)
1. `RuleBasedDetector` (job=syslog) — SSH brute-force (≥5 failures/5min/IP), invalid user scanning (≥3 usernames/IP, case-insensitive), firewall spike (>50 DROP)
2. `WindowsRuleDetector` (job=windows) — 4625/4740/4720/4732/1102/4104 + Sysmon 1/3/11, ATT&CK-mapped (`windows_rules.py`)
3. `LinuxEndpointRuleDetector` (job=~"linux_endpoint|syslog") — auditd sudo failures, useradd, suspicious EXECVE, discovery burst (`linux_rules.py`)
4. `StatisticalDetector` — log volume z-score (3σ, time-based baseline `BASELINE_WINDOW_HOURS`, judged only after 1 h of baseline history), error rate (>30%)
5. `MLDetector` — IsolationForest (LogQL-metric features); off in live loop by default, evaluated offline
- All alert types map to MITRE ATT&CK via `attack_catalog.py`; `Engine` fills `Alert.attack_techniques`
