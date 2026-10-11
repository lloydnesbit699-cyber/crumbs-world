# Harley / Cortana deployment blueprint

This is the practical deployment pattern for your real machine split:

- Cortana = AntiX public relay / front door
- Harley = Windows game server / authority

The goal is to keep the public relay simple and low-resource while keeping the real game state, auth, vaults, and Melody security on the server that can actually own them.

## 1) Role split

### Cortana (AntiX)
Cortana should be a public-facing relay only.

It should allow:
- `/`
- `/classic`
- `/manifest.webmanifest`
- `/service-worker.js`
- `/api/health`
- `/api/auth/me`
- `/api/auth/login`
- `/api/auth/logout`
- static assets
- safe public read-only routes

Cortana should reject or restrict:
- state-changing write routes
- map save/load
auth attempts that require world authority
- any route that would bypass Harley's real server-side state
- anything that touches player vaults or Melody scope

### Harley (Windows)
Harley is the real authority.

It owns:
- auth/session state
- world state and map persistence
- vault handling
- per-user storage
- Melody identity and isolation
- checkpoint/recovery logic
- version trust and startup safety

## 2) Network layout

Recommended layout:

- public domain points to Cortana
- Cortana listens on `80/443`
- Cortana proxies only allowed routes to Harley
- Harley listens on a private address or LAN-only port
- Harley is not exposed directly to the Internet

Example:

- Cortana: `play.example.com`
- Harley: `harley.internal:8778`
- Caddy or Nginx on Cortana proxies to `harley.internal:8778`

## 3) Recommended proxy policy

Use an allowlist, not a blanket pass-through.

Good allowlist examples:
- `/api/health`
- `/api/auth/me`
- `/api/auth/login`
- `/manifest.webmanifest`
- `/service-worker.js`
- the app shell page(s)

Everything else should be treated as stateful or protected unless explicitly approved.

## 4) Exact gate principle

Cortana is a relay, not a source of truth.

The public relay may do:
- serve the boot page
- serve static assets
- report health
- pass through approved read-only traffic

The public relay must never do:
- mutate world state
- decide if a vault is valid
- decide who the active user is for the world
- allow a player to bypass Harley's server-side checks

## 5) Why this is the right model for your machines

Your split is favorable:

- AntiX is low-resource and good for a public front door
- Windows is bigger and better suited to the real application logic
- each machine has a clear purpose

This keeps the system reliable while still allowing global access from anywhere.

## 6) Service startup order

On Harley:
1. start the Python server
2. verify startup trust checks
3. ensure the instance is boot-safe
4. enable private listening only

On Cortana:
1. enable Caddy or Nginx
2. configure DNS / TLS / public endpoint
3. proxy only the approved routes
4. reject or block the rest

## 7) Safety rules to keep

- no browser trust for world state
- no public relay authority
- no write requests allowed through Cortana unless explicitly designed as a trusted bridge
- keep session and vault validation inside Harley
- keep Melody, world state, and user data server-scoped
- version mismatch should halt startup on Harley

## 8) Most likely rollout path

1. Confirm Harley runs safely on Windows
2. Keep it on a private port
3. Put Caddy or Nginx in front on AntiX
4. Enable only the allowlist routes
5. Test public login and health endpoints
6. Test that Cortana rejects write-style requests
7. Start exposing it publicly

## 9) Final rule

Harley decides.
Cortana relays.
The browser is a client, never the authority.

That is the deployment model that best matches your machine split and the game’s safety requirements.
