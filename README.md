# Centralizuota žurnalų analizės ir anomalijų aptikimo sistema

Kursinis darbas mažoms organizacijoms skirta centralizuota log analizės ir anomalijų aptikimo sistema.

## Architektūra

```
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  Linux serveriai │  │ Tinklo įrenginiai │  │ Windows / Linux stotys   │
│  (rsyslog/TLS)   │  │ (MikroTik, Ubiq.) │  │ (Grafana Alloy agentas)  │
└────────┬────────┘  └────────┬─────────┘  └────────┬─────────────────┘
         │ TCP 514 / TLS 6514 │ UDP 514             │ HTTPS 3500 (mTLS)
         └────────────────────┤                     ▼
                              ▼              ┌─────────────────┐
                    ┌─────────────────┐      │  alloy-gateway  │ ← mTLS, job allowlist
                    │    syslog-ng     │      │ (loki.source.api)│
                    │  (priima, rašo)  │      └────────┬────────┘
                    └────────┬────────┘               │
                             │ failų sistema          │
                             ▼                         │
                    ┌─────────────────┐               │
                    │  Grafana Alloy   │  ← Skaito failus, siunčia į Loki
                    │  (parsina, labels)│               │
                    └────────┬────────┘               │
                             │ HTTP push              │
                             ▼◄──────────────────────┘
                    ┌─────────────────┐
                    │      Loki        │  ← Žurnalų saugykla
                    │  (indeksuoja)    │
                    └───┬─────────┬───┘
                        │         │
           ┌────────────┘         └────────────┐
           ▼                                    ▼
┌─────────────────┐                  ┌─────────────────────┐
│    Grafana       │                  │  Anomaly Detector   │
│  (vizualizacija, │                  │  (Python: rules,    │
│   alertai)       │                  │   statistics, ML)   │
└─────────────────┘                  └─────────────────────┘
     ↓ Web UI :3000                       ↓ Alertai
                                    (Telegram/Slack/Email)
```

## Tech stackas

| Komponentas       | Technologija      | Paskirtis                              |
|-------------------|-------------------|----------------------------------------|
| Kolektorius       | syslog-ng 4.8     | Syslog priėmimas iš viso tinklo (UDP/TCP 514, TLS 6514) |
| Log siuntėjas     | Grafana Alloy 1.20| Logų persiuntimas iš failų į Loki; endpoint šliuzas (mTLS) |
| Saugykla          | Grafana Loki 3.4  | Efektyvi logų saugykla (label-based)  |
| Vizualizacija     | Grafana 11.5      | Dashboard'ai, alertai, log naršymas   |
| Anomalijų apt.    | Python 3.12       | Rule-based, statistinis, ML (IsoForest)|
| Dashboard         | FastAPI + JS      | Web UI: logų srautas, anomalijos, paieška |
| Konteinerizacija  | Docker Compose    | Vienodas deployment bet kurioje aplinkoje |

## Paleidimas

### 1. Aplinkos kintamieji

```bash
cp .env.example .env
# Pakeiskite GF_SECURITY_ADMIN_PASSWORD ir DASHBOARD_ADMIN_PASSWORD reikšmes
```

### 2. Bazinis stackas

```bash
docker compose up -d
```

Dashboard automatiškai generuoja sintetinį įrenginių srautą (MacBook, Windows 11,
maršrutizatorius, web serveris), tad grafikai užsipildo per ~30 s.

### 3. Su anomalijų aptikimu (rekomenduojama demo režimui)

```bash
docker compose --profile anomaly up -d
./seed_demo.sh   # įkelia demo alertus į dashboard'ą
```

Įrenginių skiltyje „Paleisti ataką" mygtukas atveria meniu su konkrečiomis atakomis
(SSH slaptažodžių ataka, ugniasienės / prievadų skenavimas), o „Testuoti ML detektorių"
paleidžia pilną daugiapakopį scenarijų. Sugeneruotą kenkėjišką srautą aptinka
anomaly-detector ir per ~60 s parodo anomalijas „Anomalijų" skiltyje.

