# Windows Harley service setup guide

This is the authoritative Windows-side setup for the real game server.

## 1) Install always-on startup

On Harley, from the repository, run PowerShell as the same account that owns
the game profiles (currently `HARLEY\lloyd`):

```powershell
.\deployment\install_harley_autostart.ps1
```

Run this once for initial setup from an elevated PowerShell session while signed
in as that same account. Accept the UAC prompt; do not choose a different
administrator account. This registers a limited-privilege Task Scheduler task
at system startup. Its watchdog restarts the server with a backoff if it
exits and writes logs under `logs\`. It continues across sign-out and starts
after power returns, once Windows boots.

## 2) Verified push and deploy flow

From the development checkout, the push helper runs release consistency
repairs, the selected smoke tests, commits, and pushes. Pass `-ReleaseNotes`
for an app release; it bumps `APP_VERSION` and adds a matching changelog entry
(patch by default, or `-VersionBump minor|major`). It stages tracked edits and
its allowlisted automation files. Pass other new files with `-Include`; it
leaves unknown untracked files out:

```powershell
.\tools\crumbs_push.ps1 -Message "Describe the change" -ReleaseNotes "Describe what changed for players." -Include "docs\new-guide.md"
```

GitHub Actions runs `repo-verify` for pushes to `main` and pull requests. On
Harley, the verified deploy watcher checks the result for the exact `main`
commit. It waits for a successful check, refuses non-fast-forward or locally
edited tracked trees, pulls the verified commit, asks the server to save and
restart, and confirms the new version through the loopback health endpoint.
If health verification fails, it restores the previous commit and holds that
failed commit for review. It never changes profiles, vaults, or other ignored
runtime data.

### One-time verified deploy setup

The installer now registers both the always-on server watchdog and verified
deploy watcher. Make sure Harley's Windows account can run `git fetch origin
main`. GitHub Actions must be enabled and the `repo-verify` workflow must be
allowed to run.

Set `CRUMBS_SHARE_KEY` in that account's Windows user environment to the
server's stable share key. The deploy watcher uses it only for the local
loopback restart request; it is never put in Git or sent to GitHub. If the
repository is private, also set `CRUMBS_GITHUB_TOKEN` to a fine-grained token
with read-only Contents and Checks access. Public repositories do not need
that API token. Store credentials in Harley's Windows account / Git credential
manager, not in the repo or in chat.

Then, in Harley's repository folder, run once from elevated PowerShell as the
service account (accept the UAC prompt; do not use a different account):

```powershell
.\deployment\install_harley_autostart.ps1
```

The server watchdog remains a limited S4U task and starts with Windows even
when nobody is signed in. The deploy watcher uses the interactive sign-in token
and starts when `HARLEY\lloyd` signs in; it needs no password and stores no
Windows credential. It continues while the session is locked, but stops at
sign-out and resumes at the next sign-in. Therefore pushes made while signed
out are deployed after the next sign-in.

For the initial manually managed profile-hardening release, this installer
also applies ACLs to existing profiles. After setup, code-only releases deploy
automatically after CI passes; do not rerun the installer for each push.
Rerun it only after changes to task setup or profile ACL policy.

Check the tasks and run a no-change preflight on Harley with:

```powershell
.\deployment\install_harley_autostart.ps1 -Status
.\deployment\harley_verified_deploy.ps1 -Check
.\boots\crumbs-boot.ps1 -Check
```

Deploy logs go to `logs\harley-deploy.log`. A release that fails health checks
is rolled back and recorded in `.crumbs_deploy_failed`; inspect the logs and
correct the issue before removing that marker to retry the same commit.

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
