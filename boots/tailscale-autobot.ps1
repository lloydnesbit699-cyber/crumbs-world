<#
.SYNOPSIS
    tailscale-autobot.ps1 — one-shot Tailscale setup "Autobot" for Windows 11 (Harley).

.DESCRIPTION
    Native Windows setup for Tailscale. This script installs and connects the
    device by default. Tailscale SSH and public Funnel are opt-in and require
    separate interactive confirmations.

    PowerShell 5.1 compatible — no PS 7-only syntax.

    What it does, end to end:
      1. Installs Tailscale via winget (skipped if tailscale.exe is present).
      2. Ensures the Windows "Tailscale" service is running.
      3. Runs `tailscale up` to connect without changing exposure settings.
      4. Explicitly leaves Tailscale SSH disabled unless -SSH is confirmed.
      5. Verifies status and optional peer connectivity.
      6. Enables Funnel only when -Funnel <port> is confirmed.
         Tailscale status, netcheck, tailscale ping to a peer, and a
         real TCP connectivity check — including a specific diagnostic for the
         "half-open" state seen before (node Running + netcheck clean, but no
         TCP data flows to peers).

    The ONE manual step: authentication. Provide it ONE of these ways:
      a) Key file:  .\tailscale-autobot.ps1 -AuthKeyFile C:\path\to\key.txt
         The file must be readable only by you / Administrators / SYSTEM
         (the Windows equivalent of mode 600). The key is passed by file
         reference, not exposed in the process command line.
      b) Nothing: the script runs `tailscale up` in the foreground, prints the
         login URL, and waits for you to approve it in a browser.
    The key is never printed, never logged, and never written into any file
    by this script.

    Elevation: install and service-start steps need an elevated Terminal.
    The script does NOT demand elevation up front — it fails with a clear
    "re-run elevated" message only when a privileged step actually needs it.

.USAGE
    .\tailscale-autobot.ps1 [-Hostname NAME] [-Peer 100.x.y.z-or-name]
                            [-AuthKeyFile PATH] [-TcpPort 22] [-Reup]
                            [-SSH] [-Funnel PORT]

