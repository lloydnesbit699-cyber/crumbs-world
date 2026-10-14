<#
.SYNOPSIS
    crumbs-boot.ps1 — one-command boot for the Crumbs World server on Harley (native Windows).

.DESCRIPTION
    Windows rewrite of melody-boot.sh's hardening pattern, for crumbs_hud.py.
    Runs natively on Windows 11 — no WSL needed. PowerShell 5.1 compatible.

    What it does:
      1. Checks the CONFIG block below (refuses to run on placeholders).
      2. Preflight: game directory, server script, Python, Pillow.
      3. If the server already answers on its port, reports version and
         tester-shell state, and exits.
      4. Refuses to double-start (pidfile + live process scan).
      5. Otherwise starts the server detached (hidden window) with logging,
         waits up to ~30s for /api/health, and reports success — or prints
         the log tail and exits 1.

    Environment given to the server: PORT (from $Port below) and every
    entry in $ExtraEnv (default: CRUMBS_TESTER_SHELL=1). They are set in
    this session first so the child process inherits them.

.USAGE
    .\crumbs-boot.ps1         # boot (or report already-up)
    .\crumbs-boot.ps1 -Stop   # stop the server

    Exit codes:
      0  server up (or already up), or stopped cleanly with -Stop
      1  preflight / start / health-check failure

    Logs live in <GameDir>\logs\crumbs_hud_<timestamp>.out.log (and .err.log).
    The running PID is kept in <GameDir>\.crumbs_hud.pid.
#>

[CmdletBinding()]
param(
    [switch]$Stop
)

# ---------------- CONFIG ----------------
$GameDir    = "C:\Users\lloyd\OneDrive\Desktop\Vault\crumbs-world"
$Port       = 8778
$ExtraEnv   = @{
    "CRUMBS_TESTER_SHELL" = "1"
}
$ServerFile = "crumbs_hud.py"
# ----------------------------------------

$ErrorActionPreference = 'Continue'

function Write-Say([string]$msg) { Write-Host ("crumbs-boot: " + $msg) }
function Die([string]$msg) {
    [Console]::Error.WriteLine("crumbs-boot: ERROR: " + $msg)
    exit 1
}

$ServerScript = Join-Path $GameDir $ServerFile
$LogDir  = Join-Path $GameDir "logs"
$PidFile = Join-Path $GameDir ".crumbs_hud.pid"

# Never allow a placeholder through.
if ($GameDir.Contains("[SET ME]")) {
    Die "CONFIG still has [SET ME] placeholders. Edit the CONFIG block at the top of this script first."
}
foreach ($k in $ExtraEnv.Keys) {
    if (([string]$ExtraEnv[$k]).Contains("[SET ME]")) {
        Die ("CONFIG placeholder found in ExtraEnv[{0}]. Edit the CONFIG block first." -f $k)
    }
}

if (-not (Test-Path $GameDir -PathType Container)) { Die ("game directory not found: " + $GameDir) }
if (-not (Test-Path $ServerScript -PathType Leaf))   { Die ("server script not found: " + $ServerScript) }

# --------------------------------------------------------------- python ---
# Prefer the py launcher, then python, then python3.
$PythonExe = $null
$PythonArgs = @()
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $PythonExe = $pyLauncher.Source; $PythonArgs = @("-3")
} else {
    $pyPlain = Get-Command python -ErrorAction SilentlyContinue
    if ($pyPlain) { $PythonExe = $pyPlain.Source }
    else {
        $py3 = Get-Command python3 -ErrorAction SilentlyContinue
        if ($py3) { $PythonExe = $py3.Source }
    }
}
if (-not $PythonExe) {
    Die "no Python found — install it with:  winget install Python.Python.3.12   (then re-open the Terminal)"
}
$pyVer = (& $PythonExe @PythonArgs --version 2>&1 | Out-String).Trim()
Write-Say ("using " + $pyVer)

# Pillow is the game's only dependency.
& $PythonExe @PythonArgs -c "import PIL; print(PIL.__version__)" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    if ($pyLauncher) { $pipHint = "py -3 -m pip install pillow" } else { $pipHint = "python -m pip install pillow" }
    Die ("Pillow (PIL) is not importable — install it with:  " + $pipHint)
}

