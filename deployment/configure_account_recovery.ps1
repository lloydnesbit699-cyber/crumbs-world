<#
.SYNOPSIS
    Configure account-recovery email and/or SMS delivery for the current user.
.DESCRIPTION
    Prompts locally for provider settings, stores them in this Windows user's
    environment, and never prints credential values. Run as the same account
    that owns the Harley scheduled tasks. New task processes pick up changes
    after the server is gracefully restarted or Windows is rebooted.
#>
[CmdletBinding()]
param(
    [switch]$Email,
    [switch]$Sms
)

$ErrorActionPreference = 'Stop'
if (-not $Email -and -not $Sms) {
    throw 'Choose at least one provider: -Email, -Sms, or both.'
}
if ([Console]::IsInputRedirected) {
    throw 'This setup requires an interactive PowerShell window so credentials are not passed on the command line.'
}

$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($account -match '^(NT AUTHORITY|NT SERVICE|SYSTEM)\\') {
    throw "Run this as the Harley user account that owns the scheduled tasks, not $account."
}

function Read-Required([string]$Prompt) {
    while ($true) {
        $value = (Read-Host $Prompt).Trim()
        if ($value) { return $value }
        Write-Warning 'A value is required.'
    }
}

function Read-SecretText([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    if ($secure.Length -eq 0) { throw 'The secret cannot be empty.' }
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        $secure.Dispose()
    }
}

$values = @{}
if ($Email) {
    Write-Host 'Email recovery uses SMTP with TLS. Use a send-only app password if authentication is required.'
    $hostName = Read-Required 'SMTP host'
    $portText = Read-Host 'SMTP port [587; use 465 for implicit TLS]'
    if (-not $portText) { $portText = '587' }
    $port = 0
    if (-not [int]::TryParse($portText, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
        throw 'SMTP port must be an integer from 1 to 65535.'
    }
    $sender = Read-Required 'From email address'
    try { $null = New-Object System.Net.Mail.MailAddress -ArgumentList $sender }
    catch { throw 'From address must be a valid email address.' }
    $smtpUser = (Read-Host 'SMTP username (leave blank if your relay does not require login)').Trim()
    $smtpPassword = ''
    if ($smtpUser) { $smtpPassword = Read-SecretText 'SMTP app password' }
    $values['CRUMBS_RECOVERY_SMTP_HOST'] = $hostName
    $values['CRUMBS_RECOVERY_SMTP_PORT'] = [string]$port
    $values['CRUMBS_RECOVERY_SMTP_FROM'] = $sender
    $values['CRUMBS_RECOVERY_SMTP_USER'] = $smtpUser
    $values['CRUMBS_RECOVERY_SMTP_PASSWORD'] = $smtpPassword
}

if ($Sms) {
    Write-Host 'SMS recovery uses Twilio. Use a restricted API key with Messaging permission.'
    $accountSid = Read-Required 'Twilio Account SID (AC...)'
    if ($accountSid -notmatch '^AC[0-9a-fA-F]{32}$') { throw 'Twilio Account SID format is invalid.' }
    $keySid = Read-Required 'Twilio API Key SID (SK...)'
    if ($keySid -notmatch '^SK[0-9a-fA-F]{32}$') { throw 'Twilio API Key SID format is invalid.' }
    $keySecret = Read-SecretText 'Twilio API Key secret'
    $from = Read-Required 'Twilio sender number or approved sender ID'
    $values['CRUMBS_RECOVERY_TWILIO_ACCOUNT_SID'] = $accountSid
    $values['CRUMBS_RECOVERY_TWILIO_KEY_SID'] = $keySid
    $values['CRUMBS_RECOVERY_TWILIO_KEY_SECRET'] = $keySecret
    $values['CRUMBS_RECOVERY_TWILIO_FROM'] = $from
}

# No settings are persisted until all selected provider inputs validate.
# Restore previous values if a registry write fails partway through.
$previous = @{}
foreach ($key in $values.Keys) {
    $previous[$key] = @{
        User = [Environment]::GetEnvironmentVariable($key, 'User')
        Process = [Environment]::GetEnvironmentVariable($key, 'Process')
    }
}
try {
    foreach ($entry in $values.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'User')
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
} catch {
    foreach ($key in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($key, $previous[$key].User, 'User')
        [Environment]::SetEnvironmentVariable($key, $previous[$key].Process, 'Process')
    }
    throw 'Could not save recovery settings; previous settings were restored.'
}
foreach ($key in @($values.Keys)) { $values[$key] = $null }
$values.Clear()
$previous.Clear()
$entry = $null
$smtpPassword = $null
$keySecret = $null

Write-Host "Recovery delivery settings saved for $account. Values were not displayed."
Write-Host 'They apply to newly started tasks. Gracefully restart the server or reboot Harley before testing recovery.'
Write-Host 'Users must have that same email address or international phone number registered on their account.'
