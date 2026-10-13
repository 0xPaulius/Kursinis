<#
.SYNOPSIS
  Gerybinė darbo vietos veikla be atakų — klaidingai teigiamų (FPR) matavimui.

.DESCRIPTION
  Generuoja normalius procesus ir failų operacijas (Sysmon 1/11) bei teisėtus
  PowerShell scenarijus (4104), kad būtų galima matuoti FPR ataka-laisvame lange.
  Jokių žvalgybos komandų, LOLBin tinklo jungčių ar įtartinų scenarijų.
  Paleisti darbo vietoje LYGIAGREČIAI su 24–48 val. ataka-laisvu langu.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File benign.ps1 -DurationSeconds 3600
#>
[CmdletBinding()]
param(
    [int]$DurationSeconds = 3600,
    [int]$MinGapSeconds = 5,
    [int]$MaxGapSeconds = 20
)
$ErrorActionPreference = "Continue"
$work = Join-Path $env:TEMP "kursinis-benign"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$deadline = (Get-Date).AddSeconds($DurationSeconds)
Write-Host "[*] Gerybinė veikla iki $deadline" -ForegroundColor Cyan

# Teisėti kasdienės veiklos procesai (NE žvalgyba) — sukelia Sysmon Event ID 1.
$benignProcs = @(
    { Get-Date | Out-Null },
    { Get-ChildItem $env:USERPROFILE\Documents -ErrorAction SilentlyContinue | Out-Null },
    { Get-Content $env:SystemRoot\System32\drivers\etc\hosts | Out-Null },
    { Start-Process notepad -ArgumentList "/A" -WindowStyle Minimized; Start-Sleep 2;
      Get-Process notepad -ErrorAction SilentlyContinue | Stop-Process -ErrorAction SilentlyContinue }
)

while ((Get-Date) -lt $deadline) {
    # Procesas (Sysmon 1) — iš įprastų darbo komandų
    (Get-Random -InputObject $benignProcs).Invoke()

    # Failo operacija darbo aplanke (Sysmon 11) — NE Startup, tad taisyklė netriggerina
    $f = Join-Path $work ("doc-{0}.txt" -f (Get-Random))
    "benign content $(Get-Date -Format o)" | Set-Content -Path $f
    Remove-Item $f -ErrorAction SilentlyContinue

    # Teisėtas PowerShell scenarijus (4104) — be IEX/DownloadString/-enc
    & { $sum = 1..100 | Measure-Object -Sum; "Labas iš darbo vietos: $($sum.Sum)" } | Out-Null

    Start-Sleep -Seconds (Get-Random -Minimum $MinGapSeconds -Maximum $MaxGapSeconds)
}
Write-Host "[OK] Gerybinės veiklos langas baigtas." -ForegroundColor Green
