# Log Analysis System

Centralized log analysis and anomaly detection system for small organizations.
Academic coursework (kursinis darbas, Vilnius University ISKS).

## Stack
syslog-ng 4.8 → Promtail 3.4 → Loki 3.4 → Grafana 11.5 + Python 3.12 anomaly detector + FastAPI dashboard.
Everything containerized in Docker Compose.

## Structure
```
docker-compose.yml — 7 services (syslog-ng, promtail, loki, grafana, anomaly-detector, dashboard, log-generator)
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
dashboard/app/models/schemas.py      — Pydantic response models
dashboard/Dockerfile                 — Python 3.12-slim + uvicorn
dashboard/tests/                     — pytest tests (alert_reader, routes, auth enforcement)
demo_data/anomaly_history.json       — seed alert data for demo/testing
log-generator/generator.py           — realistic syslog simulator with attack scenarios
log-generator/Dockerfile
seed_demo.sh                         — loads demo_data into kursinis_anomaly-data volume
```

## Commands
- `docker compose up -d` — base stack (syslog-ng, promtail, loki, grafana, dashboard)
- `docker compose --profile dev up -d` — also start log generator (synthetic traffic)
- `docker compose --profile anomaly up -d` — also start anomaly detector
- `docker compose --profile anomaly --profile dev up -d` — everything
- `docker compose down -v` — teardown with volumes
- `docker compose logs -f anomaly-detector` — watch detections
- `docker compose restart dashboard` — apply dashboard code changes (or `up -d --build dashboard`)
- `./seed_demo.sh` — load demo alert data into dashboard

### Tests
- `docker compose run --rm dashboard pytest tests/ -v` — dashboard tests inside container
- `docker compose run --rm anomaly-detector pytest tests/ -v` — detector tests (requires `tests/` mounted or COPYed)
- Locally with venv: `cd dashboard && pytest tests/` (requires `pip install -r requirements.txt pytest`)

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
- Log generator only with `--profile dev` — never in production
- Dashboard reads Loki API for live traffic + anomaly_history.json for alerts (shared volume `anomaly-data`)
- Dashboard auth: demo Bearer token (sha256(username:salt)[:32]) enforced on all `/api/{traffic,alerts,health}` routes via `Depends(require_auth)`; client sends `Authorization: Bearer <token>` after login
- AlertReader is mtime-cached and injected via DI; alert IDs are deterministic sha1(ts|type|ip|host)[:16]
- Health checker reports syslog-ng/promtail as `unknown` when Loki is down (cannot infer freshness without Loki)

## Anomaly Detection Layers (detector.py)
1. `RuleBasedDetector` — SSH brute-force (≥5 failures/5min/IP), invalid user scanning (≥3 usernames/IP), firewall spike (>50 DROP)
2. `StatisticalDetector` — log volume z-score (threshold 3σ), error rate (>30%)
3. `MLDetector` — IsolationForest on features: log_count, unique_programs, error_rate, unique_ips, avg_msg_length