### 3a. Galinių įrenginių priėmimas (Windows/Linux)

```bash
tools/gen-certs.sh ca && tools/gen-certs.sh server <kolektoriaus-IP>
tools/gen-certs.sh client <vardas>
docker compose --profile anomaly --profile endpoints up -d
```

Galinių įrenginių paruošimas (Sysmon, Alloy, auditd) — žr. `lab/README.md`.

### 3b. Offline vertinimas (RQ1–RQ4)

```bash
anomaly-detector/evaluation/fetch_datasets.sh russellmitchell   # AIT-LDS poaibis
docker compose --profile eval run --rm evaluator ingest ait \
    --scenario-dir /datasets/ait/russellmitchell --dataset ait-russellmitchell
docker compose --profile eval run --rm evaluator run   --dataset ait-russellmitchell --run-id baseline
docker compose --profile eval run --rm evaluator score --dataset ait-russellmitchell --run-id baseline
```

Rezultatai (precision/recall/F1/FPR, ATT&CK aprėptis, LaTeX lentelės) — `eval-results/`.

### 4. Tikrinimas

- **Dashboard**: http://localhost:8080 (admin / `$DASHBOARD_ADMIN_PASSWORD`)
- **Grafana**: http://localhost:3000 (admin / `$GF_SECURITY_ADMIN_PASSWORD`)
- **Loki API**: http://localhost:3100/ready (tik vidinis)

## Anomalijų aptikimo metodai

### 1. Taisyklėmis pagrįstas (Rule-based)
- **SSH brute-force**: ≥5 nesėkmingų bandymų per 5 min iš to paties IP
- **Vartotojų skenavimas**: ≥3 skirtingi vartotojų vardai iš vieno IP
- **Firewall spike**: >50 DROP/REJECT įrašų per 5 min

### 2. Statistinis (Baseline deviation)
- **Log volume spike**: Z-score > 3.0 nuo istorinio vidurkio
- **Error rate**: Klaidų proporcija > 30%

### 3. ML (Isolation Forest)
- **Požymiai**: log kiekis, unikalios programos, error rate, unikalūs IP, vid. žinutės ilgis
- **Mokymasis**: automatinis baseline kūrimas iš pirmų 20+ stebėjimų
- **Contamination**: 5% (tikimasi kad ~5% duomenų yra anomalijos)

## Šaltinių konfigūracija

### Linux serveriai (rsyslog)
Pridėkite į `/etc/rsyslog.conf`:
```
*.* @@192.168.1.X:514    # TCP
# arba
*.* @192.168.1.X:514     # UDP
```

### MikroTik routeriai
```
/system logging action set remote=192.168.1.X remote-port=514 bsd-syslog=yes
/system logging add action=remote topics=firewall,error,warning,critical,info
```

### Windows / Linux stotys (Grafana Alloy agentas)
Galiniai įrenginiai siunčia Windows įvykių žurnalą (Security, Sysmon, PowerShell) arba
Linux auditd telemetriją per Grafana Alloy į šliuzą (`:3500`, HTTPS + kliento sertifikatas).
Sertifikatai generuojami `tools/gen-certs.sh`, paruošimas — `lab/windows/provision.ps1` ir
`lab/linux/config.alloy` (žr. `lab/README.md`). Pavyzdys (Windows):
```alloy
loki.source.windowsevent "security" { eventlog_name = "Security"  forward_to = [loki.process.win.receiver] }
loki.write "c" { endpoint { url = "https://192.168.1.X:3500/loki/api/v1/push"
  tls_config { ca_file = "ca.crt" cert_file = "client.crt" key_file = "client.key" } } }
```
TLS nepalaikantys tinklo įrenginiai (pvz. MikroTik) toliau siunčia per UDP/TCP 514.

## Dashboard (Web UI)

Papildoma žiniatinklio sąsaja šalia Grafana, pasiekiama per `http://localhost:8080`.

