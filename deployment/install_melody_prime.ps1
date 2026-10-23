<#
.SYNOPSIS
  Install or inspect the separate, loopback-only Melody Prime gateway task.
#>
[CmdletBinding()]
param([switch]$Status)

$ErrorActionPreference = 'Stop'
$taskName = 'Crumbs World Melody Prime'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $PSScriptRoot 'prime_watchdog.ps1'   # supervises start_melody_prime.ps1
$python = Join-Path $repoDir '.venv\Scripts\python.exe'
$proxy = Join-Path $repoDir 'tools\melody_prime_proxy.py'
$secretFile = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets\groq-api-key.dpapi'

if ($Status) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Output 'Melody Prime task is not installed.'; exit 1 }
    Get-ScheduledTaskInfo -TaskName $taskName |
        Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 3 |
        Select-Object ok,configured,provider,model } catch { Write-Output 'Prime proxy is not listening on 127.0.0.1:8765.' }
    exit 0
}

foreach ($path in @($runner,$python,$proxy,$secretFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Prime setup file is missing: $path"
    }
}
$token = [Environment]::GetEnvironmentVariable('MELODY_PROXY_TOKEN','User')
if ([string]::IsNullOrWhiteSpace($token)) { throw 'MELODY_PROXY_TOKEN is not configured for this Windows user.' }
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repoDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Separate loopback-only Groq gateway for Melody; the game uses only a bearer token.'
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
Write-Output "Installed and started '$taskName' for $account (interactive logon, limited privilege)."
Write-Output "Prime listens only on 127.0.0.1:8765; the Groq key is read from this user's DPAPI-protected secret file."
