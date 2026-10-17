CRUMBS HUD v1.8 — touch tile painter for dungeon maps
=====================================================

THE EASY WAY:

  Mac:  double-click  start_mac.command
        Your browser opens the map painter by itself. That's it.

  Windows (email blocks the one-click launcher, so two quick steps):
    1. Install Python 3: https://www.python.org/downloads/
       (tick "Add python.exe to PATH" during install)
    2. Extract this zip. Open the extracted folder, type  cmd  in the
       folder's address bar, press Enter (a terminal opens there).
    3. Run:  py crumbs_hud.py
       Your browser opens the map painter by itself. That's it.

IF THAT DOESN'T WORK:

  1. Install Python 3: https://www.python.org/downloads/
     (Windows: tick "Add python.exe to PATH" during install)
  2. Open a terminal IN this folder and run:
       python3 crumbs_hud.py
     (Windows:  py crumbs_hud.py)
  3. Open your browser to:  http://127.0.0.1:8778

ON AN IPHONE (needs the free a-Shell app):

  1. Copy this folder into a-Shell (via the Files app).
  2. In a-Shell, go to the folder and run:
       python3 crumbs_hud.py
  3. In Safari open:  http://127.0.0.1:8778
     Tip: Share -> Add to Home Screen gives you a one-tap icon.
     Note: iOS freezes apps in the background — if the page stops
     responding, pop back into a-Shell, restart the script, reload.
     The Setup drawer has a Stop server button that ends the server
     cleanly and returns your terminal prompt.

SHARE FROM YOUR PHONE (your friend needs nothing installed):

  1. On your phone, in this folder, run:
       python3 crumbs_hud.py --public
     The server prints:
       - Friend URL (read-only), and
       - Builder URL with ?key=... (required for edits/saves/deletes)
  2. Both devices on the same Wi-Fi.
  3. Your friend opens the Friend URL in any browser to view/play.
     Anyone editing must use the Builder URL (or send X-Crumbs-Key).
  Notes: iOS may ask a-Shell for Local Network permission — allow it.
  Keep a-Shell in the foreground while sharing. Anyone on the Wi-Fi
  can open it, so only use --public on networks you trust.
  Optional: set your own key with
    python3 crumbs_hud.py --public --share-key=YOURKEY

WHAT'S INSIDE:

  crumbs_hud.py      the server (this is what you run)
  editor.html        the page it serves (don't open this directly)
  crumbs_core.py     map engine (required, keep next to crumbs_hud.py)
  sprite_library.json  sprite list (required)
  asset_library/     starter sprite art
  vault_map.txt      starter map
  start_mac.command  double-click launcher for Mac

HOW TO USE:

  Pick a tile color (or a sprite), paint on the grid with your
  finger/mouse. Layers: Tiles, Objects, Collision. Press Play,
  then tap a tile to walk the little hero there. The Move button
  pans the map instead of painting (+/- zoom, Fit re-fits).
  It autosaves every 30 seconds. Undo/redo included.

Made for Lloyd's Crumbs Vault dungeon game.
