<#
.SYNOPSIS
  Install, inspect, or stop the always-on Harley server task.
.DESCRIPTION
  Registers a limited-privilege, at-startup Task Scheduler job for the
  loopback-only --funnel server. Tailscale Funnel remains the public front door.
#>
[CmdletBinding()]
param(
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$taskName = 'Crumbs World Harley Server'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$watchdog = Join-Path $PSScriptRoot 'harley_watchdog.ps1'

if ($Status) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Output 'Harley autostart task is not installed.'; exit 1 }
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8778 -State Listen -ErrorAction SilentlyContinue |
        Select-Object LocalAddress,LocalPort,OwningProcess
    exit 0
}

if (-not (Test-Path -LiteralPath $watchdog -PathType Leaf)) {
    throw "Watchdog script not found: $watchdog"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.venv\Scripts\python.exe') -PathType Leaf)) {
    throw 'Project .venv is missing. Run boots\crumbs-boot.ps1 once to prepare it.'
}

$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$vaultsDir = Join-Path $repoDir 'vaults'
if (-not (Test-Path -LiteralPath $vaultsDir)) {
    New-Item -ItemType Directory -Path $vaultsDir -Force | Out-Null
}
$privatePaths = @(
    (Join-Path $repoDir 'users.json'),
    (Join-Path $repoDir 'users.json.tmp'),
    (Join-Path $repoDir '.crumbs_secret'),
    $vaultsDir
)
$privatePaths += @(Get-ChildItem -LiteralPath $repoDir -Filter 'users.json.*.bak' `
    -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
foreach ($privatePath in $privatePaths) {
    if (-not (Test-Path -LiteralPath $privatePath)) { continue }
    $attributes = [System.IO.File]::GetAttributes($privatePath)
    if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to apply profile ACLs through a reparse point: $privatePath"
    }
    $aclArgs = @($privatePath, '/inheritance:r', '/grant:r',
        "${account}:F", '*S-1-5-18:F', '*S-1-5-32-544:F')
    if (($attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
        $aclArgs += @('/T', '/C')
    }
    & "$env:SystemRoot\System32\icacls.exe" @aclArgs | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict persistent profile permissions: $privatePath"
    }
}

$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watchdog`"" `
    -WorkingDirectory $repoDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Keeps the authenticated Harley authority available through the existing Tailscale Funnel; server binds only to loopback.'
try {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
} catch {
    throw "Could not register/start the system-startup task. Run this installer once as Administrator; the server itself will still run as $account with limited privilege. $($_.Exception.Message)"
}
Write-Output "Installed and started '$taskName' as $account (limited privilege, system startup)."
Write-Output 'The app listens on 127.0.0.1:8778; Tailscale Funnel remains the only public entry point.'
