# Example Windows Harley launcher for a private server.
# This is deliberately simple: it starts the authoritative process on an internal port.

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Resolve-Path (Join-Path $scriptDir "..")
$port = if ($env:CRUMBS_PORT) { $env:CRUMBS_PORT } else { "8778" }
$role = if ($env:CRUMBS_SERVER_ROLE) { $env:CRUMBS_SERVER_ROLE } else { "harley" }

Set-Location $repoDir

Write-Host "Starting Harley on internal port $port"
Write-Host "Role: $role"

$env:CRUMBS_SERVER_ROLE = $role
$env:PORT = $port

python .\crumbs_hud.py --public
