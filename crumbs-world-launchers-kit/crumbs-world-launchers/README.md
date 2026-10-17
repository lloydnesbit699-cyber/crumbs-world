# Crumbs World Launchers v1.0
Built 2026-10-14 — Wren, for Lloyd

Zero-config launchers: you send them to players, they install, the game
opens and connects to Harley by itself. No URLs to type, no setup.

## What's here

- `android/build/crumbs-world-launcher.apk` — Android installer (signed).
  Fullscreen wrapper: splash screen, verifies Harley is up via /api/health,
  checks the game version, self-updates the wrapper when you ship a new one,
  then opens the game. If Harley is down it says so instead of a blank page.
- `android/` — full source (Java, no dependencies). `Config.java` holds the
  server URL — the ONE place it lives.
- `ios/CrumbsWorld.mobileconfig` — iPhone installer. One tap installs a
  "Crumbs World" icon on the Home Screen; tapping it opens the game
  fullscreen and auto-connects. (Shows an "Unverified Profile" warning on
  install — normal for unsigned profiles; the game itself is unaffected.)
- `rebuild-apk.sh` — re-cuts the APK with a new server URL in one command.
- `crumbs-release.keystore.BACKUP` — the signing key. **Keep it.** If it's
  lost, every player must uninstall/reinstall to take updates.

## ⚠️ ONE THING BEFORE THESE WORK

Both launchers currently point at `https://HARLEY_URL_HERE` — a placeholder.
They need Harley's real public game URL baked in. On Harley, run:

    tailscale funnel status

(or check the Tailscale admin panel) and send me the https URL. I'll re-cut
both files in minutes — the APK rebuild is `./rebuild-apk.sh <url>`, and the
mobileconfig is a one-line change.

## Harley must be serving first

The launchers are dumb clients: if Harley isn't running the game, they show
"Can't reach Harley." Before sending these to players:

1. On Harley: `.\boots\crumbs-boot.ps1` (note: it still says crumbs_hud.py —
   update it to crumbs_world.py after the rename lands, or it won't find her).
2. Confirm `http://127.0.0.1:8778/api/health` answers on Harley.
3. Confirm the Funnel URL serves the game publicly.

## The in-game rename (HUD → World)

Player-visible strings now say "Crumbs World" (browser tab, header, login
screen, splash, welcome toast, tooltips). The server file stays
`crumbs_hud.py` — no file rename. Apply on Harley in your game folder:

    git pull
    git apply C:\path\to\crumbs-world-rename.patch
    git commit -am "in-game rename hud->world" ; git push

then restart the server.

## Install instructions (send to players with the files)

**Android:** Open the APK on the phone → allow "install unknown apps" once →
Install → open "Crumbs World". That's it.
**iPhone:** Open the .mobileconfig → Settings → Profile Downloaded → Install →
the Crumbs World icon appears on the Home Screen. (Unverified-profile warning
is expected.)

## Self-update

The game itself updates automatically — it's served fresh from Harley every
launch. The *wrapper* checks `/api/launcher-version` on Harley each launch;
when you bump `CRUMBS_LAUNCHER_ANDROID` on the server and drop the new APK
where `CRUMBS_LAUNCHER_APK_URL` points, players get a download prompt.
iOS needs nothing: the web clip just opens the URL.
