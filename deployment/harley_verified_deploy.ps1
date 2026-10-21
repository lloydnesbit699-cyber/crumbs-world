[CmdletBinding()]
param(
    [switch]$Once,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoSlug = 'lloydnesbit699-cyber/crumbs-world'
$branch = 'main'
$logDir = Join-Path $repoDir 'logs'
$logPath = Join-Path $logDir 'harley-deploy.log'
$failedPath = Join-Path $repoDir '.crumbs_deploy_failed'
$healthUri = 'http://127.0.0.1:8778/api/health'
$restartUri = 'http://127.0.0.1:8778/api/restart'
$mutex = New-Object System.Threading.Mutex($false, 'Local\CrumbsWorldVerifiedDeploy')

function Write-DeployLog([string]$Message) {
    if (-not (Test-Path -LiteralPath $logDir -PathType Container)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 2MB) {
        Move-Item -LiteralPath $logPath -Destination ($logPath + '.1') -Force
    }
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Output $line
}

function Invoke-Git([string[]]$GitArgs) {
    $output = & git -C $repoDir @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ('git {0} failed: {1}' -f ($GitArgs -join ' '), (($output | Out-String).Trim()))
    }
    return (($output | Out-String).Trim())
}

function Get-VerifiedCheck([string]$Commit) {
    $headers = @{
        Accept = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = '2022-11-28'
        'User-Agent' = 'Crumbs-World-Harley-Deploy'
    }
    if ($env:CRUMBS_GITHUB_TOKEN) {
        $headers.Authorization = 'Bearer ' + $env:CRUMBS_GITHUB_TOKEN
    }
    $uri = "https://api.github.com/repos/$repoSlug/commits/$Commit/check-runs?per_page=100"
    try {
        $result = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 15
    } catch {
        Write-DeployLog ("CI status unavailable for {0}: {1}" -f $Commit.Substring(0, 12), $_.Exception.Message) | Out-Null
        return $false
    }
    $checks = @($result.check_runs | Where-Object { $_.name -eq 'repo-verify' } |
        Sort-Object { [DateTime]$_.started_at } -Descending)
    if ($checks.Count -eq 0) {
        Write-DeployLog ("Waiting for repo-verify on {0}." -f $Commit.Substring(0, 12)) | Out-Null
        return $false
    }
    $latestCheck = $checks[0]
    if ($latestCheck.status -ne 'completed' -or $latestCheck.conclusion -ne 'success') {
        Write-DeployLog ("Not deploying {0}; repo-verify is {1}/{2}." -f
            $Commit.Substring(0, 12), $latestCheck.status, $latestCheck.conclusion) | Out-Null
        return $false
    }
    return $true
}

function Get-Health {
    try {
        return Invoke-RestMethod -Uri $healthUri -TimeoutSec 3
    } catch { return $null }
}

