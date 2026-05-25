# Centralizuota žurnalų analizės ir anomalijų aptikimo sistema

Kursinis darbas mažoms organizacijoms skirta centralizuota log analizės ir anomalijų aptikimo sistema.

## Architektūra

```
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Linux serveriai │  │ Tinklo įrenginiai │  │ Windows stotys   │
│  (rsyslog)       │  │ (MikroTik, Ubiq.) │  │ (NXLog)          │
└────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
         │ TCP 514            │ UDP 514              │ TCP 1514
         └────────────────────┼──────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │    syslog-ng     │  ← Centrinis kolektorius
                    │  (priima, rašo)  │
                    └────────┬────────┘
                             │ failų sistema
                             ▼
                    ┌─────────────────┐
                    │    Promtail      │  ← Skaito failus, siunčia į Loki
                    │  (parsina, labels)│
                    └────────┬────────┘
                             │ HTTP push
                             ▼
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
| Kolektorius       | syslog-ng 4.8     | Syslog priėmimas iš viso tinklo       |
| Log siuntėjas     | Promtail 3.4      | Logų persiuntimas iš failų į Loki     |
| Saugykla          | Grafana Loki 3.4  | Efektyvi logų saugykla (label-based)  |
| Vizualizacija     | Grafana 11.5      | Dashboard'ai, alertai, log naršymas   |
| Anomalijų apt.    | Python 3.12       | Rule-based, statistinis, ML (IsoForest)|
| Dashboard         | FastAPI + JS      | Web UI: logų srautas, anomalijos, paieška |
| Konteinerizacija  | Docker Compose    | Vienodas deployment bet kurioje aplinkoje |

## Paleidimas

### 1. Aplinkos kintamieji

```bash
cp .env.example .env
# Pakeiskite GF_SECURITY_ADMIN_PASSWORD reikšmę
```

### 2. Bazinis stackas (be testinių logų)

```bash
docker compose up -d
```

### 3. Su testinių logų generatoriumi

```bash
docker compose --profile dev up -d
```

### 4. Su anomalijų aptikimu

```bash
docker compose --profile anomaly up -d
```

### 5. Viskas kartu (demo režimas)

```bash
docker compose --profile dev --profile anomaly up -d
./seed_demo.sh   # įkelia demo alertus į dashboard'ą
```

### 6. Tikrinimas

- **Dashboard**: http://localhost:8080 (admin / admin123)
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

### Windows (NXLog)
Atsisiųskite NXLog CE ir konfigūruokite:
```xml
<Output out>
    Module  om_udp
    Host    192.168.1.X
    Port    514
</Output>
```

## Dashboard (Web UI)

Papildoma žiniatinklio sąsaja šalia Grafana, pasiekiama per `http://localhost:8080`.

- **Technologijos**: FastAPI + Uvicorn (backend), Vanilla JS + Tailwind CSS + Chart.js (frontend)
- **Kalba**: Lietuvių / Anglų (perjungiama UI)
- **Prisijungimas**: admin / admin123
- **Autentifikacija**: Bearer token (sha256 hash) — taikomas visiems `/api/{traffic,alerts,health}` maršrutams
- **Funkcijos**: logų srauto stebėjimas, anomalijų peržiūra, įrenginių sąrašas, paieška, sistemos būklė

## Testavimas

```bash
# Dashboard testai (30 testų: alert_reader, routes, auth)
docker compose run --rm dashboard pytest tests/ -v

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
│   ├── syslog-ng/syslog-ng.conf    # Syslog-ng konfigūracija
│   ├── loki/loki.yml               # Loki konfigūracija
│   ├── promtail/promtail.yml       # Promtail konfigūracija
│   └── grafana/
│       ├── provisioning/            # Auto-konfigūracija
│       │   ├── datasources/loki.yml
│       │   ├── dashboards/dashboards.yml
│       │   └── alerting/alerts.yml
│       └── dashboards/overview.json # Dashboard JSON
├── anomaly-detector/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── detector.py                  # Anomalijų aptikimo modulis (3 sluoksniai)
│   └── tests/                       # Rule / Statistical / ML testai
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                  # FastAPI aplikacija
│   │   ├── dependencies.py          # DI + require_auth
│   │   ├── routers/                 # auth, traffic, alerts, health
│   │   ├── services/                # loki_client, alert_reader, health_checker
│   │   ├── models/schemas.py        # Pydantic modeliai
│   │   └── static/                  # index.html, login.html, css/, js/, fonts/
│   └── tests/                       # Pytest testai (route + auth + alert_reader)
├── demo_data/
│   └── anomaly_history.json         # Demo alertų duomenys
├── log-generator/
│   ├── Dockerfile
│   └── generator.py                 # Testinių logų generatorius
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
