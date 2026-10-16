<#
.SYNOPSIS
  Securely configure the separate Melody Prime Groq gateway on Harley.
#>
[CmdletBinding()]
param([string]$Model = 'openai/gpt-oss-20b')

$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoDir '.venv\Scripts\python.exe'
$keyFinder = Join-Path $repoDir 'melody_keyfinder.py'
$proxy = Join-Path $repoDir 'tools\melody_prime_proxy.py'
$secretDir = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets'
$secretFile = Join-Path $secretDir 'groq-api-key.dpapi'
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
foreach ($path in @($python,$keyFinder,$proxy)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required Prime setup file is missing: $path" }
}

# Ask the existing finder for the key through a captured process pipe. The
# value is never printed to the terminal or sent to a log.
$keyPlain = (& $python -c "import melody_keyfinder,os,sys; sys.stdout.write(os.environ.get('GROQ_API_KEY',''))") -join ''
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($keyPlain)) {
    Remove-Variable keyPlain -ErrorAction SilentlyContinue
    throw 'melody_keyfinder.py did not find a usable key. Check its protected source file and configured search paths.'
}
$keySecure = ConvertTo-SecureString -String $keyPlain -AsPlainText -Force
Remove-Variable keyPlain

# Validate the key and selected model before changing persistent settings.
$keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($keySecure)
try {
    $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
    $env:MELODY_PRIME_MODEL = $Model
    & $python $proxy --check-upstream
    $verifyExit = $LASTEXITCODE
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
    Remove-Item Env:\GROQ_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\MELODY_PRIME_MODEL -ErrorAction SilentlyContinue
}
if ($verifyExit -ne 0) { throw 'Groq key/model verification failed; no Prime settings were changed.' }

New-Item -ItemType Directory -Path $secretDir -Force | Out-Null
$cipher = ConvertFrom-SecureString -SecureString $keySecure
$temp = "$secretFile.tmp"
[IO.File]::WriteAllText($temp, $cipher, [Text.Encoding]::UTF8)
Move-Item -LiteralPath $temp -Destination $secretFile -Force
$aclArgs = @($secretDir, '/inheritance:r', '/grant:r', "${account}:F", '*S-1-5-18:F', '*S-1-5-32-544:F')
& "$env:SystemRoot\System32\icacls.exe" @aclArgs | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the Prime secret directory permissions.' }
$aclArgs = @($secretFile, '/inheritance:r', '/grant:r', "${account}:F", '*S-1-5-18:F', '*S-1-5-32-544:F')
& "$env:SystemRoot\System32\icacls.exe" @aclArgs | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the Prime key file permissions.' }

$token = [Environment]::GetEnvironmentVariable('MELODY_PROXY_TOKEN','User')
if ([string]::IsNullOrWhiteSpace($token)) { $token = $env:MELODY_PROXY_TOKEN }
if ([string]::IsNullOrWhiteSpace($token)) {
    $random = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random) } finally { $rng.Dispose() }
    $token = [BitConverter]::ToString($random).Replace('-','').ToLowerInvariant()
}

$userSettings = @{
    MELODY_BRAIN = 'proxy'
    MELODY_PROXY_URL = 'http://127.0.0.1:8765/v1/chat/completions'
    MELODY_PROXY_TOKEN = $token
    MELODY_PROXY_MODEL = 'melody-prime'
    MELODY_PRIME_MODEL = $Model
}
foreach ($name in $userSettings.Keys) {
    [Environment]::SetEnvironmentVariable($name, $userSettings[$name], 'User')
    [Environment]::SetEnvironmentVariable($name, $userSettings[$name], 'Process')
}

$installer = Join-Path $PSScriptRoot 'install_melody_prime.ps1'
& $installer
$deadline = (Get-Date).AddSeconds(30)
$health = $null
while ((Get-Date) -lt $deadline) {
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/healthz' -TimeoutSec 2; break }
    catch { Start-Sleep -Milliseconds 500 }
}
if (-not $health -or -not $health.configured) {
    throw 'Prime did not become healthy. Check logs\melody-prime.log; the key value is not logged.'
}

# Point the game at the separate local Prime process and restart it to load the
# user-scoped endpoint/token. No Groq key is placed in the game environment.
$serverTask = Get-ScheduledTask -TaskName 'Crumbs World Harley Server' -ErrorAction SilentlyContinue
if ($serverTask -and [string]$serverTask.State -eq 'Running') {
    Stop-ScheduledTask -TaskName 'Crumbs World Harley Server'
    $stopDeadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        $serverTask = Get-ScheduledTask -TaskName 'Crumbs World Harley Server' -ErrorAction SilentlyContinue
    } while ($serverTask -and [string]$serverTask.State -eq 'Running' -and (Get-Date) -lt $stopDeadline)
    if ($serverTask -and [string]$serverTask.State -eq 'Running') {
        throw 'Could not stop the existing Harley server task cleanly; Prime is installed, but the game was not restarted.'
    }
    Start-ScheduledTask -TaskName 'Crumbs World Harley Server'
    $gameDeadline = (Get-Date).AddSeconds(30)
    $gameHealth = $null
    while ((Get-Date) -lt $gameDeadline) {
        try {
            $gameHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8778/api/melody/health' -TimeoutSec 2
            if ($gameHealth.ok -and $gameHealth.mode -eq 'proxy' -and $gameHealth.configured) { break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $gameHealth -or -not $gameHealth.ok -or $gameHealth.mode -ne 'proxy' -or -not $gameHealth.configured) {
        throw 'Prime is healthy, but the restarted game did not report the proxy backend. Check the server task and sentinel.'
    }
}
Write-Output "Prime is healthy (provider=$($health.provider), model=$($health.model)); the Harley game task was restarted to use its local proxy."
Write-Output 'The Groq key remains DPAPI-protected outside the repository and was not printed.'
