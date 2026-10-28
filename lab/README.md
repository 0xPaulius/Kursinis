# Laboratorijos stendas (RQ1–RQ4)

Kontroliuojamas virtualių mašinų stendas su realiomis atakomis ir žinomu etaloniniu
žymėjimu (ground truth). Papildo viešus rinkinius (AIT-LDS) realistiniais, pilnai
valdomais duomenimis. Nereikia keisti kolektoriaus: VM siunčia į tą patį Docker stack'ą.

## VM topologija (libvirt/QEMU, ~30 GB RAM host)

| VM | Paskirtis | RAM | Pastabos |
|----|-----------|-----|----------|
| `collector` | Docker stack (šis repo) | host | `docker compose --profile anomaly --profile endpoints up -d` |
| `win11-lab` | Windows 11 darbo vieta | 4 GB | Sysmon + Alloy agentas (Security/Sysmon/PowerShell) |
| `linux-target` | Linux serveris (taikinys) | 2 GB | sshd + rsyslog TLS + auditd (syslog įskiepis) |
| `kali` | Atakuotojas | 2 GB | hydra, nmap |

Tinklas: libvirt NAT (dažniausiai `192.168.122.0/24`), kolektorius pasiekiamas per
tilto adresą (`192.168.122.1`). Po paruošimo padarykite „clean" momentinę kopiją
(snapshot) kiekvienai VM, kad eksperimentus būtų galima kartoti.

## 1. Sertifikatai (mTLS endpoint'ams + TLS syslog)

```bash
tools/gen-certs.sh ca
tools/gen-certs.sh server 192.168.122.1      # kolektoriaus SAN
tools/gen-certs.sh client win11-lab          # -> certs/clients/win11-lab.{crt,key}, įtraukiamas į šliuzo sąrašą
cp config/syslog-ng/conf.d/tls.conf.example config/syslog-ng/conf.d/tls.conf
docker compose --profile anomaly --profile endpoints up -d
docker compose restart syslog-ng alloy-gateway   # jei stack'as jau veikė
```

Į `win11-lab` nukopijuokite `certs/ca.crt`, `certs/clients/win11-lab.crt` (-> `client.crt`)
ir `.key` (-> `client.key`) į `C:\kursinis-certs`, į `linux-target` — `certs/ca.crt`
(-> `/etc/ssl/certs/kursinis-ca.crt`). Į abi VM nukopijuokite repozitorijos `lab/` ir
`onboarding/` katalogus (kartu, kaip repozitorijoje): VM paruošimas naudoja tuos pačius
diegimo skriptus kaip realūs kompiuteriai (žr. pagrindinio README „Galinių įrenginių prijungimas").

## 2. VM paruošimas

```powershell
# win11-lab (administratorius): onboarding/windows/install.ps1 (Sysmon, audit, Alloy) + Atomic Red Team
powershell -ExecutionPolicy Bypass -File provision.ps1 -Collector 192.168.122.1 -CertDir C:\kursinis-certs
#   RQ4 apkarpytai Sysmon konfigūracijai: pridėkite -Trim
```

```bash
# linux-target (root): sshd + onboarding/linux/setup.sh (rsyslog TLS 6514 + auditd syslog įskiepis)
sudo COLLECTOR=192.168.122.1 CA_FILE=/etc/ssl/certs/kursinis-ca.crt ./linux/provision.sh
```

Patikra: `collector` dashboard (`:8080`) Įrenginių skiltyje turi atsirasti `win11-lab`
ir `linux-target`; Windows įrašai matomi su `{job="windows"}`, Linux auditd įrašai su
`{job="syslog", host="linux-target"} |= "type="`.

## 3. Sintetinio srauto išjungimas

Eksperimento metu dashboard demonstracinis srautas turi būti išjungtas, kad emiterio
šablonai neiškreiptų baseline'ų ir FPR:

```bash
SYNTHETIC_TRAFFIC=false docker compose up -d dashboard
```

## 4. Ataka-laisvas langas (FPR)

Paleiskite 24–48 val. tik gerybinės veiklos, kad išmatuotumėte klaidingai teigiamų dalį:

```powershell
powershell -ExecutionPolicy Bypass -File benign.ps1 -DurationSeconds 86400   # win11-lab
```
```bash
DURATION=86400 ./linux/benign.sh                                             # linux-target
```

## 5. Atakos su etaloniniu žymėjimu

```powershell
# win11-lab: ATT&CK technikos per Atomic Red Team (Attire laiko žymos = ground truth)
powershell -ExecutionPolicy Bypass -File run-atomics.ps1 -OutDir C:\lab-results
```
```bash
# kali: Linux atakos prieš taikinį
TARGET=192.168.122.50 ./kali/attacks.sh
```

Perkelkite `ground_truth-*.json` (Windows) ir `ground_truth.jsonl` (Kali) į kolektorių.

## 6. Etaloninio žymėjimo sujungimas ir vertinimas

```bash
# Vienas ground_truth.json iš visų šaltinių
python lab/collect_ground_truth.py ground_truth.json \
    lab-results/ground_truth-*.json kali/ground_truth.jsonl

# Eksportuoti gyvą langą -> loki-eval + meta.json (reikia --profile eval)
docker compose --profile eval up -d loki-eval
python lab/export_run.py --dataset lab-2022 --ground-truth ground_truth.json \
    --live-loki http://localhost:3100 --eval-loki http://localhost:3101

# Atkartojamas scoringas tuo pačiu Engine kaip gyvai
cd anomaly-detector
python -m evaluation --loki http://localhost:3101 --results ../eval-results \
    run   --dataset lab-2022 --run-id lab
python -m evaluation --results ../eval-results score  --dataset lab-2022 --run-id lab
python -m evaluation --results ../eval-results report --dataset lab-2022 --run-id lab
```

`score` pateikia precision/recall/F1/FPR kiekvienam sluoksniui, per-technika recall
(RQ2) ir alertų kiekius prieš/po cooldown.

## 7. Išteklių matavimas (RQ4)

```bash
# Be endpoint'ų
DURATION=1800 OUT=res-base.csv tools/measure_resources.sh
# Su Windows/Sysmon telemetrija (pilna, po to -Trim variantas)
DURATION=1800 OUT=res-sysmon-full.csv tools/measure_resources.sh
```

Palyginkite vidutinį RAM ir Loki srautų skaičių — parodo endpoint telemetrijos kainą
ir ar sistema telpa į <2 GB RAM tikslą.

## Failai

| Failas | Paskirtis |
|--------|-----------|
| `windows/provision.ps1` | Paketas iš `-CertDir` -> `onboarding/windows/install.ps1` (Sysmon, auditpol, Script Block Logging, Alloy mTLS) + Atomic Red Team |
| `../onboarding/windows/config.alloy` | Alloy agentas: Security/Sysmon/PowerShell -> gateway :3500 |
| `windows/run-atomics.ps1` | ATT&CK technikos + Attire ground truth |
| `windows/benign.ps1` | Gerybinė Windows veikla (FPR) |
| `linux/provision.sh` | sshd + `onboarding/linux/setup.sh` (rsyslog TLS 6514 + auditd) taikinyje |
| `linux/benign.sh` | Gerybinė Linux veikla (FPR) |
| `kali/attacks.sh` | hydra/nmap atakos + ground truth |
| `collect_ground_truth.py` | Sujungia ground truth failus |
| `export_run.py` | Gyvo lango eksportas -> loki-eval (atkartojamas scoringas) |
