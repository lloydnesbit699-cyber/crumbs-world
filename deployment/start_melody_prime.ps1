param([switch]$CheckUpstream)

$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoDir '.venv\Scripts\python.exe'
$prime = Join-Path $repoDir 'tools\melody_prime_proxy.py'
$secretFile = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets\groq-api-key.dpapi'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Project Python runtime is missing.' }
if (-not (Test-Path -LiteralPath $prime -PathType Leaf)) { throw 'Melody Prime proxy source is missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Groq key is not configured; run configure_melody_prime.ps1.' }

try {
    $cipher = [IO.File]::ReadAllText($secretFile).Trim()
    $secureKey = ConvertTo-SecureString -String $cipher
    $keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try { $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr) }
} catch {
    throw 'Could not decrypt the Groq key for this Windows account.'
}

$env:MELODY_PROXY_TOKEN = [Environment]::GetEnvironmentVariable('MELODY_PROXY_TOKEN', 'User')
$env:MELODY_PRIME_MODEL = [Environment]::GetEnvironmentVariable('MELODY_PRIME_MODEL', 'User')
try {
    if ($CheckUpstream) { & $python $prime --check-upstream }
    else { & $python $prime }
    exit $LASTEXITCODE
}
finally { Remove-Item Env:\GROQ_API_KEY -ErrorAction SilentlyContinue }
