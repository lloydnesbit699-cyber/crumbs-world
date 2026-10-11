# Windows Harley service setup guide

This is the authoritative Windows-side setup for the real game server.

## 1) Run on a private port

Use a private port such as `8778` and keep it off the public internet.

## 2) Run from the repo

```powershell
cd C:\path\to\crumbs-world
$env:CRUMBS_SERVER_ROLE = "harley"
python .\crumbs_hud.py
```

## 3) Keep the role explicit

Set the environment variable before startup:

```powershell
$env:CRUMBS_SERVER_ROLE = "harley"
```

This makes the app clearly behave as the authoritative Harley server.

## 4) Prefer a private bind

Make sure the server is bound to an internal/private address or private network only.

Do not expose the raw Harley port directly to the Internet.

## 5) Required behavior on Harley

Harley must keep:
- auth and user records
- player vault data
- world state
- recovery and checkpoint logic
- version trust checks
- Melody safety boundaries

## 6) Keep truth on the server

Harley is where truth lives.

This means:
- no relay should decide game correctness
- no browser should own the state
- no public-facing edge should be the authority

## 7) Firewall guidance

On Windows, restrict access so only the relay or trusted internal hosts can reach the server.

Example policy:
- allow only local LAN / Cortana IP to port `8778`
- deny public internet to that port

## 8) Operational safety

Keep these running and monitored:
- app process
- version trust checks
- backup rotation
- checkpoint verification
- restart recovery

## 9) Final rule

Cortana may be public.
Harley is the one that decides what is real.
