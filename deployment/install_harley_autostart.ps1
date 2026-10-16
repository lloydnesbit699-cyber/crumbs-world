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
$deployTaskName = 'Crumbs World Verified Deploy'
$sentinelTaskName = 'Crumbs World Ops Sentinel'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$watchdog = Join-Path $PSScriptRoot 'harley_watchdog.ps1'
$deployScript = Join-Path $PSScriptRoot 'harley_verified_deploy.ps1'
$sentinelScript = Join-Path $PSScriptRoot 'crumbs_ops_sentinel.ps1'

if ($Status) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Output 'Harley autostart task is not installed.'; exit 1 }
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
    $deployTask = Get-ScheduledTask -TaskName $deployTaskName -ErrorAction SilentlyContinue
    if ($deployTask) {
        Get-ScheduledTaskInfo -TaskName $deployTaskName | Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
    } else {
        Write-Output 'Verified deploy watcher is not installed yet.'
    }
    $sentinelTask = Get-ScheduledTask -TaskName $sentinelTaskName -ErrorAction SilentlyContinue
    if ($sentinelTask) {
        Get-ScheduledTaskInfo -TaskName $sentinelTaskName | Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
    } else {
        Write-Output 'Operations sentinel is not installed yet.'
    }
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8778 -State Listen -ErrorAction SilentlyContinue |
        Select-Object LocalAddress,LocalPort,OwningProcess
    exit 0
}

if (-not (Test-Path -LiteralPath $watchdog -PathType Leaf)) {
    throw "Watchdog script not found: $watchdog"
}
if (-not (Test-Path -LiteralPath $deployScript -PathType Leaf)) {
    throw "Verified deploy watcher not found: $deployScript"
}
if (-not (Test-Path -LiteralPath $sentinelScript -PathType Leaf)) {
    throw "Operations sentinel not found: $sentinelScript"
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
        # OneDrive Files On-Demand marks cloud-managed files/directories as
        # reparse points too. Allow only the documented Cloud Files tag family
        # (0x9000001A..0x9000F01A); continue refusing symlinks/junctions and
        # unknown tags so ACL changes cannot be redirected elsewhere.
        $fsutil = Join-Path $env:SystemRoot 'System32\fsutil.exe'
        $reparseInfo = (& $fsutil reparsepoint query $privatePath 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            throw "Could not verify the reparse tag for profile data: $privatePath"
        }
        $tagMatch = [regex]::Match($reparseInfo, '0x[0-9A-Fa-f]{8}')
        if (-not $tagMatch.Success -or $tagMatch.Value -notmatch '^0x9000[0-9A-Fa-f]01[Aa]$') {
            throw "Refusing an unsupported reparse point in profile data: $privatePath"
        }
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
$deployPrincipal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Keeps the authenticated Harley authority available through the existing Tailscale Funnel; server binds only to loopback.'
try {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $taskName -ErrorAction Stop

    $deployAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$deployScript`"" `
        -WorkingDirectory $repoDir
    # Use the signed-in user's interactive token. This supports passwordless
    # Microsoft accounts and avoids storing a Windows password in Task Scheduler.
    # The server itself remains an at-startup S4U task; deployments begin at logon.
    $deployTrigger = New-ScheduledTaskTrigger -AtLogOn -User $account
    $deploySettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $deployTask = New-ScheduledTask -Action $deployAction -Trigger $deployTrigger `
        -Principal $deployPrincipal -Settings $deploySettings `
        -Description 'Polls GitHub main and deploys only commits with a successful repo-verify check; rolls back if local health verification fails.'
    Register-ScheduledTask -TaskName $deployTaskName -InputObject $deployTask `
        -Force -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $deployTaskName -ErrorAction Stop

    $sentinelAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$sentinelScript`" -Watch" `
        -WorkingDirectory $repoDir
    $sentinelTrigger = New-ScheduledTaskTrigger -AtLogOn -User $account
    $sentinelSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $sentinelTask = New-ScheduledTask -Action $sentinelAction -Trigger $sentinelTrigger `
        -Principal $deployPrincipal -Settings $sentinelSettings `
        -Description 'Audits Harley boot, dependencies, credentials presence, recovery, Tailscale, Funnel, tasks, and repository integrity; logs state changes without printing secrets.'
    Register-ScheduledTask -TaskName $sentinelTaskName -InputObject $sentinelTask `
        -Force -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $sentinelTaskName -ErrorAction Stop
} catch {
    throw "Could not register/start the scheduled task. Run this installer in an elevated PowerShell session as $account (do not use a different account); the server task remains an at-startup task and the deploy watcher runs at sign-in. $($_.Exception.Message)"
}
Write-Output "Installed and started '$taskName' as $account (limited privilege, system startup)."
Write-Output "Installed and started '$deployTaskName' as $account (limited privilege, starts at sign-in; no password stored)."
Write-Output "Installed and started '$sentinelTaskName' as $account (limited privilege, starts at sign-in; redacted diagnostic monitor)."
Write-Output 'The app listens on 127.0.0.1:8778; Tailscale Funnel remains the only public entry point.'
if (-not $env:CRUMBS_SHARE_KEY) {
    Write-Warning 'Verified deployments are paused until CRUMBS_SHARE_KEY is set for this Windows account and the tasks are restarted.'
}
