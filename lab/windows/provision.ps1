<#
.SYNOPSIS
  Paruošia Windows 11 laboratorijos darbo vietą endpoint telemetrijai ir atakų testams.

.DESCRIPTION
  1. Surenka tokį pat paketą kaip tools/gen-certs.sh bundle (sertifikatai iš -CertDir,
     Alloy v1.20.1 su SHA256 patikra, Sysmon, pinned SwiftOnSecurity konfigūracija) ir paleidžia
     onboarding/windows/install.ps1: Sysmon (pilna arba -Trim konfigūracija), audito politika,
     PowerShell Script Block Logging (4104), Grafana Alloy agentas (Security/Sysmon/PowerShell
     kanalai į kolektorių per mTLS)
  2. Invoke-AtomicRedTeam (ATT&CK technikų vykdymas su laiko žymėmis)

  Paleisti kaip administratorius iš repozitorijos lab\windows aplanko (šalia turi būti ir
  onboarding\windows). Sertifikatai (tools/gen-certs.sh client <vardas>): ca.crt, client.crt,
  client.key kataloge -CertDir.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File provision.ps1 -Collector 192.168.122.1 -CertDir C:\kursinis-certs -Trim
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Collector,
    [int]$Port = 3500,
    [string]$CertDir = "C:\kursinis-certs",
    [string]$SysmonConfigUrl = "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/1836897f12fbd6a0a473665ef6abc34a6b497e31/sysmonconfig-export.xml",
    [switch]$Trim   # RQ4: apkarpyta Sysmon konfigūracija (mažesnė įrašų apimtis)
)
$ErrorActionPreference = "Stop"
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Paleiskite kaip administratorius."
}
$work = Join-Path $env:TEMP "kursinis-lab"
$bundle = Join-Path $work "kursinis-windows"
$src = Join-Path $PSScriptRoot "..\..\onboarding\windows"
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

Write-Host "[1/3] Diegimo paketas ($bundle)..." -ForegroundColor Cyan
foreach ($f in "ca.crt", "client.crt", "client.key") {
    if (-not (Test-Path (Join-Path $CertDir $f))) {
        throw "Nerastas $CertDir\$f. Sukurkite su tools/gen-certs.sh client <vardas> ir nukopijuokite."
    }
    Copy-Item (Join-Path $CertDir $f) $bundle -Force
}
Copy-Item (Join-Path $src "install.ps1") $bundle -Force
$cfg = (Get-Content (Join-Path $src "config.alloy") -Raw -Encoding UTF8).Replace("COLLECTOR:3500", "${Collector}:$Port")
[IO.File]::WriteAllText((Join-Path $bundle "config.alloy"), $cfg)   # UTF-8 be BOM
$rel = "https://github.com/grafana/alloy/releases/download/v1.20.1"
$zip = Join-Path $work "alloy-installer-windows-amd64.exe.zip"
Invoke-WebRequest "$rel/alloy-installer-windows-amd64.exe.zip" -OutFile $zip -UseBasicParsing
Invoke-WebRequest "$rel/SHA256SUMS" -OutFile (Join-Path $work "SHA256SUMS") -UseBasicParsing
$want = (Select-String -Path (Join-Path $work "SHA256SUMS") -Pattern " alloy-installer-windows-amd64\.exe\.zip$").Line.Split(" ")[0]
if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $want) { throw "Alloy diegimo programos SHA256 nesutampa su $rel/SHA256SUMS" }
Expand-Archive $zip -DestinationPath $bundle -Force
Invoke-WebRequest "https://download.sysinternals.com/files/Sysmon.zip" -OutFile (Join-Path $bundle "Sysmon.zip") -UseBasicParsing
Invoke-WebRequest $SysmonConfigUrl -OutFile (Join-Path $bundle "sysmonconfig.xml") -UseBasicParsing
Get-ChildItem $bundle -File | Where-Object Name -NotIn "SHA256SUMS", "bundle-id" | Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } |
    Set-Content (Join-Path $bundle "SHA256SUMS") -Encoding ASCII
Set-Content (Join-Path $bundle "bundle-id") "lab-$((Get-FileHash (Join-Path $bundle "SHA256SUMS")).Hash.Substring(0, 12).ToLower())" -Encoding ASCII

Write-Host "[2/3] install.ps1: Sysmon, audito politika, Alloy..." -ForegroundColor Cyan
$installArgs = @{}
if ($Trim) {
    # Apkarpyta: tik proceso kūrimas (1), tinklo jungtys (3) ir failų kūrimas (11).
    $installArgs.SysmonConfig = Join-Path $work "sysmonconfig-trim.xml"
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
"@ | Set-Content -Encoding UTF8 $installArgs.SysmonConfig
}
& (Join-Path $bundle "install.ps1") @installArgs

Write-Host "[3/3] Invoke-AtomicRedTeam..." -ForegroundColor Cyan
Install-Module -Name powershell-yaml -Scope AllUsers -Force -ErrorAction SilentlyContinue
IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing)
Install-AtomicRedTeam -getAtomics -Force

Write-Host "`nParuošta. Kolektorius: ${Collector}:${Port}. Atakas vykdykite su run-atomics.ps1." -ForegroundColor Green