function Request-Restart {
    $headers = @{ 'X-Crumbs-Key' = $env:CRUMBS_SHARE_KEY }
    try {
        Invoke-RestMethod -Uri $restartUri -Method Post -Headers $headers `
            -ContentType 'application/json' -Body '{}' -TimeoutSec 15 | Out-Null
        return $true
    } catch {
        # The handler deliberately re-execs shortly after scheduling restart;
        # a dropped response is ambiguous until the new instance is healthy.
        Write-DeployLog ("Restart response was not confirmed: {0}" -f $_.Exception.Message) | Out-Null
        return $false
    }
}

function Wait-ForVersion([string]$Version, [string]$OldInstance, [int]$TimeoutSeconds = 75) {
    $until = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $until) {
        $health = Get-Health
        if ($health -and $health.ok -and $health.version -eq $Version -and
            $health.instance -and $health.instance -ne $OldInstance) {
            return $health
        }
        Start-Sleep -Seconds 2
    }
    return $null
}

function Invoke-DeployOnce {
    if (-not $env:CRUMBS_SHARE_KEY) {
        Write-DeployLog 'CRUMBS_SHARE_KEY is not configured for the deploy task; no repository changes made.'
        return
    }
    $status = Invoke-Git @('status', '--porcelain', '--untracked-files=no')
    if ($status) {
        Write-DeployLog 'Tracked Harley working-tree edits exist; refusing to pull or overwrite them.'
        return
    }
    $origin = Invoke-Git @('remote', 'get-url', 'origin')
    if ($origin -notmatch [regex]::Escape($repoSlug)) {
        Write-DeployLog ("Origin does not identify the expected repository; refusing deploy (origin: {0})." -f $origin)
        return
    }
    $localBranch = Invoke-Git @('branch', '--show-current')
    if ($localBranch -ne $branch) {
        Write-DeployLog ("Harley checkout is on '{0}', not '{1}'; refusing deploy." -f $localBranch, $branch)
        return
    }
    Invoke-Git @('fetch', '--quiet', 'origin', $branch) | Out-Null
    $target = Invoke-Git @('rev-parse', 'FETCH_HEAD')
    $current = Invoke-Git @('rev-parse', 'HEAD')
    if ($target -eq $current) {
        if ($Check) { Write-DeployLog "Harley is current at $($current.Substring(0, 12))." }
        return
    }
    if ((Test-Path -LiteralPath $failedPath) -and
        (Get-Content -LiteralPath $failedPath -Raw).Trim() -eq $target) {
        Write-DeployLog ("Commit {0} previously failed its live health check; held for manual review." -f $target.Substring(0, 12))
        return
    }
    if (-not (Get-VerifiedCheck $target)) { return }
    & git -C $repoDir merge-base --is-ancestor $current $target
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog 'Remote main is not a fast-forward from Harley HEAD; refusing deployment.'
        return
    }
    if ($Check) {
        Write-DeployLog ("Verified {0} is ready to deploy; check mode made no changes." -f $target.Substring(0, 12))
        return
    }

    $oldVersionMatch = [regex]::Match((Get-Content -LiteralPath (Join-Path $repoDir 'crumbs_hud.py') -Raw),
        '(?m)^APP_VERSION\s*=\s*"([^"]+)"')
    $oldVersion = if ($oldVersionMatch.Success) { $oldVersionMatch.Groups[1].Value } else { 'unknown' }
    $oldHealth = Get-Health
    if (-not $oldHealth -or -not $oldHealth.ok) {
        Write-DeployLog 'Current Harley server is unhealthy; refusing to deploy over an unverified base.'
        return
    }
    $oldInstance = [string]$oldHealth.instance
    $oldHead = $current
    Invoke-Git @('merge', '--ff-only', $target) | Out-Null
    $versionMatch = [regex]::Match((Get-Content -LiteralPath (Join-Path $repoDir 'crumbs_hud.py') -Raw),
        '(?m)^APP_VERSION\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) {
        Invoke-Git @('reset', '--hard', $oldHead) | Out-Null
        Set-Content -LiteralPath $failedPath -Value $target -Encoding ASCII
        throw 'Pulled commit has no readable APP_VERSION; rolled the checkout back.'
    }
    $newVersion = $versionMatch.Groups[1].Value
    Write-DeployLog ("Pulled verified commit {0} (v{1}); asking Harley to save and restart." -f
        $target.Substring(0, 12), $newVersion)
    $restartConfirmed = Request-Restart
    if (-not $restartConfirmed) {
        Write-DeployLog 'Checking for the new healthy instance before deciding whether to roll back.'
    }
    if (Wait-ForVersion $newVersion $oldInstance) {
        Set-Content -LiteralPath (Join-Path $repoDir '.crumbs_last_deployed') -Value $target -Encoding ASCII
        Remove-Item -LiteralPath $failedPath -Force -ErrorAction SilentlyContinue
        Write-DeployLog ("Deployment healthy: v{0}, commit {1}." -f $newVersion, $target.Substring(0, 12))
        return
    }

    Write-DeployLog ("Health check failed for v{0}; restoring commit {1}." -f $newVersion, $oldHead.Substring(0, 12))
    Invoke-Git @('reset', '--hard', $oldHead) | Out-Null
    Set-Content -LiteralPath $failedPath -Value $target -Encoding ASCII
    # If the new server is still answering, request a safe save/re-exec into
    # the restored tree. If it is down, the existing watchdog starts it there.
    $restoredHealth = Get-Health
    if ($restoredHealth -and $restoredHealth.ok) {
        [void](Request-Restart)
        $rollbackInstance = [string]$restoredHealth.instance
    } else {
        $rollbackInstance = ''
    }
    if (-not (Wait-ForVersion $oldVersion $rollbackInstance 90)) {
        Write-DeployLog 'Rollback is restored on disk; waiting for the watchdog to bring the prior version back healthy.'
        return
    }
    Write-DeployLog 'Automatic rollback completed; inspect Harley deploy logs and server logs.'
}

function Invoke-DeployGuarded {
    $locked = $false
    try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { return }
    try { Invoke-DeployOnce }
    catch { Write-DeployLog ("Deploy check failed safely: {0}" -f $_.Exception.Message) }
    finally { $mutex.ReleaseMutex() }
}

if ($Once -or $Check) {
    Invoke-DeployGuarded
} else {
    Write-DeployLog "Verified deploy watcher started for origin/$branch."
    while ($true) {
        Invoke-DeployGuarded
        Start-Sleep -Seconds 300
    }
}
