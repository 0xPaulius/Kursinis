# Log Analysis System

Centralized log analysis and anomaly detection system for small organizations.
Academic coursework (kursinis darbas, Vilnius University ISKS).

## Stack
syslog-ng 4.8 → Promtail 3.4 → Loki 3.4 → Grafana 11.5 + Python 3.12 anomaly detector.
Everything containerized in Docker Compose.

## Structure
```
docker-compose.yml                  — 6 services (syslog-ng, promtail, loki, grafana, anomaly-detector, log-generator)
config/syslog-ng/syslog-ng.conf    — syslog receiver, filters, destinations
config/loki/loki.yml               — storage, retention (30d), schema
config/promtail/promtail.yml       — regex parsing, label extraction
config/grafana/provisioning/       — auto datasource + dashboard provider
config/grafana/dashboards/         — dashboard JSON files
anomaly-detector/detector.py       — 3-layer detection (rule, statistical, ML)
anomaly-detector/Dockerfile        — Python 3.12-slim
anomaly-detector/requirements.txt  — requests, numpy, scikit-learn
log-generator/generator.py         — realistic syslog simulator with attack scenarios
log-generator/Dockerfile
```

## Commands
- `docker compose up -d` — production (no test data)
- `docker compose --profile dev up -d` — with log generator
- `docker compose down -v` — teardown with volumes
- `docker compose logs -f anomaly-detector` — watch detections
- `docker compose restart anomaly-detector` — apply code changes

## Ports
- 514/TCP,UDP — syslog input from network
- 3100 — Loki API (internal)
- 3000 — Grafana UI (admin / admin123)

## Code Style
- Python: type hints, dataclasses, f-strings, docstrings
- Academic comments in Lithuanian, technical in English
- YAML configs for Loki/Promtail/Grafana, native syntax for syslog-ng
- Grafana: JSON provisioned dashboards, Europe/Vilnius timezone

## Key Architecture Decisions
- syslog-ng writes files → Promtail reads them (shared Docker volume `syslog-ng-logs`)
- Promtail regex must match syslog-ng output template: `${ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`
- Loki: label-based indexing only (no full-text), 30-day retention
- Anomaly detector queries Loki HTTP API (`/loki/api/v1/query_range`)
- ML detector (IsolationForest) trains after ≥20 samples, runs every 5th cycle
- Log generator only with `--profile dev` — never in production

## Anomaly Detection Layers (detector.py)
1. `RuleBasedDetector` — SSH brute-force (≥5 failures/5min/IP), invalid user scanning (≥3 usernames/IP), firewall spike (>50 DROP)
2. `StatisticalDetector` — log volume z-score (threshold 3σ), error rate (>30%)
3. `MLDetector` — IsolationForest on features: log_count, unique_programs, error_rate, unique_ips, avg_msg_length