- **Technologijos**: FastAPI + Uvicorn (backend), Vanilla JS + Tailwind CSS + Chart.js (frontend)
- **Kalba**: Lietuvių / Anglų (perjungiama UI)
- **Prisijungimas**: admin / `$DASHBOARD_ADMIN_PASSWORD` (pirmas admin sukuriamas paleidus)
- **Autentifikacija**: scrypt slaptažodžių maišos (`/state/users.json`), HMAC parašu pasirašyti galiojantys tokenai, rolės admin/viewer, bandymų ribojimas; vartotojų valdymas — `python -m app.manage_users`
- **Funkcijos**: logų srauto stebėjimas, anomalijų peržiūra, įrenginių sąrašas ir žemėlapis, MITRE ATT&CK aprėpties skiltis, demonstracinės atakos, webhook pranešimai, paieška, sistemos būklė
- **Gyvi atnaujinimai**: Server-Sent Events (`/api/stream`) — pultas atsinaujina realiu laiku be perkrovimo

## Testavimas

```bash
# Anomaly detector testai (rule, statistical, ML feature extraction)
docker compose run --rm anomaly-detector pytest tests/ -v
```

## Failų struktūra

```
.
├── docker-compose.yml               # Pagrindinis Docker Compose
├── .env / .env.example              # Aplinkos kintamieji (.env gitignored)
├── docs/
│   └── ARCHITECTURE.md              # Architektūros aprašymas
├── config/
│   ├── syslog-ng/syslog-ng.conf    # Syslog-ng konfigūracija (+ conf.d/tls.conf.example)
│   ├── loki/loki.yml               # Loki konfigūracija
│   ├── loki/loki-eval.yml          # Vertinimo Loki (originalios laiko žymos)
│   ├── alloy/collector.alloy       # Alloy: syslog-ng failų skaitymas -> Loki
│   ├── alloy/gateway.alloy         # Alloy: endpoint šliuzas (:3500, mTLS)
│   └── grafana/                    # provisioning/ + dashboards/
├── anomaly-detector/
│   ├── Dockerfile                   # base + eval + runtime targets
│   ├── common.py                    # Alert, LokiClient, Selectors, konfigūracija
│   ├── detector.py                  # Engine: rule/stat/ML + endpoint sluoksniai
│   ├── windows_rules.py             # Windows Event Log / Sysmon taisyklės -> ATT&CK
│   ├── linux_rules.py               # Linux auditd taisyklės -> ATT&CK
│   ├── attack_catalog.py            # alert_type -> ATT&CK, aprėptis
│   ├── evaluation/                  # offline vertinimas (fetch/ingest/run/score/report)
│   └── tests/                       # rule/stat/ML/engine/windows/linux/eval testai
├── dashboard/
│   └── app/
│       ├── main.py, dependencies.py # FastAPI + DI (require_auth / require_admin)
│       ├── manage_users.py          # Vartotojų CLI
│       ├── log_selectors.py         # bendras {job=~"syslog|windows|linux_endpoint"}
│       ├── routers/                 # auth, traffic, alerts, health, devices, notifications, stream, attack
│       ├── services/                # loki_client, alert_reader, health_checker, device_registry, device_monitor, syslog_emitter, notifier, host_info, user_store, attack_coverage
│       ├── models/schemas.py        # Pydantic modeliai
│       └── static/                  # index.html, login.html, css/, js/, fonts/
├── lab/                             # VM stendo scenarijai (Windows/Linux/Kali) + ground truth
├── tools/                           # gen-certs.sh, parity_check.py, measure_resources.sh
├── demo_data/anomaly_history.json   # Demo alertų duomenys
├── seed_demo.sh                     # Demo duomenų įkėlimo skriptas
├── CLAUDE.md                        # Agent kontekstas
└── README.md
```

## Resursų poreikis

Mažai organizacijai (10-50 įrenginių):
- **RAM**: ~2 GB (Loki ~512MB, Grafana ~256MB, kiti ~256MB)
- **CPU**: 2 vCPU
- **Diskas**: 10-50 GB (priklausomai nuo retencijos)
- **Tinklas**: Vidinis LAN prieiga prie visų šaltinių

## Licencija

Akademinis darbas. Naudojamos technologijos yra open-source (Apache 2.0 / AGPLv3).
