# Windows Harley service setup guide

This is the authoritative Windows-side setup for the real game server.

## 1) Install always-on startup

On Harley, from the repository, run PowerShell:

```powershell
.\deployment\install_harley_autostart.ps1
```

Run this once for initial setup, elevated as Harley's normal service account
(currently `HARLEY\lloyd`). This registers a limited-privilege Task Scheduler
task at system startup. Its watchdog restarts the server with a backoff if it
exits and writes logs under `logs\`. It continues across sign-out and starts
after power returns, once Windows boots.

## 2) Routine repo update

After committing and pushing changes from the development checkout, update
Harley from an elevated PowerShell window in its repo folder:

```powershell
git status --short
git pull --ff-only origin main
```

For this profile-hardening release, run the installer once after the pull so
it applies the new ACL policy to existing profile data:

```powershell
.\deployment\install_harley_autostart.ps1
```

Then use the game's **Restart server** control. It saves dirty world state and
re-executes the server into the pulled code while the watchdog remains active.
Confirm the version with:

```powershell
.\boots\crumbs-boot.ps1 -Check
```

For ordinary future code-only pushes, the installer does not need to run
again; pull the repo and use **Restart server**. Re-run the installer only
after changes to the task setup or profile ACL policy. Before pulling, check
`git status --short` and preserve any Harley-local edits to tracked code.

## 3) Keep the public entry point private

Harley uses `--funnel`, which enables the authenticated account system while
binding only to `127.0.0.1:8778`. The existing Tailscale Funnel proxies to that
loopback address. Do not use `--public` on Harley; that binds all interfaces
and exposes the raw port to the LAN.

## 4) Configure recovery delivery

Email and SMS recovery are available when configured on Harley. Use a
send-only SMTP/app-password credential and a restricted Twilio API key with
Messaging permission. Keep these values in Harley's user environment, never
in the repository or in chat. Set the following variables for the account
that runs the scheduled task, then restart the task or reboot:

- Email: `CRUMBS_RECOVERY_SMTP_HOST`, `CRUMBS_RECOVERY_SMTP_FROM`, and
  optionally `CRUMBS_RECOVERY_SMTP_PORT` (default 587),
  `CRUMBS_RECOVERY_SMTP_USER`, `CRUMBS_RECOVERY_SMTP_PASSWORD`.
- SMS: `CRUMBS_RECOVERY_TWILIO_ACCOUNT_SID`,
  `CRUMBS_RECOVERY_TWILIO_KEY_SID`,
  `CRUMBS_RECOVERY_TWILIO_KEY_SECRET`,
  `CRUMBS_RECOVERY_TWILIO_FROM`.

Users must have registered the same email or a phone number in international
format (for example `+15551234567`). Recovery codes expire after 10 minutes,
allow five guesses, and are limited to three sends per destination per hour
and thirty sends total per hour. Recovery responses don't reveal whether an
account exists.

Check status or reinstall the task with:

```powershell
.\deployment\install_harley_autostart.ps1 -Status
.\deployment\install_harley_autostart.ps1
```

## 5) Protect persistent profiles

The installer removes inherited access from
the existing `users.json`, its retained backups, the server secret, and the
vault tree, granting access to the service account, SYSTEM, and local
Administrators. New account database writes apply the same Windows ACL before
the atomic replace; POSIX installs use mode `0600`. The installer permits
Microsoft Cloud Files reparse tags (used by OneDrive Files On-Demand) and
still rejects symlinks, junctions, and unknown reparse tags. Keep
`users.json.*.bak` out of Git.

New accounts and password changes require 6-1024 characters. Existing
passwords remain valid until changed, so account owners should update weak
passwords after the update. Funnel-mode login cookies are marked Secure.

## 6) Required behavior on Harley

Harley must keep:
- auth and user records
- player vault data
- world state
- recovery and checkpoint logic
- version trust checks
- Melody safety boundaries

## 7) Keep truth on the server

Harley is where truth lives.

This means:
- no relay should decide game correctness
- no browser should own the state
- no public-facing edge should be the authority

## 8) Firewall guidance

The server binds loopback only, so remote clients cannot connect directly to
port 8778. Tailscale Funnel is the public entry point; keep its ACLs and
account protections enabled.

Example policy:
- allow only local LAN / Cortana IP to port `8778`
- deny public internet to that port

## 9) Operational safety

Keep these running and monitored:
- app process
- version trust checks
- backup rotation
- checkpoint verification
- restart recovery

## 10) Final rule

Cortana may be public.
Harley is the one that decides what is real.
