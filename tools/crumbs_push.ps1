[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Message,
    [string[]]$Include = @(),
    [string]$ReleaseNotes,
    [ValidateSet('patch', 'minor', 'major')]
    [string]$VersionBump = 'patch'
)

$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repoDir

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed ({0}): {1}" -f $Program, ($Arguments -join ' '))
    }
}

$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') {
    throw "Push helper only publishes main; current branch is '$branch'."
}

Invoke-Checked 'git' @('pull', '--ff-only', 'origin', 'main')
Invoke-Checked 'python' @('tools/repo_guard.py', '--fix')
if ($ReleaseNotes) {
    Invoke-Checked 'python' @('tools/repo_guard.py', '--release', '--bump', $VersionBump, '--notes', $ReleaseNotes)
}
Invoke-Checked 'python' @('tools/repo_guard.py', '--check')
Invoke-Checked 'python' @('-m', 'py_compile', 'crumbs_hud.py', 'crumbs_core.py', 'crumbs_recovery.py', 'melody_agent.py')
Invoke-Checked 'python' @('tools/repo_guard_test.py')
Invoke-Checked 'python' @('auth_test.py')
Invoke-Checked 'python' @('recovery_smoke_test.py')
Invoke-Checked 'python' @('core_smoke_test.py')

# Existing tracked edits are safe to stage together. New automation files are
# explicitly allowlisted; any other new file must be passed with -Include so
# runtime data and personal scripts cannot slip into a release by accident.
Invoke-Checked 'git' @('add', '-u')
$managedNewFiles = @(
    '.github/workflows/verify.yml',
    'tools/repo_guard.py',
    'tools/repo_guard_test.py',
    'tools/crumbs_push.ps1',
    'deployment/harley_verified_deploy.ps1'
)
$newManagedFiles = @()
foreach ($path in $managedNewFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoDir $path) -PathType Leaf)) { continue }
    # A missing pathspec makes git ls-files --error-unmatch write to stderr.
    # PowerShell 7 can promote that native stderr stream to a terminating
    # error, so query the cached index without using an error-producing mode.
    $trackedEntry = @(& git ls-files --cached -- $path)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect Git index for '$path'."
    }
    if ($trackedEntry.Count -eq 0) { $newManagedFiles += $path }
}
$toAdd = @($newManagedFiles) + @($Include)
if ($toAdd.Count -gt 0) { Invoke-Checked 'git' (@('add', '--') + $toAdd) }
Invoke-Checked 'python' @('tools/repo_guard.py', '--check')
Invoke-Checked 'git' @('diff', '--cached', '--check')
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { throw 'There are no staged changes to commit.' }
if ($LASTEXITCODE -gt 1) { throw 'Could not inspect the staged changes.' }
Invoke-Checked 'git' @('status', '--short')
Invoke-Checked 'git' @('commit', '-m', $Message)
Invoke-Checked 'git' @('push', 'origin', 'main')
Write-Output 'Push complete. GitHub Actions will verify the commit; Harley deploys only after repo-verify succeeds.'
