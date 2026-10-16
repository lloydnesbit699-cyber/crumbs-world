# Persistent, loopback-only Harley server supervisor. Run by Task Scheduler.
$ErrorActionPreference = 'Continue'
$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoDir '.venv\Scripts\python.exe'
$server = Join-Path $repoDir 'crumbs_hud.py'
$logDir = Join-Path $repoDir 'logs'
$port = 8778

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "Crumbs server is missing: $server"
}
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$env:PORT = [string]$port
$env:CRUMBS_SERVER_ROLE = 'harley'
$delay = 5

while ($true) {
    Get-ChildItem -LiteralPath $logDir -Filter 'harley-server-*.log' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip 60 |
        Remove-Item -Force -ErrorAction SilentlyContinue
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdout = Join-Path $logDir ("harley-server-$stamp.out.log")
    $stderr = Join-Path $logDir ("harley-server-$stamp.err.log")
    $started = Get-Date
    # --funnel enables account authentication but binds only to 127.0.0.1;
    # Tailscale Funnel already forwards to this exact local endpoint.
    $proc = Start-Process -FilePath $python -ArgumentList ('"' + $server + '" --funnel') `
        -WorkingDirectory $repoDir -WindowStyle Hidden -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr -Wait -PassThru
    if (((Get-Date) - $started).TotalMinutes -ge 10) { $delay = 5 }
    Start-Sleep -Seconds $delay
    $delay = [Math]::Min(60, $delay * 2)
}
