<#
.SYNOPSIS
  Windowless runner for the Melody Prime proxy (no console, ever).

  Drop-in replacement for deployment\start_melody_prime.ps1. The proxy's
  runtime logging already goes to logs\melody-prime.log (rotating file),
  so nothing is lost when the console goes away. Startup failures that
  happen BEFORE the proxy launches are appended to
  logs\melody-prime-startup.log, because with no window there is nowhere
  else for a pre-launch error to be seen.

  --check-upstream still runs under python.exe (visible console) because
  that path is only ever run by hand from configure_melody_prime.ps1.
#>
param([switch]$CheckUpstream)

$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python  = Join-Path $repoDir '.venv\Scripts\python.exe'
$pythonw = Join-Path $repoDir '.venv\Scripts\pythonw.exe'
$prime = Join-Path $repoDir 'tools\melody_prime_proxy.py'
$secretFile = Join-Path $env:LOCALAPPDATA 'CrumbsWorld\secrets\groq-api-key.dpapi'
$startupLog = Join-Path $repoDir 'logs\melody-prime-startup.log'

function Write-StartupLog([string]$level, [string]$msg) {
    $dir = Split-Path -Parent $startupLog
    if (-not (Test-Path -LiteralPath $dir -PathType Directory)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -LiteralPath $startupLog -Value "$ts [$level] $msg"
}

try {
    foreach ($req in @($python, $pythonw, $prime)) {
        if (-not (Test-Path -LiteralPath $req -PathType Leaf)) {
            throw "Required Prime file is missing: $req"
        }
    }
    if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
        throw 'Groq key is not configured; run configure_melody_prime.ps1.'
    }

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

    if ($CheckUpstream) {
        # Interactive use only: keep the console python so the result is readable.
        & $python $prime --check-upstream
        $code = $LASTEXITCODE
    } else {
        # Windowless: pythonw.exe has no console at all, so there is no window
        # to close and no console event that can reach her. NOTE: PowerShell's &
        # does NOT wait for GUI-subsystem exes, so launch with -Wait and read
        # ExitCode explicitly; otherwise the task would end while she runs on.
        $proc = Start-Process -FilePath $pythonw -ArgumentList "`"$prime`"" `
            -WorkingDirectory $repoDir -Wait -PassThru
        $code = $proc.ExitCode
    }
    Write-StartupLog 'INFO' "proxy exited with code $code"
    exit $code
} catch {
    Write-StartupLog 'ERROR' $_.Exception.Message
    throw
} finally {
    Remove-Item Env:\GROQ_API_KEY -ErrorAction SilentlyContinue
}