.EXAMPLE
    .\tailscale-autobot.ps1 -Hostname harley -Peer 100.82.195.90 `
        -AuthKeyFile "$env:USERPROFILE\.tailscale-authkey"

    .\tailscale-autobot.ps1 -SSH
    .\tailscale-autobot.ps1 -Funnel 8778
    .\tailscale-autobot.ps1 -SSH -Funnel 8778

    Exit codes:
      0  everything installed, up, and verified
      1  usage / preflight / install failure
      2  service would not start, or `tailscale up` failed
      3  verification failed (includes the "half-open" diagnosis)

    Idempotent: safe to re-run. An existing install, a running service, and
    an already-up node are detected and left alone (use -Reup to force
    `tailscale up` again).

    This script performs NO destructive actions: no formatting, no firewall
    changes, no package removals.
#>

[CmdletBinding()]
param(
    [string]$Hostname = "",
    [string]$Peer = "",
    [string]$AuthKeyFile = "",
    [int]$TcpPort = 22,
    [Alias("SSH")]
    [switch]$EnableSSH,
    [int]$Funnel = 0,
    [switch]$Reup
)

$ErrorActionPreference = 'Continue'

# ---------------------------------------------------------------- helpers ---
function Write-Log([string]$msg)  { Write-Host ("[..] " + $msg) }
function Write-Ok([string]$msg)   { Write-Host ("[OK] " + $msg) -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Warning ("[!!] " + $msg) }
function Die([string]$msg, [int]$code = 1) {
    [Console]::Error.WriteLine("[FAIL] " + $msg)
    exit $code
}

$IsAdmin = ([Security.Principal.WindowsPrincipal]`
    [Security.Principal.WindowsIdentity]::GetCurrent()`
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Deep-JSON parse that works on PowerShell 5.1 (ConvertFrom-Json has no
# -Depth there and truncates). Returns nested dictionaries, or $null.
function ConvertFrom-DeepJson {
    param([Parameter(Mandatory = $true)][string]$Json)
    try {
        Add-Type -AssemblyName System.Web.Extensions -ErrorAction Stop
        $ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer -ErrorAction Stop
        $ser.MaxJsonLength = 10485760
        return $ser.DeserializeObject($Json)
    } catch {
        return $null
    }
}

function Test-TcpPort {
    param([string]$Ip, [int]$Port, [int]$TimeoutMs = 8000)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($Ip, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return "TIMEOUT" }
        $client.EndConnect($iar)
        if ($client.Connected) { return "OPEN" }
        return "ERROR:connect completed but not connected"
    } catch [System.Net.Sockets.SocketException] {
        if ($_.Exception.SocketErrorCode -eq [System.Net.Sockets.SocketError]::ConnectionRefused) {
            return "REFUSED"
        }
        return ("ERROR:" + $_.Exception.Message)
    } catch {
        return ("ERROR:" + $_.Exception.Message)
    } finally {
        $client.Close()
    }
}

function Test-HttpPort {
    param([int]$Port, [int]$TimeoutMs = 3000)
    $request = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/")
    $request.Method = "GET"
    $request.Timeout = $TimeoutMs
    try {
        $response = [System.Net.HttpWebResponse]$request.GetResponse()
        try { return ($response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500) }
        finally { $response.Close() }
    } catch [System.Net.WebException] {
        if ($_.Exception.Response -is [System.Net.HttpWebResponse]) {
            $response = [System.Net.HttpWebResponse]$_.Exception.Response
            try { return ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500) }
            finally { $response.Close() }
        }
        return $false
    }
}

function Confirm-Exposure([string]$Description) {
    if ([Console]::IsInputRedirected) {
        Die "refusing exposure change without an interactive confirmation: $Description" 1
    }
    Write-Host ""
    Write-Warn $Description
    $answer = Read-Host "Type YES to continue; anything else cancels this exposure change"
    return ($answer -ceq "YES")
}

if ($Funnel -lt 0 -or $Funnel -gt 65535) {
    Die "-Funnel must be a local TCP port from 1 through 65535" 1
}
if ($Funnel -eq 0 -and $PSBoundParameters.ContainsKey("Funnel")) {
    Die "-Funnel requires a port from 1 through 65535" 1
}

$EnableSSHConfirmed = $false
if ($EnableSSH) {
    $EnableSSHConfirmed = Confirm-Exposure (
        "This enables Tailscale SSH on this machine. Tailnet policy may allow authorized tailnet users to open remote shell sessions."
    )
    if (-not $EnableSSHConfirmed) { Write-Log "SSH enablement cancelled; continuing with SSH disabled" }
}

$FunnelConfirmed = $false
if ($Funnel -gt 0) {
    $FunnelConfirmed = Confirm-Exposure (
        "This publishes the local HTTP service on port $Funnel to the public internet through Tailscale Funnel. Anyone with its URL may reach it; do not expose private or unreviewed services."
    )
    if (-not $FunnelConfirmed) { Write-Log "Funnel enablement cancelled; continuing without a new Funnel" }
}

# --------------------------------------------------------------- preflight --
Write-Log "preflight checks"
if (-not $IsAdmin) {
    Write-Warn "not running elevated — install and service steps will fail if they are needed; re-run in an elevated Terminal if so"
}

# Resolve tailscale.exe: PATH first, then the standard install location
# (winget does not always refresh PATH in the current session).
$TailscaleExe = $null
$cmd = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if ($cmd) { $TailscaleExe = $cmd.Source }
if (-not $TailscaleExe) {
    $probe = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path $probe) { $TailscaleExe = $probe }
}
Write-Ok "preflight done"

# ------------------------------------------------------------- 1. install ---
if ($TailscaleExe) {
    $ver = (& $TailscaleExe version 2>$null | Select-Object -First 1)
    Write-Ok ("tailscale already installed ({0}) — skipping install" -f $ver)
} else {
    if (-not $IsAdmin) {
        Die "tailscale.exe not found and this Terminal is not elevated — re-run in an elevated Terminal so winget can install Tailscale" 1
    }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { Die "winget.exe not found — install Tailscale by hand from https://tailscale.com/download/windows" 1 }
    Write-Log "installing Tailscale via winget"
    & $winget.Source install --exact --id Tailscale.Tailscale --silent `
        --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Die ("winget install failed (exit {0})" -f $LASTEXITCODE) 1 }
    $probe = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path $probe) { $TailscaleExe = $probe }
    else {
        $cmd = Get-Command tailscale.exe -ErrorAction SilentlyContinue
        if ($cmd) { $TailscaleExe = $cmd.Source }
    }
    if (-not $TailscaleExe) { Die "install finished but tailscale.exe not found" 1 }
    Write-Ok "tailscale installed"
}

