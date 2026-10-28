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

### 3a. Realus biuras (gamybinis režimas)

```bash
./setup-collector.sh 192.168.1.10   # fiksuotas kolektoriaus IP (DHCP rezervacija)
```

Vienas žingsnis: `.env` su atsitiktiniais slaptažodžiais (jei jų dar nėra), sertifikatai,
TLS 6514, Windows/Linux diegimo paketai ir paleidimas gamybiniu režimu
(`docker-compose.prod.yml`: be sintetinio srauto ir demonstracinių įrenginių, detektorius
kas 60 s, be Grafana/Alloy telemetrijos, profiliai `anomaly` ir `endpoints`). Skriptas į `.env`
įrašo `COMPOSE_FILE` ir `COMPOSE_PROFILES`, todėl vėlesnės `docker compose` komandos naudoja tuos
pačius nustatymus. Kartoti saugu. Grįžti į demonstracinį režimą: ištrinkite šias dvi eilutes iš
`.env` ir paleiskite `docker compose up -d`. Įrenginiai — žr. „Galinių įrenginių prijungimas".

Gamybiniu režimu dashboard ir Grafana veikia per HTTPS su kolektoriaus sertifikatu
(`https://192.168.1.10:8080`, `https://192.168.1.10:3000`). Kad naršyklė nerodytų įspėjimo,
administratorių kompiuteriuose įdiekite `certs/ca.crt` kaip patikimą šakninę CA.

### 3b. Offline vertinimas (RQ1–RQ4)

