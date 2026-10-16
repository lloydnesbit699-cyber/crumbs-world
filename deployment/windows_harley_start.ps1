# Install and start the persistent, loopback-only Harley task.
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install_harley_autostart.ps1'
& $installer
