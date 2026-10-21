<#
.SYNOPSIS
    Read-only operations sentinel for the persistent Harley server.
.DESCRIPTION
    Audits boot files, scheduled tasks, Python dependencies, recovery state,
    credential presence (never values), Tailscale/Funnel, repository identity,
    and local health. -Watch repeats checks and logs only state changes.
#>
[CmdletBinding()]
param(
    [switch]$Watch,
    [ValidateRange(15, 3600)][int]$IntervalSeconds = 60
)

$ErrorActionPreference = 'Continue'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $repoDir 'logs'
$logPath = Join-Path $logDir 'crumbs-ops-sentinel.log'
$taskNames = @('Crumbs World Harley Server', 'Crumbs World Melody Prime',
    'Crumbs World Verified Deploy', 'Crumbs World Ops Sentinel')
$requiredFiles = @(
    'crumbs_hud.py', 'crumbs_recovery.py', 'requirements.txt',
    'boots\crumbs-boot.ps1', 'deployment\harley_watchdog.ps1',
    'deployment\harley_verified_deploy.ps1', 'deployment\install_harley_autostart.ps1',
    'deployment\crumbs_ops_sentinel.ps1', 'deployment\configure_account_recovery.ps1',
    'deployment\configure_melody_prime.ps1', 'deployment\install_melody_prime.ps1',
    'deployment\start_melody_prime.ps1', 'tools\melody_prime_proxy.py',
    'tools\boot_preflight.py'
)

function Add-Check([System.Collections.Generic.List[object]]$Items,
                   [string]$Name, [string]$State, [string]$Detail) {
    $Items.Add([pscustomobject]@{ Name = $Name; State = $State; Detail = $Detail })
}

