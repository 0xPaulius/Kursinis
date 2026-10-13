<#
.SYNOPSIS
  Vykdo ATT&CK technikas per Invoke-AtomicRedTeam ir įrašo etaloninį žymėjimą (ground truth).

.DESCRIPTION
  Technikų sąrašas imamas iš -TechniqueFile (viena technika eilutėje, pvz. T1059.001)
  arba numatyto lab rinkinio. Kiekvienai technikai vykdomi visi jos testai su
  Attire JSON vykdymo žurnalu (laiko žymos = ground truth intervalai). Tarp testų —
  atsitiktinės pauzės, po kiekvieno — cleanup, kad VM liktų švari.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File run-atomics.ps1 -TechniqueFile techniques.txt -OutDir C:\lab-results
#>
[CmdletBinding()]
param(
    [string]$TechniqueFile,
    [string]$OutDir = "C:\lab-results",
    [int]$MinGapSeconds = 20,
    [int]$MaxGapSeconds = 90
)
$ErrorActionPreference = "Continue"
Import-Module Invoke-AtomicRedTeam -ErrorAction Stop
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Numatytas rinkinys (atitinka windows_rules.py + attack_catalog LAB_TECHNIQUE_SET padengtas).
$techniques = if ($TechniqueFile) { Get-Content $TechniqueFile | Where-Object { $_ -and $_ -notmatch '^\s*#' } }
else { @("T1110.001", "T1136.001", "T1098", "T1070.001", "T1059.001", "T1087.001", "T1033",
         "T1105", "T1547.001", "T1053.005", "T1003.001") }

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$ground = @()
$attireLog = Join-Path $OutDir "atomic-$runId.json"
$env:PSDefaultParameterValues = @{ "Invoke-AtomicTest:LoggingModule" = "Attire-ExecutionLogger";
                                   "Invoke-AtomicTest:ExecutionLogPath" = $attireLog }

foreach ($t in $techniques) {
    Write-Host "== $t ==" -ForegroundColor Cyan
    $start = (Get-Date).ToUniversalTime()
    try {
        Invoke-AtomicTest $t -GetPrereqs -ErrorAction SilentlyContinue | Out-Null
        Invoke-AtomicTest $t -ErrorAction Continue
    } catch { Write-Warning "$t klaida: $_" }
    $end = (Get-Date).ToUniversalTime()
    Invoke-AtomicTest $t -Cleanup -ErrorAction SilentlyContinue | Out-Null
    $ground += [pscustomobject]@{
        technique = $t
        start     = $start.ToString("o")
        end       = $end.ToString("o")
        host      = $env:COMPUTERNAME
    }
    Start-Sleep -Seconds (Get-Random -Minimum $MinGapSeconds -Maximum $MaxGapSeconds)
}

$gtPath = Join-Path $OutDir "ground_truth-$runId.json"
$ground | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $gtPath
Write-Host "`nGround truth: $gtPath" -ForegroundColor Green
Write-Host "Attire log:   $attireLog" -ForegroundColor Green
Write-Host "Perkelkite abu failus į kolektorių ir paleiskite lab/collect_ground_truth.py" -ForegroundColor Yellow
