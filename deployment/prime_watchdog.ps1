# Supervisor for the loopback-only Melody Prime gateway. Run by Task Scheduler.
# Restarts Prime if it exits OR if /healthz stops answering (hung but listening).
# Only Prime is affected: the game never waits on it (5s timeout, built-in-guide fallback).
$ErrorActionPreference = 'Continue'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner  = Join-Path $PSScriptRoot 'start_melody_prime.ps1'
$logDir  = Join-Path $repoDir 'logs'
$health  = 'http://127.0.0.1:8765/healthz'
$ps      = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$wlog = Join-Path $logDir 'melody-prime-watchdog.log'
function Log($m) {
    Add-Content -LiteralPath $wlog -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m)
    if ((Get-Item -LiteralPath $wlog).Length -gt 500KB) {
        Move-Item -LiteralPath $wlog -Destination ($wlog + '.old') -Force
    }
}
function Test-Prime {
    try {
        $r = Invoke-RestMethod -Uri $health -TimeoutSec 5
        return [bool]$r.ok
    } catch { return $false }
}

$delay = 5
while ($true) {
    $started = Get-Date
    $proc = Start-Process -FilePath $ps -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$runner`"")
    Log "started Prime runner pid=$($proc.Id)"
    Start-Sleep -Seconds 20          # boot grace: key decrypt + bind
    $fails = 0
    while (-not $proc.HasExited) {
        if (Test-Prime) { $fails = 0 } else { $fails++ }
        if ($fails -ge 3) {
            Log 'healthz failed 3x in a row - restarting Prime'
            # kill the runner and its python child only (tree), never by name
            & taskkill.exe /PID $proc.Id /T /F | Out-Null
            break
        }
        Start-Sleep -Seconds 30
    }
    if ($proc.HasExited) { Log "Prime exited code=$($proc.ExitCode)" }
    if (((Get-Date) - $started).TotalMinutes -ge 10) { $delay = 5 }
    Start-Sleep -Seconds $delay
    $delay = [Math]::Min(60, $delay * 2)
}