function Get-OpsSnapshot {
    $items = New-Object 'System.Collections.Generic.List[object]'
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $accountLeaf = ($account -split '\\')[-1]
    foreach ($relative in $requiredFiles) {
        $path = Join-Path $repoDir $relative
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Add-Check $items "File: $relative" 'PASS' 'present'
        } else {
            Add-Check $items "File: $relative" 'FAIL' 'missing'
        }
    }

    $python = Join-Path $repoDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        $pipOutput = & $python -m pip check 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { Add-Check $items 'Python dependencies' 'PASS' 'pip check clean' }
        else { Add-Check $items 'Python dependencies' 'FAIL' (($pipOutput.Trim() -replace '[\r\n]+',' ') -replace '\s{2,}',' ') }
        $moduleOutput = & $python -c "import PIL, crumbs_core, crumbs_recovery, melody_agent" 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { Add-Check $items 'Runtime imports' 'PASS' 'Pillow, game core, recovery, and Melody import successfully' }
        else { Add-Check $items 'Runtime imports' 'FAIL' (($moduleOutput.Trim() -replace '[\r\n]+',' ') -replace '\s{2,}',' ') }
    } else {
        Add-Check $items 'Python dependencies' 'FAIL' '.venv\Scripts\python.exe missing; run boots\crumbs-boot.ps1'
    }
    $keyfinder = Join-Path $repoDir 'tools\melody_keyfinder.py'
    $brainMode = [Environment]::GetEnvironmentVariable('MELODY_BRAIN', 'User')
    if (-not $brainMode) { $brainMode = [Environment]::GetEnvironmentVariable('MELODY_BRAIN', 'Process') }
    if (Test-Path -LiteralPath $keyfinder -PathType Leaf) {
        Add-Check $items 'Melody keyfinder helper' 'PASS' 'owner key loader file is present (key value hidden)'
    } elseif ($brainMode -eq 'proxy') {
        Add-Check $items 'Melody keyfinder helper' 'PASS' 'not required; the separate Prime process owns the Groq credential'
    } else {
        Add-Check $items 'Melody keyfinder helper' 'WARN' 'optional owner key loader is missing; Melody must use environment or another configured backend'
    }
    $brainMode = [Environment]::GetEnvironmentVariable('MELODY_BRAIN', 'User')
    if (-not $brainMode) { $brainMode = [Environment]::GetEnvironmentVariable('MELODY_BRAIN', 'Process') }
    if (-not $brainMode) { $brainMode = 'groq' }
    $brainReady = $false
    $brainMissing = @()
    switch ($brainMode.ToLowerInvariant()) {
        'off' { $brainReady = $true }
        'proxy' {
            foreach ($name in @('MELODY_PROXY_URL','MELODY_PROXY_TOKEN')) {
                $value = [Environment]::GetEnvironmentVariable($name, 'User')
                if (-not $value) { $value = [Environment]::GetEnvironmentVariable($name, 'Process') }
                if ([string]::IsNullOrWhiteSpace($value)) { $brainMissing += $name }
            }
            $brainReady = $brainMissing.Count -eq 0
        }
        'gemini' {
            $brainReady = -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User')) -or
                -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'Process'))
            if (-not $brainReady) { $brainMissing += 'GEMINI_API_KEY' }
        }
        'ollama' {
            $base = [Environment]::GetEnvironmentVariable('MELODY_BRAIN_BASE', 'User')
            if (-not $base) { $base = [Environment]::GetEnvironmentVariable('MELODY_BRAIN_BASE', 'Process') }
            if (-not $base) { $base = 'http://127.0.0.1:11434/v1' }
            try { $brainReady = Test-NetConnection -ComputerName ([Uri]$base).DnsSafeHost -Port ([Uri]$base).Port -InformationLevel Quiet -WarningAction SilentlyContinue }
            catch { $brainReady = $false }
            if (-not $brainReady) { $brainMissing += 'local model endpoint' }
        }
        default {
            $brainReady = -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'User')) -or
                -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'Process'))
            if (-not $brainReady -and (Test-Path -LiteralPath (Join-Path $repoDir 'tools\melody_keyfinder.py') -PathType Leaf)) {
                $brainReady = $true
            }
            if (-not $brainReady) { $brainMissing += 'GROQ_API_KEY' }
        }
    }
    if (-not $brainReady) {
        Add-Check $items 'Melody backend configuration' 'WARN' ("mode=$brainMode; missing or unreachable: " + ($brainMissing -join ', '))
    } else {
        Add-Check $items 'Melody backend configuration' 'PASS' "mode=$brainMode; required settings present (values hidden)"
    }
    $directGroqKey = [Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'User')
    if (-not $directGroqKey) { $directGroqKey = [Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'Process') }
    if ($directGroqKey) {
        Add-Check $items 'Game credential isolation' 'WARN' 'GROQ_API_KEY is present in the game account environment; Prime mode should keep it in its DPAPI-protected secret file'
    } else {
        Add-Check $items 'Game credential isolation' 'PASS' 'game environment has no direct Groq API key'
    }

    foreach ($name in $taskNames) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if (-not $task) {
            if ($name -eq 'Crumbs World Ops Sentinel') {
                Add-Check $items "Task: $name" 'WARN' 'not installed yet; rerun install_harley_autostart.ps1 after this update reaches Harley'
            } elseif ($name -eq 'Crumbs World Melody Prime') {
                $primeSecret = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets\groq-api-key.dpapi'
                if (Test-Path -LiteralPath $primeSecret -PathType Leaf) {
                    Add-Check $items "Task: $name" 'FAIL' 'Groq key is provisioned but the separate Prime task is not installed'
                } else {
                    Add-Check $items "Task: $name" 'WARN' 'not configured yet; run configure_melody_prime.ps1 with the Groq key'
                }
            } else { Add-Check $items "Task: $name" 'FAIL' 'not registered' }
            continue
        }
        $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
        $resultNote = switch ([long]$info.LastTaskResult) {
            0 { 'success' }
            267009 { '0x00041301 means task is currently running' }
            3221225786 { '0xC000013A means interrupted/control-C exit' }
            default { 'unclassified result code' }
        }
        $detail = "state=$($task.State); lastRun=$($info.LastRunTime); result=$($info.LastTaskResult) ($resultNote)"
        $taskAccount = [string]$task.Principal.UserId
        $taskAccountLeaf = ($taskAccount -split '\\')[-1]
        if ($taskAccount -and $taskAccount -ne ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value) -and
            -not [string]::Equals($taskAccount, $account, [StringComparison]::OrdinalIgnoreCase) -and
            -not [string]::Equals($taskAccountLeaf, $accountLeaf, [StringComparison]::OrdinalIgnoreCase)) {
            Add-Check $items "Task owner: $name" 'WARN' ("runs as $($task.Principal.UserId), sentinel runs as $account")
        }
        if ([string]$task.State -eq 'Running') {
            Add-Check $items "Task: $name" 'PASS' $detail
        } elseif ($info.LastTaskResult -eq 3221225786) {
            Add-Check $items "Task: $name" 'WARN' $detail
        } else {
            Add-Check $items "Task: $name" 'WARN' $detail
        }
    }

    $primeHealth = $null
    try { $primeHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 3 -ErrorAction Stop }
    catch { }
    if ($primeHealth -and $primeHealth.ok -and $primeHealth.configured) {
        Add-Check $items 'Melody Prime proxy' 'PASS' ("separate loopback service healthy; provider=$($primeHealth.provider); model=$($primeHealth.model)")
    } else {
        $primeSecret = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets\groq-api-key.dpapi'
        if (Test-Path -LiteralPath $primeSecret -PathType Leaf) {
            Add-Check $items 'Melody Prime proxy' 'FAIL' 'Groq key file exists, but Prime is not healthy on 127.0.0.1:8765'
        } else {
            Add-Check $items 'Melody Prime proxy' 'WARN' 'not configured; the game chat will use knowledge-only answers until Prime is set up'
        }
    }

    $shareKey = [Environment]::GetEnvironmentVariable('CRUMBS_SHARE_KEY', 'User')
    if ([string]::IsNullOrWhiteSpace($shareKey)) { $shareKey = $env:CRUMBS_SHARE_KEY }
    if ([string]::IsNullOrWhiteSpace($shareKey)) {
        Add-Check $items 'Deploy restart key' 'FAIL' 'CRUMBS_SHARE_KEY missing; verified deploy cannot request a safe restart'
    } else { Add-Check $items 'Deploy restart key' 'PASS' 'configured (value hidden)' }

    $emailRequired = @('CRUMBS_RECOVERY_SMTP_HOST', 'CRUMBS_RECOVERY_SMTP_FROM')
    $emailMissing = @($emailRequired | Where-Object {
        [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, 'User')) -and
        [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, 'Process'))
    })
    if ($emailMissing.Count -eq 0) { Add-Check $items 'Email account recovery' 'PASS' 'SMTP host and sender configured (values hidden)' }
    else { Add-Check $items 'Email account recovery' 'WARN' ('not configured; missing ' + ($emailMissing -join ', ')) }
    $smtpUser = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_USER', 'User')
    $smtpPass = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_PASSWORD', 'User')
    if ([string]::IsNullOrWhiteSpace($smtpUser)) { $smtpUser = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_USER', 'Process') }
    if ([string]::IsNullOrWhiteSpace($smtpPass)) { $smtpPass = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_PASSWORD', 'Process') }
    if (([bool]$smtpUser) -ne ([bool]$smtpPass)) {
        Add-Check $items 'SMTP authentication pair' 'FAIL' 'username and password must both be set, or both be blank'
    } elseif ($emailMissing.Count -eq 0) {
        Add-Check $items 'SMTP authentication pair' 'PASS' 'authentication settings are paired (values hidden)'
    }
    $smtpPortText = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_PORT', 'User')
    if (-not $smtpPortText) { $smtpPortText = [Environment]::GetEnvironmentVariable('CRUMBS_RECOVERY_SMTP_PORT', 'Process') }
    if ($smtpPortText) {
        $smtpPort = 0
        if (-not [int]::TryParse($smtpPortText, [ref]$smtpPort) -or $smtpPort -lt 1 -or $smtpPort -gt 65535) {
            Add-Check $items 'SMTP port' 'FAIL' 'must be an integer from 1 through 65535'
        } else { Add-Check $items 'SMTP port' 'PASS' "valid port $smtpPort" }
    }

    $smsRequired = @('CRUMBS_RECOVERY_TWILIO_ACCOUNT_SID', 'CRUMBS_RECOVERY_TWILIO_KEY_SID',
        'CRUMBS_RECOVERY_TWILIO_KEY_SECRET', 'CRUMBS_RECOVERY_TWILIO_FROM')
    $smsMissing = @($smsRequired | Where-Object {
        [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, 'User')) -and
        [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, 'Process'))
    })
    if ($smsMissing.Count -eq 0) { Add-Check $items 'SMS account recovery' 'PASS' 'Twilio settings configured (values hidden)' }
    else { Add-Check $items 'SMS account recovery' 'WARN' ('not configured; missing ' + ($smsMissing -join ', ')) }

    $health = $null
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8778/api/health' -TimeoutSec 3 } catch { }
    if ($health -and $health.ok) { Add-Check $items 'Local server health' 'PASS' "version=$($health.version)" }
    else { Add-Check $items 'Local server health' 'FAIL' 'no valid response from 127.0.0.1:8778/api/health' }

    $logsPath = Join-Path $repoDir 'logs'
    if (-not (Test-Path -LiteralPath $logsPath -PathType Container)) {
        Add-Check $items 'Operational logs' 'FAIL' 'logs directory is missing'
    } else {
        Add-Check $items 'Operational logs' 'PASS' 'logs directory is present'
        $recentErrors = @(Get-ChildItem -LiteralPath $logsPath -Filter 'harley-server-*.err.log' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 10)
        $signatures = @{}
        foreach ($logFile in $recentErrors) {
            $signals = @(Get-Content -LiteralPath $logFile.FullName -Tail 400 -ErrorAction SilentlyContinue |
                Where-Object { $_ -match '^([A-Za-z_]+(Error|Exception)):' -or $_ -match '\b(FATAL|ERROR)\b' })
            foreach ($signal in $signals) { $signatures[$signal.Trim()] = $true }
        }
        $runtimeErrorPath = Join-Path $logsPath 'runtime-errors.jsonl'
        $runtimeRows = @()
        if (Test-Path -LiteralPath $runtimeErrorPath -PathType Leaf) {
            foreach ($line in (Get-Content -LiteralPath $runtimeErrorPath -Tail 100 -ErrorAction SilentlyContinue)) {
                try { $runtimeRows += ($line | ConvertFrom-Json -ErrorAction Stop) } catch { }
            }
        }
        if ($runtimeRows.Count -gt 0) {
            $latest = @($runtimeRows | Select-Object -Last 5 | ForEach-Object {
                "$($_.id) v$($_.version) $($_.code) at $($_.location): $($_.fix)"
            }) -join ' | '
            Add-Check $items 'Recent server request errors' 'WARN' "$($runtimeRows.Count) persisted error(s); $latest"
        } elseif ($signatures.Count -eq 0) {
            Add-Check $items 'Recent server errors' 'PASS' 'no distinct fatal/error signatures in the 10 newest stderr logs'
        } else {
            $examples = @($signatures.Keys | Select-Object -First 5) -join '; '
            Add-Check $items 'Recent server errors' 'WARN' "$($signatures.Count) distinct error signature(s) in the 10 newest stderr logs: $examples; inspect matching logs for source location"
        }
    }

    $usersFile = Join-Path $repoDir 'users.json'
    if (Test-Path -LiteralPath $usersFile -PathType Leaf) {
        try {
            $null = Get-Content -LiteralPath $usersFile -Raw | ConvertFrom-Json -ErrorAction Stop
            Add-Check $items 'Persistent user records' 'PASS' 'users.json parses; account contents are not shown'
        } catch { Add-Check $items 'Persistent user records' 'FAIL' 'users.json is not valid JSON; preserve it and inspect backups before repair' }
    } else { Add-Check $items 'Persistent user records' 'WARN' 'users.json is not present in this checkout' }

    $recoveryReport = Join-Path $repoDir '.crumbs_recovery\last_report.json'
    if (Test-Path -LiteralPath $recoveryReport -PathType Leaf) {
        try {
            $report = Get-Content -LiteralPath $recoveryReport -Raw | ConvertFrom-Json
            $finding = [string]$report.checkpoint.finding
            $risk = [string]$report.risk.level
            if ($finding -eq 'PASS' -and $report.primary.state -eq 'healthy') {
                Add-Check $items 'Persistent recovery state' 'PASS' "checkpoint=$finding; risk=$risk; action=$($report.action)"
            } else { Add-Check $items 'Persistent recovery state' 'WARN' "checkpoint=$finding; risk=$risk; action=$($report.action)" }
        } catch { Add-Check $items 'Persistent recovery state' 'WARN' 'last recovery report is unreadable' }
    } else { Add-Check $items 'Persistent recovery state' 'WARN' 'no startup recovery report found yet' }

    $tailExe = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if (-not $tailExe) {
        $candidate = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
        if (Test-Path -LiteralPath $candidate) { $tailExe = Get-Item -LiteralPath $candidate }
    }
    if (-not $tailExe) {
        Add-Check $items 'Tailscale' 'FAIL' 'tailscale.exe not found'
        Add-Check $items 'Tailscale Funnel' 'WARN' 'cannot inspect Funnel without tailscale.exe'
    } else {
        $exePath = if ($tailExe.Source) { $tailExe.Source } else { $tailExe.FullName }
        $svc = Get-Service -Name Tailscale -ErrorAction SilentlyContinue
        $statusJson = & $exePath status --json 2>$null | Out-String
        $backend = 'unknown'
        try { $backend = [string](($statusJson | ConvertFrom-Json).BackendState) } catch { }
        if ($svc -and $svc.Status -eq 'Running' -and $backend -eq 'Running') {
            Add-Check $items 'Tailscale' 'PASS' 'service and backend are Running'
        } else { Add-Check $items 'Tailscale' 'FAIL' "service=$($svc.Status); backend=$backend" }
        $funnel = (& $exePath funnel status 2>&1 | Out-String).Trim()
        if ($funnel -match '8778|crumbs|https://') { Add-Check $items 'Tailscale Funnel' 'PASS' 'Funnel configuration found (details omitted)' }
        elseif ($funnel -match 'no serve config|no funnel') { Add-Check $items 'Tailscale Funnel' 'FAIL' 'no Funnel configuration reported' }
        else { Add-Check $items 'Tailscale Funnel' 'WARN' 'Funnel status is ambiguous; inspect tailscale funnel status' }
    }

    $origin = & git -C $repoDir remote get-url origin 2>$null | Out-String
    if ($origin -match 'lloydnesbit699-cyber/crumbs-world') { Add-Check $items 'Repository identity' 'PASS' 'origin matches expected project' }
    else { Add-Check $items 'Repository identity' 'FAIL' 'origin is missing or does not match expected project' }
    $branch = (& git -C $repoDir branch --show-current 2>$null | Out-String).Trim()
    if ($branch -eq 'main') { Add-Check $items 'Deployment branch' 'PASS' 'on main' }
    else { Add-Check $items 'Deployment branch' 'WARN' "on '$branch' (automatic deploy expects main)" }
    $trackedChanges = & git -C $repoDir status --porcelain --untracked-files=no 2>$null | Out-String
    if ([string]::IsNullOrWhiteSpace($trackedChanges)) { Add-Check $items 'Tracked repository files' 'PASS' 'no local tracked edits' }
    else { Add-Check $items 'Tracked repository files' 'WARN' 'local tracked edits found; verified deploy will refuse to update this checkout' }
    Add-Check $items 'Sentinel account' 'INFO' "running as $account; no credential values are read or printed"
    foreach ($privateName in @('users.json', '.crumbs_secret', 'vaults')) {
        $privatePath = Join-Path $repoDir $privateName
        if (-not (Test-Path -LiteralPath $privatePath)) {
            Add-Check $items "Private data: $privateName" 'WARN' 'not present in this checkout'
            continue
        }
        try {
            $acl = Get-Acl -LiteralPath $privatePath
            $broad = @($acl.Access | Where-Object {
                $_.AccessControlType -eq 'Allow' -and
                $_.IdentityReference.Value -match '(^|\\)(Users|Everyone|Authenticated Users)$'
            })
            if ($broad.Count -eq 0) { Add-Check $items "Private data ACL: $privateName" 'PASS' 'no broad Users/Everyone grant found' }
            else { Add-Check $items "Private data ACL: $privateName" 'FAIL' 'broad Users/Everyone access grant found' }
        } catch { Add-Check $items "Private data ACL: $privateName" 'WARN' 'could not inspect permissions' }
    }
    return $items
}

