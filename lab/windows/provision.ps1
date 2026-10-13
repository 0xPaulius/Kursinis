<#
.SYNOPSIS
  Paruošia Windows 11 laboratorijos darbo vietą endpoint telemetrijai ir atakų testams.

.DESCRIPTION
  1. Sysmon su pinned konfigūracija (pilna + apkarpyta RQ4 variantui)
  2. Audito politika: prisijungimo nesėkmės, paskyrų ir grupių valdymas
  3. PowerShell Script Block Logging (Event ID 4104)
  4. Grafana Alloy agentas (siunčia Security/Sysmon/PowerShell kanalus į kolektorių per mTLS)
  5. Invoke-AtomicRedTeam (ATT&CK technikų vykdymas su laiko žymėmis)

  Paleisti kaip administratorius. Parametrai nurodo kolektorių ir sertifikatų katalogą
  (sugeneruotą tools/gen-certs.sh: ca.crt + clients/<vardas>.crt/.key).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File provision.ps1 -Collector 192.168.122.1 -CertDir C:\kursinis-certs -Trim
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Collector,
    [int]$Port = 3500,
    [string]$CertDir = "C:\kursinis-certs",
    [string]$SysmonConfigUrl = "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml",
    [switch]$Trim   # RQ4: apkarpyta Sysmon konfigūracija (mažesnė įrašų apimtis)
)
$ErrorActionPreference = "Stop"
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Paleiskite kaip administratorius."
}
$work = Join-Path $env:TEMP "kursinis-lab"
New-Item -ItemType Directory -Force -Path $work | Out-Null

Write-Host "[1/5] Sysmon..." -ForegroundColor Cyan
$sysmonZip = Join-Path $work "Sysmon.zip"
Invoke-WebRequest "https://download.sysinternals.com/files/Sysmon.zip" -OutFile $sysmonZip
Expand-Archive $sysmonZip -DestinationPath (Join-Path $work "Sysmon") -Force
$sysmonCfg = Join-Path $work "sysmonconfig.xml"
if ($Trim) {
    # Apkarpyta: tik proceso kūrimas (1), tinklo jungtys (3) ir failų kūrimas (11).
    @"
<Sysmon schemaversion="4.90">
  <EventFiltering>
    <RuleGroup groupRelation="or"><ProcessCreate onmatch="include"/></RuleGroup>
    <RuleGroup groupRelation="or"><NetworkConnect onmatch="include"/></RuleGroup>
    <RuleGroup groupRelation="or"><FileCreate onmatch="include"/></RuleGroup>
    <ProcessTerminate onmatch="include"/>
    <ImageLoad onmatch="include"/>
  </EventFiltering>
</Sysmon>
"@ | Set-Content -Encoding UTF8 $sysmonCfg
} else {
    Invoke-WebRequest $SysmonConfigUrl -OutFile $sysmonCfg
}
& (Join-Path $work "Sysmon\Sysmon64.exe") -accepteula -i $sysmonCfg
& (Join-Path $work "Sysmon\Sysmon64.exe") -c $sysmonCfg   # perkrauna, jei jau įdiegtas

Write-Host "[2/5] Audito politika..." -ForegroundColor Cyan
# ATT&CK ryšys: 4625 (T1110), 4720/4740 (T1136/T1110), 4732 (T1098), 1102 (T1070.001)
auditpol /set /subcategory:"Logon" /success:enable /failure:enable | Out-Null
auditpol /set /subcategory:"User Account Management" /success:enable /failure:enable | Out-Null
auditpol /set /subcategory:"Security Group Management" /success:enable /failure:enable | Out-Null
auditpol /set /subcategory:"Audit Policy Change" /success:enable /failure:enable | Out-Null

Write-Host "[3/5] PowerShell Script Block Logging (4104)..." -ForegroundColor Cyan
$sbl = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
New-Item -Path $sbl -Force | Out-Null
Set-ItemProperty -Path $sbl -Name EnableScriptBlockLogging -Value 1 -Type DWord

Write-Host "[4/5] Grafana Alloy..." -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $CertDir "ca.crt"))) {
    throw "Nerasti sertifikatai $CertDir (ca.crt, client.crt, client.key). Sukurkite su tools/gen-certs.sh ir nukopijuokite."
}
$alloyMsi = Join-Path $work "alloy-installer.exe"
$rel = Invoke-RestMethod "https://api.github.com/repos/grafana/alloy/releases/tags/v1.20.1"
$asset = $rel.assets | Where-Object { $_.name -eq "alloy-installer-windows-amd64.exe.zip" } | Select-Object -First 1
Invoke-WebRequest $asset.browser_download_url -OutFile (Join-Path $work "alloy-installer.zip")
Expand-Archive (Join-Path $work "alloy-installer.zip") -DestinationPath (Join-Path $work "alloy") -Force
& (Get-ChildItem (Join-Path $work "alloy") -Filter *.exe | Select-Object -First 1).FullName /S
$alloyDir = "$env:ProgramFiles\GrafanaLabs\Alloy"
$cfg = (Get-Content (Join-Path $PSScriptRoot "config.alloy") -Raw).
    Replace("COLLECTOR", $Collector).Replace("3500", "$Port").
    Replace("C:\\kursinis-certs", $CertDir.Replace("\", "\\"))
Set-Content -Path (Join-Path $alloyDir "config.alloy") -Value $cfg -Encoding UTF8
Restart-Service -Name Alloy -ErrorAction SilentlyContinue

Write-Host "[5/5] Invoke-AtomicRedTeam..." -ForegroundColor Cyan
Install-Module -Name powershell-yaml -Scope AllUsers -Force -ErrorAction SilentlyContinue
IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing)
Install-AtomicRedTeam -getAtomics -Force

Write-Host "`nParuošta. Kolektorius: ${Collector}:${Port}. Atakas vykdykite su run-atomics.ps1." -ForegroundColor Green
