<#
.SYNOPSIS
    Start, check, or stop the local Crumbs World server on Windows.

.DESCRIPTION
    Uses the game folder containing this script, so it works from any install
    location. The server remains on its configured loopback interface; this
    launcher does not expose it to the LAN or internet.

.USAGE
    .\crumbs-boot.ps1
    .\crumbs-boot.ps1 -Check
    .\crumbs-boot.ps1 -Stop
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8778,
    [switch]$Stop,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$BootDir = $PSScriptRoot
$GameDir = (Resolve-Path (Join-Path $BootDir "..")).Path
$ServerScript = Join-Path $GameDir "crumbs_hud.py"
$LogDir = Join-Path $GameDir "logs"
$PidFile = Join-Path $GameDir ".crumbs_hud.pid"
$VenvPython = Join-Path $GameDir ".venv\Scripts\python.exe"
$HealthUri = "http://127.0.0.1:$Port/api/health"

function Write-Say([string]$Message) {
    Write-Host ("crumbs-boot: " + $Message)
}

function Die([string]$Message) {
    [Console]::Error.WriteLine("crumbs-boot: ERROR: " + $Message)
    exit 1
}

function Get-ServerHealth {
    try {
        $response = Invoke-WebRequest -Uri $HealthUri -TimeoutSec 2 `
            -UseBasicParsing -ErrorAction Stop
        $health = $response.Content | ConvertFrom-Json -ErrorAction Stop
        if ($health.ok -eq $true -and $health.version) { return $health }
    } catch {
        return $null
    }
    return $null
}

function Get-CrumbsProcesses {
    try {
        return @(Get-CimInstance Win32_Process `
            -Filter "Name='python.exe' OR Name='pythonw.exe'" |
            Where-Object { $_.CommandLine -like ("*" + $ServerScript + "*") })
    } catch {
        return @()
    }
}

if (-not (Test-Path $ServerScript -PathType Leaf)) {
    Die ("server script not found beside the launcher: " + $ServerScript)
}

if ($Check) {
    Write-Progress -Activity 'Crumbs World boot check' -Status 'Checking local health endpoint' -PercentComplete 70
    $health = Get-ServerHealth
    if ($null -eq $health) { Die ("server did not answer a valid health check at " + $HealthUri) }
    Write-Say ("server is healthy (version " + $health.version + ")")
    Write-Progress -Activity 'Crumbs World boot check' -Completed
    exit 0
}