```bash
anomaly-detector/evaluation/fetch_datasets.sh russellmitchell   # AIT-LDS poaibis
docker compose --profile eval run --rm evaluator ingest ait \
    --scenario-dir /datasets/ait/russellmitchell --dataset ait-russellmitchell
docker compose --profile eval run --rm evaluator run   --dataset ait-russellmitchell --run-id baseline
docker compose --profile eval run --rm evaluator score --dataset ait-russellmitchell --run-id baseline

# Windows ATT&CK korpusas (OTRF, 107 įrašai, ~55 MB): per-technique aptikimas (RQ2)
WINDOWS=1 anomaly-detector/evaluation/fetch_datasets.sh
docker compose --profile eval run --rm evaluator ingest otrf --scenario-dir /datasets/otrf --dataset otrf-windows
docker compose --profile eval run --rm evaluator run   --dataset otrf-windows --run-id rules
docker compose --profile eval run --rm evaluator score --dataset otrf-windows --run-id rules
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

### Windows / Linux kompiuteriai
Windows siunčia įvykių žurnalą (Security, Sysmon, PowerShell) per Grafana Alloy agentą į
šliuzą (`:3500`, HTTPS + kliento sertifikatas), Linux — rsyslog ir auditd įrašus per TLS 6514.
Abu diegiami vienu paketu — žr. „Galinių įrenginių prijungimas". TLS nepalaikantys tinklo
įrenginiai (pvz. MikroTik) toliau siunčia per UDP/TCP 514.

## Galinių įrenginių prijungimas (onboarding)

Windows kompiuteriai gauna vieną diegimo paketą (Sysmon + Grafana Alloy agentas, siunčia į
šliuzą `:3500` per mTLS). Visi kompiuteriai naudoja tą patį „fleet" kliento sertifikatą, o
šliuzas priima tik sertifikatus iš savo sąrašo (`certs/server/clients.pem`). Linux kompiuteriai
lieka be agento: rsyslog ir auditd syslog įskiepis siunčia į syslog-ng per TLS 6514
(`job="syslog"`, todėl veikia ir SSH taisyklės). Linux pakete nėra jokios paslapties, tik CA.

### Vieną kartą serveryje

Visus šiuos veiksmus (ir gamybinį režimą) atlieka `./setup-collector.sh 192.168.1.10`
(žr. „Paleidimas", 3a). Rankiniu būdu:

```bash
tools/gen-certs.sh ca
tools/gen-certs.sh server 192.168.1.10        # fiksuotas kolektoriaus IP (DHCP rezervacija)
cp config/syslog-ng/conf.d/tls.conf.example config/syslog-ng/conf.d/tls.conf   # TLS 6514 Linux/macOS
tools/gen-certs.sh bundle 192.168.1.10        # certs/bundles/kursinis-windows.zip ir kursinis-linux.tar.gz
docker compose --profile anomaly --profile endpoints up -d
docker compose restart syslog-ng alloy-gateway   # jei stack'as jau veikė (up -d failų pakeitimų nemato)
```

`bundle` išveda `bundle-id` (jo reikia Intune aptikimo taisyklei). Sertifikatai paimami iš
`certs/` (gitignored), konteineriai mato tik `certs/server/` (be CA rakto). Paketams reikia
interneto tik pirmą kartą: Alloy (tikrinamas pagal leidimo `SHA256SUMS`), Sysmon ir
SwiftOnSecurity konfigūracija saugomi `certs/bundles/cache/`. Norėdami atnaujinti Sysmon,
ištrinkite `cache/Sysmon.zip`.

### Kiekviename kompiuteryje

```powershell
# Windows, administratoriaus PowerShell, išarchyvavus kursinis-windows.zip
cd kursinis-windows
powershell -ExecutionPolicy Bypass -File install.ps1               # -NoSysmon: be Sysmon
powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall    # -KeepSysmon: Sysmon palikti
```
```bash
# Linux (Debian/Ubuntu, RHEL/Fedora)
tar xzf kursinis-linux.tar.gz && cd kursinis-linux && sudo ./setup.sh
```

Pakartotinis paleidimas yra ir atnaujinimas (nauja versija, adresas ar sertifikatas). Jei
kolektorius nepasiekiamas, skriptai tik įspėja: Windows agentas bando iš naujo, kol pristato,
o rsyslog kaupia žurnalus diske (iki 1 GB). Po kelių minučių kompiuteris atsiranda dashboard
žemėlapyje savaime: Windows su `{job="windows", host="<kompiuterio vardas>"}`, Linux su
`{job="syslog", host="<hostname>"}`. Windows diegimo žurnalas yra
`C:\Windows\Temp\kursinis-install.log`.

### Atšaukimas ir rotacija

- Atskiras sertifikatas nešiojamam ar asmeniniam kompiuteriui:
  `tools/gen-certs.sh bundle 192.168.1.10 laptop-07` → `certs/bundles/laptop-07/kursinis-windows.zip`.
  Vardai turi būti neutralūs: šliuzas visų sąraše esančių sertifikatų CN parodo kiekvienam,
  kas jungiasi prie `:3500`.
- Atšaukimas: `tools/gen-certs.sh revoke laptop-07 && docker compose restart alloy-gateway`
  (sąrašas perskaitomas tik paleidžiant šliuzą, `/-/reload` nepadeda). `revoke fleet`
  atjungia visus bendrą sertifikatą naudojančius kompiuterius.
- Fleet sertifikato keitimas (nutekėjo arba baigiasi 825 d. galiojimas):
  `bundle 192.168.1.10 fleet-2` → `restart alloy-gateway` (seną ir naują šliuzas priima kartu)
  → išplatinti naują paketą (pasikeitęs `bundle-id` priverčia Intune jį įdiegti iš naujo)
  → `revoke fleet` → `restart alloy-gateway`.
- Atšauktas agentas pats klaidos nerodo (bando be galo). Signalas yra šliuzo žurnale:
  `docker compose logs alloy-gateway | grep "TLS handshake error"` su kompiuterio IP ir
  `certificate signed by unknown authority`.

### Masinis diegimas

- **GPO:** išarchyvuotą `kursinis-windows` aplanką įdėkite į tik administratoriams rašomą
  bendrinamą aplanką (pvz. `\\server\kursinis$`; skaityti gali tik `Domain Computers`, nes jame
  yra `client.key`). Computer Configuration → Policies → Windows Settings → Scripts → Startup:
  programa `powershell.exe`, parametrai
  `-NoProfile -ExecutionPolicy Bypass -File \\server\kursinis$\kursinis-windows\install.ps1`.
  Vykdoma kaip SYSTEM kiekvieno paleidimo metu (pakartoti saugu).
- **Intune:** Win32 programa iš aplanko (`IntuneWinAppUtil -c kursinis-windows -s install.ps1 -o out`).
  Diegimas `powershell.exe -NoProfile -ExecutionPolicy Bypass -File install.ps1`, šalinimas
  `... -File install.ps1 -Uninstall`, vykdyti kaip System. Intune paleidžia 32 bitų PowerShell,
  `install.ps1` pats persijungia į 64 bitų. Aptikimas pasirinktiniu skriptu:
  `if ((Get-Content "$env:ProgramData\Kursinis\bundle-id" -ErrorAction SilentlyContinue) -eq "<bundle-id>") { "OK" }`.
  Pakeitus paketą, atnaujinkite `bundle-id` taisyklėje ir Intune įdiegs naują versiją.
- **Ansible:**
  ```yaml
  - ansible.windows.win_copy: { src: certs/bundles/kursinis-windows.zip, dest: C:\Windows\Temp\ }
  - ansible.windows.win_shell: |
      Expand-Archive C:\Windows\Temp\kursinis-windows.zip C:\Windows\Temp -Force
      powershell -NoProfile -ExecutionPolicy Bypass -File C:\Windows\Temp\kursinis-windows\install.ps1
  - ansible.builtin.unarchive: { src: certs/bundles/kursinis-linux.tar.gz, dest: /tmp }
  - ansible.builtin.shell: /tmp/kursinis-linux/setup.sh
    become: true
  ```

### Eksploatacija

- Kolektoriui skirkite fiksuotą IP (DHCP rezervaciją): adresas įrašytas serverio sertifikate ir
  paketuose. Pasikeitus adresui: `server <naujas IP>`, `bundle <naujas IP>` ir paketus išplatinti iš naujo.
- Prievadus 3500 (Windows agentai), 6514 (Linux/macOS TLS) ir 514 (tinklo įrenginiai)
  atidarykite tik biuro LAN potinkliams. Linux eilutės, kaip ir visas syslog, neautentifikuotos.
- Paketo niekada neplatinkite per dashboard (paprastas HTTP) ar kitą HTTP šaltinį: Windows
  pakete yra kliento privatusis raktas. Naudokite USB, administratorių bendrinamą aplanką,
  Intune arba Ansible.

## Dashboard (Web UI)

Papildoma žiniatinklio sąsaja šalia Grafana, pasiekiama per `http://localhost:8080`.