function Write-Snapshot($Items, [switch]$ToLog) {
    $bad = @($Items | Where-Object { $_.State -eq 'FAIL' }).Count
    $warn = @($Items | Where-Object { $_.State -eq 'WARN' }).Count
    $summary = "Ops sentinel: $bad failure(s), $warn warning(s), checked $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host $summary
    $Items | Format-Table State, Name, Detail -AutoSize -Wrap | Out-Host
    if ($ToLog) {
        if (-not (Test-Path -LiteralPath $logDir -PathType Container)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
        if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 2MB) { Move-Item -LiteralPath $logPath -Destination ($logPath + '.1') -Force }
        Add-Content -LiteralPath $logPath -Encoding UTF8 -Value $summary
        foreach ($item in $Items) { Add-Content -LiteralPath $logPath -Encoding UTF8 -Value ("{0} [{1}] {2}: {3}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $item.State, $item.Name, $item.Detail) }
    }
}

if (-not $Watch) {
    $snapshot = Get-OpsSnapshot
    Write-Snapshot $snapshot
    if (@($snapshot | Where-Object { $_.State -eq 'FAIL' }).Count -gt 0) { exit 1 }
    exit 0
}

Write-Host "Crumbs operations sentinel watching every $IntervalSeconds seconds. Stop with Ctrl+C."
$previous = @{}
while ($true) {
    $snapshot = Get-OpsSnapshot
    $current = @{}
    foreach ($item in $snapshot) { $current[$item.Name] = "$($item.State)|$($item.Detail)" }
    $changed = $false
    foreach ($item in $snapshot) {
        if ($previous[$item.Name] -ne $current[$item.Name]) { $changed = $true }
    }
    if ($changed) { Write-Snapshot $snapshot -ToLog }
    $previous = $current
    Start-Sleep -Seconds $IntervalSeconds
}