if ($Stop) {
    try {
        $response = Invoke-WebRequest -Uri $HealthUri -Method Post `
            -ContentType "application/json" -Body "{}" -TimeoutSec 3 `
            -UseBasicParsing -ErrorAction Stop
        $result = $response.Content | ConvertFrom-Json -ErrorAction Stop
        if ($result.ok -eq $true) {
            Write-Say "requested graceful save and shutdown"
            exit 0
        }
    } catch {}

    if (Test-Path $PidFile -PathType Leaf) {
        $oldPid = (Get-Content -LiteralPath $PidFile -TotalCount 1 -ErrorAction SilentlyContinue).Trim()
        if ($oldPid -match '^\d+$') {
            $owned = Get-CrumbsProcesses | Where-Object { $_.ProcessId -eq [int]$oldPid }
            if ($owned) {
                Stop-Process -Id ([int]$oldPid) -Force -ErrorAction Stop
                Write-Say ("stopped verified server process " + $oldPid)
            }
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

$health = Get-ServerHealth
if ($null -ne $health) {
    Write-Progress -Activity 'Crumbs World boot' -Completed
    Write-Say ("server is already UP on port {0} (version {1}, tester_shell={2})" -f
        $Port, $health.version, $health.tester_shell)
    exit 0
}

if (Test-Path $PidFile -PathType Leaf) {
    $oldPid = (Get-Content -LiteralPath $PidFile -TotalCount 1 -ErrorAction SilentlyContinue).Trim()
    if ($oldPid -match '^\d+$') {
        $owned = Get-CrumbsProcesses | Where-Object { $_.ProcessId -eq [int]$oldPid }
        if ($owned) {
            Die ("server process " + $oldPid + " is running but failed its health check; inspect logs before retrying")
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $VenvPython -PathType Leaf)) {
    Write-Progress -Activity 'Crumbs World boot' -Status 'Preparing isolated Python environment' -PercentComplete 15
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -3 -m venv (Join-Path $GameDir ".venv")
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
        if (-not $python) { Die "Python 3 is required; install it and rerun this launcher" }
        & $python.Source -m venv (Join-Path $GameDir ".venv")
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython -PathType Leaf)) {
        Die "could not create the project-local .venv"
    }
}

Write-Progress -Activity 'Crumbs World boot' -Status 'Checking and repairing Python dependencies' -PercentComplete 35
& $VenvPython (Join-Path $GameDir 'tools\boot_preflight.py')
if ($LASTEXITCODE -ne 0) { Die "boot preflight failed; repair the project .venv before serving login" }

try {
    Write-Progress -Activity 'Crumbs World boot' -Status 'Preparing logs and starting the server' -PercentComplete 55
    if (-not (Test-Path $LogDir -PathType Container)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
} catch {
    Die ("cannot create log directory: " + $_.Exception.Message)
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logOut = Join-Path $LogDir ("crumbs_hud_" + $stamp + ".out.log")
$logErr = Join-Path $LogDir ("crumbs_hud_" + $stamp + ".err.log")
$oldPort = $env:PORT
$oldShell = $env:CRUMBS_TESTER_SHELL
try {
    $env:PORT = [string]$Port
    if (-not $env:CRUMBS_TESTER_SHELL) { $env:CRUMBS_TESTER_SHELL = "1" }
    Write-Say ("starting server on port " + $Port + "...")
    $proc = Start-Process -FilePath $VenvPython `
        -ArgumentList ('"' + $ServerScript + '"') `
        -WorkingDirectory $GameDir -WindowStyle Hidden `
        -RedirectStandardOutput $logOut -RedirectStandardError $logErr -PassThru
} catch {
    Die ("server process could not start: " + $_.Exception.Message)
} finally {
    $env:PORT = $oldPort
    $env:CRUMBS_TESTER_SHELL = $oldShell
}

$pidTemp = $PidFile + "." + [Guid]::NewGuid().ToString("N") + ".tmp"
try {
    [IO.File]::WriteAllText($pidTemp, [string]$proc.Id)
    Move-Item -LiteralPath $pidTemp -Destination $PidFile -Force
} catch {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pidTemp -Force -ErrorAction SilentlyContinue
    Die ("could not write PID file: " + $_.Exception.Message)
}

$up = $null
for ($i = 0; $i -lt 30; $i++) {
    Write-Progress -Activity 'Crumbs World boot' -Status ("Waiting for healthy server response ({0}/30)" -f ($i + 1)) -PercentComplete (60 + [int](35 * ($i + 1) / 30))
    $up = Get-ServerHealth
    if ($null -ne $up) { break }
    if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds 1
}
if ($null -ne $up) {
    Write-Progress -Activity 'Crumbs World boot' -Completed
    Write-Say ("server is UP on port {0} (version {1}, tester_shell={2}, pid {3})" -f
        $Port, $up.version, $up.tester_shell, $proc.Id)
    Write-Say ("log: " + $logOut)
    exit 0
}

Write-Say "server did not become healthy; recent log output:"
Write-Progress -Activity 'Crumbs World boot' -Completed
if (Test-Path $logOut) { Get-Content $logOut -Tail 40 | Write-Host }
if (Test-Path $logErr) { Get-Content $logErr -Tail 40 | Write-Host }
if (Get-CrumbsProcesses | Where-Object { $_.ProcessId -eq $proc.Id }) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
exit 1
