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
[Tinklo įrenginiai / serveriai]            [Windows / Linux galiniai įrenginiai]
       |  syslog (UDP/TCP 514, TLS 6514)           |  Alloy agentas, HTTPS push + mTLS
       v                                           v
[syslog-ng]   — surenka, rašo į shared volume   [alloy-gateway :3500] — mTLS, job allowlist
       |  failai (Docker volume: syslog-ng-logs)   |
       v                                           |
[Alloy]       — tail'ina failus, parsuoja regex'u, prideda labels, siunčia į Loki
       |  HTTP push                                |
       v                                           v
[Loki]        — saugo logus indeksuotus tik pagal labels (be full-text), 30 d. retencija
       |  HTTP query API (/loki/api/v1/query_range)
       v
[Anomaly Detector]  — Python servisas, polins Loki, aptinka grėsmes, rašo alertus į JSON
[Grafana]           — skaito Loki, teikia dashboardus ir alerting UI
[Dashboard]         — FastAPI/Python web UI, skaito Loki + anomaly JSON

Vertinimui (profilis `eval`): [loki-eval] + [evaluator] — detektorius paleidžiamas
virtualiu laikrodžiu per pažymėtus rinkinius (AIT-LDS, OTRF, EVTX) ir skaičiuoja
precision/recall/F1/FPR bei ATT&CK aprėptį (anomaly-detector/evaluation/).
```

## Servisai (docker-compose.yml)

Bazinis stackas + profiliai: `anomaly` (detektorius), `endpoints` (Windows/Linux galinių
įrenginių šliuzas), `eval` (offline vertinimas).

1. **syslog-ng** (`balabit/syslog-ng:4.8.3`)
   - Klauso 514/UDP, 514/TCP, 1514/TCP; TLS 6514 (įjungiama `config/syslog-ng/conf.d/tls.conf`)
   - Konfigūracija: `config/syslog-ng/syslog-ng.conf` (+ `conf.d/*.conf`)
   - Rašo į shared volume: `/var/log/syslog-ng`
   - Output template: `${ISODATE} ${HOST} ${FACILITY}.${LEVEL} ${PROGRAM}[${PID}]: ${MESSAGE}`

2. **alloy** (`grafana/alloy:v1.20.1`) — pakeitė Promtail
   - Skaito syslog-ng log failus iš shared volume
   - Konfigūracija: `config/alloy/collector.alloy` (konvertuota iš Promtail per `alloy convert`)
   - Parsuoja logus regex'u, išgauna labels: `host`, `facility`, `severity`, `program`
   - `legacy_positions_file` perima Promtail pozicijas (migracija be pakartotinio skaitymo)
   - **Regex privalo tiksliai atitikti syslog-ng output template'ą**

   **alloy-gateway** (`grafana/alloy:v1.20.1`, profilis `endpoints`)
   - `loki.source.api` :3500 — galinių įrenginių (Windows/Linux Alloy agentų) Loki push
   - TLS su kliento sertifikatais (mTLS); job allowlist `{job=~"windows|linux_endpoint"}`
   - Konfigūracija: `config/alloy/gateway.alloy`; sertifikatai: `tools/gen-certs.sh`

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
   - Aptikimo sluoksniai (bendras `Engine.run_cycle(now)` — gyvai ir vertinimui):
     - **RuleBasedDetector** (job=syslog): SSH brute-force (≥5 nesėkmių/5min/IP), neegzistuojantis vartotojas (≥3 unikalūs/IP), firewall spike (>50 DROP); kiekiai per `count_over_time` (be 5000 ribos)
     - **WindowsRuleDetector** (job=windows): 4625/4740/4720/4732/1102/4104 + Sysmon 1/3/11, susieti su ATT&CK (`windows_rules.py`)
     - **LinuxEndpointRuleDetector** (job=linux_endpoint): auditd sudo nesėkmės, useradd, įtartinas EXECVE, žvalgyba (`linux_rules.py`)
     - **StatisticalDetector**: log volume z-score (laiko langas `BASELINE_WINDOW_HOURS`), error rate (>30%)
     - **MLDetector** (IsolationForest): požymiai per LogQL metrikas; **gyvai išjungtas** (`ENABLE_ML=false` — per daug klaidingų teigiamų), vertinamas offline (RQ3)
   - ATT&CK susiejimas: `attack_catalog.py`; startuojant rašo `/data/attack_catalog.json`
   - Rašo į `/data/anomaly_history.json` (volume: `anomaly-data`)
   - Webhook (Telegram/Slack) per `ALERT_WEBHOOK_URL`
   - Health: liečia `/tmp/detector.alive` kiekvieną ciklą

   **loki-eval + evaluator** (profilis `eval`)
   - `loki-eval`: atskiras Loki su originaliomis rinkinių laiko žymomis (`config/loki/loki-eval.yml`)
   - `evaluator`: `python -m evaluation` (ingest → run → score → report); metrikos ir LaTeX lentelės į `eval-results/`

6. **dashboard** (FastAPI + Uvicorn, custom)
   - Šaltinis: `dashboard/app/`
   - Web UI portas 8080
   - Dvikalbis UI (LT/EN)
   - Backend: `routers/` (auth, traffic, alerts, health, devices, notifications, stream, attack) + `services/` (loki_client, alert_reader, health_checker, device_registry, device_monitor, syslog_emitter, notifier, host_info, user_store, attack_coverage)
   - Pydantic modeliai: `models/schemas.py`
   - Frontend: Vanilla JS + Tailwind + Chart.js; skiltys: Apžvalga, Anomalijos, Įrenginiai, ATT&CK aprėptis, Pranešimai
   - Auth: scrypt slaptažodžių maišos (`/state/users.json`), HMAC parašu pasirašyti galiojantys tokenai, rolės admin/viewer, bandymų ribojimas; vartotojų CLI `python -m app.manage_users`
   - ATT&CK aprėptis: `GET /api/attack/coverage` (skaito `/data/attack_catalog.json` + alertų istoriją)
   - Srautas/žemėlapis/būklė naudoja `{job=~"syslog|windows|linux_endpoint"}` (endpoint'ai matomi)
   - Skaito Loki API gyvam srautui, `/data/anomaly_history.json` alertams
   - Generuoja sintetinį įrenginių srautą (normalų) ir demonstracines atakas tiesiai į `syslog-ng:514` („Paleisti ataką" meniu: SSH brute-force / ugniasienės skenavimas; „Testuoti ML detektorių" — pilnas scenarijus; atskiras generatorius nebereikalingas)

## Failų struktūra

```
docker-compose.yml
config/
  syslog-ng/syslog-ng.conf, syslog-ng/conf.d/tls.conf.example
  loki/loki.yml, loki/loki-eval.yml
  alloy/collector.alloy, alloy/gateway.alloy
  grafana/provisioning/, grafana/dashboards/
anomaly-detector/
  common.py, detector.py, windows_rules.py, linux_rules.py, attack_catalog.py
  evaluation/                         — offline vertinimas (adapters/, metrics, report, CLI)
  Dockerfile, requirements.txt, requirements-eval.txt
  tests/                              — pytest (rule/statistical/ml/engine/windows/linux/eval)
dashboard/
  app/
    main.py, dependencies.py, manage_users.py, log_selectors.py
    routers/   — auth, traffic, alerts, health, devices, notifications, stream, attack
    services/  — loki_client, alert_reader, health_checker, device_registry, device_monitor, syslog_emitter, notifier, host_info, user_store, attack_coverage
    models/schemas.py
    static/    — index.html, login.html, css/, js/, fonts/
  Dockerfile, requirements.txt
  tests/                              — auth (user_store, tokens, roles, CLI)
lab/                                  — VM stendas (windows/, linux/, kali/) + ground truth įrankiai
tools/                               — gen-certs.sh, parity_check.py, measure_resources.sh
demo_data/anomaly_history.json
seed_demo.sh
```

## Portai

| Portas | Servisas |
|--------|----------|
| 514/UDP, 514/TCP | syslog input (eksponuotas) |
| 1514/TCP | alternatyvus syslog input |
| 6514/TCP | syslog per TLS (RFC 5425; įjungiama conf.d/tls.conf) |
| 3500/TCP | alloy-gateway — galinių įrenginių Loki push (HTTPS, mTLS; profilis `endpoints`) |
| 3000 | Grafana web UI |
| 8080 | Dashboard web UI |
| 3100 | Loki API (tik vidinis) |

## Docker volumes

| Volume | Paskirtis |
|--------|-----------|
| `syslog-ng-logs` | syslog-ng (rašo) ↔ alloy (skaito) |
| `loki-data` | Loki saugykla |
| `loki-eval-data` | loki-eval saugykla (profilis `eval`) |
| `grafana-data` | Grafana būsena |
| `anomaly-data` | anomaly_history.json + attack_catalog.json: detector ↔ dashboard |
| `dashboard-state` | vartotojai, įrenginiai, tokenų raktas (`/state`) |
| `alloy-data` | Alloy WAL / būsena |
| `promtail-positions` | perimamos Promtail pozicijos (migracijai) |

## Aplinkos kintamieji (svarbiausi)

| Kintamasis | Paskirtis |
|-----------|-----------|
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin slaptažodis (privalomas) |
| `DASHBOARD_ADMIN_USER` / `DASHBOARD_ADMIN_PASSWORD` | Pirmas dashboard admin (bootstrap) |
| `DASHBOARD_SECRET_KEY` | Tokenų parašo raktas (tuščias = generuojamas į `/state/secret.key`) |
| `LOKI_URL` | Loki endpoint (default: `http://loki:3100`) |
| `CHECK_INTERVAL` | Detektoriaus polinimo intervalas, s (default: 60) |
| `SSH_BRUTE_THRESHOLD` | Maks. SSH nesėkmių (default: 5) |
| `LOG_SPIKE_MULTIPLIER` | Z-score slenkstis spike alertui (default: 3.0) |
| `BASELINE_WINDOW_HOURS` | Statistinio baseline langas, val. (default: 24) |
| `ENABLE_ML` | ML sluoksnis gyvame cikle (default: false) |
| `ENABLE_WINDOWS_RULES` / `ENABLE_LINUX_RULES` | Endpoint taisyklės (default: true) |
| `ML_TRAINING_MODE` | `online` / `frozen` (vertinimui, RQ3) |
| `SYNTHETIC_TRAFFIC` | Dashboard demo srautas (laboratorijoje: false) |
| `ALERT_WEBHOOK_URL` | Pasirinktinis webhook URL alertams |

## Kodo stilius

- Python: type hints, dataclasses, f-strings, docstrings public metoduose
- Komentarai: akademiniai/aiškinamieji LT, techniniai inline EN
- Konfigai: YAML (Loki/Grafana), Alloy river syntax, syslog-ng native syntax
- Be paslapčių kode — viskas per environment variables (`.env` failas)
