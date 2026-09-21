# Crumbs HUD — hosted on Replit (free)

No a-Shell, no restarts, no server babysitting. The HUD lives on Replit;
your phone is just a browser.

## One-time setup (about 5 minutes, works from your phone)

1. Go to **replit.com** and sign up free (the Google or GitHub button is
   fastest).
2. **+ Create** → **Import from GitHub** → paste
   `https://github.com/lloydnesbit699-cyber/crumbs-world` → Import.
3. It starts by itself. Watch the **Console** tab for
   `Crumbs HUD v5.22.9` — that means it's up.
4. **Lock in a permanent key** (do this once — otherwise the write key is
   random on every restart and your bookmark breaks):
   - Sidebar → **Tools** → **Secrets** → new secret.
   - Name: `CRUMBS_SHARE_KEY` — value: a passphrase you invent
     (e.g. four random words). This is yours alone; it never leaves Replit.
   - **Stop** the repl, then **Run** again so the key takes effect.
5. Open the preview in a new tab (the "open in new tab" icon on the
   webview). The address looks like
   `https://crumbs-world.<yourname>.replit.app` — add your key to it:
   `https://crumbs-world.<yourname>.replit.app/?key=YOUR-PASSPHRASE`
6. In Safari: **Share → Add to Home Screen**. That's your Crumbs app now.

## Daily use

- Open it from the Home Screen. If the repl slept, it wakes in a few
  seconds — give it a moment, then reload.
- Updates: **Menu → Check for updates** in the HUD installs the new build
  and restarts by itself (your write key unlocks it; strangers can't).
- Your maps, tiles, and backups live in the repl's workspace and persist
  across sleeps and restarts. They're yours — never in the git repo.

## Don't

- Don't use Replit's **Deploy** button for this: deployments get an
  ephemeral disk, so your map saves would vanish on restart. The workspace
  repl is the one that keeps your stuff.
- Don't share the `?key=` URL — anyone with it can edit your dungeon.

## Project files

- `crumbs_hud.py`: HTTP server and persistence endpoints
- `crumbs_core.py`: map engine
- `crumbs_recovery.py`: recovery/audit engine
- `editor.html`: browser interface
- `shared_library.json` + `shared_library/`: the default tile library
  (curated starter pack; the full Utumno sheet stays dormant)
- Map edits autosave to `hud_map.json` when the editor is dirty.
