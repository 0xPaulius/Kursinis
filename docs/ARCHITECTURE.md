# Architektūra — centralizuotos žurnalų analizės sistema

**Kursinis darbas, Vilniaus universitetas, ISKS**
Autorius: Paulius Turauskas

Centralizuotas žurnalų rinkimas, saugojimas, vizualizavimas ir anomalijų aptikimas mažoms organizacijoms.

## Apžvalga

Sistema veikia kaip pilnai konteinerizuotas (Docker Compose) žurnalų analizės konvejeris.
Tinklo įrenginiai ir serveriai siunčia syslog žinutes; logai surenkami, saugomi ir analizuojami.
Anomalijos aptinkamos automatiškai naudojant taisyklėmis pagrįstą, statistinį ir ML metodus.
Be Grafana, sistema turi savą FastAPI dashboard'ą su lietuviška sąsaja.

### Duomenų srautas

```
[Tinklo įrenginiai / serveriai]
       |  syslog (UDP/TCP 514)
       v
[syslog-ng]   — surenka, rašo į shared volume
       |  failai (Docker volume: syslog-ng-logs)
       v
[Promtail]    — tail'ina failus, parsuoja regex'u, prideda labels, siunčia į Loki
       |  HTTP push
       v
[Loki]        — saugo logus indeksuotus tik pagal labels (be full-text), 30 d. retencija
       |  HTTP query API (/loki/api/v1/query_range)
       v
[Anomaly Detector]  — Python servisas, polins Loki, aptinka grėsmes, rašo alertus į JSON
[Grafana]           — skaito Loki, teikia dashboardus ir alerting UI
[Dashboard]         — FastAPI/Python web UI, skaito Loki + anomaly JSON
```

## Servisai (docker-compose.yml — 7 konteineriai)

1. **syslog-ng** (`balabit/syslog-ng:4.8.3`)
   - Klauso 514/UDP, 514/TCP, 1514/TCP
   - Konfigūracija: `config/syslog-ng/syslog-ng.conf`
   - Rašo į shared volume: `/var/log/syslog-ng`
   - Output template: `${ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`

2. **promtail** (`grafana/promtail:3.4.2`)
   - Skaito syslog-ng log failus iš shared volume
   - Konfigūracija: `config/promtail/promtail.yml`
   - Parsuoja logus regex'u, išgauna labels: `host`, `facility`, `level`, `program`, `pid`
   - Siunčia į Loki
   - **Regex privalo tiksliai atitikti syslog-ng output template'ą**

3. **loki** (`grafana/loki:3.4.2`)
   - Žurnalų saugykla
   - Konfigūracija: `config/loki/loki.yml`
   - Indeksavimas tik pagal labels (be full-text)
   - 30 d. retencija
   - Vidinis portas 3100 (neeksponuotas)

4. **grafana** (`grafana/grafana:11.5.2`)
   - Web UI portas 3000
   - Kredencialai: admin / `$GF_SECURITY_ADMIN_PASSWORD`
   - Loki datasource auto-provisioning: `config/grafana/provisioning/`
   - Dashboards auto-provisioning: `config/grafana/dashboards/`
   - Laiko juosta: Europe/Vilnius

5. **anomaly-detector** (Python 3.12-slim, custom)
   - Šaltinis: `anomaly-detector/detector.py`
   - Polins Loki HTTP API kas 60s (`CHECK_INTERVAL`)
   - Trijų sluoksnių aptikimas:
     - **RuleBasedDetector**: SSH brute-force (≥5 nesėkmių/5min/IP), neegzistuojantis vartotojas (≥3 unikalūs/IP), firewall spike (>50 DROP)
     - **StatisticalDetector**: log volume z-score (3σ), error rate (>30%)
     - **MLDetector** (IsolationForest): features = log_count, unique_programs, error_rate, unique_ips, avg_msg_length; treniruojamas po ≥20 imčių; vykdomas kas 5-ą ciklą
   - Rašo į `/data/anomaly_history.json` (volume: `anomaly-data`)
   - Webhook (Telegram/Slack) per `ALERT_WEBHOOK_URL`
   - Health: liečia `/tmp/detector.alive` kiekvieną ciklą

6. **dashboard** (FastAPI + Uvicorn, custom)
   - Šaltinis: `dashboard/app/`
   - Web UI portas 8080
   - Dvikalbis UI (LT/EN)
   - Backend: `routers/` (auth, traffic, alerts, health) + `services/` (loki_client, alert_reader, health_checker)
   - Pydantic modeliai: `models/schemas.py`
   - Frontend: Vanilla JS + Tailwind + Chart.js
   - Auth: demo kredencialai admin / admin123, Bearer token Authorization antraštėje
   - Skaito Loki API gyvam srautui, `/data/anomaly_history.json` alertams
   - Testai: `dashboard/tests/` (pytest)

7. **log-generator** (DEV only — `--profile dev`)
   - Šaltinis: `log-generator/generator.py`
   - Siunčia realistiškas syslog žinutes į `syslog-ng:514`
   - Simuliuoja normalų srautą + atakas (SSH brute-force, port scan ir kt.)

## Failų struktūra

```
docker-compose.yml
config/
  syslog-ng/syslog-ng.conf
  loki/loki.yml
  promtail/promtail.yml
  grafana/provisioning/, grafana/dashboards/
anomaly-detector/
  detector.py, Dockerfile, requirements.txt
  tests/                              — pytest testai (rule/statistical/ml)
dashboard/
  app/
    main.py, dependencies.py
    routers/   — auth, traffic, alerts, health
    services/  — loki_client, alert_reader, health_checker
    models/schemas.py
    static/    — index.html, login.html, css/, js/, fonts/
  Dockerfile, requirements.txt
  tests/                              — test_alert_reader, test_routes
demo_data/anomaly_history.json
seed_demo.sh
log-generator/generator.py, Dockerfile
```

## Portai

| Portas | Servisas |
|--------|----------|
| 514/UDP, 514/TCP | syslog input (eksponuotas) |
| 1514/TCP | alternatyvus syslog input |
| 3000 | Grafana web UI |
| 8080 | Dashboard web UI |
| 3100 | Loki API (tik vidinis) |

## Docker volumes

| Volume | Paskirtis |
|--------|-----------|
| `syslog-ng-logs` | syslog-ng (rašo) ↔ promtail (skaito) |
| `loki-data` | Loki saugykla |
| `grafana-data` | Grafana būsena |
| `anomaly-data` | anomaly_history.json: detector ↔ dashboard |
| `promtail-positions` | Promtail failo skaitymo pozicijos |

## Aplinkos kintamieji (svarbiausi)

| Kintamasis | Paskirtis |
|-----------|-----------|
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin slaptažodis (privalomas) |
| `LOKI_URL` | Loki endpoint (default: `http://loki:3100`) |
| `CHECK_INTERVAL` | Detektoriaus polinimo intervalas, s (default: 60) |
| `SSH_BRUTE_THRESHOLD` | Maks. SSH nesėkmių (default: 5) |
| `LOG_SPIKE_MULTIPLIER` | Z-score slenkstis spike alertui (default: 3.0) |
| `ALERT_WEBHOOK_URL` | Pasirinktinis webhook URL alertams |

## Kodo stilius

- Python: type hints, dataclasses, f-strings, docstrings public metoduose
- Komentarai: akademiniai/aiškinamieji LT, techniniai inline EN
- Konfigai: YAML (Loki/Promtail/Grafana), syslog-ng native syntax
- Be paslapčių kode — viskas per environment variables (`.env` failas)