# ------------------------------------------------------- health probe -----
function Get-ServerHealth {
    param([int]$Port)
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $Port + "/api/health") `
            -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
            try { return ($r.Content | ConvertFrom-Json) }
            catch { return New-Object PSObject -Property @{ ok = $true; version = "?"; note = "unparsed" } }
        }
    } catch { }
    return $null
}

function Test-ServerProcessRunning {
    # Any live python whose command line mentions the server script?
    $procs = @(Get-CimInstance Win32_Process `
        -Filter "Name='python.exe' OR Name='pythonw.exe'" `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like ("*" + $ServerFile + "*") })
    return $procs
}

# ------------------------------------------------------------------ -Stop --
if ($Stop) {
    $didSomething = $false
    if (Test-Path $PidFile) {
        $oldPid = ((Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1) + "").Trim()
        if ($oldPid -match '^\d+$') {
            $p = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
            if ($p) {
                Write-Say ("stopping server (pid " + $oldPid + ")...")
                Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
                $didSomething = $true
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    foreach ($p in (Test-ServerProcessRunning)) {
        Write-Say ("stopping leftover server process (pid " + $p.ProcessId + ")...")
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $didSomething = $true
    }
    if ($didSomething) { Write-Say "server stopped." } else { Write-Say "server is not running. Nothing to do." }
    exit 0
}

# ------------------------------------------------- already answering? ------
$health = Get-ServerHealth -Port $Port
if ($health -ne $null) {
    $ts = ""
    if ($health.tester_shell -ne $null) { $ts = (", tester_shell=" + $health.tester_shell) }
    Write-Say ("server is already UP on port {0} (version {1}{2}). Nothing to do." -f $Port, $health.version, $ts)
    exit 0
}

# ------------------------------------------------------- no double-start --
if (Test-Path $PidFile) {
    $oldPid = ((Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1) + "").Trim()
    $alive = $false
    if ($oldPid -match '^\d+$') {
        $p = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($p) {
            $cmdLine = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $oldPid) `
                -ErrorAction SilentlyContinue).CommandLine
            if ($cmdLine -like ("*" + $ServerFile + "*")) { $alive = $true }
        }
    }
    if ($alive) {
        Write-Say ("server process is already running (pid " + $oldPid + "). Nothing to do.")
        exit 0
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
$dupes = @(Test-ServerProcessRunning)
if ($dupes.Count -gt 0) {
    Write-Say ("a server process is already running (pid " + ($dupes[0].ProcessId) + "). Nothing to do.")
    exit 0
}

# ------------------------------------------------------------------ start --
if (-not (Test-Path $LogDir -PathType Container)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$stamp   = (Get-Date -Format "yyyyMMdd-HHmmss")
$logOut  = Join-Path $LogDir ("crumbs_hud_" + $stamp + ".out.log")
$logErr  = Join-Path $LogDir ("crumbs_hud_" + $stamp + ".err.log")

# Environment for the child: PORT follows $Port; ExtraEnv entries on top.
$env:PORT = "$Port"
foreach ($k in $ExtraEnv.Keys) { [Environment]::SetEnvironmentVariable($k, [string]$ExtraEnv[$k], "Process") }

$argList = @($PythonArgs | ForEach-Object { $_ }) + @($ServerScript)
Write-Say ("starting server on port " + $Port + "...")
$proc = Start-Process -FilePath $PythonExe -ArgumentList $argList `
    -WorkingDirectory $GameDir -WindowStyle Hidden `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr -PassThru
if (-not $proc) { Die "Start-Process failed to launch the server" }
$proc.Id | Out-File -FilePath $PidFile -Encoding ascii -NoNewline

# ------------------------------------------------------------- health loop --
$tries = 0
$up = $null
while ($tries -lt 30) {
    $up = Get-ServerHealth -Port $Port
    if ($up -ne $null) { break }
    # Bail early if the process died.
    if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds 1
    $tries++
}

if ($up -ne $null) {
    $ts = ""
    if ($up.tester_shell -ne $null) { $ts = (", tester_shell=" + $up.tester_shell) }
    Write-Say ("server is UP on port {0} (version {1}{2}, pid {3}). Log: {4}" -f $Port, $up.version, $ts, $proc.Id, $logOut)
    exit 0
}

Write-Say "server did not come up. Last 30 log lines:"
if (Test-Path $logOut) { Write-Host "--- stdout ---"; Get-Content $logOut -Tail 30 -ErrorAction SilentlyContinue | Write-Host }
if (Test-Path $logErr) { Write-Host "--- stderr ---"; Get-Content $logErr -Tail 30 -ErrorAction SilentlyContinue | Write-Host }
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
exit 1