- **Technologijos**: FastAPI + Uvicorn (backend), JS moduliai be surinkimo žingsnio + Tailwind CSS + Chart.js (frontend)
- **Išvaizda**: Grafana stiliaus skydeliai; tamsi tema pagal nutylėjimą, šviesią galima įjungti viršutinėje juostoje (pasirinkimas įsimenamas naršyklėje)
- **Kalba**: Lietuvių / Anglų (perjungiama UI)
- **Prisijungimas**: admin / `$DASHBOARD_ADMIN_PASSWORD` (pirmas admin sukuriamas paleidus)
- **Autentifikacija**: scrypt slaptažodžių maišos (`/state/users.json`), HMAC parašu pasirašyti galiojantys tokenai, rolės admin/viewer, bandymų ribojimas; vartotojų valdymas — `python -m app.manage_users`
- **Funkcijos**: logų srauto stebėjimas, anomalijų peržiūra, įrenginių sąrašas ir žemėlapis, MITRE ATT&CK aprėpties skiltis, demonstracinės atakos, webhook pranešimai, paieška, sistemos būklė
- **Gyvi atnaujinimai**: Server-Sent Events (`/api/stream`) — pultas atsinaujina realiu laiku be perkrovimo
- **Atnaujinus iš senesnės versijos**: naršyklėje, kurioje buvo atidarytas senasis pultas, vieną kartą paspauskite Ctrl+Shift+R; vėlesni atnaujinimai įkeliami savaime

## Testavimas

```bash
# Anomaly detector testai (rule, statistical, ML feature extraction)
docker compose run --rm anomaly-detector pytest tests/ -v
```

## Failų struktūra

```
.
├── docker-compose.yml               # Pagrindinis Docker Compose
├── docker-compose.prod.yml          # Gamybinio režimo nustatymai (setup-collector.sh)
├── .env / .env.example              # Aplinkos kintamieji (.env gitignored)
├── setup-collector.sh               # Kolektoriaus paruošimas realiam biurui vienu žingsniu
├── onboarding/                      # windows/install.ps1 + config.alloy, linux/setup.sh
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
├── tools/                           # gen-certs.sh (CA, paketai, revoke), parity_check.py, measure_resources.sh
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