# --------------------------------------------------- 2. service ------------
Write-Log "ensuring the Tailscale Windows service is running"
$svc = Get-Service -Name "Tailscale" -ErrorAction SilentlyContinue
if (-not $svc) { Die "Windows service 'Tailscale' not found — the install may be incomplete" 2 }
if ($svc.Status -ne 'Running') {
    if (-not $IsAdmin) {
        Die "the Tailscale service is not running and this Terminal is not elevated — re-run elevated so the service can be started" 2
    }
    Write-Log "starting the Tailscale service"
    try {
        Start-Service -Name "Tailscale" -ErrorAction Stop
        $svc.WaitForStatus('Running', (New-TimeSpan -Seconds 30))
    } catch {
        Die ("could not start the Tailscale service: " + $_.Exception.Message) 2
    }
}
$svc = Get-Service -Name "Tailscale"
if ($svc.Status -ne 'Running') { Die "the Tailscale service would not start — check Services.msc and the Tailscale log" 2 }
Write-Ok "Tailscale service is running"

# ---------------------------------------------------------- 3. tailscale up --
function Get-BackendState {
    $raw = (& $TailscaleExe status --json 2>$null | Out-String)
    if ($raw -match '"BackendState"\s*:\s*"([^"]+)"') { return $Matches[1] }
    return "unknown"
}

$State = Get-BackendState
Write-Log ("backend state: " + $State)

