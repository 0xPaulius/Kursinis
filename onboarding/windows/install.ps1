<#
.SYNOPSIS
  Prijungia Windows kompiuterį prie kolektoriaus: Sysmon, audito politika ir Grafana Alloy agentas.

.DESCRIPTION
  Paleidžiama kaip administratorius išarchyvuoto paketo (tools/gen-certs.sh bundle) aplanke:
    powershell -ExecutionPolicy Bypass -File install.ps1             # diegimas arba atnaujinimas
    powershell -ExecutionPolicy Bypass -File install.ps1 -NoSysmon   # be Sysmon
    powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall [-KeepSysmon]

  Kartoti saugu: tas pats paleidimas atnaujina agentą, konfigūraciją ir sertifikatus.
  Jei kolektorius nepasiekiamas, rodomas įspėjimas ir grąžinamas 0 (agentas jungsis vėliau pats).
  Žurnalas GPO / Intune paleidimams: C:\Windows\Temp\kursinis-install.log
#>
[CmdletBinding()]
param(
    [switch]$NoSysmon,
    [switch]$Uninstall,
    [switch]$KeepSysmon,
    [string]$SysmonConfig   # numatyta paketo sysmonconfig.xml; lab/windows/provision.ps1 -Trim perduoda kitą
)
$ErrorActionPreference = "Stop"

# Intune paleidžia 32 bitų PowerShell, kuriame $env:ProgramFiles rodo į „Program Files (x86)".
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
    $pass = foreach ($p in $PSBoundParameters.GetEnumerator()) {
        if ($p.Value -is [switch]) { if ($p.Value) { "-$($p.Key)" } } else { "-$($p.Key)"; $p.Value }
    }
    & "$env:WINDIR\SysNative\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @pass
    exit $LASTEXITCODE
}

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Paleiskite kaip administratorius."
}
Start-Transcript -Path "$env:WINDIR\Temp\kursinis-install.log" -Append | Out-Null

$dest = Join-Path $env:ProgramData "Kursinis"
$alloyDir = Join-Path $env:ProgramFiles "GrafanaLabs\Alloy"
$sysmonExe = Join-Path $env:WINDIR "Sysmon64.exe"

if ($Uninstall) {
    $uninstaller = Join-Path $alloyDir "uninstall.exe"
    if (Test-Path $uninstaller) {
        # _?= vykdo NSIS šalinimą vietoje ir jo sulaukia (kitaip uninstall.exe grįžta iškart).
        Start-Process -FilePath $uninstaller -ArgumentList "/S _?=$alloyDir" -Wait
        Remove-Item $alloyDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not $KeepSysmon -and (Test-Path $sysmonExe)) {
        & $sysmonExe -accepteula -u force
    }
    Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Pašalinta." -ForegroundColor Green
    exit 0
}

Write-Host "[1/5] Paketo vientisumas (SHA256SUMS)..." -ForegroundColor Cyan
Get-ChildItem $PSScriptRoot -File | Unblock-File
foreach ($line in Get-Content "$PSScriptRoot\SHA256SUMS") {
    $hash, $file = $line -split "\s+\*?", 2
    if ((Get-FileHash "$PSScriptRoot\$file" -Algorithm SHA256).Hash -ne $hash) {
        throw "Sugadintas paketo failas: $file (perkopijuokite paketą)"
    }
}

Write-Host "[2/5] Sertifikatai ir konfigūracija -> $dest..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $dest | Out-Null
# Tik SYSTEM (Alloy tarnyba) ir administratoriai: čia laikomas kliento raktas.
icacls $dest /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $dest" }
New-Item -ItemType Directory -Force -Path "$dest\certs" | Out-Null
Copy-Item "$PSScriptRoot\ca.crt", "$PSScriptRoot\client.crt", "$PSScriptRoot\client.key" "$dest\certs" -Force
Copy-Item "$PSScriptRoot\config.alloy" $dest -Force

Write-Host "[3/5] Audito politika ir PowerShell Script Block Logging (4104)..." -ForegroundColor Cyan
# ATT&CK ryšys: 4625 (T1110), 4720/4740 (T1136/T1110), 4732 (T1098), 1102 (T1070.001).
# Subkategorijos nurodytos GUID, nes jų pavadinimai lokalizuoti (lietuviškoje Windows kitokie).
$subcategories = @(
    "{0CCE9215-69AE-11D9-BED3-505054503030}"   # Logon
    "{0CCE9235-69AE-11D9-BED3-505054503030}"   # User Account Management
    "{0CCE9237-69AE-11D9-BED3-505054503030}"   # Security Group Management
    "{0CCE922F-69AE-11D9-BED3-505054503030}"   # Audit Policy Change
)
foreach ($sub in $subcategories) {
    auditpol /set /subcategory:$sub /success:enable /failure:enable | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "auditpol $sub" }
}
$sbl = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
if (-not (Test-Path $sbl)) { New-Item -Path $sbl -Force | Out-Null }
Set-ItemProperty -Path $sbl -Name EnableScriptBlockLogging -Value 1 -Type DWord

if ($NoSysmon) {
    Write-Host "[4/5] Sysmon praleistas (-NoSysmon)" -ForegroundColor Yellow
} else {
    Write-Host "[4/5] Sysmon..." -ForegroundColor Cyan
    if (-not $SysmonConfig) { $SysmonConfig = "$PSScriptRoot\sysmonconfig.xml" }
    $sysmonDir = Join-Path $env:TEMP "kursinis-sysmon"
    Expand-Archive "$PSScriptRoot\Sysmon.zip" -DestinationPath $sysmonDir -Force
    if (Get-Service Sysmon64 -ErrorAction SilentlyContinue) {
        & $sysmonExe -accepteula -c $SysmonConfig
    } else {
        & "$sysmonDir\Sysmon64.exe" -accepteula -i $SysmonConfig
    }
    if ($LASTEXITCODE -ne 0) { throw "Sysmon: kodas $LASTEXITCODE" }
}

Write-Host "[5/5] Grafana Alloy..." -ForegroundColor Cyan
# /FORCEREGISTRY: kitaip diegimo programa registre palieka ankstesnį konfigūracijos kelią.
$setup = Start-Process -FilePath "$PSScriptRoot\alloy-installer-windows-amd64.exe" -Wait -PassThru `
    -ArgumentList "/S /CONFIG=$dest\config.alloy /DISABLEREPORTING=yes /FORCEREGISTRY=yes"
if ($setup.ExitCode -ne 0) { throw "Alloy diegimas: kodas $($setup.ExitCode)" }
Restart-Service -Name Alloy
Copy-Item "$PSScriptRoot\bundle-id" $dest -Force

$url = [regex]::Match((Get-Content "$dest\config.alloy" -Raw), 'https://([^:/"]+):(\d+)')
$collector, $port = $url.Groups[1].Value, [int]$url.Groups[2].Value
$tcp = New-Object Net.Sockets.TcpClient
try { $reachable = $tcp.ConnectAsync($collector, $port).Wait(3000) } catch { $reachable = $false }
$tcp.Close()
if ($reachable) {
    Write-Host "Paruošta: agentas siunčia į ${collector}:$port (bundle-id $(Get-Content "$dest\bundle-id"))." -ForegroundColor Green
} else {
    Write-Warning "Kolektorius ${collector}:$port nepasiekiamas. Agentas įdiegtas ir prisijungs, kai kolektorius bus pasiekiamas."
}
exit 0