if (($State -eq "Running") -and (-not $Reup)) {
    Write-Ok "node already up — skipping 'tailscale up' (use -Reup to force)"
} else {
    # Resolve the auth key: file only. Never printed, never logged.
    $authKey = ""
    if ($AuthKeyFile -ne "") {
        if (-not (Test-Path $AuthKeyFile -PathType Leaf)) { Die ("authkey file not found: " + $AuthKeyFile) 1 }
        $AuthKeyFile = (Resolve-Path -LiteralPath $AuthKeyFile).Path
        # Windows equivalent of mode 600: only you, Administrators, SYSTEM.
        $mySid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $allowedSids = @($mySid, "S-1-5-32-544", "S-1-5-18")
        $bad = @()
        foreach ($ace in (Get-Acl -LiteralPath $AuthKeyFile).Access) {
            if ($ace.AccessControlType -ne 'Allow') { continue }
            $sid = $null
            try { $sid = $ace.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { }
            if ($sid -eq $null -or -not ($allowedSids -contains $sid)) {
                $bad += $ace.IdentityReference.Value
            }
        }
        if ($bad.Count -gt 0) {
            Die ("refusing to read key: {0} grants access to {1} — restrict the file to yourself only" -f $AuthKeyFile, ($bad -join ", ")) 1
        }
        if ((Get-Item -LiteralPath $AuthKeyFile).Length -eq 0) {
            Die ("authkey file is empty: " + $AuthKeyFile) 1
        }
        $authKey = "file:" + $AuthKeyFile
        Write-Log "using auth key from file (permissions verified, value never shown)"
    }

    $upArgs = @("up")
    if ($authKey -ne "") { $upArgs += ("--auth-key=" + $authKey) }

    if ($authKey -eq "") {
        $interactive = $false
        try { $interactive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected } catch { }
        if (-not $interactive) {
            Die "no auth key given and no interactive terminal — re-run with -AuthKeyFile" 1
        }
        Write-Warn "no auth key provided — 'tailscale up' will print a login URL; approve it in your browser to continue"
    }

    Write-Log ("running: tailscale up" + $(if ($authKey) { " (auth key read from protected file)" } else { "" }))
    & $TailscaleExe @upArgs
    $authKey = $null
    if ($LASTEXITCODE -ne 0) { Die "'tailscale up' failed — check the key / approval and try again" 2 }
    Write-Ok "tailscale up completed"

    $State = Get-BackendState
    if ($State -ne "Running") {
        Die ("tailscale up finished but backend state is '{0}', not Running" -f $State) 2
    }
}

# `set` changes only this preference, preserving existing routes, tags, and
# exit-node settings. A declined or absent --SSH explicitly leaves SSH off.
$sshValue = "false"
if ($EnableSSHConfirmed) { $sshValue = "true" }
Write-Log ("setting Tailscale SSH to " + $sshValue)
& $TailscaleExe set ("--ssh=" + $sshValue)
if ($LASTEXITCODE -ne 0) {
    Die "could not set the Tailscale SSH preference; update the Tailscale client and retry" 2
}
if ($Hostname -ne "") {
    & $TailscaleExe set ("--hostname=" + $Hostname)
    if ($LASTEXITCODE -ne 0) {
        Die "could not set the requested Tailscale hostname" 2
    }
}

# ---------------------------------------------------------- 4. verify ------
Write-Log "verification phase"
$verifyFailed = $false

Write-Host "--- tailscale status ---"
& $TailscaleExe status
if ($LASTEXITCODE -ne 0) { Write-Warn "tailscale status failed"; $verifyFailed = $true }

Write-Host "--- tailscale netcheck ---"
$netcheckOut = (& $TailscaleExe netcheck 2>&1 | Out-String)
Write-Host $netcheckOut
$udpOk = ($netcheckOut | Select-String -Pattern '(?m)^UDP:\s*true' -Quiet)

# Pick a peer: explicit -Peer, else first online peer from status JSON.
$peerIp = ""; $peerName = ""
$statusJson = (& $TailscaleExe status --json 2>$null | Out-String)
$st = ConvertFrom-DeepJson $statusJson
if ($Peer -ne "") {
    if ($Peer -match '^\d{1,3}(\.\d{1,3}){3}$') {
        $peerIp = $Peer; $peerName = $Peer
    } elseif ($st -ne $null) {
        $want = $Peer.ToLower()
        foreach ($k in $st["Peer"].Keys) {
            $p = $st["Peer"][$k]
            $names = @([string]$p["HostName"], [string]$p["DNSName"]) |
                ForEach-Object { $_.ToLower().TrimEnd('.') }
            if ($names -contains $want) {
                $ips = $p["TailscaleIPs"]
                if ($ips -ne $null -and $ips.Count -gt 0) {
                    $peerIp = [string]$ips[0]; $peerName = $Peer; break
                }
            }
        }
        if ($peerIp -eq "") { Write-Warn ("could not resolve peer '{0}' to a tailnet IP — skipping peer tests" -f $Peer) }
    } else {
        Write-Warn "peer name given but status JSON could not be parsed — skipping peer tests"
    }
} elseif ($st -ne $null) {
    foreach ($k in $st["Peer"].Keys) {
        $p = $st["Peer"][$k]
        if ($p["Online"] -eq $true) {
            $ips = $p["TailscaleIPs"]
            if ($ips -ne $null -and $ips.Count -gt 0) {
                $peerIp = [string]$ips[0]; $peerName = [string]$p["HostName"]; break
            }
        }
    }
    if ($peerIp -ne "") { Write-Log ("auto-selected peer: {0} ({1})" -f $peerName, $peerIp) }
    else { Write-Warn "no online peers found — skipping peer ping/TCP tests (re-run with -Peer once a peer is up)" }
} else {
    Write-Warn "status JSON could not be parsed — skipping peer auto-select (re-run with -Peer to test one)"
}

$pongCount = "n/a"; $tcpResult = "n/a"
if ($peerIp -ne "") {
    Write-Host ("--- tailscale ping {0} ({1}) ---" -f $peerName, $peerIp)
    $pingOut = (& $TailscaleExe ping --c=4 --timeout=10s $peerIp 2>&1 | Out-String)
    Write-Host $pingOut
    $pongCount = (@($pingOut | Select-String -Pattern '^pong')).Count

    Write-Host ("--- TCP check to {0} port {1} (8s timeout) ---" -f $peerIp, $TcpPort)
    $tcpResult = Test-TcpPort -Ip $peerIp -Port $TcpPort -TimeoutMs 8000
    Write-Log ("TCP result: " + $tcpResult)
    switch ($tcpResult) {
        "OPEN"    { Write-Ok ("TCP connected to {0} port {1} — data path works" -f $peerName, $TcpPort) }
        "REFUSED" { Write-Ok ("TCP refused by {0} port {1} — port closed but packets flow, data path works" -f $peerName, $TcpPort) }
        "TIMEOUT" { Write-Warn ("TCP to {0} port {1} timed out — packets are NOT getting through" -f $peerName, $TcpPort) }
        default   { Write-Warn ("TCP test error: " + $tcpResult) }
    }
}

# --------------------------------------- half-open diagnostic ----------------
# Seen before: node shows Running, netcheck is clean (UDP true), but NO TCP
# data flows to peers. Detect exactly that combination and say so plainly.
if (($State -eq "Running") -and $udpOk -and ($tcpResult -eq "TIMEOUT")) {
    Write-Host ""
    Write-Host "=================================================================="
    Write-Host "[DIAGNOSIS] HALF-OPEN TAILSCALE STATE DETECTED"
    Write-Host "=================================================================="
    Write-Host @'
What this means, in plain English:
  - Your node IS logged in and the Tailscale control plane can reach it
    (status shows Running).
  - UDP hole-punching works (netcheck says UDP: true).
  - BUT no TCP connection to a peer completes — every attempt times out.

This is the "half-open" state: signalling works, data does not.

Likely causes:
  1. Windows Defender Firewall (or the network you are on) is dropping
     the TCP packets.
  2. The path is forced through a DERP relay that is having trouble.
  3. tailscaled needs a fresh session (stale key / partial network change).

What to try, in order:
  1. Run:  tailscale netcheck
     and look at the "PreferredDERP" line and latency numbers.
  2. Check the device is Approved in the Tailscale admin console.
  3. Check Windows Defender Firewall is not blocking tailscaled.
  4. Force a fresh login: re-run this script with -Reup and a key file:
       .\tailscale-autobot.ps1 -Reup -AuthKeyFile C:\path\to\key.txt
  5. If it still fails, capture: tailscale bugreport
     and share the report ID when asking for help.
'@
    Write-Host "=================================================================="
    Die "verification failed: half-open state (TCP data path broken)" 3
}

if ($verifyFailed) {
    Die "verification failed — see messages above" 3
}

# ---------------------------------------------------------- 5. funnel ------
if ($FunnelConfirmed) {
    if (-not (Test-HttpPort -Port $Funnel)) {
        Die ("refusing to publish port {0}: no valid HTTP response from http://127.0.0.1:{0}/" -f $Funnel) 3
    }
    Write-Log ("publishing local port " + $Funnel + " through Tailscale Funnel")
    $funnelOut = (& $TailscaleExe funnel --bg $Funnel 2>&1 | Out-String)
    $funnelCode = $LASTEXITCODE
    Write-Host $funnelOut
    if ($funnelCode -eq 0) {
        $url = ""
        if ($funnelOut -match '(https://[^\s"''<>]+)') { $url = $Matches[1] }
        if ($url -ne "") { Write-Ok ("Funnel is live: " + $url) }
        else { Write-Ok "Funnel enabled in the background — see the status above" }
    } else {
        Write-Warn ("'tailscale funnel --bg {0}' failed (exit {1}) — output above" -f $Funnel, $funnelCode)
        $verifyFailed = $true
    }
} else {
    Write-Log "no new Funnel requested; existing Funnel settings, if any, were not changed"
    $existingFunnel = (& $TailscaleExe funnel status 2>&1 | Out-String).Trim()
    if ($existingFunnel -and $existingFunnel -notmatch "no serve config|no funnel") {
        Write-Warn "Funnel status follows. Any pre-existing public Funnel remains configured; this script did not change it."
        Write-Host $existingFunnel
    }
}

if ($verifyFailed) {
    Die "verification failed — see messages above" 3
}

# ---------------------------------------------------------------- summary ---
Write-Host ""
Write-Host "[OK] Tailscale Autobot finished successfully" -ForegroundColor Green
Write-Host ("  backend : " + $State)
Write-Host ("  ssh     : " + $(if ($EnableSSHConfirmed) { "enabled by explicit confirmation" } else { "disabled" }))
if ($Hostname -ne "") { Write-Host ("  hostname: " + $Hostname) }
if ($peerIp -ne "") { Write-Host ("  peer    : {0} ({1}), ping pongs {2}/4, TCP {3}" -f $peerName, $peerIp, $pongCount, $tcpResult) }
Write-Host "  service : the Windows 'Tailscale' service supervises tailscaled"
if ($FunnelConfirmed) { Write-Host ("  funnel  : local port " + $Funnel + " published to the public internet") }
else { Write-Host "  funnel  : no new public service enabled (existing configuration unchanged)" }
exit 0
