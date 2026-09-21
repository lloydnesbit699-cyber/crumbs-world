#!/usr/bin/env python3
"""
Crumbs HUD — touch-friendly web tile painter for the Crumbs Vault dungeon editor.

Serves editor.html and a small JSON API backed by crumbs_core (headless engine).
Stdlib only — no pip installs. GUI-free model logic lives in crumbs_core.py.

v1.1 (2026-09-18): playtest mode (tap-to-walk hero, BFS over collision layer),
server autosave every 30s, /api/status, empty-palette paint guard.
v1.2 (2026-09-18): sprite support — /api/sprites lists image/animation tiles,
/api/thumb/<id> serves PNG thumbnails, starter art pack (hero_hood, logo_rata,
palette, portrait).
v1.3 (2026-09-18): remote JS debugging — POST /api/jslog prints page errors
to the server terminal; editor.html shows them on-page too.
v1.4 (2026-09-18): freeze-proofing — server swallows BrokenPipeError noise;
page retries failed fetches 3x so brief iOS freezes heal themselves.
v1.5 (2026-09-18): compact phone layout — setup controls collapse into a
drawer, tighter buttons on narrow screens, map auto-fits the screen width;
render() no longer crashes when thumbnails load before the map data.
v1.6 (2026-09-18): shareable — server auto-opens the browser on desktop;
added double-click launchers (Mac/Windows) and a plain-English README.
v1.7 (2026-09-18): camera — Move button toggles pan mode (drag moves the
map instead of painting); -/+ zoom, Fit re-fits the screen.
v1.8 (2026-09-18): Stop server button in the Setup drawer — saves dirty
work, shuts the server down, and returns the a-Shell prompt.
v1.9 (2026-09-18): --public flag — serve on the Wi-Fi network so a friend
can open the HUD in their browser with no downloads; banner prints the
phone's Wi-Fi address.
v2.0 (2026-09-18): map-first phone layout — the map owns the whole screen;
tile palette and tools live in sliding edge trays, actions in a top-bar
dropdown menu, setup in a bottom sheet; zoom controls float over the map.
v2.1 (2026-09-18): two-finger gestures on the map — drag with two fingers
to pan, pinch to zoom, both at once; one finger keeps painting.
v2.2 (2026-09-18): transform-based camera — the map is positioned with a
transform offset instead of container scrolling, so panning works
identically at every zoom level; pinch zooms anchor at the fingers.
v2.3 (2026-09-18): resize() now preserves the overlapping map instead of
wiping it (fixed in crumbs_core and vaults_editor); save UI split into
explicit Save / Save As / Load in the header menu, with a Load bottom sheet
and a read-only current-map label in Setup.
v2.4 (2026-09-18): pinch zoom quantized to whole-pixel steps — at 64x64 every
fractional zoom change was redrawing all 4096 tiles per pointer move and
freezing the map; now it only redraws when the size actually changes.
v2.5 (2026-09-18): fixed TILES/TOOLS trays never opening — the ID selector
for the hidden position was beating the .open rule (CSS specificity).
v3.0 (2026-09-18): custom tiles — import PNGs from the page, pick a function
preset (wall/floor/water/door/decor, collision baked in); multi-frame import
= animated tiles (tray previews + map animate, redraws only on frame change);
custom tiles live in the TILES tray for select-and-place; play mode walks the
hero as a sprite with collision respected.
v5.6 (2026-09-19): MVP finish — server event log (/api/log), one-tap map
validator (/api/validate), PNG export (/api/export/png), map thumbnails
(/api/map/thumb), map management (rename/duplicate/delete-to-trash/import/
metadata), play-session save slots (/api/slots*).
v5.7 (2026-09-19): speed-run batch — Generate busy indicator (button
disables + "generating…" toast so slow 64x64 builds never look dead);
top-bar menu scrolls within the viewport (Stop server reachable again);
bottom sheet capped at 60dvh with internal scroll; linked collision
stamps are atomic — /api/stroke takes link_cells in one call and pushes
a single MultiCommand, so undo/redo move tiles+collision together.
v5.8 (2026-09-19): synthesized sound effects — Web Audio engine, zero
audio files: UI blips, throttled brush ticks, generate whoosh, undo/redo
sweeps, save chirp, error buzz, NPC simlish-style mumbles (tap a placed
character), bird chirps, water splash, looped wind ambience. Setup sheet
gains Sound: mute, volume slider, wind toggle, demo button; choices
persist in localStorage.
v5.9 (2026-09-20): curated starter tile pack — 92 hand-picked Project Utumno
(CC0) cells packed into one shared_library/starter_pack.png strip, registered
as pack "starter" (ids 70000+). The full 6,038-cell Utumno library stays in
shared_library.json but is opt-in (ENABLE_FULL_UTUMNO); the palette opens on
the Starter pack only, so the app is fun immediately. Starter tiles are
built-in: the delete/scope endpoints refuse them (they share one strip).
v5.10 (2026-09-20): height/elevation system — every tile has a numeric
height (deep water -2 < water -1 < plains 0 < hills 1 < mountains 2; walls
stand +1). Per-tile height is editable in the tile panel. Height drives
soft shadows, scaled 2.5D tall faces, climb movement costs, cliff blocking
(can't step up more than one level), line of sight (/api/visibility powers
a play-mode 👁 fog-of-war toggle), and a ⛰ height overlay. Starter pack
grows to 100 with 4 hills + 4 mountains.
v5.16 (2026-09-20): the sellable-build pass —
- public-mode security: --share-key= write token for writes (a random key
  is generated when you share without one), Content-Type + Origin/Host
  checks on POSTs, per-IP rate limits, JSON/bundle/image size caps,
  hardened image uploads;
- backup/restore: /api/backups lists .backup files, /api/restore rolls a
  map or sidecar back; corrupt sidecars are quarantined, never fatal;
- schema versioning: SCHEMA_VERSION stamped on saves, migrations run on
  load, bundles refuse (with a clear message) when they need a newer app;
- sellable outputs: /api/export/tiled (Tiled JSON) + /api/export/tileset.png,
  shareable .crumbs.zip map bundles (/api/bundle/export + /api/bundle/import),
  template starter maps, deterministic generation presets (/api/generate
  takes preset=, /api/generation-presets lists them);
- entitlement-aware art packs: *.pack.json may declare "entitlement":
  "paid"; paid packs load only when entitlements.json grants them.

Run:   python3 crumbs_hud.py
Open:  http://127.0.0.1:8778   (same phone's browser)
"""
import json
import io
import glob
import hmac
import os
import base64
import copy
import hmac
import random
import re
import secrets
import socket
import shutil
import ssl
import sys
import threading
import time
import heapq
import zipfile
import urllib.request
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import crumbs_core as core

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", 8778))  # v1.9: $PORT for cloud hosts
APP_VERSION = "5.21.8"

# ---- v5.18: in-app self-update -------------------------------------------------
# Lloyd's rule: updates overwrite the old files in place — no more downloading a
# suffixed copy and renaming it by hand. Menu -> Check for updates pulls the
# latest editor.html / crumbs_hud.py / crumbs_core.py from the repo's main
# branch and swaps them in atomically, keeping one .update-backup of each.
# v5.21: honest errors (which leg failed + fix hint), auto-certifi for a-Shell's
# missing CA certs, changelog in the update dialog, save-before-update, and
# File -> Roll back update to undo an install.
UPDATE_REPO = "lloydnesbit699-cyber/crumbs-world"
UPDATE_BRANCH = "main"
UPDATE_FILES = ["editor.html", "crumbs_hud.py", "crumbs_core.py"]

def _update_ssl_context():
    # v5.21: a-Shell's Python ships without CA certificates, so HTTPS to
    # GitHub fails verification out of the box. If certifi is installed
    # (pip install certifi) its bundle is used automatically — no env vars.
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile:
        try:
            import certifi
            cafile = certifi.where()
        except ImportError:
            cafile = None
    return ssl.create_default_context(cafile=cafile)


def _update_fetch(name, tries=2):
    # v5.21.2: cache-buster — raw.githubusercontent.com is a CDN whose edge
    # nodes can serve a stale copy for a while after a push (this exact
    # thing bit a phone install of v5.21.1). A unique query string makes
    # every fetch miss the cache and hit origin instead.
    url = (f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}/{name}"
           f"?t={int(time.time())}")
    req = urllib.request.Request(url, headers={"User-Agent": "crumbs-hud-updater"})
    ctx = _update_ssl_context()
    last = None
    for _ in range(max(1, tries)):
        try:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1)
    raise last


def _update_hint(e):
    # v5.21: the check/apply errors say which leg failed; the hint says the fix.
    n = e.__class__.__name__
    s = str(e).lower()
    if "ssl" in n or "certificate" in s:
        return "in a-Shell run: pip install certifi — then restart the server"
    if "urlerror" in n or "nodename" in s or "name resolution" in s:
        return "is the phone online? raw.githubusercontent.com must be reachable"
    if "timeout" in n or "timed out" in s:
        return "GitHub timed out — try again in a bit"
    return ""


def _update_can_rollback():
    # v5.21: an update is undoable while its .update-backup files survive.
    return any(os.path.exists(os.path.join(SCRIPT_DIR, n + ".update-backup"))
               for n in UPDATE_FILES)


def _update_disk_version():
    # v5.21.5: what version do the files ON DISK say? If the disk is newer
    # than the running server, an update was installed but the server was
    # never restarted — the check should say "restart", not offer install.
    try:
        with open(os.path.join(SCRIPT_DIR, "crumbs_hud.py"), "rb") as f:
            # APP_VERSION lives near the top, but the header comment block
            # has long lines — 16KB comfortably covers it.
            m = re.search(br'^APP_VERSION\s*=\s*"([^"]+)"', f.read(16384), re.M)
        return m.group(1).decode() if m else None
    except OSError:
        return None


def _update_install(blobs):
    # v5.21.5: shared installer — sanity-checks, version-guards, and
    # atomically swaps a {name: bytes} bundle. Used by /api/update/apply
    # (the server downloads) and /api/update/apply-blobs (the page
    # downloads; the browser stays in the foreground, so iOS can't freeze
    # it mid-file the way it freezes a-Shell).
    # v5.21: sanity-check the downloads before swapping — a truncated
    # file must never replace a good one.
    bad = [n for n, b in blobs.items()
           if not b
           or (n == "crumbs_hud.py" and b"APP_VERSION" not in b)
           or (n == "editor.html" and b"<html" not in b.lower())
           or (n == "crumbs_core.py"
               and b"def " not in b and b"class " not in b)]
    if bad:
        return {"ok": False, "leg": "github",
                "error": f"downloaded {', '.join(bad)} looked wrong — old files untouched, try again"}
    # v5.21.2: the download must actually be NEWER than this build.
    # The check may have seen a fresh version while the file fetch
    # hit a stale CDN edge — installing that would be a downgrade,
    # so refuse it and leave the old files alone.
    m = re.search(br'^APP_VERSION\s*=\s*"([^"]+)"', blobs["crumbs_hud.py"], re.M)
    dl_version = m.group(1).decode() if m else None
    if not dl_version or not _ver_tuple(dl_version) > _ver_tuple(APP_VERSION):
        return {"ok": False, "leg": "github",
                "error": f"GitHub served a stale copy (v{dl_version or 'unreadable'}) — old files untouched, try again in a bit"}
    updated = []
    try:
        for n, blob in blobs.items():
            p = os.path.join(SCRIPT_DIR, n)
            if os.path.exists(p):
                shutil.copy2(p, p + ".update-backup")
            tmp = p + ".update-tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, p)  # atomic: the same name just gets the new bytes
            updated.append(n)
    except OSError as e:
        return {"ok": False, "error": f"write failed ({e}) — backups kept"}
    return {"ok": True, "updated": updated,
            "can_rollback": True,
            "note": "restart the server to run the new build"}


def _ver_tuple(v):
    # v5.21: "5.18.1" -> (5, 18, 1); garbage -> (0,) so it never looks newer.
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def _update_changelog(current, limit=5):
    # v5.21: newest-first CHANGELOG.md sections strictly newer than
    # `current`, for the update dialog — Lloyd decides with the notes in
    # front of him.
    raw = _update_fetch("CHANGELOG.md").decode("utf-8", "replace")
    entries, cur = [], None
    cur_v = _ver_tuple(current)

    def flush():
        if cur and _ver_tuple(cur["version"]) > cur_v and len(entries) < limit:
            entries.append(cur)

    for line in raw.splitlines():
        m = re.match(r"##\s+v([\d.]+)\s*(?:[—–-]\s*(.*))?$", line.strip())
        if m:
            flush()
            if len(entries) >= limit:
                break
            # Newest-first: once we reach our own version (or anything
            # older), nothing below it can be newer.
            if _ver_tuple(m.group(1)) <= cur_v:
                cur = None
                break
            cur = {"version": m.group(1), "date": (m.group(2) or "").strip(),
                   "notes": []}
        elif cur is not None:
            cur["notes"].append(line)
    flush()
    for e in entries:
        e["notes"] = "\n".join(e["notes"]).strip()
        if len(e["notes"]) > 1200:
            e["notes"] = e["notes"][:1200] + "…"
    return entries

def _update_remote_version():
    raw = _update_fetch("crumbs_hud.py").decode("utf-8", "replace")
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', raw, re.M)
    return m.group(1) if m else None
SCHEMA_VERSION = 1  # v5.16: stamped on every save; migrations run on load
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(SCRIPT_DIR, "editor.html")
DEFAULT_SAVE = "hud_map.json"
LAYERS = ("tiles", "objects", "collision")
PUBLIC_MODE = False
PUBLIC_WRITE_KEY = ""
WRITE_KEY_HEADER = "X-Crumbs-Key"
WRITE_KEY_QUERY = "key"

# ---- v5.16: abuse guards (rate limits, size caps) ---------------------------
# PUBLIC_MODE / PUBLIC_WRITE_KEY are set in __main__ (--public / --share-key= / $CRUMBS_SHARE_KEY).
MAX_JSON_BYTES = 64 * 1024 * 1024   # JSON bodies; base64 inflates bundles
                                  # ~4/3, and the decoded zip is still capped
                                  # at MAX_BUNDLE_BYTES below
MAX_BUNDLE_BYTES = 48 * 1024 * 1024  # .crumbs.zip bundle imports
MAX_IMAGE_DIM = 2048                 # per-side cap on uploaded tile art
MAX_IMAGE_PIXELS = 2048 * 2048
# per-IP sliding-window rate limits: (max hits, window seconds)
_RL_POST = (120, 60)
_RL_GET = (600, 60)
_rl_buckets = {}
_rl_lock = threading.Lock()


def _rate_ok(kind, ip):
    """Tiny in-memory token bucket. Generous for a human, stops floods."""
    limit, window = _RL_POST if kind == "POST" else _RL_GET
    now = time.monotonic()
    with _rl_lock:
        arr = [t for t in _rl_buckets.get((kind, ip), []) if now - t < window]
        if len(arr) >= limit:
            _rl_buckets[(kind, ip)] = arr
            return False
        arr.append(now)
        _rl_buckets[(kind, ip)] = arr
        return True

# ---- v3.0: custom imported tiles -------------------------------------------
CUSTOM_DIR = os.path.join(SCRIPT_DIR, "custom_tiles")
CUSTOM_REG = os.path.join(SCRIPT_DIR, "custom_tiles.json")
# v3.8: the shared shelf — imported tiles published for everyone.
# TRACKED in git (unlike custom_tiles/): a pull delivers them everywhere.
SHARED_DIR = os.path.join(SCRIPT_DIR, "shared_library")
SHARED_REG = os.path.join(SCRIPT_DIR, "shared_library.json")
CUSTOM_MAX_FRAMES = 8
CUSTOM_MAX_FILE_CHARS = 1500000  # ~1.1MB per frame dataURL

# preset definitions: what each tile IS and what it DOES (collision baked in)
# v3.1: height feeds the depth-cue renderer (tall walls get an extruded face)
TILE_PRESETS = {
    # v5.10: height is numeric now — deep water -2 < water -1 < plains 0
    # < hills 1 < mountains 2. Drives shadows, tall faces, movement cost,
    # climb blocking, line of sight, and the height overlay.
    "wall":  {"label": "Wall",  "hint": "solid, stands +1", "solid": True,  "height": 1},
    "floor": {"label": "Floor", "hint": "walkable", "solid": False, "height": 0},
    "water": {"label": "Water", "hint": "swim — slow", "solid": False, "height": -1,
              "swim": True},
    # v3.6: deep water — impassable WITHOUT the swim animation. Passable WITH
    # it once SWIM_UNLOCKED flips (see the SWIM HOOK below). Shallow water's
    # ripple wading is untouched.
    "deepwater": {"label": "Deep water", "hint": "needs swim", "solid": True,
                  "height": -2, "deep": True},
    "door":  {"label": "Door",  "hint": "walkable", "solid": False, "height": 0},
    "decor": {"label": "Decor", "hint": "walkable", "solid": False, "height": 0},
    "character": {"label": "Character", "hint": "walkable sprite", "solid": False,
                  "height": 0},
    "hill":  {"label": "Hill",  "hint": "walkable, slow climb", "solid": False,
              "height": 1},
    "mountain": {"label": "Mountain", "hint": "tall, blocking", "solid": True,
                  "height": 2},
}


def _norm_height(entry):
    """v5.10: registry height is an int. Migrates the old "tall"/"short"
    strings and missing values to the preset default."""
    h = entry.get("height", None)
    if isinstance(h, int):
        return max(core.HEIGHT_MIN, min(core.HEIGHT_MAX, h))
    if h == "tall":
        return 1
    return TILE_PRESETS.get(entry.get("preset", "decor"), {}).get("height", 0)

_custom_tiles = []  # registry mirror: [{id,name,preset,solid,frame_ms,files,scope}]
_shared_tiles = []  # v3.8: the shared shelf — same shape, scope="shared"
_shared_skipped = []  # v5.9: registry entries kept on disk but NOT registered (opt-in full library)
# v5.9: the full 6,038-cell Utumno library ships in shared_library.json but stays
# dormant — only the curated "starter" pack (plus local imports) loads into the
# palette. Flip to True (or ship a build with it True) to restore the full shelf.
ENABLE_FULL_UTUMNO = False


def _custom_public(entry):
    return {"id": entry["id"], "name": entry["name"], "preset": entry["preset"],
            "solid": entry["solid"], "height": _norm_height(entry),
            "swim": bool(entry.get("swim", False)),
            "deep": bool(entry.get("deep", False)),
            "scope": entry.get("scope", "local"),
            "pack": entry.get("pack"),
            "frames": len(entry["files"]), "frame_ms": entry["frame_ms"]}


def _find_custom(tid):
    """v3.8: find an imported tile on either shelf -> (entry, scope)."""
    for e in _custom_tiles:
        if int(e["id"]) == tid:
            return e, "local"
    for e in _shared_tiles:
        if int(e["id"]) == tid:
            return e, "shared"
    return None, None


def _save_custom_registry(scope="local"):
    path = SHARED_REG if scope == "shared" else CUSTOM_REG
    tiles = _shared_tiles if scope == "shared" else _custom_tiles
    # v5.14: drop-in art packs live in their *.pack.json — never merge them here.
    tiles = [t for t in tiles if not t.get("_from_pack")]
    if scope == "shared":
        # v5.9: keep dormant full-library entries in the JSON so they are not
        # wiped by a rewrite — they just stay unregistered until opted in.
        tiles = list(tiles) + list(_shared_skipped)
    try:
        # v5.2: preserve top-level metadata (e.g. "packs") across rewrites
        try:
            doc = json.load(open(path))
            if not isinstance(doc, dict):
                doc = {}
        except Exception:
            doc = {}
        doc["tiles"] = tiles
        with open(path, "w") as f:
            json.dump(doc, f)
    except Exception as e:
        print(f"[hud] could not save {scope} tile registry: {e}")


def _register_custom_tile(entry, tile_dir):
    """Load a registry entry's PNGs and register it as a first-class asset tile,
    so collision, thumbnails and play-mode pathfinding all work with it."""
    frames = []
    for fn in entry["files"]:
        p = os.path.join(tile_dir, fn)
        if os.path.exists(p):
            frames.append(core.Image.open(p).convert("RGBA"))
    if not frames:
        return False
    # v5.9: starter-pack entries name a cell of a packed 32px strip — crop it.
    if "cell" in entry:
        ci = int(entry["cell"])
        strip = frames[0]
        frames = [strip.crop((ci * 32, 0, (ci + 1) * 32, 32)).copy()]
    tid = int(entry["id"])
    # v5.10: numeric height, migrated once — the registry saves back normalized.
    entry["height"] = _norm_height(entry)
    assets.add_tile(tid, "custom", {
        "name": entry["name"],
        "category": "custom",
        "preset": entry.get("preset", "decor"),
        "height": entry["height"],
        "frames": frames,
        "frame_ms": int(entry.get("frame_ms", 400)),
    })
    assets.tiles[tid]["properties"]["height"] = entry["height"]
    assets.tiles[tid]["properties"]["solid"] = bool(entry.get("solid", False))
    # v3.2: swim flag — water tiles slow the hero instead of blocking
    swim = bool(entry.get("swim", False))
    if entry.get("preset") == "water":
        # v3.2 migration: water used to be solid; now it's swimmable
        assets.tiles[tid]["properties"]["solid"] = False
        entry["solid"] = False
        swim = True
        entry["swim"] = True
    assets.tiles[tid]["properties"]["swim"] = swim
    # v3.6: deep-water flag — solid (blocking) until SWIM_UNLOCKED flips
    deep = bool(entry.get("deep", False)) or entry.get("preset") == "deepwater"
    if deep:
        assets.tiles[tid]["properties"]["solid"] = True
        assets.tiles[tid]["properties"]["deep"] = True
        entry["solid"] = True
        entry["deep"] = True
    else:
        assets.tiles[tid]["properties"]["deep"] = False
    return True


def _load_custom_tiles():
    """Re-register imported tiles at startup — this device's shelf plus the
    shared shelf. Entries without a scope predate v3.8 and are local."""
    for d in (CUSTOM_DIR, SHARED_DIR):
        os.makedirs(d, exist_ok=True)
    if not core.PIL_AVAILABLE:
        return
    for reg_path, tile_dir, store, scope in (
            (CUSTOM_REG, CUSTOM_DIR, _custom_tiles, "local"),
            (SHARED_REG, SHARED_DIR, _shared_tiles, "shared")):
        if not os.path.exists(reg_path):
            continue
        try:
            reg = json.load(open(reg_path))
        except Exception as e:
            print(f"[hud] {scope} tile registry unreadable: {e}")
            continue
        for entry in reg.get("tiles", []):
            try:
                entry["scope"] = scope
                # v5.9: full Utumno library is opt-in — keep its entries on disk
                # but out of memory and out of the palette until enabled.
                if (scope == "shared" and not ENABLE_FULL_UTUMNO
                        and entry.get("pack") == "utumno"):
                    _shared_skipped.append(entry)
                    continue
                if _register_custom_tile(entry, tile_dir):
                    store.append(entry)
            except Exception as e:
                print(f"[hud] skipping {scope} tile {entry.get('id')}: {e}")
    # v5.14: drop-in art packs — any *.pack.json in custom_tiles/ loads
    # additively. Pack entries are never merged into custom_tiles.json, so
    # deleting the pack files uninstalls the pack cleanly.
    n_pack = 0
    # v5.16: paid packs load only when entitlements.json grants them.
    granted = _load_entitlements()
    for pack_path in sorted(glob.glob(os.path.join(CUSTOM_DIR, "*.pack.json"))):
        try:
            doc = json.load(open(pack_path))
        except Exception as e:
            print(f"[hud] art pack unreadable {pack_path}: {e}")
            continue
        pack_name = (doc.get("name")
                     or os.path.basename(pack_path)[:-len(".pack.json")])
        if doc.get("entitlement", "free") == "paid" \
                and pack_name not in granted:
            print(f"[hud] art pack '{pack_name}' is paid and not entitled "
                  "— skipped")
            continue
        for entry in doc.get("tiles", []):
            try:
                entry["scope"] = "local"
                entry["_from_pack"] = True
                if _register_custom_tile(entry, CUSTOM_DIR):
                    _custom_tiles.append(entry)
                    n_pack += 1
            except Exception as e:
                print(f"[hud] skipping pack tile {entry.get('id')}: {e}")
    if _custom_tiles or _shared_tiles:
        print(f"[hud] loaded {len(_custom_tiles)} local + {len(_shared_tiles)} shared tile(s) ({n_pack} from art packs)")
    _save_custom_registry("local")   # v3.2: persist water→swim migrations, if any
    _save_custom_registry("shared")


# ---- v3.3: one-button animation ("Make it move") ------------------------------
def _divisor_frames(img):
    """Last-resort split for edge-to-edge sheets with no detectable gaps.
    Only fires when the shape clearly says 'strip' (much wider than tall);
    anything else comes back as one picture — a wrong split is worse than
    asking the user for a gapped sheet."""
    w, h = img.size
    if w < 1.8 * h:
        return [img]
    for n in range(8, 1, -1):
        if w % n:
            continue
        if h * 0.5 <= w / n <= h * 2.0:
            fw = w // n
            return [img.crop((c * fw, 0, (c + 1) * fw, h))
                    for c in range(n)][:CUSTOM_MAX_FRAMES]
    return [img]


def _autoslice_pil(img):
    """Split one picture into animation poses. Transparent gaps or a solid
    background color mark the cuts; otherwise try even splits."""
    img = img.convert("RGBA")
    if max(img.size) > 256:
        img.thumbnail((256, 256), core.Image.Resampling.NEAREST)
    w, h = img.size
    px = img.load()
    corners = (px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1])
    if all(c[3] == 0 for c in corners):
        def empty(p): return p[3] == 0
    elif len({(c[0], c[1], c[2]) for c in corners}) == 1:
        bg = (corners[0][0], corners[0][1], corners[0][2])

        def empty(p): return (p[0], p[1], p[2]) == bg
    else:
        return _divisor_frames(img)

    def bands(flags):
        out, i = [], 0
        n = len(flags)
        while i < n:
            if not flags[i]:
                j = i
                while j < n and not flags[j]:
                    j += 1
                out.append((i, j))
                i = j
            else:
                i += 1
        return out

    row_empty = [all(empty(px[x, y]) for x in range(w)) for y in range(h)]
    col_empty = [all(empty(px[x, y]) for y in range(h)) for x in range(w)]
    rb, cb = bands(row_empty), bands(col_empty)
    if not (len(cb) >= 2 and rb):
        return _divisor_frames(img)
    frames = []
    for (y0, y1) in rb:
        for (x0, x1) in cb:
            cell = img.crop((x0, y0, x1, y1))
            cw, ch = cell.size
            cpx = cell.load()
            if all(empty(cpx[x, y]) for y in range(ch) for x in range(cw)):
                continue  # stray blank cell
            frames.append(cell)
            if len(frames) >= CUSTOM_MAX_FRAMES:
                break
        if len(frames) >= CUSTOM_MAX_FRAMES:
            break
    return frames or _divisor_frames(img)


def _walkbob_frames(img):
    """v3.4: fake a walk from one front-facing picture — bob + sway offsets.
    Four frames: plant, lift+lean, plant, lift+lean the other way."""
    img = img.convert("RGBA")
    if max(img.size) > 256:
        img.thumbnail((256, 256), core.Image.Resampling.NEAREST)
    w, h = img.size
    bob = max(2, h // 16)     # ~6% vertical bounce — reads at any draw size
    sway = max(1, w // 32)    # ~3% side sway
    frames = []
    for dx, dy in ((0, 0), (sway, -bob), (0, 0), (-sway, -(bob // 2))):
        cell = core.Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cell.paste(img, (dx, dy), img)
        frames.append(cell)
    return frames


def _body_scope(body):
    """v3.8: import shelf — 'shared' publishes to the shared library, anything
    else stays on this device."""
    return "shared" if body.get("scope") == "shared" else "local"


def _store_custom_tile(name, preset, frame_ms, pil_images, scope="local"):
    """Write PIL frames to the right shelf (this device / shared), register the
    tile, save that shelf's registry. Returns the entry. Rolls back partial
    writes on failure."""
    tile_dir = SHARED_DIR if scope == "shared" else CUSTOM_DIR
    store = _shared_tiles if scope == "shared" else _custom_tiles
    tid = assets._next_id()
    files = []
    try:
        for i, im in enumerate(pil_images):
            im = im.convert("RGBA")
            if max(im.size) > 256:
                im.thumbnail((256, 256), core.Image.Resampling.NEAREST)
            fn = f"{tid}_f{i}.png"
            im.save(os.path.join(tile_dir, fn), "PNG")
            files.append(fn)
    except Exception:
        for fn in files:
            try:
                os.remove(os.path.join(tile_dir, fn))
            except OSError:
                pass
        raise
    entry = {"id": tid, "name": name, "preset": preset,
             "solid": TILE_PRESETS[preset]["solid"],
             "height": TILE_PRESETS[preset]["height"],
             "swim": bool(TILE_PRESETS[preset].get("swim", False)),
             "deep": bool(TILE_PRESETS[preset].get("deep", False)),
             "frame_ms": frame_ms, "files": files, "scope": scope}
    store.append(entry)
    _register_custom_tile(entry, tile_dir)
    _save_custom_registry(scope)
    return entry

# ---- v3.4: patrol routes ----------------------------------------------------
PATROL_SAVE = os.path.join(SCRIPT_DIR, "hud_patrols.json")
_patrols = []          # [{id, tile_id, points: [[x, y], ...]}]
_patrol_seq = {"next": 1}


def _save_patrols():
    try:
        with open(PATROL_SAVE, "w") as f:
            json.dump(_stamp({"patrols": _patrols, "next": _patrol_seq["next"]}), f)
    except Exception as e:
        print(f"[hud] could not save patrols: {e}")


# ---- v5.12: Melody's mission workshop ---------------------------------------
# She designs missions from presets + a short questionnaire, builds the enemy
# flows the difficulty calls for, and playtests every objective herself.
_missions = []          # [{id,name,preset,difficulty,reward,objectives,
                        #   hazard_count,active,won,placed,danger}]
_mission_seq = {"next": 1}
mission_run = None      # live run state while play mode is active


# ---- v5.16: schema versioning + corrupt-sidecar recovery ---------------------
# Every sidecar save is stamped {"schema": SCHEMA_VERSION}. On load, older
# docs are migrated forward; docs newer than this build refuse with a clear
# message; corrupt JSON is quarantined (never fatal, never silently lost).


def _stamp(doc):
    """Stamp the data-schema version on a sidecar doc before saving."""
    doc["schema"] = SCHEMA_VERSION
    return doc


def _migrate_sidecar(kind, doc):
    """Bring a sidecar doc up to SCHEMA_VERSION. Returns the doc, or a
    {"error": ...} dict when the doc needs a newer app than this one."""
    if not isinstance(doc, dict):
        return {}
    v = doc.get("schema", 0)
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = 0
    if v > SCHEMA_VERSION:
        return {"error": "needs newer Crumbs",
                "detail": f"this {kind} file was written by schema {v}; "
                          f"this build understands schema {SCHEMA_VERSION}. "
                          "Update the app to open it."}
    if v < 1:
        # v0 -> v1: nothing structural changed; stamp and fill the keys
        # each loader already defaults, so just record the migration.
        doc["schema"] = 1
        doc["_migrated_from"] = v
    return doc


def _quarantine(path, exc):
    """Move a corrupt sidecar aside with a timestamp; never delete data."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = f"{path}.corrupt-{stamp}"
    try:
        os.replace(path, dest)
    except OSError:
        dest = path + " (rename failed)"
    _log_event(f"quarantined corrupt {os.path.basename(path)} -> "
               f"{os.path.basename(dest)}: {exc}")
    print(f"[hud] quarantined corrupt {path}: {exc}")
    return dest


def _load_json_file(path, kind, default):
    """Load a JSON sidecar: migrate old schemas, quarantine corrupt files.

    Returns (doc, error). error is None on success (fresh or migrated);
    on a too-new schema, doc is {} and error names the problem.
    """
    try:
        with open(path) as f:
            doc = json.load(f)
    except FileNotFoundError:
        return default, None
    except ValueError as e:  # corrupt JSON — quarantine, start fresh
        _quarantine(path, e)
        return default, None
    except OSError as e:
        print(f"[hud] could not read {path}: {e}")
        return default, None
    doc = _migrate_sidecar(kind, doc)
    if isinstance(doc, dict) and doc.get("error"):
        return {}, doc
    return doc if isinstance(doc, dict) else default, None


def _load_entitlements():
    """Pack names this device is granted (entitlements.json is user data,
    gitignored — the storefront that sells grants is a Later item)."""
    try:
        d = json.load(open(os.path.join(SCRIPT_DIR, "entitlements.json")))
        packs = d.get("packs", [])
        return set(packs) if isinstance(packs, list) else set()
    except (OSError, ValueError):
        return set()


def _pack_catalog():
    catalog, granted = [], _load_entitlements()
    for pack_path in sorted(glob.glob(os.path.join(CUSTOM_DIR, "*.pack.json"))):
        try:
            doc = json.load(open(pack_path))
        except Exception:
            continue
        name = doc.get("name") or os.path.basename(pack_path)[:-len(".pack.json")]
        ent = doc.get("entitlement", "free")
        catalog.append({"pack": name, "entitlement": ent,
                        "granted": ent != "paid" or name in granted,
                        "tiles": len(doc.get("tiles", []))})
    return catalog, granted


def _missions_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".missions.json")


def _load_missions(name):
    global _missions, _mission_seq
    d, err = _load_json_file(_missions_path(name), "missions",
                             {"missions": [], "next": 1})
    if err:
        _log_event(f"missions sidecar: {err['detail']}")
        d = {"missions": [], "next": 1}
    _missions = d.get("missions", [])
    _mission_seq["next"] = d.get("next", len(_missions) + 1)


def _save_missions(name):
    try:
        with open(_missions_path(name), "w") as f:
            json.dump(_stamp({"missions": _missions,
                              "next": _mission_seq["next"]}), f)
    except OSError as e:
        print(f"[hud] could not save missions: {e}")


def _mission_by_id(mid):
    return next((m for m in _missions if m["id"] == mid), None)


# Melody's Tier-0 voice: deterministic lines (picked by mission id so she's
# consistent, not random). Warm, a little playful — Lloyd's kid.
_MELODY_LINES = {
    "built": [
        "Ooh, '{name}' — I like it. {diff} it is.",
        "'{name}' is ready, builder. {diff} — brave choice.",
        "Done! '{name}' is on the board. {diff}, just how you asked.",
    ],
    "tested_ok": [
        "I walked it myself — every mark is reachable. You've got this.",
        "Ran the route as a ghost: all clear. Go get '{name}'.",
        "Playtested and beatable. The {hazards} hazard(s) are the spicy part.",
    ],
    "tested_bad": [
        "Hmm, I tried to run it and got stuck: {issue} Want me to move the mark?",
        "My ghost couldn't finish it — {issue} Let's fix the map first.",
    ],
    "won": [
        "You did it! '{name}' complete! {reward}",
        "'{name}' — cleared! {reward} I'm proud of you, builder.",
    ],
}
_DIFF_WORDS = {1: "Gentle", 2: "Bold", 3: "Brave", 4: "Fierce", 5: "Legend"}


def _melody_says(kind, seed=0, **kw):
    lines = _MELODY_LINES[kind]
    line = lines[seed % len(lines)]
    try:
        return line.format(**kw)
    except (KeyError, IndexError):
        return line


def _mission_enemy_tile():
    """Melody drafts her challengers: mean-looking critters first."""
    pool = [t for t in _shared_tiles + _custom_tiles
            if t.get("preset") == "character"]
    if not pool:
        return None
    prefs = ("spider", "hound", "rat", "imp", "bat", "wolf", "goblin",
             "orc", "snake", "scorpion")
    for want in prefs:
        for t in pool:
            if want in t.get("name", "").lower():
                return t["id"]
    return pool[0]["id"]


def _mission_clear_hazards(mission):
    """Pull this mission's enemy flows off the map."""
    global _patrols
    mid = mission["id"]
    _patrols = [p for p in _patrols if p.get("mission_id") != mid]
    for x, y in mission.get("placed", []):
        if 0 <= x < world.width and 0 <= y < world.height:
            if world.object_layer[y][x] == mission.get("enemy_tile"):
                world.object_layer[y][x] = None
    mission["placed"] = []
    mission["danger"] = []
    _save_patrols()


def _mission_place_hazards(mission):
    """Build the enemy flows this difficulty calls for: hazard patrols near
    the objectives. Returns (placed_count, danger_cells)."""
    _mission_clear_hazards(mission)
    n = mission.get("hazard_count", 0)
    if not n:
        return 0, []
    tid = _mission_enemy_tile()
    if tid is None:
        return 0, []
    mission["enemy_tile"] = tid
    targets = core.mission_target_cells(mission) or [(world.width // 2,
                                                      world.height // 2)]
    rng = random.Random(mission["id"] * 7919 + 13)  # deterministic per mission
    placed, danger = [], set()
    tries = 0
    while len(placed) < n and tries < 60:
        tries += 1
        tx, ty = targets[rng.randrange(len(targets))]
        ax = tx + rng.randint(-4, 4)
        ay = ty + rng.randint(-4, 4)
        if not (0 <= ax < world.width and 0 <= ay < world.height):
            continue
        if not _walkable(ax, ay) or world.object_layer[ay][ax] is not None:
            continue
        if any(abs(ax - px) + abs(ay - py) < 3 for px, py in placed):
            continue
        # route: anchor + 2-3 nearby walkable stops
        pts = [[ax, ay]]
        for _ in range(rng.randint(2, 3)):
            bx, by = pts[-1]
            cands = [(bx + dx, by + dy) for dx, dy in
                     ((1, 0), (-1, 0), (0, 1), (0, -1))]
            cands = [(x, y) for x, y in cands
                     if 0 <= x < world.width and 0 <= y < world.height
                     and _walkable(x, y) and [x, y] not in pts]
            if not cands:
                break
            pts.append(list(rng.choice(cands)))
        if len(pts) < 2:
            continue
        world.object_layer[ay][ax] = tid
        pid = _patrol_seq["next"]
        _patrol_seq["next"] += 1
        _patrols.append({"id": pid, "tile_id": tid, "x": ax, "y": ay,
                         "points": pts, "hazard": True,
                         "mission_id": mission["id"],
                         "map": _current_map})
        placed.append((ax, ay))
        danger.update((x, y) for x, y in pts)
    mission["placed"] = placed
    mission["danger"] = sorted(danger)
    _save_patrols()
    return len(placed), sorted(danger)


def _mission_playtest(mission):
    sx, sy = _find_spawn()
    return core.mission_playtest(
        world, mission, (sx, sy), _walkable,
        lambda ax, ay, bx, by: bool(_find_path(ax, ay, bx, by)[0]))


def _mission_start_run(mission):
    """Snapshot a fresh run when play mode starts."""
    global mission_run
    mission_run = {
        "mission_id": mission["id"],
        "objectives": copy.deepcopy(mission["objectives"]),
        "tick0": _tick_n,
        "inv0": dict(_inv),
        "won": False,
        "failed": False,
    }


def _mission_bump_meters(d_health=0):
    m = world_profile.get("meters", {})
    if m.get("health") and d_health:
        _meters["health"] = max(0, min(10, _meters["health"] + d_health))


def _check_mission(x, y):
    """Per hero step: hazard damage + objective progress. Returns events."""
    global mission_run, _gold
    events = []
    if not mission_run or mission_run["won"] or mission_run["failed"]:
        return events
    mission = _mission_by_id(mission_run["mission_id"])
    if mission is None:
        return events
    danger = {tuple(c) for c in mission.get("danger", [])}
    if (x, y) in danger:
        # v5.13: a drawn weapon keeps hazard ground at bay; a ward charm
        # softens it. Bare hands still bleed.
        w = _equipped_def("weapon")
        if w:
            events.append({"t": "toast",
                           "text": f"🗡️ your {w['name']} keeps them at bay!"})
        else:
            hurt = 1
            tool = _equipped_def("tool")
            if tool and tool.get("effect") == "ward":
                hurt = 0
                events.append({"t": "toast",
                               "text": f"🛡️ your {tool['name']} wards them off!"})
            if hurt:
                _mission_bump_meters(d_health=-hurt)
                _log_event("hazard hit")
                events.append({"t": "toast",
                               "text": "⚠ hazard patrol's ground — ouch!"})
            if _meters.get("health", 10) <= 0:
                mission_run["failed"] = True
                events.append({"t": "message",
                               "text": "The hazards got you… mission failed."})
                return events
    # v5.13: step onto a hazard's own anchor with a weapon drawn and you
    # drive it off the map for good.
    w = _equipped_def("weapon")
    if w:
        for hp in list(_patrols):
            if hp.get("hazard") and hp.get("mission_id") == mission["id"] \
                    and (hp.get("x"), hp.get("y")) == (x, y):
                _patrols.remove(hp)
                et = mission.get("enemy_tile")
                if et is not None and world.object_layer[y][x] == et:
                    world.object_layer[y][x] = None
                mission["danger"] = sorted(
                    {tuple(c) for q in _patrols
                     if q.get("mission_id") == mission["id"]
                     for c in q.get("points", [])})
                _save_patrols()
                _save_missions(_current_map)
                _mark_dirty()
                events.append({"t": "npcs"})  # client rebuilds the walkers
                events.append({"t": "toast",
                               "text": f"⚔️ you drove it off with your "
                                       f"{w['name']}!"})
                _log_event("hazard defeated")
                break
    elapsed = _tick_n - mission_run["tick0"]
    gathered = {k: _inv.get(k, 0) - mission_run["inv0"].get(k, 0)
                for k in ("wood", "food")}
    for o in mission_run["objectives"]:
        if o.get("done") or o.get("failed"):
            continue
        k = o["kind"]
        if k == "reach" and (x, y) == (o["x"], o["y"]):
            o["done"] = True
            events.append({"t": "toast", "text": "📍 waypoint reached!"})
        elif k == "timed":
            o["elapsed"] = elapsed
            if (x, y) == (o["x"], o["y"]):
                o["done"] = True
                events.append({"t": "toast", "text": "⏱ made it in time!"})
            elif elapsed >= o["ticks"]:
                o["failed"] = True
                mission_run["failed"] = True
                events.append({"t": "message",
                               "text": "⏱ out of time… mission failed."})
                return events
        elif k == "collect":
            o["have"] = max(0, gathered.get(o["what"], 0))
            if o["have"] >= o["count"]:
                o["done"] = True
                events.append({"t": "toast",
                               "text": f"🌾 gathered {o['count']} {o['what']}!"})
        elif k == "survive":
            o["elapsed"] = elapsed
            if elapsed >= o["ticks"]:
                o["done"] = True
                events.append({"t": "toast", "text": "❤ survived!"})
    if all(o.get("done") for o in mission_run["objectives"]):
        mission_run["won"] = True
        mission["won"] = True
        _save_missions(_current_map)
        reward = mission.get("reward") or "bragging rights"
        msg = _melody_says("won", mission["id"], name=mission["name"],
                           reward=f"Reward: {reward}.")
        events.append({"t": "message", "text": "🏆 " + msg})
        # v5.13: a number in the reward ("100 gold stars") pays out in coin.
        mg = re.search(r"(\d+)", reward)
        if mg:
            g = min(9999, int(mg.group(1)))
            _gold += g
            events.append({"t": "toast", "text": f"🪙 +{g} gold!"})
        _log_event(f"mission won: {mission['name']}")
    return events


def _mission_run_text():
    if not mission_run:
        return ""
    m = _mission_by_id(mission_run["mission_id"])
    if not m:
        return ""
    tmp = dict(m)
    tmp["objectives"] = mission_run["objectives"]
    txt, _, _ = core.mission_progress_text(tmp)
    return txt


# ---- v5.13: gear — items on the ground, packs on backs, folks in town -------
# Weapons and tools are objects: defined from tiles, dropped on the map,
# picked up into a stacking inventory, equipped on the hero — and stocked
# by merchant NPCs for stores and markets.
_items = []          # [{id,name,tile_id,kind,power,effect,stack,price}]
_item_seq = {"next": 1}
_item_cells = {}     # "x,y" -> [item_id, qty] — the stuff lying on the map
_npcs = []           # [{id,name,tile_id,x,y,role,line,stock:[{item,price,qty}]}]
_npc_seq = {"next": 1}
_hero_inv = []       # [{item, qty}] — this run's pack, stacking
_gold = 25           # this run's coin
_equipped = {"weapon": None, "tool": None}  # item ids, or None
_npc_near = set()    # npc ids the hero is already beside (no repeat hellos)


def _items_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".items.json")


def _npcs_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".npcs.json")


def _gear_path(name):
    # v5.13: the hero's own pack — coin, carried gear, and hands — rides
    # with the map so it survives stop/start. User data, never committed.
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".gear.json")


def _load_gear(name):
    """Fill the hero's pack from this map's gear sidecar (fresh if none)."""
    global _hero_inv, _gold, _equipped
    d, err = _load_json_file(_gear_path(name), "gear",
                             {"inv": [], "gold": 25, "equipped": {}})
    if err:
        _log_event(f"gear sidecar: {err['detail']}")
        d = {"inv": [], "gold": 25, "equipped": {}}
    try:
        _hero_inv = [r for r in d.get("inv", [])
                     if isinstance(r, dict) and _item_by_id(r.get("item"))]
        _gold = max(0, int(d.get("gold", 25)))
        eq = d.get("equipped", {}) or {}
        _equipped = {"weapon": None, "tool": None}
        for slot in ("weapon", "tool"):
            iid = eq.get(slot)
            if iid is not None and _item_by_id(iid):
                _equipped[slot] = iid
    except (TypeError, ValueError):
        _hero_inv, _gold = [], 25
        _equipped = {"weapon": None, "tool": None}
    _npc_near.clear()


def _save_gear(name):
    if not name:
        return
    try:
        with open(_gear_path(name), "w") as f:
            json.dump(_stamp({"inv": _hero_inv, "gold": _gold,
                       "equipped": _equipped}), f)
    except OSError as e:
        print(f"[hud] could not save gear: {e}")


def _load_items(name):
    global _items, _item_seq, _item_cells
    d, err = _load_json_file(_items_path(name), "items",
                             {"items": [], "next": 1, "cells": {}})
    if err:
        _log_event(f"items sidecar: {err['detail']}")
        d = {"items": [], "next": 1, "cells": {}}
    try:
        _items = d.get("items", [])
        _item_seq["next"] = d.get("next", len(_items) + 1)
        _item_cells = {str(k): [int(v[0]), int(v[1])]
                       for k, v in (d.get("cells") or {}).items()}
    except (TypeError, ValueError):
        _items, _item_seq, _item_cells = [], {"next": 1}, {}


def _save_items(name):
    try:
        with open(_items_path(name), "w") as f:
            json.dump(_stamp({"items": _items, "next": _item_seq["next"],
                       "cells": _item_cells}), f)
    except OSError as e:
        print(f"[hud] could not save items: {e}")


def _load_npcs(name):
    global _npcs, _npc_seq
    d, err = _load_json_file(_npcs_path(name), "npcs",
                             {"npcs": [], "next": 1})
    if err:
        _log_event(f"npcs sidecar: {err['detail']}")
        d = {"npcs": [], "next": 1}
    _npcs = d.get("npcs", [])
    for n in _npcs:
        g = n.get("gear") or {}
        n["gear"] = {"weapon": g.get("weapon"), "tool": g.get("tool")}
    _npc_seq["next"] = d.get("next", len(_npcs) + 1)


def _save_npcs(name):
    try:
        with open(_npcs_path(name), "w") as f:
            json.dump(_stamp({"npcs": _npcs, "next": _npc_seq["next"]}), f)
    except OSError as e:
        print(f"[hud] could not save npcs: {e}")


def _item_by_id(iid):
    return next((t for t in _items if t["id"] == iid), None)


def _npc_by_id(nid):
    return next((n for n in _npcs if n["id"] == nid), None)


def _item_cell_key(x, y):
    return f"{x},{y}"


def _inv_add(iid, qty):
    """Stack iid into the hero's pack, honoring the item's stack max."""
    d = _item_by_id(iid)
    if not d or qty <= 0:
        return
    cap = d.get("stack", core.ITEM_MAX_STACK)
    for row in _hero_inv:
        if row["item"] == iid and row["qty"] < cap:
            take = min(cap - row["qty"], qty)
            row["qty"] += take
            qty -= take
            if qty <= 0:
                return
    while qty > 0:
        take = min(cap, qty)
        _hero_inv.append({"item": iid, "qty": take})
        qty -= take
    _save_gear(_current_map)


def _inv_count(iid):
    return sum(r["qty"] for r in _hero_inv if r["item"] == iid)


def _inv_take(iid, qty):
    """Remove qty of iid from the pack. Returns False if not enough."""
    if _inv_count(iid) < qty:
        return False
    left = qty
    for row in list(_hero_inv):
        if row["item"] != iid:
            continue
        take = min(row["qty"], left)
        row["qty"] -= take
        left -= take
        if row["qty"] <= 0:
            _hero_inv.remove(row)
        if left <= 0:
            break
    _save_gear(_current_map)
    return True


def _equipped_def(slot):
    iid = _equipped.get(slot)
    return _item_by_id(iid) if iid else None


def _inv_state():
    """The hero's pack, coin, and hands for the client."""
    out = []
    for row in _hero_inv:
        d = _item_by_id(row["item"])
        if d:
            out.append({"item": row["item"], "qty": row["qty"],
                        "name": d["name"], "tile_id": d["tile_id"],
                        "kind": d["kind"], "power": d["power"],
                        "effect": d["effect"], "price": d["price"]})
    return {"ok": True, "inv": out, "gold": _gold,
            "equipped": {"weapon": (_equipped_def("weapon") or {}).get("id"),
                         "tool": (_equipped_def("tool") or {}).get("id")}}


def _check_items(x, y):
    """Per hero step: pick up whatever's lying at (x, y)."""
    key = _item_cell_key(x, y)
    cell = _item_cells.pop(key, None)
    if not cell:
        return []
    iid, qty = cell
    d = _item_by_id(iid)
    if not d:
        return []
    _inv_add(iid, qty)
    _save_items(_current_map)
    _mark_dirty()
    return [{"t": "toast",
             "text": f"🎒 picked up {d['name']}"
                     + (f" ×{qty}" if qty > 1 else "")}]


def _check_npcs(x, y):
    """Per hero step: greet folks nearby; merchants open their stores."""
    events = []
    near = {n["id"] for n in _npcs
            if max(abs(n["x"] - x), abs(n["y"] - y)) <= 1}
    new = near - _npc_near
    _npc_near.clear()
    _npc_near.update(near)
    for n in _npcs:
        if n["id"] not in new:
            continue
        if n.get("role") == "merchant":
            events.append({"t": "shop", "npc": n["id"], "name": n["name"]})
        else:
            line = (n.get("line") or "").strip()
            if line:
                events.append({"t": "toast",
                               "text": f"🧑 {n['name']}: “{line}”"})
    return events


def _mission_reconcile_patrols():
    """Mission patrols belong to the map they were placed on. On load:
    drop any whose map isn't this one (or whose mission is gone), and
    rebuild the active mission's flows only if it has none here —
    placement is deterministic per mission, so rebuilds land where
    Melody put them."""
    global _patrols
    mids = {m.get("id") for m in _missions}
    _patrols = [p for p in _patrols
                if not p.get("mission_id")
                or (p.get("map", _current_map) == _current_map
                    and p.get("mission_id") in mids)]
    for m in _missions:
        if m.get("active"):
            here = [p for p in _patrols if p.get("mission_id") == m.get("id")]
            if not here:
                _mission_place_hazards(m)
            break
    _save_patrols()


def _load_patrols():
    global _patrols
    _patrols = []
    reg, err = _load_json_file(PATROL_SAVE, "patrols", {"patrols": []})
    if err:
        _log_event(f"patrols: {err['detail']}")
        return
    for p in reg.get("patrols", []):
        try:
            pts = [[int(a), int(b)] for a, b in p["points"]]
            tid = int(p["tile_id"])
            if len(pts) >= 2 and tid in assets.tiles:
                # v5.13: keep the whole record — mission_id/hazard/x/y are
                # what let mission hazards survive a restart on their own map
                rec = {"id": int(p["id"]), "tile_id": tid, "points": pts}
                for k in ("x", "y"):
                    if p.get(k) is not None:
                        rec[k] = int(p[k])
                if p.get("hazard"):
                    rec["hazard"] = True
                if p.get("mission_id") is not None:
                    rec["mission_id"] = int(p["mission_id"])
                if p.get("map"):
                    rec["map"] = str(p["map"])
                _patrols.append(rec)
        except (KeyError, TypeError, ValueError):
            continue
    _patrol_seq["next"] = max([p["id"] for p in _patrols] + [0]) + 1
    if _patrols:
        print(f"[hud] loaded {len(_patrols)} patrol(s)")


# ---- in-memory session state ---------------------------------------------
assets = core.AssetManager()
world = core.WorldMap(25, 15, assets)
history = core.HistoryManager()

# ---- v3.7: per-map game rules ---------------------------------------------------
# Rules differ per build (saved with the map) and per user preference (the
# client keeps personal defaults in localStorage and pushes them after
# Generate). Sidecar file because crumbs_core's save schema is untouched.
DEFAULT_RULES = {"walk_ms": 140,     # hero step delay: 90 fast / 140 normal / 220 slow
                 "swim_mult": 3,     # water slowdown: 2x / 3x / 4x
                 "ghost": False,     # builder noclip: walk through walls
                 "touch": True,      # show the on-screen controls in play mode
                 "hero_tile": None}  # v4.8: the chosen PC sprite (inspector assignment)
rules = dict(DEFAULT_RULES)
_current_map = DEFAULT_SAVE

# ---- v3.9: game rules — what makes a build a *game* --------------------------
# goals (reach X = win), hazards (touch X = lose), key&door pairs, and
# step-on messages. Live in the same sidecar, under "game".
game_rules = []  # [{id, kind, ...}]
_game_seq = {"next": 1}

GAME_KINDS = ("goal", "hazard", "keydoor", "message")


def _valid_game_rule(d):
    """Normalize a submitted game rule; return None if it's nonsense."""
    if not isinstance(d, dict):
        return None
    kind = d.get("kind")
    if kind not in GAME_KINDS:
        return None
    text = str(d.get("text", "")).strip()[:140]

    def _cell(v):
        return (isinstance(v, (list, tuple)) and len(v) == 2 and
                all(isinstance(n, int) for n in v))

    def _tid(v):
        return isinstance(v, int) and v > 0 and v in assets.tiles
    if kind == "goal":
        x, y = d.get("x"), d.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            return None
        if not (0 <= x < world.width and 0 <= y < world.height):
            return None
        return {"kind": kind, "x": x, "y": y, "text": text}
    if kind == "message":
        # v4.6: words can ride a cell (x, y) or a character/object tile —
        # bump into him and he talks.
        if _tid(d.get("tile")):
            return {"kind": kind, "tile": int(d["tile"]), "text": text}
        x, y = d.get("x"), d.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            return None
        if not (0 <= x < world.width and 0 <= y < world.height):
            return None
        return {"kind": kind, "x": x, "y": y, "text": text}
    if kind == "hazard":
        if not _tid(d.get("tile")):
            return None
        return {"kind": kind, "tile": int(d["tile"]), "text": text}
    if kind == "keydoor":
        if not _tid(d.get("key")) or not _tid(d.get("door")):
            return None
        if int(d["key"]) == int(d["door"]):
            return None
        return {"kind": kind, "key": int(d["key"]), "door": int(d["door"]),
                "text": text}
    return None


def _load_game_rules(saved_list):
    global game_rules
    game_rules = []
    _game_seq["next"] = 1
    for d in saved_list or []:
        r = _valid_game_rule(d)
        if r is None:
            continue
        r["id"] = _game_seq["next"]
        _game_seq["next"] += 1
        game_rules.append(r)


def _rules_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".rules.json")


# ---- v4.0: the nature of the world -----------------------------------------
# Plain-word traits stamped on tiles; the hero lives inside their mixing.
# One trait per cell; a parallel grid so crumbs_core stays untouched.
TRAITS = {
    "hot":   {"emoji": "🔥", "words": "warms you up"},
    "cold":  {"emoji": "❄️", "words": "chills you to the bone"},
    "sharp": {"emoji": "🗡️", "words": "hurts to step on"},
    "wood":  {"emoji": "🪵", "words": "pick it up by walking over"},
    "food":  {"emoji": "🍖", "words": "eat it by walking over"},
}
traits_grid = []  # [y][x] -> trait id or None

# The builder's selectors for this world's nature: which meters exist,
# and what the sky is doing. Weather is physics, not a mind: rain is cold
# and kills fire, snow is cold that stays, fog is for the eyes (the client
# draws it thicker), storm is angry rain. Clear skies do nothing.
WEATHERS = ("clear", "rain", "fog", "snow", "storm")
DEFAULT_WORLD = {"meters": {"health": True, "warmth": False, "belly": False},
                 "weather": "clear"}
world_profile = {"meters": dict(DEFAULT_WORLD["meters"]),
                 "weather": DEFAULT_WORLD["weather"]}
# MIND HOOK: when a mind (Melody) is present, it can set WEATHER_MIND to a
# callable taking no arguments and drive the sky itself — pick the weather,
# aim the lightning, whatever it fancies. Until then, the script below is
# the weather. False intelligence now, true intelligence later.
WEATHER_MIND = None

# Per-play-run nature state: meters, gathered wood, trait edits made during
# play (reverted afterwards, like keys/doors in v3.9).
_meters = {"health": 10, "warmth": 10, "belly": 10}
_inv = {"wood": 0, "food": 0}
_nature_mods = []  # [(x, y, previous_trait, kind)] — kind is "gather",
# "fire", or "snow" so the sky can tell its own work apart on revert.
_tick_n = 0

def _traits_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".traits.json")

def _blank_traits():
    return [[None] * world.width for _ in range(world.height)]

def _fit_traits():
    # keep the trait grid matched to the map after resize/generate
    global traits_grid
    ng = _blank_traits()
    for y in range(min(world.height, len(traits_grid))):
        for x in range(min(world.width, len(traits_grid[y]))):
            ng[y][x] = traits_grid[y][x]
    traits_grid = ng

def _load_traits(name):
    global traits_grid
    traits_grid = _blank_traits()
    saved, err = _load_json_file(_traits_path(name), "traits", {})
    if err:
        _log_event(f"traits sidecar: {err['detail']}")
        return
    rows = (saved or {}).get("traits", [])
    for y in range(min(world.height, len(rows))):
        for x in range(min(world.width, len(rows[y]))):
            t = rows[y][x]
            traits_grid[y][x] = t if t in TRAITS else None

def _save_traits(name):
    try:
        with open(_traits_path(name), "w") as f:
            json.dump(_stamp({"traits": traits_grid}), f)
    except OSError as e:
        print(f"[hud] could not save traits: {e}")

# v5.1: per-instance names — "Grub" the goblin, not just "goblin #70".
# Keyed by "x,y" so a name belongs to THAT placed instance. The tile
# palette rename still renames the tile definition for everywhere.
object_names = {}  # "x,y" -> name

def _names_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".names.json")

def _name_key(x, y):
    return "%d,%d" % (x, y)

def _load_names(name):
    global object_names
    object_names = {}
    # v5.16: quarantine corrupt files instead of silently starting empty.
    saved, err = _load_json_file(_names_path(name), "names", {})
    if err:
        _log_event(f"names sidecar: {err['detail']}")
        return
    rows = (saved or {}).get("names", {})
    if isinstance(rows, dict):
        for k, v in rows.items():
            if isinstance(v, str) and v.strip():
                object_names[k] = v.strip()[:40]

def _save_names(name):
    try:
        with open(_names_path(name), "w") as f:
            json.dump(_stamp({"names": object_names}), f)
    except OSError as e:
        print(f"[hud] could not save names: {e}")

def _instance_name(x, y):
    return object_names.get(_name_key(x, y))

def _trait_at(x, y):
    if 0 <= y < len(traits_grid) and 0 <= x < len(traits_grid[y]):
        return traits_grid[y][x]
    return None


# ---- v5.6: MVP finish -------------------------------------------------------
# Event log, map validator, PNG export, map management (rename/duplicate/
# delete-to-trash/import/metadata), play-session save slots.

_events = deque(maxlen=200)
def _log_event(msg):
    _events.append({"t": time.strftime("%H:%M:%S"), "msg": str(msg)[:160]})

def _map_png(scale=4, data=None, objects=None, w=None, h=None):
    """Composite tiles + objects layers into a PIL image. None without Pillow."""
    if not core.PIL_AVAILABLE:
        return None
    data = world.data if data is None else data
    objects = world.object_layer if objects is None else objects
    w = world.width if w is None else w
    h = world.height if h is None else h
    ts = 32 * scale
    img = core.Image.new("RGBA", (w * ts, h * ts), (0, 0, 0, 255))
    for y in range(h):
        for x in range(w):
            for tid in (data[y][x], objects[y][x]):
                if not tid:
                    continue
                th = assets.get_thumbnail(tid, size=32)
                if th is None:
                    continue
                th = th.resize((ts, ts), core.Image.NEAREST)
                if th.mode == "RGBA":
                    img.alpha_composite(th, (x * ts, y * ts))
                else:
                    img.paste(th, (x * ts, y * ts))
    return img.convert("RGB")

def _validate_map():
    """One-tap map check: spawn exists, regions reachable, tile ids valid."""
    issues = []
    # v5.16: a degenerate/hand-edited layer shape must report an issue,
    # not drop the connection with a traceback.
    for _lname, _layer in (("tiles", world.data),
                           ("objects", world.object_layer),
                           ("collision", world.collision_layer)):
        if (not isinstance(_layer, list) or len(_layer) != world.height
                or any(not isinstance(_r, list) or len(_r) != world.width
                       for _r in _layer)):
            issues.append({"kind": "bad_layers",
                           "msg": f"Layer '{_lname}' is malformed "
                                  f"(expected {world.width}x{world.height}); "
                                  "re-save the map to repair it."})
            return issues
    sx, sy = _find_spawn()
    if not _walkable(sx, sy):
        issues.append({"kind": "no_spawn", "msg": "No walkable spawn point found."})
    else:
        seen = {(sx, sy)}
        dq = deque([(sx, sy)])
        hg = core.height_grid(world)  # v5.10: reachability obeys climb limits
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if (0 <= nx < world.width and 0 <= ny < world.height
                        and (nx, ny) not in seen and _walkable(nx, ny)
                        and hg[ny][nx] - hg[cy][cx] <= 1):
                    seen.add((nx, ny))
                    dq.append((nx, ny))
        unreachable = sum(
            1 for y in range(world.height) for x in range(world.width)
            if world.data[y][x] and not world.collision_layer[y][x]
            and (x, y) not in seen)
        if unreachable:
            issues.append({"kind": "unreachable",
                           "msg": f"{unreachable} floor tile(s) can't be reached from spawn."})
    bad = sum(
        1 for y in range(world.height) for x in range(world.width)
        for tid in (world.data[y][x], world.object_layer[y][x])
        if tid and tid not in assets.tiles)
    if bad:
        issues.append({"kind": "bad_tile",
                       "msg": f"{bad} cell(s) reference missing tile ids."})
    return issues

_TRASH_DIR = os.path.join(SCRIPT_DIR, "_trash")
_NON_MAPS = {"custom_tiles.json", "sprite_library.json", "shared_library.json",
             "hud_patrols.json"}

def _map_sidecars(name):
    base = name[:-5] if name.endswith(".json") else name
    return [os.path.join(SCRIPT_DIR, base + ext)
            for ext in (".json", ".rules.json", ".traits.json", ".names.json",
                        ".missions.json", ".items.json",
                        ".npcs.json")]  # v5.12, v5.13

def _slots_path():
    base = _current_map or DEFAULT_SAVE
    base = base[:-5] if base.endswith(".json") else base
    return os.path.join(SCRIPT_DIR, base + ".slots.json")

def _load_slots():
    slots, err = _load_json_file(_slots_path(), "slots", {"slots": []})
    if err:
        _log_event(f"slots sidecar: {err['detail']}")
        return []
    return slots.get("slots", [])

def _save_slots(slots):
    try:
        json.dump(_stamp({"slots": slots}), open(_slots_path(), "w"))
        return True
    except OSError:
        return False

hero_override = None  # v5.6: a loaded save slot's hero position, used by next Play


# ---- v5.0: universal undo/redo -------------------------------------------
# The map layers already had history; everything else (patrols, nature
# traits, rules, game rules, world profile, map seed) lived outside it.
# _snapshot_state grabs the whole design state, _restore_state puts it back
# and persists the sidecars, and _undoable wraps any mutation as ONE step.
map_meta = {"biome": None, "seed": None}  # v5.0: what seed built this map


def _snapshot_state():
    return {
        "width": world.width, "height": world.height,  # v5.0: resize undoes too
        "tiles": [row[:] for row in world.data],
        "objects": [row[:] for row in world.object_layer],
        "collision": [row[:] for row in world.collision_layer],
        "patrols": copy.deepcopy(_patrols),
        "patrol_seq": copy.deepcopy(_patrol_seq),  # v5.0: was a live ref — undo skipped IDs
        "traits": copy.deepcopy(traits_grid),
        "names": copy.deepcopy(object_names),  # v5.1: per-instance names undo too
        "rules": copy.deepcopy(rules),
        "game_rules": copy.deepcopy(game_rules),
        "game_seq": copy.deepcopy(_game_seq),
        "world": copy.deepcopy(world_profile),
        "meta": copy.deepcopy(map_meta),
    }


def _restore_state(s):
    global _patrols, _patrol_seq, traits_grid, rules, game_rules
    global _game_seq, map_meta, object_names
    world.width, world.height = s["width"], s["height"]
    world.data = [row[:] for row in s["tiles"]]
    world.object_layer = [row[:] for row in s["objects"]]
    world.collision_layer = [row[:] for row in s["collision"]]
    _patrols = copy.deepcopy(s["patrols"])
    _patrol_seq = copy.deepcopy(s["patrol_seq"])
    traits_grid = copy.deepcopy(s["traits"])
    object_names = copy.deepcopy(s.get("names", {}))  # v5.1 (old saves: {})
    rules = copy.deepcopy(s["rules"])
    game_rules = copy.deepcopy(s["game_rules"])
    _game_seq = copy.deepcopy(s["game_seq"])
    world_profile["meters"] = copy.deepcopy(s["world"]["meters"])
    world_profile["weather"] = s["world"]["weather"]
    map_meta = copy.deepcopy(s["meta"])
    _save_patrols()
    _save_traits(_current_map)
    _save_names(_current_map)  # v5.1
    _save_rules(_current_map)
    _mark_dirty()


def _undoable(label, fn):
    """Run fn() as one undo step. The command snapshots before, and captures
    after when fn finishes; a throw inside fn leaves history untouched."""
    cmd = core.StateSnapshotCommand(_snapshot_state, _restore_state, label)
    out = fn()
    cmd.capture_after()
    history.push(cmd)
    return out


def _natural_tile(x, y):
    """v5.0: what the eraser restores — the seed's own ground for this cell,
    or the map's most common ground tile when the seed is unknown."""
    t = core.natural_tile_at(assets.tiles, map_meta.get("biome"),
                             map_meta.get("seed"), x, y)
    if t is not None:
        return t
    return _common_ground()


def _common_ground():
    cnt = {}
    for row in world.data:
        for v in row:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get) if cnt else 0


def _natural_grid():
    """v5.0: the whole seed-ground grid for the eraser preview cache."""
    g = core.natural_grid(assets.tiles, map_meta.get("biome"),
                          map_meta.get("seed"), world.width, world.height)
    if g is not None:
        return g
    base = _common_ground()
    return [[base] * world.width for _ in range(world.height)]


def _revert_nature_mods():
    for (x, y, old, _kind) in _nature_mods:
        if 0 <= y < len(traits_grid) and 0 <= x < len(traits_grid[y]):
            traits_grid[y][x] = old
    _nature_mods.clear()

def _reset_nature_session():
    # fresh meters + inventory; undo trait changes made during this run
    global _tick_n
    _revert_nature_mods()
    _load_gear(_current_map)  # v5.13: the hero keeps their own pack
    _meters.update({"health": 10, "warmth": 10, "belly": 10})
    for _k in _inv:
        _inv[_k] = 0
    _tick_n = 0

def _apply_nature(x, y):
    """The world's nature touches the hero at (x, y). Returns toast events.
    Runs per hero step AND on the ambient tick, so cold bites even when the
    hero stands still."""
    global _tick_n, _rule_over
    notes = []
    if not play["active"] or _rule_over:
        return notes
    _tick_n += 1
    m = world_profile["meters"]
    def bump(k, d):
        _meters[k] = max(0, min(10, _meters[k] + d))
    t = _trait_at(x, y)
    if t == "hot" and m["warmth"]:
        if _meters["warmth"] < 10:
            bump("warmth", 1)
            notes.append({"t": "toast", "text": "The warmth soaks in…"})
    elif t == "cold" and m["warmth"]:
        bump("warmth", -1)
        if _meters["warmth"] <= 3:
            notes.append({"t": "toast", "text": "You're shivering…"})
    elif t == "sharp" and m["health"]:
        bump("health", -1)
        notes.append({"t": "toast", "text": "Ouch — sharp!"})
    elif t == "wood":
        _inv["wood"] += 1
        _nature_mods.append((x, y, "wood", "gather"))
        traits_grid[y][x] = None
        notes.append({"t": "toast",
                      "text": "Wood gathered (%d)" % _inv["wood"]})
    elif t == "food":
        # v5.13: food goes in the pack (gather missions can count it); if
        # the belly meter is on and there's room, one gets eaten on the spot.
        _inv["food"] += 1
        _nature_mods.append((x, y, "food", "gather"))
        traits_grid[y][x] = None
        if m["belly"] and _meters["belly"] < 10:
            bump("belly", 1)
            notes.append({"t": "toast",
                          "text": "Tasty. (food: %d)" % _inv["food"]})
        else:
            notes.append({"t": "toast",
                          "text": "Food gathered (%d)" % _inv["food"]})
    # v4.1: the sky has its nature too. If a mind is driving (WEATHER_MIND),
    # it gets the sky; otherwise this script is the weather. Rain is cold
    # and kills built fires; snow is cold that stays and piles up; fog is
    # for the eyes (the client draws it thicker); storm is angry rain.
    w = world_profile.get("weather", "clear")
    if WEATHER_MIND is not None:
        try:
            WEATHER_MIND()
        except Exception as e:
            print(f"[hud] weather mind stumbled: {e}")
    if w in ("rain", "storm") and _tick_n % (2 if w == "storm" else 4) == 0:
        for i, (fx, fy, _old, kind) in enumerate(_nature_mods):
            if kind == "fire":
                traits_grid[fy][fx] = None
                del _nature_mods[i]
                notes.append({"t": "toast",
                              "text": "The rain put out your fire…"})
                break
    if w in ("rain", "storm") and m["warmth"] and t != "hot" \
            and _tick_n % 8 == 0:
        bump("warmth", -1)
        if _meters["warmth"] <= 3:
            notes.append({"t": "toast",
                          "text": "You're soaked and shivering…"})
    if w == "snow" and _tick_n % 12 == 0:
        if sum(1 for _, _, _, k in _nature_mods if k == "snow") < 12:
            for _ in range(20):  # snowfall: an empty tile turns cold
                rx = random.randrange(len(traits_grid[0]))
                ry = random.randrange(len(traits_grid))
                if traits_grid[ry][rx] is None:
                    _nature_mods.append((rx, ry, None, "snow"))
                    traits_grid[ry][rx] = "cold"
                    break
    # the slow truths: belly empties over time; freezing and starving
    # wear health down
    if m["belly"] and _tick_n % 6 == 0:
        bump("belly", -1)
        if _meters["belly"] <= 2:
            notes.append({"t": "toast", "text": "Your belly rumbles…"})
    if m["warmth"] and _meters["warmth"] <= 0 and _tick_n % 2 == 0 \
            and m["health"]:
        bump("health", -1)
        notes.append({"t": "toast",
                      "text": "You're freezing — build a fire!"})
    if m["belly"] and _meters["belly"] <= 0 and _tick_n % 4 == 0 \
            and m["health"]:
        bump("health", -1)
        notes.append({"t": "toast", "text": "Starving… eat something!"})
    if m["health"] and _meters["health"] <= 0:
        _rule_over = "lose"
        notes.append({"t": "lose", "text": "You didn't make it…"})
    return notes

def _nature_state():
    # meter + inventory snapshot for the play HUD
    return {"meters": dict(_meters), "inv": dict(_inv),
            "profile": {"meters": dict(world_profile["meters"]),
                        "weather": world_profile.get("weather", "clear")}}

def _load_rules(name):
    """v3.7: read this map's rules sidecar; fall back to defaults.
    v3.9: sidecar v2 is {"tweaks": {...}, "game": [...]}; the old flat
    {"walk_ms": ...} shape still loads. v4.0 adds "world" (meter selectors);
    missing keys simply fall back to defaults. v4.1: world also carries
    "weather"; old sidecars without it get clear skies. v5.0: "meta" carries
    the map's biome/seed so the eraser can restore the seed's ground."""
    global rules, _current_map, map_meta
    _current_map = name
    rules = dict(DEFAULT_RULES)
    map_meta = {"biome": None, "seed": None}  # v5.0
    world_profile["meters"] = dict(DEFAULT_WORLD["meters"])
    world_profile["weather"] = DEFAULT_WORLD["weather"]  # v4.1
    # v5.16: migrate old schemas, quarantine corrupt files (never silently
    # reset — the broken file is kept as *.corrupt-* for recovery).
    saved, err = _load_json_file(_rules_path(name), "rules", {})
    if err:
        _log_event(f"rules sidecar: {err['detail']}")
    if not saved:
        _load_game_rules([])
        return
    if "tweaks" in saved or "game" in saved or "world" in saved:
        tweaks = saved.get("tweaks") or {}
        game = saved.get("game") or []
        wblk = saved.get("world") or {}
        wm = wblk.get("meters") or {}
    else:
        tweaks, game, wblk, wm = saved, [], {}, {}
    for k, v in tweaks.items():
        if k == "walk_ms" and v in (90, 140, 220):
            rules[k] = v
        elif k == "swim_mult" and v in (2, 3, 4):
            rules[k] = v
        elif k in ("ghost", "touch") and isinstance(v, bool):
            rules[k] = v
        elif k == "hero_tile" and (v is None or (isinstance(v, int) and v in assets.tiles)):
            rules[k] = v   # v4.8: the chosen PC survives reloads
    for k in DEFAULT_WORLD["meters"]:
        if isinstance(wm.get(k), bool):
            world_profile["meters"][k] = wm[k]
    if isinstance(wblk.get("weather"), str) and wblk["weather"] in WEATHERS:
        world_profile["weather"] = wblk["weather"]  # v4.1
    mblk = saved.get("meta") or {}  # v5.0: map seed for the eraser
    if isinstance(mblk.get("biome"), str):
        map_meta["biome"] = mblk["biome"]
    if isinstance(mblk.get("seed"), int):
        map_meta["seed"] = mblk["seed"]
    _load_game_rules(game)


def _save_rules(name):
    try:
        with open(_rules_path(name), "w") as f:
            json.dump(_stamp({"tweaks": rules, "game": game_rules,
                       "world": world_profile, "meta": map_meta}), f)  # v5.0: meta
    except OSError as e:
        print(f"[hud] could not save rules: {e}")


# try to resume: last HUD save, else the blank starter, else fresh 25x15
for _name, _loader in ((DEFAULT_SAVE, world.load), ("vault_map.txt", world.load_csv)):
    _p = os.path.join(SCRIPT_DIR, _name)
    if os.path.exists(_p) and _loader(_p):
        print(f"[hud] loaded starter map {_name} ({world.width}x{world.height})")
        break
else:
    print(f"[hud] fresh map {world.width}x{world.height}")

_load_custom_tiles()  # v3.0: imported tiles back into the asset manager
_load_patrols()       # v3.4: patrol routes back (needs tiles loaded first)
_mission_reconcile_patrols()  # v5.13: only this map's hazards stay
_load_rules(DEFAULT_SAVE)  # v3.7: this build's rules (or defaults)
_load_traits(DEFAULT_SAVE)  # v4.0: this build's nature traits (or blank)
_load_names(DEFAULT_SAVE)   # v5.1: per-instance names (or none)
_load_missions(DEFAULT_SAVE)  # v5.12: Melody's missions (or none)
_load_items(DEFAULT_SAVE)    # v5.13: this map's gear (or none)
_load_npcs(DEFAULT_SAVE)     # v5.13: this map's folks (or none)

# v3.2: built-in water/ocean colors are swimmable — slow the hero, don't block
for _tid, _t in assets.tiles.items():
    _nm = str(_t.get("name", "")).lower()
    if _t.get("type") == "color" and ("water" in _nm or "ocean" in _nm):
        _t["properties"]["swim"] = True


# ---- playtest state (tile-space hero; crumbs_core untouched) ----------------
play = {"active": False, "tx": 0, "ty": 0}

# ---- v3.9: game-rule session state -------------------------------------------
# Keys get picked up and doors swing open *during play only* — the world edits
# are recorded in _rule_mods and reverted when play starts, stops, or saves,
# so a playtest never permanently changes the build.
_rule_mods = []    # [(layer, x, y, old_value)]
_rule_shown = set()  # message-rule ids already delivered this session
_rule_keys = set()   # keydoor-rule ids already used this session
_rule_over = None    # None | "win" | "lose"


def _revert_rule_mods():
    for layer, x, y, old in reversed(_rule_mods):
        try:
            _grid(layer)[y][x] = old
        except IndexError:
            pass
    _rule_mods.clear()


def _reset_rule_session():
    _revert_rule_mods()
    _rule_shown.clear()
    _rule_keys.clear()
    _reset_nature_session()  # v4.0: meters fresh, gathered traits restored
    global _rule_over
    _rule_over = None


def _tile_at_any_layer(x, y):
    """Tile id under the hero's feet — the objects layer sits on top of the
    tiles layer, so a key lying on grass reads as the key, not the grass."""
    try:
        o = world.object_layer[y][x]
        if o:
            return o
        return world.data[y][x]
    except IndexError:
        return None


def _clear_tile_everywhere(tid):
    """Remove every cell painted with tid (tiles + objects layers),
    recording the edits so play can put them back."""
    for layer in ("tiles", "objects"):
        grid = _grid(layer)
        empty = _default_value(layer)
        for y in range(world.height):
            row = grid[y]
            for x in range(world.width):
                if row[x] == tid:
                    _rule_mods.append((layer, x, y, tid))
                    row[x] = empty


def _check_rules(x, y):
    """Run the build's game rules for the hero arriving at (x, y).
    Returns [events]; each event is {"t": ..., "text": ...}."""
    global _rule_over
    events = []
    if _rule_over:
        return events
    for r in game_rules:
        kind = r["kind"]
        if kind == "message":
            if "tile" in r:
                # v4.6: words riding a character/object — the hero bumps into him
                if _tile_at_any_layer(x, y) == r["tile"] and r["id"] not in _rule_shown:
                    _rule_shown.add(r["id"])
                    events.append({"t": "message",
                                   "text": r["text"] or "He nods at you."})
            elif r["x"] == x and r["y"] == y and r["id"] not in _rule_shown:
                _rule_shown.add(r["id"])
                events.append({"t": "message",
                               "text": r["text"] or "Something catches your eye…"})
        elif kind == "keydoor":
            if r["id"] not in _rule_keys and _tile_at_any_layer(x, y) == r["key"]:
                _rule_keys.add(r["id"])
                _clear_tile_everywhere(r["key"])
                _clear_tile_everywhere(r["door"])
                events.append({"t": "unlock",
                               "text": r["text"] or "Click — a door swings open!"})
        elif kind == "goal":
            if r["x"] == x and r["y"] == y:
                _rule_over = "win"
                events.append({"t": "win",
                               "text": r["text"] or "You made it — you win!"})
                break
        elif kind == "hazard":
            if _tile_at_any_layer(x, y) == r["tile"]:
                _rule_over = "lose"
                events.append({"t": "lose",
                               "text": r["text"] or "Oh no — game over."})
                break
    return events

# ---- v3.6 SWIM HOOK ----------------------------------------------------------
# Deep water is IMPASSABLE until the swim animation exists. When the swim
# animation gets built, flip this to True: deep water becomes swimmable
# (slow, with the swim animation) instead of blocking, and the per-step
# "deep" flags already flowing to the client light up the animation hook
# in the renderer. Nothing else needs to change.
SWIM_UNLOCKED = False


def _tile_solid(tx, ty):
    tile = assets.tiles.get(world.data[ty][tx])
    return bool(tile and tile.get("properties", {}).get("solid"))


def _walkable(tx, ty):
    if not (0 <= tx < world.width and 0 <= ty < world.height):
        return False
    if world.collision_layer[ty][tx]:
        return False
    if _deep_at(tx, ty):
        return SWIM_UNLOCKED  # v3.6: no swim animation yet — deep water blocks
    return not _tile_solid(tx, ty)


def _deep_at(tx, ty):
    """v3.6: True when this tile is deep water — needs the swim animation."""
    tile = assets.tiles.get(world.data[ty][tx])
    return bool(tile and tile.get("properties", {}).get("deep"))


def _swim_at(tx, ty):
    """v3.2: True when this tile is water — walkable, but slow (swim effect)."""
    tile = assets.tiles.get(world.data[ty][tx])
    return bool(tile and tile.get("properties", {}).get("swim"))


def _find_spawn():
    # v4.9: the crowned hero starts where he stands — the selected PC's
    # placed instance is the spawn point, so "set as hero" puts YOU there.
    ht = rules.get("hero_tile")
    if ht is not None:
        for y in range(world.height):
            for x in range(world.width):
                if (world.object_layer[y][x] == ht and _walkable(x, y)
                        and not _swim_at(x, y)):
                    return x, y
    cx, cy = world.width // 2, world.height // 2
    if _walkable(cx, cy) and not _swim_at(cx, cy):
        return cx, cy
    for r in range(1, max(world.width, world.height)):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = cx + dx, cy + dy
                if _walkable(x, y) and not _swim_at(x, y):
                    return x, y
    return 0, 0


def _find_path(sx, sy, tx, ty, ghost=False):
    """v3.2: Dijkstra over walkable tiles — water costs 4x (swim), so the hero
    walks around it when a dry route exists and swims only when it must.
    v3.6: deep water is unwalkable until SWIM_UNLOCKED flips; then it costs
    4x like shallow water and its steps are flagged deep for the client.
    v3.7: ghost (builder noclip rule) walks straight through everything.
    v5.10: climbing costs +1 per height level gained; a step up more than one
    level is a cliff — unpathable (unless ghost).
    Returns ([(x,y), ...] excluding the start, [swim?, ...], [deep?, ...])."""
    def _ok(x, y):
        return (0 <= x < world.width and 0 <= y < world.height
                and (ghost or _walkable(x, y)))
    if (sx, sy) == (tx, ty) or not _ok(tx, ty):
        return [], [], []
    SWIM_COST = 4
    dist = {(sx, sy): 0}
    prev = {(sx, sy): None}
    pq = [(0, sx, sy)]
    hg = core.height_grid(world)  # v5.10: per-cell heights for climb costs
    while pq:
        d, x, y = heapq.heappop(pq)
        if d != dist[(x, y)]:
            continue
        if (x, y) == (tx, ty):
            break
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not _ok(nx, ny):
                continue
            if ghost:
                nd = d + 1
            else:
                dh = hg[ny][nx] - hg[y][x]
                if dh > 1:
                    continue  # cliff — can't climb it in one step
                step = SWIM_COST if (_swim_at(nx, ny) or _deep_at(nx, ny)) else 1
                nd = d + step + max(0, dh)
            if nd < dist.get((nx, ny), float("inf")):
                dist[(nx, ny)] = nd
                prev[(nx, ny)] = (x, y)
                heapq.heappush(pq, (nd, nx, ny))
    if (tx, ty) not in prev:
        return [], [], []
    path = [(tx, ty)]
    while path[-1] != (sx, sy):
        p = prev.get(path[-1])
        if p is None:
            return [], [], []
        path.append(p)
    path.reverse()
    steps = path[1:]
    return (steps,
            [_swim_at(x, y) for x, y in steps],
            [_deep_at(x, y) for x, y in steps])


# ---- autosave state ----------------------------------------------------------
_save_state = {"dirty": False, "last": None}


def _mark_dirty():
    _save_state["dirty"] = True


def _save_now(name=DEFAULT_SAVE):
    p = os.path.join(SCRIPT_DIR, name)
    if world.save(p, schema=SCHEMA_VERSION):  # v5.16: stamp the data schema
        _save_state["dirty"] = False
        _save_state["last"] = time.strftime("%H:%M:%S")
        _save_rules(name)  # v3.7: rules ride alongside the map
        return True
    return False


# ---- v5.16: exports, bundles -----------------------------------------------
# (entitlement helpers live near the schema block, above — pack discovery
# runs at import time and needs them early)


def _export_map_doc(name):
    """Load a saved map file for export. Dict or None."""
    try:
        m = json.load(open(os.path.join(SCRIPT_DIR, name)))
        return {"name": name, "w": int(m["width"]), "h": int(m["height"]),
                "tiles": m["tiles"], "objects": m.get("objects"),
                "collision": m.get("collision")}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _export_used_tiles(doc):
    """Tile ids used by the map, first-seen order — the gid authority."""
    used = []
    for layer in (doc["tiles"], doc.get("objects") or []):
        for row in layer:
            for t in row:
                if t and t not in used:
                    used.append(t)
    return used


def _tiled_doc(name, doc, used):
    """Tiled (mapeditor.org) JSON. gid = index+1 over used tiles; the
    companion crumbs-tileset.png (8 columns of 32px) carries the art."""
    w, h = doc["w"], doc["h"]
    gid = {t: i + 1 for i, t in enumerate(used)}
    data = [gid.get(t, 0) for row in doc["tiles"] for t in row]
    objs, oid = [], 1
    for y, row in enumerate(doc.get("objects") or []):
        for x, t in enumerate(row):
            if t:
                objs.append({"gid": gid[t], "height": 32, "id": oid,
                             "name": str(t), "type": "", "visible": True,
                             "width": 32, "x": x * 32, "y": (y + 1) * 32})
                oid += 1
    cols = 8
    rows = max(1, (len(used) + cols - 1) // cols)
    base = name[:-5] if name.endswith(".json") else name
    return {
        "compressionlevel": -1, "height": h, "infinite": False,
        "layers": [
            {"data": data, "height": h, "id": 1, "name": "tiles",
             "opacity": 1, "type": "tilelayer", "visible": True,
             "width": w, "x": 0, "y": 0},
            {"draworder": "index", "id": 2, "name": "objects",
             "objects": objs, "opacity": 1, "type": "objectgroup",
             "visible": True, "x": 0, "y": 0}],
        "nextlayerid": 3, "nextobjectid": oid,
        "orientation": "orthogonal", "renderorder": "right-down",
        "tiledversion": "1.10.2", "tileheight": 32, "tilewidth": 32,
        "tilesets": [{"columns": cols, "firstgid": 1,
                      "image": "crumbs-tileset.png",
                      "imageheight": rows * 32, "imagewidth": cols * 32,
                      "margin": 0, "name": "crumbs", "spacing": 0,
                      "tilecount": len(used), "tileheight": 32,
                      "tilewidth": 32, "type": "tileset"}],
        "type": "map", "version": "1.10", "width": w,
        "editorsettings": {"export": {"target": base + ".tiled.json"}},
    }


def _tileset_png_bytes(used):
    """Render the used tiles into the 8-column strip the Tiled export names."""
    if not core.PIL_AVAILABLE or not used:
        return None
    cols = 8
    rows = (len(used) + cols - 1) // cols
    img = core.Image.new("RGBA", (cols * 32, rows * 32), (0, 0, 0, 0))
    for i, tid in enumerate(used):
        th = assets.get_thumbnail(tid, size=32)
        if th is None:
            continue
        img.paste(th.convert("RGBA"), ((i % cols) * 32, (i // cols) * 32))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


_BUNDLE_EXTS = (".rules.json", ".traits.json", ".names.json",
                ".missions.json", ".items.json", ".npcs.json",
                ".gear.json", ".slots.json")  # v5.16: gear rides the bundle


def _build_bundle(name):
    """Shareable .crumbs.zip: native map + sidecars + Tiled JSON + tileset
    + manifest (app version + schema stamp). Returns (bytes, filename)."""
    doc = _export_map_doc(name)
    if not doc:
        return None, None
    base = name[:-5] if name.endswith(".json") else name
    used = _export_used_tiles(doc)
    manifest = {"app": "crumbs-hud", "app_version": APP_VERSION,
                "schema": SCHEMA_VERSION, "map": name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "tiles_used": len(used), "sidecars": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(base + ".json", json.dumps(
            {"version": "3.0", "schema": SCHEMA_VERSION, "width": doc["w"],
             "height": doc["h"], "tiles": doc["tiles"],
             "objects": doc["objects"], "collision": doc["collision"]}))
        for ext in _BUNDLE_EXTS:
            fn = base + ext
            p = os.path.join(SCRIPT_DIR, fn)
            if not os.path.isfile(p):
                continue
            try:
                side = _migrate_sidecar(ext, json.load(open(p)))
                if isinstance(side, dict) and side.get("error"):
                    continue
                zf.writestr(fn, json.dumps(side))
                manifest["sidecars"].append(fn)
            except (OSError, ValueError):
                continue
        zf.writestr(base + ".tiled.json",
                    json.dumps(_tiled_doc(name, doc, used)))
        tset = _tileset_png_bytes(used)
        if tset:
            zf.writestr("crumbs-tileset.png", tset)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue(), base + ".crumbs.zip"


def _import_bundle(raw, want_name):
    """Validate + install a .crumbs.zip. Never overwrites: lands on a fresh
    unique name. Returns (ok, payload) — payload is the result dict or an
    error string."""
    if len(raw) > MAX_BUNDLE_BYTES:
        return False, "bundle too large"
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        manifest = json.loads(zf.read("manifest.json"))
    except Exception as e:
        return False, f"not a crumbs bundle: {e}"
    if manifest.get("app") != "crumbs-hud":
        return False, "not a crumbs bundle"
    mschema = manifest.get("schema", 0)
    if mschema > SCHEMA_VERSION:
        return False, (f"bundle needs newer Crumbs "
                       f"(bundle schema {mschema}, this app reads "
                       f"{SCHEMA_VERSION}) — update the app first")
    src_map = manifest.get("map") or "map.json"
    src_base = src_map[:-5] if src_map.endswith(".json") else src_map
    want = _safe_name(want_name) or (src_base + ".json")
    base = want[:-5] if want.endswith(".json") else want
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-") or "imported"
    candidate, i = base + ".json", 2
    while os.path.exists(os.path.join(SCRIPT_DIR, candidate)):
        candidate, i = f"{base}-{i}.json", i + 1
    dst_base = candidate[:-5]
    allowed = {src_base + ".json"} | {src_base + e for e in _BUNDLE_EXTS}
    wrote = []
    try:
        for arc in zf.namelist():
            if arc in ("manifest.json",) or arc.endswith(".tiled.json") \
                    or arc == "crumbs-tileset.png":
                continue
            if arc not in allowed:
                continue  # never write anything unexpected
            data = json.loads(zf.read(arc))  # must be valid JSON
            data = _migrate_sidecar(arc, data)
            if isinstance(data, dict) and data.get("error"):
                continue
            out = (dst_base + arc[len(src_base):]
                   if arc != src_base + ".json" else candidate)
            with open(os.path.join(SCRIPT_DIR, out), "w") as f:
                json.dump(data, f)
            wrote.append(out)
    except Exception as e:
        return False, f"bundle unreadable: {e}"
    if candidate not in wrote:
        return False, "bundle has no map"
    _log_event(f"imported bundle as {candidate}"
               + (" (migrated)" if mschema < SCHEMA_VERSION else ""))
    return True, {"file": candidate, "sidecars": [w for w in wrote
                                                 if w != candidate],
                  "migrated": mschema < SCHEMA_VERSION}


def _restore_backup(name):
    """Copy <name>.backup over <name>; refresh live state when the file
    belongs to the current map. Returns (ok, message)."""
    p = os.path.join(SCRIPT_DIR, name)
    src = p + ".backup"
    if not os.path.isfile(src):
        return False, "no backup for that file"
    try:
        if os.path.isfile(p):
            # v5.16: the thing being replaced gets its own snapshot first —
            # a restore is always undoable.
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            shutil.copy2(p, f"{p}.pre-restore-{stamp}")
        shutil.copy2(src, p)
    except OSError as e:
        return False, str(e)
    cur = _current_map or ""
    cb = cur[:-5] if cur.endswith(".json") else cur
    nb = name[:-5] if name.endswith(".json") else name
    if nb == cb:
        if name == cur or name.endswith(".json"):
            # the live map itself — reload everything like /api/load
            history.undo_stack.clear()
            history.redo_stack.clear()
            world.load(p)
            _load_rules(name)
            _load_traits(name)
            _load_names(name)
            _load_missions(name)
            _load_items(name)
            _load_npcs(name)
            _mission_reconcile_patrols()
        else:
            for ext, loader in ((".rules.json", _load_rules),
                                (".traits.json", _load_traits),
                                (".names.json", _load_names),
                                (".missions.json", _load_missions),
                                (".items.json", _load_items),
                                (".npcs.json", _load_npcs),
                                (".gear.json", _load_gear)):
                if name == cb + ext:
                    loader(_current_map)
                    break
    _log_event(f"restored {name} from backup")
    return True, "restored"


def _autosave_loop():
    while True:
        time.sleep(30)
        if _save_state["dirty"] and _save_now():
            print(f"[hud] autosaved {DEFAULT_SAVE} at {_save_state['last']}")


def _grid(layer):
    if layer == "objects":
        return world.object_layer
    if layer == "collision":
        return world.collision_layer
    return world.data


def _snapshot():
    return ([r[:] for r in world.data],
            [r[:] for r in world.object_layer],
            [r[:] for r in world.collision_layer])


def _paint_value(layer, tile_id):
    if layer == "collision":
        # v3.1: collision is 0 = open, 1 = solid, 2 = locked (both block)
        try:
            v = int(tile_id)
        except (TypeError, ValueError):
            return False
        return v if v in (1, 2) else bool(v)
    if layer == "objects":
        return None if tile_id is None else int(tile_id)
    return int(tile_id)


def _default_value(layer):
    return {"tiles": 0, "objects": None, "collision": False}[layer]


def _safe_name(name):
    """Basename-only map filenames; no path traversal."""
    name = os.path.basename(str(name or "")).strip()
    return name if name else None


def _map_state():
    return {"width": world.width, "height": world.height,
            "tiles": world.data, "objects": world.object_layer,
            "collision": world.collision_layer}


class Handler(BaseHTTPRequestHandler):
    server_version = "CrumbsHUD/1.9"

    def log_message(self, *a):  # keep the console quiet
        pass

    def handle_one_request(self):
        # v1.4: a phone browser often hangs up mid-write (iOS froze the server,
        # user reloaded, etc.). Swallow the dead-socket noise, keep serving.
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # -- helpers -----------------------------------------------------------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, max_bytes=MAX_JSON_BYTES):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if not n:
            return {}
        if n > max_bytes:  # v5.16: reject oversized bodies before reading
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return None

    def _is_json_request(self):
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        return ctype == "application/json"

    def _same_origin_ok(self):
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False

        def _host_matches(url_value):
            parsed = urlparse(url_value or "")
            if not parsed.scheme or not parsed.netloc:
                return False
            return parsed.netloc.strip().lower() == host

        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        if origin and not _host_matches(origin):
            return False
        if referer and not _host_matches(referer):
            return False
        return True

    def _write_key_ok(self):
        if not PUBLIC_MODE:
            return True
        if not PUBLIC_WRITE_KEY:
            return False
        key = self.headers.get(WRITE_KEY_HEADER) or ""
        if not key:
            q = parse_qs(urlparse(self.path).query)
            key = (q.get(WRITE_KEY_QUERY) or [""])[0]
        return bool(key) and hmac.compare_digest(key, PUBLIC_WRITE_KEY)

    def _client_ip(self):
        return (self.client_address[0] if self.client_address else "?")

    def _safe_open_image(self, raw, what="image"):
        """v5.16: hardened upload decode — real image, sane dimensions,
        bounded pixels (decompression-bomb guard). Returns RGBA or raises."""
        if not core.PIL_AVAILABLE:
            raise ValueError("image support unavailable")
        if len(raw) > MAX_IMAGE_PIXELS * 4:
            raise ValueError(f"{what}: file too large")
        img = core.Image.open(io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG", "GIF", "WEBP", "BMP"):
            raise ValueError(f"{what}: unsupported format {img.format}")
        w, h = img.size
        if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM or w * h > MAX_IMAGE_PIXELS:
            raise ValueError(f"{what}: dimensions too large ({w}x{h})")
        return img.convert("RGBA")

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
        if not _rate_ok("GET", self._client_ip()):
            return self._send_json({"ok": False, "error": "slow down"}, 429)
        path = urlparse(self.path).path
        if path == "/":
            try:
                with open(HTML_PATH, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"editor.html not found next to crumbs_hud.py")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # v5.21.4: Safari heuristic-caches the page aggressively with no
            # cache headers, so it can keep serving a stale editor.html after
            # an update. 180KB over localhost — always fetch it fresh.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/map":
            self._send_json(_map_state())
        elif path == "/api/height-grid":
            # v5.10: per-cell numeric heights for shadows, tall faces,
            # the height overlay, and line-of-sight.
            self._send_json({"w": world.width, "h": world.height,
                             "grid": core.height_grid(world)})
        elif path == "/api/visibility":
            # v5.10: ?x=&y= — 2D bool grid of cells visible from (x, y)
            # via line_of_sight (fog-of-war lite for play mode).
            try:
                q = parse_qs(urlparse(self.path).query)
                vx, vy = int(q.get("x", [0])[0]), int(q.get("y", [0])[0])
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad x/y"}, 400)
            vis = [[core.line_of_sight(world, vx, vy, x, y)
                    for x in range(world.width)] for y in range(world.height)]
            self._send_json({"w": world.width, "h": world.height, "vis": vis})
        elif path == "/api/palette":
            sw = []
            for tid in sorted(assets.tiles):
                t = assets.tiles[tid]
                if t["type"] == "color" and t.get("category") == "tiles":
                    sw.append({"id": tid, "name": t["name"], "color": t.get("color")})
            self._send_json({"tiles": sw})
        elif path == "/api/sprites":
            sp = []
            for tid in sorted(assets.tiles):
                t = assets.tiles[tid]
                if t["type"] != "color":
                    sp.append({"id": tid, "name": t["name"], "type": t["type"],
                               "category": t.get("category", "objects")})
            self._send_json({"tiles": sp})
        elif path == "/api/presets":
            # v3.0: tile function presets for the import picker
            self._send_json({"presets": [{"id": k, **v} for k, v in TILE_PRESETS.items()]})
        elif path == "/api/custom-tiles":
            # v3.0: imported tiles with animation metadata
            # v3.8: both shelves — shared first, then this device's
            self._send_json({"tiles": [_custom_public(e) for e in _shared_tiles + _custom_tiles]})
        elif path == "/api/patrols":
            # v3.4: patrol routes — [{id, tile_id, points}]
            self._send_json({"patrols": _patrols})
        elif path == "/api/missions/presets":
            # v5.12: Melody's preset library + difficulty tiers
            self._send_json({
                "ok": True,
                "presets": core.MISSION_PRESETS,
                "difficulties": [
                    {"n": n, "label": t["label"], "hazards": t["hazards"]}
                    for n, t in sorted(core.DIFFICULTY_TIERS.items())],
            })
        elif path == "/api/missions":
            # v5.12: missions for this map
            self._send_json({"ok": True, "missions": [
                {k: m[k] for k in ("id", "name", "preset", "difficulty",
                                   "reward", "objectives", "hazard_count",
                                   "active", "won")}
                for m in _missions]})
        elif path == "/api/items":
            # v5.13: this map's item library + what's lying on the ground
            cells = []
            for k, v in _item_cells.items():
                x, y = k.split(",")
                cells.append([int(x), int(y), v[0], v[1]])
            self._send_json({"ok": True, "items": _items, "cells": cells})
        elif path == "/api/npcs":
            # v5.13: this map's folks
            self._send_json({"ok": True, "npcs": _npcs})
        elif path == "/api/inv":
            # v5.13: the hero's pack, coin, and hands
            self._send_json(_inv_state())
        elif path == "/api/missions/state":
            # v5.12: live run progress for the play HUD
            active = next((m for m in _missions if m.get("active")), None)
            self._send_json({
                "ok": True,
                "active": ({k: active[k] for k in
                            ("id", "name", "preset", "difficulty", "reward")}
                           if active else None),
                "progress": _mission_run_text(),
                "danger": active.get("danger", []) if active else [],
                "won": bool(mission_run and mission_run["won"]),
                "failed": bool(mission_run and mission_run["failed"]),
            })
        elif path.startswith("/api/thumb/"):
            try:
                tid = int(path.rsplit("/", 1)[1])
            except ValueError:
                return self._send_json({"ok": False, "error": "bad tile id"}, 400)
            thumb = None
            # v3.0: ?frame=N serves a specific animation frame
            q = parse_qs(urlparse(self.path).query)
            if "frame" in q and core.PIL_AVAILABLE:
                fr = (assets.tiles.get(tid) or {}).get("frames") or []
                if fr:
                    try:
                        fi = int(q["frame"][0]) % len(fr)
                    except ValueError:
                        fi = 0
                    thumb = fr[fi].resize((64, 64), core.Image.Resampling.NEAREST)
            if thumb is None:
                thumb = assets.get_thumbnail(tid, size=64)
            if thumb is None:
                return self._send_json({"ok": False, "error": "no thumbnail"}, 404)
            buf = io.BytesIO()
            thumb.save(buf, "PNG")
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/maps":
            # v5.6: rich entries — dims, modified time, description — for the picker
            out = []
            for f in sorted(os.listdir(SCRIPT_DIR)):
                if f in _NON_MAPS or not os.path.isfile(os.path.join(SCRIPT_DIR, f)):
                    continue
                if not (f.endswith(".json") or f.endswith(".txt")):
                    continue
                if f.endswith((".rules.json", ".traits.json", ".names.json",
                               ".slots.json")):
                    continue
                p = os.path.join(SCRIPT_DIR, f)
                w = h = None
                if f.endswith(".json"):
                    try:
                        m = json.load(open(p))
                        w, h = m.get("width"), m.get("height")
                    except (OSError, ValueError):
                        pass
                meta = {}
                try:
                    meta = (json.load(open(_rules_path(f))) or {}).get("meta") or {}
                except (OSError, ValueError):
                    pass
                try:
                    mtime = int(os.path.getmtime(p))
                except OSError:
                    mtime = 0
                out.append({"file": f, "width": w, "height": h,
                            "modified": meta.get("modified") or mtime,
                            "description": meta.get("description") or ""})
            self._send_json({"maps": out})
        elif path == "/api/biomes":
            self._send_json({"biomes": [{"id": k, "name": v["name"]} for k, v in core.BIOMES.items()]})
        elif path == "/api/rules":
            # v3.7: this build's game rules
            self._send_json({"ok": True, "rules": rules})
        elif path == "/api/game-rules":
            # v3.9: this build's game rules (goals, hazards, keys, messages)
            tids = set()
            for r in game_rules:
                for k in ("tile", "key", "door"):
                    if k in r:
                        tids.add(r[k])
            names = {str(t): assets.tiles[t]["name"]
                     for t in tids if t in assets.tiles}
            self._send_json({"ok": True, "rules": game_rules, "names": names})
        elif path == "/api/traits":
            # v4.0: this build's nature traits + the plain-words legend
            self._send_json({"ok": True, "traits": traits_grid,
                             "legend": TRAITS})
        elif path == "/api/object-names":
            # v5.1: per-instance names, "x,y" -> name
            self._send_json({"ok": True, "names": object_names})
        elif path == "/api/natural":
            # v5.0: the seed's own ground per cell — the eraser preview cache.
            # Falls back to the map's most common ground when seed unknown.
            self._send_json({"ok": True, "natural": _natural_grid()})
        elif path == "/api/world":
            # v4.0: this build's world profile (meter selectors, v4.1: sky)
            self._send_json({"ok": True, "world": world_profile})
        elif path == "/api/status":
            self._send_json({"dirty": _save_state["dirty"],
                             "last_save": _save_state["last"],
                             "play": play["active"]})
        elif path == "/api/log":
            # v5.6: server event log for debugging without watching the terminal
            q = parse_qs(urlparse(self.path).query)
            try:
                n = min(200, max(1, int((q.get("n") or ["100"])[0])))
            except ValueError:
                n = 100
            self._send_json({"events": list(_events)[-n:]})
        elif path == "/api/backups":
            # v5.16: every save rotates a .backup — list them for restore.
            out = []
            for f in sorted(os.listdir(SCRIPT_DIR)):
                if not f.endswith(".backup"):
                    continue
                try:
                    st = os.stat(os.path.join(SCRIPT_DIR, f))
                except OSError:
                    continue
                out.append({"file": f[:-len(".backup")], "bytes": st.st_size,
                            "modified": int(st.st_mtime)})
            return self._send_json({"ok": True, "backups": out})
        elif path == "/api/entitlements":
            # v5.16: which art packs this device may load.
            catalog, granted = _pack_catalog()
            return self._send_json({"ok": True, "granted": sorted(granted),
                                    "catalog": catalog})
        elif path == "/api/generation-presets":
            # v5.16: deterministic recipes — same seed, same map, every time.
            return self._send_json({
                "ok": True,
                "presets": [{"id": pid, "label": p["label"],
                             "biome": p["biome"], "blurb": p["blurb"]}
                            for pid, p in core.GENERATION_PRESETS.items()]})
        elif path == "/api/templates":
            # v5.16: template-* starter maps ship instant outcomes.
            out = []
            for f in sorted(os.listdir(SCRIPT_DIR)):
                if not (f.startswith("template-") and f.endswith(".json")):
                    continue
                try:
                    m = json.load(open(os.path.join(SCRIPT_DIR, f)))
                    w, h = int(m["width"]), int(m["height"])
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                out.append({"file": f, "width": w, "height": h,
                            "label": f[len("template-"):-len(".json")]
                            .replace("-", " ").title()})
            return self._send_json({"ok": True, "templates": out})
        elif path == "/api/update/check":
            # v5.18: is there a newer build on the repo's main branch?
            # v5.21: the error names the failing leg (this server -> GitHub)
            # with a fix hint, and reports whether a rollback target exists.
            try:
                latest = _update_remote_version()
            except Exception as e:
                return self._send_json({"ok": False, "leg": "github",
                                        "error": f"this server couldn't reach GitHub ({e.__class__.__name__}: {str(e)[:100]})",
                                        "hint": _update_hint(e)})
            if not latest:
                return self._send_json({"ok": False, "leg": "github",
                                        "error": "GitHub answered but the version was unreadable"})
            disk = _update_disk_version()
            return self._send_json({"ok": True, "current": APP_VERSION,
                                    "latest": latest,
                                    # v5.21.1: numeric compare — a stale
                                    # GitHub cache must never offer a
                                    # *downgrade* as an update.
                                    "available": _ver_tuple(latest) > _ver_tuple(APP_VERSION),
                                    "can_rollback": _update_can_rollback(),
                                    # v5.21.5: installed-but-not-restarted —
                                    # don't loop the install dialog; say restart.
                                    "disk_version": disk,
                                    "pending_restart": bool(disk and _ver_tuple(disk) > _ver_tuple(APP_VERSION))})
        elif path == "/api/update/changelog":
            # v5.21: what's new between this build and main, for the update
            # dialog — so the decision happens with the notes in front of you.
            try:
                entries = _update_changelog(APP_VERSION)
            except Exception as e:
                return self._send_json({"ok": False, "leg": "github",
                                        "error": f"couldn't fetch the changelog ({e.__class__.__name__})",
                                        "hint": _update_hint(e)})
            return self._send_json({"ok": True, "current": APP_VERSION,
                                    "entries": entries})
        elif path == "/api/export/tiled":
            # v5.16: Tiled (mapeditor.org) JSON + companion tileset.
            q = parse_qs(urlparse(self.path).query)
            name = _safe_name((q.get("file") or [""])[0]) or _current_map
            doc = _export_map_doc(name)
            if not doc:
                return self._send_json({"ok": False,
                                        "error": "cannot load map"}, 404)
            body = json.dumps(
                _tiled_doc(name, doc, _export_used_tiles(doc))).encode()
            base = name[:-5] if name.endswith(".json") else name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition",
                             f'attachment; filename="{base}.tiled.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        elif path == "/api/export/tileset.png":
            # v5.16: the 8-column art strip the Tiled export's gids name.
            q = parse_qs(urlparse(self.path).query)
            name = _safe_name((q.get("file") or [""])[0]) or _current_map
            doc = _export_map_doc(name)
            if not doc:
                return self._send_json({"ok": False,
                                        "error": "cannot load map"}, 404)
            png = _tileset_png_bytes(_export_used_tiles(doc))
            if not png:
                return self._send_json({"ok": False,
                                        "error": "no tiles or Pillow "
                                                 "unavailable"}, 400)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Disposition",
                             'attachment; filename="crumbs-tileset.png"')
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            return self.wfile.write(png)
        elif path == "/api/bundle/export":
            # v5.16: shareable .crumbs.zip — map + sidecars + Tiled + manifest.
            q = parse_qs(urlparse(self.path).query)
            name = _safe_name((q.get("file") or [""])[0]) or _current_map
            data, arcname = _build_bundle(name)
            if not data:
                return self._send_json({"ok": False,
                                        "error": "cannot build bundle"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition",
                             f'attachment; filename="{arcname}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        elif path == "/api/export/png":
            # v5.6: full-res render of the map as a downloadable PNG
            q = parse_qs(urlparse(self.path).query)
            try:
                scale = min(8, max(1, int((q.get("scale") or ["4"])[0])))
            except ValueError:
                scale = 4
            img = _map_png(scale)
            if img is None:
                return self._send_json({"ok": False, "error": "Pillow unavailable"}, 500)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition",
                             'attachment; filename="crumbs-map.png"')
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/map/thumb":
            # v5.6: small PNG preview of any saved map, for the picker
            q = parse_qs(urlparse(self.path).query)
            name = _safe_name((q.get("file") or [""])[0])
            if not name:
                return self._send_json({"ok": False, "error": "file required"}, 400)
            p = os.path.join(SCRIPT_DIR, name)
            try:
                m = json.load(open(p))
                img = _map_png(1, m["tiles"], m.get("objects"),
                               m["width"], m["height"])
            except (OSError, ValueError, KeyError, IndexError, TypeError):
                img = None
            if img is None:
                return self._send_json({"ok": False, "error": "cannot render"}, 404)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/slots":
            # v5.6: play-session save slots for the current map
            self._send_json({"slots": _load_slots(), "map": _current_map})
        elif path in ("/icon-512.png", "/favicon.ico"):
            # v5.6: app icon / favicon (splash + home-screen icon)
            try:
                with open(os.path.join(SCRIPT_DIR, "icon-512.png"), "rb") as f:
                    data = f.read()
            except OSError:
                return self._send_json({"ok": False, "error": "no icon yet"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send_json({"ok": False, "error": "not found"}, 404)

    # -- POST --------------------------------------------------------------
    def do_POST(self):
        global traits_grid, hero_override  # v5.6: slots/load rebinds these
        global _current_map, mission_run  # v5.12: rename + mission runs
        global _gold, _item_cells  # v5.13: coin + ground items
        # v5.16: abuse guards run before any mutation.
        if not _rate_ok("POST", self._client_ip()):
            return self._send_json({"ok": False, "error": "slow down"}, 429)
        path = urlparse(self.path).path
        if not self._is_json_request():
            return self._send_json({"ok": False, "error": "Content-Type must be application/json"}, 415)
        if not self._same_origin_ok():
            return self._send_json({"ok": False, "error": "origin/host check failed"}, 403)
        if path != "/api/jslog" and not self._write_key_ok():
            return self._send_json({"ok": False, "error": "read-only in public mode (write key required)"}, 403)
        body = self._read_json()
        if body is None or not isinstance(body, dict):
            # QA 2026-09-19: a JSON list/string/number parsed fine but has no
            # .get — reject it here instead of dying mid-handler with a bare
            # dropped connection and a terminal traceback.
            return self._send_json({"ok": False, "error": "bad JSON"}, 400)

        if path == "/api/update/apply":
            # v5.18: local mode only — a public link must never rewrite the server.
            if PUBLIC_MODE:
                return self._send_json({"ok": False, "error": "updates are local-mode only"}, 403)
            # v5.21: save dirty map work before touching anything, so the
            # update can never eat an unsaved build.
            map_saved = bool(_save_state["dirty"] and _save_now())
            try:
                blobs = {n: _update_fetch(n) for n in UPDATE_FILES}
            except Exception as e:
                return self._send_json({"ok": False, "leg": "github",
                                        "error": f"download failed ({e.__class__.__name__}) — old files untouched",
                                        "hint": _update_hint(e)})
            # v5.21.5: shared installer (sanity checks + version guard +
            # atomic swap); page-fed installs use /api/update/apply-blobs.
            res = _update_install(blobs)
            if res.get("ok"):
                res["map_saved"] = map_saved
            return self._send_json(res)
        if path == "/api/update/apply-blobs":
            # v5.21.5: the PAGE downloaded the files and posts them here.
            # The browser is foreground, so iOS can't freeze it mid-download
            # the way it freezes this server — the server-side work is just
            # the guarded swap, done in milliseconds. Same local-mode rule
            # and same guards as /api/update/apply.
            if PUBLIC_MODE:
                return self._send_json({"ok": False, "error": "updates are local-mode only"}, 403)
            files = body.get("files")
            if not isinstance(files, dict):
                return self._send_json({"ok": False, "error": "files must be a {name: text} object"}, 400)
            blobs = {}
            for n in UPDATE_FILES:
                t = files.get(n)
                if not isinstance(t, str) or not t:
                    return self._send_json({"ok": False, "error": f"missing file in bundle: {n}"}, 400)
                blobs[n] = t.encode("utf-8")
            map_saved = bool(_save_state["dirty"] and _save_now())
            res = _update_install(blobs)
            if res.get("ok"):
                res["map_saved"] = map_saved
            return self._send_json(res)
        if path == "/api/update/rollback":
            # v5.21: put the .update-backup files back — the update, undone.
            # Local mode only, like apply.
            if PUBLIC_MODE:
                return self._send_json({"ok": False, "error": "updates are local-mode only"}, 403)
            if not _update_can_rollback():
                return self._send_json({"ok": False,
                                        "error": "no update backups found — nothing to roll back"})
            restored = []
            try:
                for n in UPDATE_FILES:
                    p = os.path.join(SCRIPT_DIR, n)
                    bak = p + ".update-backup"
                    if os.path.exists(bak):
                        shutil.copy2(bak, p)
                        restored.append(n)
            except OSError as e:
                return self._send_json({"ok": False,
                                        "error": f"rollback failed ({e})"})
            return self._send_json({"ok": True, "restored": restored,
                                    "note": "restart the server to run the restored build"})
        if path == "/api/paint":
            x, y, layer = body.get("x"), body.get("y"), body.get("layer", "tiles")
            if layer not in LAYERS or not isinstance(x, int) or not isinstance(y, int):
                return self._send_json({"ok": False, "error": "x/y ints and layer required"}, 400)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False, "error": "out of bounds"}, 400)
            tile_id = body.get("tile_id")
            if layer == "tiles" and tile_id is None:
                return self._send_json({"ok": False, "error": "no tile selected"}, 400)
            # v5.0: "natural" = the eraser — restore the seed's own ground
            # for this cell instead of a fixed tile 0.
            new_val = _natural_tile(x, y) \
                if layer == "tiles" and tile_id == "natural" \
                else _paint_value(layer, tile_id)
            grid = _grid(layer)
            if grid[y][x] == new_val:
                return self._send_json({"ok": True, "noop": True})
            if layer == "objects":
                # v5.1: painting over him ends his instance — name included —
                # as one undo step.
                def _do():
                    _grid(layer)[y][x] = new_val
                    if object_names.pop(_name_key(x, y), None):
                        _save_names(_current_map)
                    _mark_dirty()
                _undoable("paint object", _do)
            else:
                cmd = core.SetTileCommand(world, x, y, grid[y][x], new_val, layer)
                history.push(cmd)
                cmd.execute()
                _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/stroke":
            layer = body.get("layer", "tiles")
            cells = body.get("cells", [])
            if layer not in LAYERS or not isinstance(cells, list):
                return self._send_json({"ok": False, "error": "cells list and layer required"}, 400)
            paints = []
            seen = set()
            for c in cells:
                x, y = c.get("x"), c.get("y")
                if not isinstance(x, int) or not isinstance(y, int):
                    continue
                if not (0 <= x < world.width and 0 <= y < world.height):
                    continue
                if (x, y) in seen:
                    continue
                seen.add((x, y))
                if layer == "tiles" and c.get("tile_id") is None:
                    continue  # nothing selected: skip instead of crashing
                # v5.0: "natural" = the eraser — the seed's own ground per cell
                tid = c.get("tile_id")
                new_val = _natural_tile(x, y) \
                    if layer == "tiles" and tid == "natural" \
                    else _paint_value(layer, tid)
                grid = _grid(layer)
                if grid[y][x] != new_val:
                    paints.append((x, y, new_val))
            if not paints:
                return self._send_json({"ok": True, "painted": 0, "noop": True})
            if layer == "objects":
                # v5.1: one stroke, one undo step — displaced names go too.
                def _do():
                    g = _grid(layer)
                    touched = False
                    for (sx, sy, nv) in paints:
                        g[sy][sx] = nv
                        if object_names.pop(_name_key(sx, sy), None):
                            touched = True
                    if touched:
                        _save_names(_current_map)
                    _mark_dirty()
                _undoable("stroke objects", _do)
                return self._send_json({"ok": True, "painted": len(paints)})
            cmds = [core.SetTileCommand(world, x, y, _grid(layer)[y][x], nv, layer)
                    for (x, y, nv) in paints]
            # v5.7: linked collision stamps ride in the SAME undo step — one
            # stroke, one history entry, so undo/redo move tiles+collision
            # together instead of stranding the collision behind.
            if layer != "collision":
                seen_link = set()
                for c in body.get("link_cells") or []:
                    lx, ly = c.get("x"), c.get("y")
                    if not isinstance(lx, int) or not isinstance(ly, int):
                        continue
                    if not (0 <= lx < world.width and 0 <= ly < world.height):
                        continue
                    if (lx, ly) in seen_link:
                        continue
                    seen_link.add((lx, ly))
                    lnv = _paint_value("collision", c.get("tile_id"))
                    if world.collision_layer[ly][lx] != lnv:
                        cmds.append(core.SetTileCommand(
                            world, lx, ly, world.collision_layer[ly][lx], lnv,
                            "collision"))
            multi = core.MultiCommand(cmds)
            history.push(multi)
            multi.execute()
            _mark_dirty()
            return self._send_json({"ok": True, "painted": len(cmds)})

        if path == "/api/move":
            # v5.0: slide one object tile — clear + place as ONE undo step.
            # A patrol anchored to him moves with him: the whole route shifts
            # by the same delta when every shifted stop stays walkable,
            # otherwise just his anchor moves and he walks to his old route.
            try:
                fx, fy, tx, ty = (int(body.get(k))
                                 for k in ("fx", "fy", "tx", "ty"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False,
                                        "error": "fx/fy/tx/ty ints required"}, 400)
            for x, y in ((fx, fy), (tx, ty)):
                if not (0 <= x < world.width and 0 <= y < world.height):
                    return self._send_json({"ok": False, "error": "off the map"}, 400)
            if (fx, fy) == (tx, ty):
                return self._send_json({"ok": True, "noop": True})
            tile = world.object_layer[fy][fx]
            if tile is None:
                return self._send_json({"ok": False, "error": "nothing there"}, 400)
            dx, dy = tx - fx, ty - fy
            def _do():
                world.object_layer[fy][fx] = None
                world.object_layer[ty][tx] = tile
                # v5.1: his name walks with him
                nm = object_names.pop(_name_key(fx, fy), None)
                if nm:
                    object_names[_name_key(tx, ty)] = nm
                    _save_names(_current_map)
                for p in _patrols:
                    if p.get("x") == fx and p.get("y") == fy:
                        shifted = [[sx + dx, sy + dy] for sx, sy in p["points"]]
                        if all(0 <= sx < world.width and 0 <= sy < world.height
                               and _walkable(sx, sy) for sx, sy in shifted):
                            p["points"] = shifted
                        p["x"], p["y"] = tx, ty
                _save_patrols()
                _mark_dirty()
            _undoable("move", _do)
            return self._send_json({"ok": True})

        if path == "/api/remove-object":
            # v5.0: lift one placed character — and end his patrol with him,
            # as ONE undo step (the route belonged to him).
            try:
                x, y = int(body.get("x")), int(body.get("y"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "x/y ints required"}, 400)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False, "error": "out of bounds"}, 400)
            if world.object_layer[y][x] is None:
                return self._send_json({"ok": True, "noop": True})
            def _do():
                world.object_layer[y][x] = None
                # v5.1: his name goes with him
                if object_names.pop(_name_key(x, y), None):
                    _save_names(_current_map)
                _patrols[:] = [p for p in _patrols
                               if not (p.get("x") == x and p.get("y") == y)]
                _save_patrols()
                _mark_dirty()
            _undoable("remove", _do)
            return self._send_json({"ok": True})

        if path == "/api/custom-tiles":
            # v3.0: import image(s) as a tile — body: {name, preset,
            # frame_ms, frames: [dataURL, ...]}. Multiple frames = animated tile.
            if not core.PIL_AVAILABLE:
                return self._send_json({"ok": False, "error": "image support unavailable"}, 500)
            name = str(body.get("name", "")).strip()[:24] or "custom"
            preset = body.get("preset", "decor")
            if preset not in TILE_PRESETS:
                return self._send_json({"ok": False, "error": "unknown preset"}, 400)
            frames_in = body.get("frames", [])
            if not isinstance(frames_in, list) or not (1 <= len(frames_in) <= CUSTOM_MAX_FRAMES):
                return self._send_json({"ok": False, "error": f"1-{CUSTOM_MAX_FRAMES} frames required"}, 400)
            try:
                frame_ms = max(80, min(2000, int(body.get("frame_ms", 400))))
            except (TypeError, ValueError):
                frame_ms = 400
            try:
                pil_images = []
                for i, durl in enumerate(frames_in):
                    if not isinstance(durl, str) or not durl.startswith("data:image/"):
                        raise ValueError(f"frame {i}: not an image")
                    if len(durl) > CUSTOM_MAX_FILE_CHARS:
                        raise ValueError(f"frame {i}: too large (keep each under ~1MB)")
                    raw = base64.b64decode(durl.split(",", 1)[1])
                    pil_images.append(self._safe_open_image(raw, f"frame {i}"))
                entry = _store_custom_tile(name, preset, frame_ms, pil_images,
                                           _body_scope(body))
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            return self._send_json({"ok": True, "tile": _custom_public(entry)})

        if path == "/api/autoslice":
            # v3.3: one-button animation — body: {name, preset, frame_ms,
            # image: dataURL}. The server finds the poses and makes the tile.
            if not core.PIL_AVAILABLE:
                return self._send_json({"ok": False, "error": "image support unavailable"}, 500)
            name = str(body.get("name", "")).strip()[:24] or "custom"
            preset = body.get("preset", "decor")
            if preset not in TILE_PRESETS:
                return self._send_json({"ok": False, "error": "unknown preset"}, 400)
            try:
                frame_ms = max(80, min(2000, int(body.get("frame_ms", 400))))
            except (TypeError, ValueError):
                frame_ms = 400
            durl = body.get("image", "")
            try:
                if not isinstance(durl, str) or not durl.startswith("data:image/"):
                    raise ValueError("not an image")
                if len(durl) > CUSTOM_MAX_FILE_CHARS:
                    raise ValueError("too large (keep under ~1MB)")
                raw = base64.b64decode(durl.split(",", 1)[1])
                frames = _autoslice_pil(self._safe_open_image(raw, "autoslice"))
                entry = _store_custom_tile(name, preset, frame_ms, frames,
                                           _body_scope(body))
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            return self._send_json({"ok": True, "tile": _custom_public(entry),
                                    "frames": len(frames), "single": len(frames) == 1})

        if path == "/api/bring-to-life":
            # v3.4: one picture -> living character. If it's a sheet, slice the
            # poses; if it's a single pose, fake the walk with a bob.
            # Body: {name, preset, frame_ms, image: dataURL}.
            if not core.PIL_AVAILABLE:
                return self._send_json({"ok": False, "error": "image support unavailable"}, 500)
            name = str(body.get("name", "")).strip()[:24] or "custom"
            preset = body.get("preset", "decor")
            if preset not in TILE_PRESETS:
                return self._send_json({"ok": False, "error": "unknown preset"}, 400)
            try:
                frame_ms = max(80, min(2000, int(body.get("frame_ms", 400))))
            except (TypeError, ValueError):
                frame_ms = 400
            durl = body.get("image", "")
            try:
                if not isinstance(durl, str) or not durl.startswith("data:image/"):
                    raise ValueError("not an image")
                if len(durl) > CUSTOM_MAX_FILE_CHARS:
                    raise ValueError("too large (keep under ~1MB)")
                raw = base64.b64decode(durl.split(",", 1)[1])
                img = self._safe_open_image(raw, "sheet")
                frames = _autoslice_pil(img)
                method = "sliced"
                if len(frames) == 1:
                    frames = _walkbob_frames(img)
                    method = "walk"
                entry = _store_custom_tile(name, preset, frame_ms, frames,
                                           _body_scope(body))
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            return self._send_json({"ok": True, "tile": _custom_public(entry),
                                    "frames": len(frames), "method": method})

        if path == "/api/sprite/import":
            # v5.11: sprite-sheet importer. Body:
            #   {sheets: [{image: dataURL, cell: 8|16|32, ox?, oy?, picks: [
            #      {kind:"tile", index, name, preset} |
            #      {kind:"anim", start, count, name, preset, frame_ms?}]}],
            #    scope}
            # Each sheet is sliced with the GUI-free core model (the same math
            # the browser uses for its Canvas preview), cells upscale 8/16->32
            # with nearest neighbor, and every pick becomes a tile. Multiple
            # sheets = per-layer source mixing (ground from one sheet,
            # creatures from another, one batch).
            if not core.PIL_AVAILABLE:
                return self._send_json({"ok": False,
                                        "error": "image support unavailable"}, 500)
            sheets = body.get("sheets")
            if not isinstance(sheets, list) or not sheets:
                return self._send_json({"ok": False, "error": "sheets required"},
                                       400)
            if len(sheets) > 4:
                return self._send_json({"ok": False, "error": "max 4 sheets"},
                                       400)
            scope = _body_scope(body)
            made = []
            try:
                for sh in sheets:
                    durl = sh.get("image", "")
                    if not isinstance(durl, str) or not durl.startswith("data:image/"):
                        raise ValueError("not an image")
                    if len(durl) > CUSTOM_MAX_FILE_CHARS:
                        raise ValueError("too large (keep under ~1MB)")
                    try:
                        cell = int(sh.get("cell", 16))
                    except (TypeError, ValueError):
                        raise ValueError("cell must be 8, 16, or 32")
                    if cell not in core.SPRITE_CELL_SIZES:
                        raise ValueError("cell must be 8, 16, or 32")
                    try:
                        ox = max(0, int(sh.get("ox", 0)))
                        oy = max(0, int(sh.get("oy", 0)))
                    except (TypeError, ValueError):
                        raise ValueError("bad offset")
                    raw = base64.b64decode(durl.split(",", 1)[1])
                    img = self._safe_open_image(raw, "sheet")
                    sw, sh_px = img.size
                    if sw > 1024 or sh_px > 1024:
                        raise ValueError("sheet too big (max 1024px)")
                    flat = list(img.getdata())
                    cells = core.slice_sheet(flat, sw, sh_px, cell, ox, oy)
                    if not cells:
                        raise ValueError("no whole cells fit — check cell size")
                    picks = sh.get("picks") or []
                    for p in picks:
                        if p.get("preset", "decor") not in TILE_PRESETS:
                            raise ValueError("unknown preset")
                    for job in core.sprite_import_plan(cells, picks):
                        frames = []
                        for c in job["frames"]:
                            up = core.upscale_nearest(c)
                            fim = core.Image.new("RGBA", (32, 32))
                            fim.putdata([tuple(p) for p in up["pixels"]])
                            frames.append(fim)
                        entry = _store_custom_tile(
                            job["name"], job["preset"], job["frame_ms"],
                            frames, scope)
                        made.append(_custom_public(entry))
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            return self._send_json({"ok": True, "tiles": made,
                                    "count": len(made)})

        if path == "/api/patrols/create":
            # v3.4: {tile_id, points: [[x,y], ...]} — 2-8 walkable stops.
            # v5.0: patrols are ASSIGNED to already-placed characters, never
            # spawned — {x, y} must already hold that character's tile, or the
            # call is rejected. {replace_id} re-routes atomically: old route
            # out, new route in, one undo step.
            try:
                tid = int(body.get("tile_id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad tile"}, 400)
            if tid not in assets.tiles:
                return self._send_json({"ok": False, "error": "unknown tile"}, 400)
            pts_in = body.get("points", [])
            try:
                pts = [[int(a), int(b)] for a, b in pts_in]
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad points"}, 400)
            if not (2 <= len(pts) <= 8):
                return self._send_json({"ok": False, "error": "tap 2-8 stops"}, 400)
            for x, y in pts:
                if not (0 <= x < world.width and 0 <= y < world.height):
                    return self._send_json({"ok": False, "error": "stop off the map"}, 400)
                if not _walkable(x, y):
                    return self._send_json({"ok": False, "error": "a stop is blocked"}, 400)
            try:
                ax, ay = int(body.get("x")), int(body.get("y"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "anchor x/y required"}, 400)
            if not (0 <= ax < world.width and 0 <= ay < world.height):
                return self._send_json({"ok": False, "error": "anchor off the map"}, 400)
            if world.object_layer[ay][ax] != tid:
                # v5.0: a patrol never creates its character — the tile must
                # already be standing at the anchor.
                return self._send_json(
                    {"ok": False,
                     "error": "no such character at the anchor — place him first"},
                    400)
            replace_id = body.get("replace_id")
            if replace_id is not None:
                try:
                    replace_id = int(replace_id)
                except (TypeError, ValueError):
                    return self._send_json({"ok": False, "error": "bad replace_id"}, 400)
                if not any(p["id"] == replace_id for p in _patrols):
                    return self._send_json({"ok": False, "error": "patrol not found"}, 404)
            p = {"id": _patrol_seq["next"], "tile_id": tid,
                 "x": ax, "y": ay, "points": pts}
            def _do():
                if replace_id is not None:
                    _patrols[:] = [q for q in _patrols if q["id"] != replace_id]
                # v5.0: the character is already standing at the anchor — a
                # patrol only assigns the route, it never places or moves him.
                _patrol_seq["next"] += 1
                _patrols.append(p)
                _save_patrols()
                _mark_dirty()
            _undoable("re-route patrol" if replace_id is not None else "assign patrol", _do)
            return self._send_json({"ok": True, "patrol": p})

        if path == "/api/patrols/delete":
            # v3.4: {id}
            try:
                pid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            if not any(p["id"] == pid for p in _patrols):
                return self._send_json({"ok": False, "error": "not found"}, 404)
            def _do():
                _patrols[:] = [p for p in _patrols if p["id"] != pid]
                _save_patrols()
                _mark_dirty()
            _undoable("delete patrol", _do)  # v5.0
            return self._send_json({"ok": True})

        if path == "/api/missions/create":
            # v5.12: Melody designs a mission from preset + questionnaire.
            # {preset, answers: {name, difficulty, reward, target/targets,
            #  what, count, ticks}}
            preset = body.get("preset")
            answers = body.get("answers") or {}
            try:
                m = core.build_mission(preset, answers)
            except ValueError as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            m["id"] = _mission_seq["next"]
            _mission_seq["next"] += 1
            m["placed"] = []
            m["danger"] = []
            _missions.append(m)
            _save_missions(_current_map)
            _log_event(f"mission created: {m['name']}")
            diff = _DIFF_WORDS[m["difficulty"]]
            return self._send_json({
                "ok": True, "mission": m,
                "melody_says": _melody_says("built", m["id"], name=m["name"],
                                            diff=diff)})

        if path == "/api/missions/apply":
            # v5.12: Melody builds it — places enemy flows per difficulty,
            # playtests every objective herself, reports back.
            try:
                mid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            m = _mission_by_id(mid)
            if m is None:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            for other in _missions:
                other["active"] = (other["id"] == mid)
            placed, danger = _mission_place_hazards(m)
            issues = _mission_playtest(m)
            _save_missions(_current_map)
            _mark_dirty()
            _log_event(f"mission applied: {m['name']} ({placed} hazards)")
            if issues:
                says = _melody_says("tested_bad", m["id"],
                                    issue=issues[0])
            else:
                says = _melody_says("tested_ok", m["id"], name=m["name"],
                                    hazards=placed)
            return self._send_json({"ok": True, "mission": m,
                                    "hazards": placed, "danger": danger,
                                    "issues": issues, "melody_says": says})

        if path == "/api/missions/delete":
            # v5.12: {id} — pulls its enemy flows off the map too
            try:
                mid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            m = _mission_by_id(mid)
            if m is None:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            _mission_clear_hazards(m)
            _missions[:] = [x for x in _missions if x["id"] != mid]
            _save_missions(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/missions/suggest-target":
            # v5.12: Melody picks her own marks — walkable cells far from
            # spawn and from each other. {n}
            try:
                n = max(1, min(4, int(body.get("n", 1))))
            except (TypeError, ValueError):
                n = 1
            sx, sy = _find_spawn()
            rng = random.Random()
            cands = [(x, y) for y in range(world.height)
                     for x in range(world.width)
                     if _walkable(x, y)
                     and abs(x - sx) + abs(y - sy) >= 4]
            rng.shuffle(cands)
            picked = []
            for c in cands:
                if len(picked) >= n:
                    break
                if all(abs(c[0] - p[0]) + abs(c[1] - p[1]) >= 5
                       for p in picked):
                    picked.append(c)
            return self._send_json({"ok": True,
                                    "targets": [list(c) for c in picked]})

        # ---- v5.13: gear -------------------------------------------------
        if path == "/api/items/create":
            # {name, tile_id, kind, power, effect, stack, price}
            try:
                d = core.build_item(body.get("name"), body.get("tile_id"),
                                    body.get("kind", "trinket"),
                                    body.get("power", 0),
                                    body.get("effect", "none"),
                                    body.get("stack", core.ITEM_MAX_STACK),
                                    body.get("price", 0))
            except ValueError as e:
                return self._send_json({"ok": False, "error": str(e)}, 400)
            d["id"] = _item_seq["next"]
            _item_seq["next"] += 1
            _items.append(d)
            _save_items(_current_map)
            _log_event(f"item created: {d['name']}")
            return self._send_json({"ok": True, "item": d})

        if path == "/api/items/delete":
            try:
                iid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            _items[:] = [t for t in _items if t["id"] != iid]
            _item_cells = {k: v for k, v in _item_cells.items()
                           if v[0] != iid}
            for n in _npcs:  # merchants stop stocking it too
                n["stock"] = [ln for ln in n.get("stock", [])
                              if ln.get("item") != iid]
                g = n.get("gear") or {}
                if g.get("weapon") == iid:
                    g["weapon"] = None
                if g.get("tool") == iid:
                    g["tool"] = None
            if _equipped.get("weapon") == iid:
                _equipped["weapon"] = None
            if _equipped.get("tool") == iid:
                _equipped["tool"] = None
            _save_items(_current_map)
            _save_npcs(_current_map)
            _save_gear(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/items/place":
            # {item, x, y, qty?} — drop gear on the map
            try:
                iid = int(body.get("item"))
                x, y = int(body.get("x")), int(body.get("y"))
                qty = max(1, min(99, int(body.get("qty", 1))))
            except (TypeError, ValueError):
                return self._send_json({"ok": False,
                                        "error": "item/x/y required"}, 400)
            if _item_by_id(iid) is None:
                return self._send_json({"ok": False,
                                        "error": "unknown item"}, 404)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False,
                                        "error": "off the map"}, 400)
            key = _item_cell_key(x, y)
            have = _item_cells.get(key, [iid, 0])
            if have[0] != iid:
                return self._send_json({"ok": False,
                                        "error": "something else is there"},
                                       409)
            _item_cells[key] = [iid, have[1] + qty]
            _save_items(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/items/unplace":
            try:
                x, y = int(body.get("x")), int(body.get("y"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False,
                                        "error": "x/y required"}, 400)
            _item_cells.pop(_item_cell_key(x, y), None)
            _save_items(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/npcs/create":
            # {tile_id, x, y} — put a folk on the map
            try:
                tid = int(body.get("tile_id"))
                x, y = int(body.get("x")), int(body.get("y"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False,
                                        "error": "tile_id/x/y required"}, 400)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False,
                                        "error": "off the map"}, 400)
            nid = _npc_seq["next"]
            _npc_seq["next"] += 1
            n = {"id": nid, "name": f"Traveler {nid}", "tile_id": tid,
                 "x": x, "y": y, "role": "villager",
                 "line": "Mind the roads, traveler.", "stock": [],
                 "gear": {"weapon": None, "tool": None}}
            _npcs.append(n)
            _save_npcs(_current_map)
            _mark_dirty()
            _log_event(f"npc placed: {n['name']}")
            return self._send_json({"ok": True, "npc": n})

        if path == "/api/npcs/update":
            # {id, name?, role?, line?}
            try:
                nid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            n = _npc_by_id(nid)
            if n is None:
                return self._send_json({"ok": False,
                                        "error": "not found"}, 404)
            if "name" in body:
                n["name"] = str(body.get("name") or "").strip()[:32] \
                    or n["name"]
            if "role" in body:
                if body.get("role") not in ("villager", "merchant"):
                    return self._send_json({"ok": False,
                                            "error": "bad role"}, 400)
                n["role"] = body.get("role")
            if "line" in body:
                n["line"] = str(body.get("line") or "").strip()[:120]
            if "gear" in body:
                # {weapon: id|null, tool: id|null} — what's in their hands
                g = body.get("gear") or {}
                gear = {"weapon": None, "tool": None}
                for slot, kind in (("weapon", "weapon"), ("tool", "tool")):
                    iid = g.get(slot)
                    if iid is None:
                        continue
                    try:
                        iid = int(iid)
                    except (TypeError, ValueError):
                        return self._send_json(
                            {"ok": False, "error": "bad gear id"}, 400)
                    d = _item_by_id(iid)
                    if d is None or d.get("kind") != kind:
                        return self._send_json(
                            {"ok": False,
                             "error": f"{slot} must be a {kind}"}, 400)
                    gear[slot] = iid
                n["gear"] = gear
            _save_npcs(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True, "npc": n})

        if path == "/api/npcs/delete":
            try:
                nid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            _npcs[:] = [n for n in _npcs if n["id"] != nid]
            _save_npcs(_current_map)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/npcs/stock":
            # {id, stock: [{item, price, qty}]} — a merchant's shelves
            try:
                nid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            n = _npc_by_id(nid)
            if n is None:
                return self._send_json({"ok": False,
                                        "error": "not found"}, 404)
            if n.get("role") != "merchant":
                return self._send_json({"ok": False,
                                        "error": "not a merchant"}, 400)
            stock = body.get("stock") or []
            if not isinstance(stock, list) or len(stock) > 24:
                return self._send_json({"ok": False,
                                        "error": "bad stock"}, 400)
            clean = []
            for ln in stock:
                try:
                    iid = int(ln.get("item"))
                    price = max(0, min(9999, int(ln.get("price", 0))))
                    qty = int(ln.get("qty", 1))
                    qty = -1 if qty < 0 else min(99, qty)
                except (TypeError, ValueError, AttributeError):
                    return self._send_json({"ok": False,
                                            "error": "bad stock line"}, 400)
                if _item_by_id(iid) is None:
                    return self._send_json({"ok": False,
                                            "error": "unknown item"}, 404)
                clean.append({"item": iid, "price": price, "qty": qty})
            n["stock"] = clean
            _save_npcs(_current_map)
            return self._send_json({"ok": True, "npc": n})

        if path == "/api/inv/equip":
            # {item} — put a weapon or tool in the hero's hands
            try:
                iid = int(body.get("item"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            d = _item_by_id(iid)
            if d is None or d["kind"] not in ("weapon", "tool"):
                return self._send_json({"ok": False,
                                        "error": "not equipable"}, 400)
            if _inv_count(iid) < 1:
                return self._send_json({"ok": False,
                                        "error": "not in your pack"}, 400)
            _equipped[d["kind"]] = iid
            _save_gear(_current_map)
            return self._send_json(_inv_state())

        if path == "/api/inv/unequip":
            slot = body.get("slot")
            if slot not in ("weapon", "tool"):
                return self._send_json({"ok": False, "error": "bad slot"},
                                       400)
            _equipped[slot] = None
            _save_gear(_current_map)
            return self._send_json(_inv_state())

        if path == "/api/inv/use":
            # {item} — eat food (belly+), quaff a draught is food-kind too
            try:
                iid = int(body.get("item"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            d = _item_by_id(iid)
            if d is None or d["kind"] != "food":
                return self._send_json({"ok": False,
                                        "error": "can't use that"}, 400)
            if not _inv_take(iid, 1):
                return self._send_json({"ok": False,
                                        "error": "none left"}, 400)
            if world_profile.get("meters", {}).get("belly"):
                _meters["belly"] = max(0, min(10,
                                              _meters["belly"] + d["power"]))
            return self._send_json({**_inv_state(), "nature": _nature_state(),
                                    "events": [{"t": "toast",
                                                "text": f"😋 ate {d['name']}"}]})

        if path == "/api/inv/drop":
            # {item} — set one down at the hero's feet
            try:
                iid = int(body.get("item"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            if _item_by_id(iid) is None or not _inv_take(iid, 1):
                return self._send_json({"ok": False,
                                        "error": "not in your pack"}, 400)
            hx, hy = play["tx"], play["ty"]
            key = _item_cell_key(hx, hy)
            have = _item_cells.get(key)
            if have and have[0] != iid:
                _inv_add(iid, 1)  # put it back — can't drop here
                return self._send_json({"ok": False,
                                        "error": "something else is there"},
                                       409)
            _item_cells[key] = [iid, (have[1] if have else 0) + 1]
            if _inv_count(iid) == 0:
                if _equipped.get("weapon") == iid:
                    _equipped["weapon"] = None
                if _equipped.get("tool") == iid:
                    _equipped["tool"] = None
            _save_items(_current_map)
            _mark_dirty()
            return self._send_json(_inv_state())

        if path == "/api/shop/buy":
            # {npc, item} — buy one off a merchant's shelf
            try:
                nid, iid = int(body.get("npc")), int(body.get("item"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"},
                                       400)
            n = _npc_by_id(nid)
            if n is None or n.get("role") != "merchant":
                return self._send_json({"ok": False,
                                        "error": "not a merchant"}, 404)
            ln = next((s for s in n.get("stock", [])
                       if s.get("item") == iid and s.get("qty", 0) != 0),
                      None)
            if ln is None:
                return self._send_json({"ok": False,
                                        "error": "sold out"}, 404)
            if _gold < ln["price"]:
                return self._send_json({"ok": False,
                                        "error": "not enough gold"}, 400)
            _gold -= ln["price"]
            if ln["qty"] > 0:
                ln["qty"] -= 1  # -1 = endless shelf, never runs out
            _inv_add(iid, 1)
            _save_npcs(_current_map)
            _save_gear(_current_map)
            d = _item_by_id(iid)
            return self._send_json({**_inv_state(), "npc": n,
                                    "events": [{"t": "toast",
                                                "text": f"🪙 bought "
                                                        f"{d['name']}"}]})

        if path == "/api/shop/sell":
            # {item} — sell one from the pack at half price
            try:
                iid = int(body.get("item"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            d = _item_by_id(iid)
            if d is None or not _inv_take(iid, 1):
                return self._send_json({"ok": False,
                                        "error": "not in your pack"}, 400)
            gain = max(1, d.get("price", 0) // 2)
            _gold += gain
            _save_gear(_current_map)
            if _inv_count(iid) == 0:
                if _equipped.get("weapon") == iid:
                    _equipped["weapon"] = None
                if _equipped.get("tool") == iid:
                    _equipped["tool"] = None
            return self._send_json({**_inv_state(), "gained": gain,
                                    "events": [{"t": "toast",
                                                "text": f"🪙 sold "
                                                        f"{d['name']} "
                                                        f"(+{gain})"}]})

        if path == "/api/patrol-paths":
            # v3.4: {legs: [[[x1,y1],[x2,y2]], ...]} -> {paths: [[[x,y],...]]}.
            # NPC legs ride the same Dijkstra the hero uses (walls avoided,
            # water swimmable).
            legs = body.get("legs", [])
            if not isinstance(legs, list) or len(legs) > 64:
                return self._send_json({"ok": False, "error": "bad legs"}, 400)
            paths = []
            for leg in legs:
                try:
                    (x1, y1), (x2, y2) = leg
                    cells, _swim, _deep = _find_path(int(x1), int(y1), int(x2), int(y2))
                except (TypeError, ValueError):
                    cells = []
                paths.append([list(c) for c in cells])
            return self._send_json({"ok": True, "paths": paths})

        if path == "/api/custom/update":
            # v3.3: rename / re-designate an imported tile — {id, name?, preset?}
            try:
                tid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            entry, scope = _find_custom(tid)
            if entry is None:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            if "name" in body:
                entry["name"] = str(body.get("name", "")).strip()[:24] or entry["name"]
            if "preset" in body:
                preset = body.get("preset")
                if preset not in TILE_PRESETS:
                    return self._send_json({"ok": False, "error": "unknown preset"}, 400)
                entry["preset"] = preset
                entry["solid"] = TILE_PRESETS[preset]["solid"]
                entry["height"] = TILE_PRESETS[preset]["height"]
                entry["swim"] = bool(TILE_PRESETS[preset].get("swim", False))
                entry["deep"] = bool(TILE_PRESETS[preset].get("deep", False))
            if "height" in body:
                # v5.10: explicit per-tile height override (-2..3)
                try:
                    entry["height"] = max(core.HEIGHT_MIN,
                                          min(core.HEIGHT_MAX, int(body.get("height"))))
                except (TypeError, ValueError):
                    return self._send_json({"ok": False, "error": "bad height"}, 400)
            t = assets.tiles.get(tid)
            if t is not None:
                t["name"] = entry["name"]
                t["preset"] = entry["preset"]
                t["height"] = entry["height"]
                t["properties"]["height"] = entry["height"]
                t["properties"]["solid"] = bool(entry.get("solid", False))
                t["properties"]["swim"] = bool(entry.get("swim", False))
                t["properties"]["deep"] = bool(entry.get("deep", False))
            _save_custom_registry(scope)
            return self._send_json({"ok": True, "tile": _custom_public(entry)})

        if path == "/api/custom/share":
            # v3.8: move an imported tile between shelves — {id, scope}.
            # "shared" publishes it to the shared library (git-tracked, so a
            # pull delivers it to every deployment); "local" pulls it back to
            # this device only.
            try:
                tid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            scope = _body_scope(body)
            entry, cur = _find_custom(tid)
            if entry is None:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            if entry.get("pack") == "starter":
                # v5.9: starter tiles share one packed strip — built in, can't move
                return self._send_json({"ok": False, "error": "starter tiles are built in"}, 403)
            if cur != scope:
                src_dir = SHARED_DIR if cur == "shared" else CUSTOM_DIR
                dst_dir = SHARED_DIR if scope == "shared" else CUSTOM_DIR
                try:
                    for fn in entry.get("files", []):
                        os.rename(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))
                except OSError as e:
                    return self._send_json({"ok": False, "error": f"could not move files: {e}"}, 500)
                if cur == "shared":
                    _shared_tiles[:] = [e for e in _shared_tiles if int(e["id"]) != tid]
                    _custom_tiles.append(entry)
                else:
                    _custom_tiles[:] = [e for e in _custom_tiles if int(e["id"]) != tid]
                    _shared_tiles.append(entry)
                entry["scope"] = scope
                _save_custom_registry("local")
                _save_custom_registry("shared")
            return self._send_json({"ok": True, "tile": _custom_public(entry)})

        if path == "/api/custom/delete":
            # v3.3: delete an imported tile — {id}. Files removed, map scrubbed.
            try:
                tid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            entry, scope = _find_custom(tid)
            if entry is None:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            if entry.get("pack") == "starter":
                # v5.9: starter tiles share one packed strip — built in, can't delete
                return self._send_json({"ok": False, "error": "starter tiles are built in"}, 403)
            if entry.get("_from_pack"):
                # v5.14: art-pack tiles share packed strips — delete the pack's
                # files to uninstall it, not tile by tile
                return self._send_json({"ok": False, "error": "pack tiles uninstall with their pack"}, 403)
            tile_dir = SHARED_DIR if scope == "shared" else CUSTOM_DIR
            if scope == "shared":
                _shared_tiles[:] = [e for e in _shared_tiles if int(e["id"]) != tid]
            else:
                _custom_tiles[:] = [e for e in _custom_tiles if int(e["id"]) != tid]
            for fn in entry.get("files", []):
                try:
                    os.remove(os.path.join(tile_dir, fn))
                except OSError:
                    pass
            assets.tiles.pop(tid, None)
            # v3.4: patrols riding a deleted tile go with it
            if any(p["tile_id"] == tid for p in _patrols):
                _patrols[:] = [p for p in _patrols if p["tile_id"] != tid]
                _save_patrols()
            for y in range(world.height):
                for x in range(world.width):
                    if world.data[y][x] == tid:
                        world.data[y][x] = 0
                    if world.object_layer[y][x] == tid:
                        world.object_layer[y][x] = None
            _save_custom_registry(scope)
            _mark_dirty()
            return self._send_json({"ok": True})

        if path == "/api/undo":
            ok = history.undo()
            if ok:
                _mark_dirty()
            return self._send_json({"ok": ok})

        if path == "/api/redo":
            ok = history.redo()
            if ok:
                _mark_dirty()
            return self._send_json({"ok": ok})

        if path == "/api/generate":
            # v5.16: a named preset is a deterministic recipe — same seed,
            # same map, every time. A raw biome still works on its own.
            preset_id = str(body.get("preset", "") or "")
            noise_over = None
            biome = str(body.get("biome", "dungeon"))
            if preset_id:
                preset = core.GENERATION_PRESETS.get(preset_id)
                if not preset:
                    return self._send_json({"ok": False,
                                            "error": "unknown preset"}, 400)
                biome = preset["biome"]
                noise_over = preset["noise"] or None
            if biome not in core.BIOMES:
                return self._send_json({"ok": False, "error": "unknown biome"}, 400)
            seed = body.get("seed")
            seed = int(seed) if isinstance(seed, int) or (isinstance(seed, str) and seed.strip().lstrip("-").isdigit()) else None
            if seed is None:
                # v5.0: a blank seed still gets a concrete one — otherwise the
                # build can't be reproduced or restored by the eraser.
                seed = random.randrange(1_000_000_000)
            def _do():
                world.generate_biome(biome, seed, noise_over)
                map_meta["biome"] = biome  # v5.0: the eraser needs the seed
                map_meta["seed"] = seed
                if preset_id:
                    map_meta["preset"] = preset_id  # v5.16: which recipe
                rules.clear()
                rules.update(DEFAULT_RULES)  # v3.7: fresh build, fresh rules
                world_profile["meters"] = dict(DEFAULT_WORLD["meters"])  # v4.0
                world_profile["weather"] = DEFAULT_WORLD["weather"]  # v4.1: fresh sky
                traits_grid[:] = _blank_traits()  # v4.0: fresh build, fresh nature
                object_names.clear()  # v5.1: fresh build, no names yet
                _save_names(_current_map)
                _save_rules(_current_map)
                _save_traits(_current_map)
                _mark_dirty()
            _undoable("generate " + biome, _do)  # v5.0: whole build, one step
            _log_event(f"generated {biome} (seed {seed})")  # v5.6
            return self._send_json({"ok": True, "biome": biome, "seed": seed,
                                    "rules": rules})

        if path == "/api/newmap":
            # v5.20: Reset map — archive the current build first (world.save
            # rotates it to .backup, restorable from Load), then a fresh
            # blank map takes its place: default rules, nature and names.
            # One undo step, same as generate.
            w, h = world.width, world.height
            def _do():
                _save_now(_current_map)  # archive -> .backup before wiping
                world.data = [[0 for _ in range(w)] for _ in range(h)]
                world.object_layer = [[None for _ in range(w)]
                                      for _ in range(h)]
                world.collision_layer = [[False for _ in range(w)]
                                         for _ in range(h)]
                rules.clear()
                rules.update(DEFAULT_RULES)  # v3.7: fresh build, fresh rules
                world_profile["meters"] = dict(DEFAULT_WORLD["meters"])  # v4.0
                world_profile["weather"] = DEFAULT_WORLD["weather"]  # v4.1
                traits_grid[:] = _blank_traits()  # v4.0: fresh nature
                object_names.clear()  # v5.1: fresh build, no names yet
                _save_names(_current_map)
                _save_rules(_current_map)
                _save_traits(_current_map)
                _mark_dirty()
            _undoable("reset map", _do)  # v5.0: whole reset, one step
            _log_event("map reset to blank")  # v5.6
            return self._send_json({"ok": True})

        if path == "/api/clear_layer":
            layer = body.get("layer", "tiles")
            if layer not in LAYERS:
                return self._send_json({"ok": False, "error": "bad layer"}, 400)
            grid, default = _grid(layer), _default_value(layer)
            if all(v == default for row in grid for v in row):
                return self._send_json({"ok": True, "noop": True})
            def _do():
                grid, default = _grid(layer), _default_value(layer)
                for yy in range(world.height):
                    for xx in range(world.width):
                        grid[yy][xx] = default
                if layer == "objects" and object_names:
                    # v5.1: clearing the cast clears their names
                    object_names.clear()
                    _save_names(_current_map)
                _mark_dirty()
            _undoable("clear " + layer, _do)  # v5.0
            return self._send_json({"ok": True, "layer": layer})

        if path == "/api/resize":
            try:
                w, h = int(body.get("width", world.width)), int(body.get("height", world.height))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "width/height ints required"}, 400)
            w, h = max(4, min(64, w)), max(4, min(64, h))
            if w == world.width and h == world.height:
                return self._send_json({"ok": True, "noop": True})
            def _do():
                world.resize(w, h)
                _fit_traits()  # v4.0: keep the nature grid matched to the map
                _save_traits(_current_map)
                # v5.1: names outside the new bounds fall off with their tiles
                for k in [k for k in object_names
                          if int(k.split(",")[0]) >= w or int(k.split(",")[1]) >= h]:
                    del object_names[k]
                _save_names(_current_map)
                _mark_dirty()
            _undoable("resize", _do)  # v5.0: dims undo too now
            return self._send_json({"ok": True, "width": w, "height": h})

        if path == "/api/save":
            name = _safe_name(body.get("filename") or DEFAULT_SAVE)
            if not name.endswith(".json"):
                name += ".json"
            _revert_rule_mods()  # v3.9: a playtest never permanently edits the build
            _revert_nature_mods()  # v4.0: gathered wood / built fires neither
            now = int(time.time())
            map_meta.setdefault("created", now)  # v5.6: map metadata
            map_meta["modified"] = now
            ok = world.save(os.path.join(SCRIPT_DIR, name),
                            schema=SCHEMA_VERSION)  # v5.16: stamp the schema
            if ok:
                _save_rules(name)  # v3.7
                _save_missions(name)  # v5.12: Melody's missions ride along
                _log_event(f"saved {name}")
            return self._send_json({"ok": ok, "file": name})

        if path == "/api/load":
            name = _safe_name(body.get("filename"))
            if not name:
                return self._send_json({"ok": False, "error": "filename required"}, 400)
            p = os.path.join(SCRIPT_DIR, name)
            if not os.path.isfile(p):
                return self._send_json({"ok": False, "error": "file not found"}, 404)
            ok = world.load(p) or world.load_csv(p)
            if ok:
                history.undo_stack.clear()
                history.redo_stack.clear()
                _load_rules(name)  # v3.7: this build's rules come with it
                _load_traits(name)  # v4.0: this build's nature comes with it
                _load_names(name)  # v5.1: this build's names come with it
                _load_missions(name)  # v5.12: Melody's missions come with it
                _load_items(name)  # v5.13: this map's gear
                _load_npcs(name)  # v5.13: this map's folks
                _mission_reconcile_patrols()  # v5.13: hazards stay on their map
                _log_event(f"loaded {name}")
            return self._send_json({"ok": ok, "width": world.width,
                                    "height": world.height, "rules": rules})

        if path == "/api/validate":
            # v5.6: one-tap map check — spawn, reachability, tile ids
            return self._send_json({"ok": True, "issues": _validate_map()})

        if path == "/api/maps/rename":
            # v5.6: rename a map + its sidecars
            src = _safe_name(body.get("from"))
            dst = _safe_name(body.get("to"))
            if not src or not dst:
                return self._send_json({"ok": False, "error": "from/to required"}, 400)
            if not dst.endswith(".json"):
                dst += ".json"
            if os.path.exists(os.path.join(SCRIPT_DIR, dst)):
                return self._send_json({"ok": False, "error": "name taken"}, 409)
            moved = 0
            for p in _map_sidecars(src):
                if os.path.isfile(p):
                    base = dst[:-5] if dst.endswith(".json") else dst
                    ext = p[len(os.path.join(SCRIPT_DIR,
                                             src[:-5] if src.endswith(".json") else src)):]
                    os.rename(p, os.path.join(SCRIPT_DIR, base + ext))
                    moved += 1
            if _current_map == src:
                _current_map = dst
            _log_event(f"renamed {src} -> {dst}")
            return self._send_json({"ok": moved > 0, "file": dst})

        if path == "/api/maps/duplicate":
            # v5.6: copy a map + its sidecars (shutil is imported at module top)
            src = _safe_name(body.get("from"))
            dst = _safe_name(body.get("to"))
            if not src:
                return self._send_json({"ok": False, "error": "from required"}, 400)
            if not dst:
                base = src[:-5] if src.endswith(".json") else src
                dst = base + " copy.json"
            if not dst.endswith(".json"):
                dst += ".json"
            if os.path.exists(os.path.join(SCRIPT_DIR, dst)):
                return self._send_json({"ok": False, "error": "name taken"}, 409)
            copied = 0
            src_base = src[:-5] if src.endswith(".json") else src
            dst_base = dst[:-5] if dst.endswith(".json") else dst
            for p in _map_sidecars(src):
                if os.path.isfile(p):
                    ext = p[len(os.path.join(SCRIPT_DIR, src_base)):]
                    shutil.copy2(p, os.path.join(SCRIPT_DIR, dst_base + ext))
                    copied += 1
            _log_event(f"duplicated {src} -> {dst}")
            return self._send_json({"ok": copied > 0, "file": dst})

        if path == "/api/maps/delete":
            # v5.6: delete moves to _trash/ — never permanent (house rule)
            name = _safe_name(body.get("file"))
            if not name:
                return self._send_json({"ok": False, "error": "file required"}, 400)
            if name == DEFAULT_SAVE:
                return self._send_json({"ok": False, "error": "cannot delete the default map"}, 400)
            os.makedirs(_TRASH_DIR, exist_ok=True)
            moved = 0
            src_base = name[:-5] if name.endswith(".json") else name
            for p in _map_sidecars(name):
                if os.path.isfile(p):
                    ext = p[len(os.path.join(SCRIPT_DIR, src_base)):]
                    dest = os.path.join(_TRASH_DIR, src_base + ext)
                    n = 1
                    while os.path.exists(dest):
                        dest = os.path.join(_TRASH_DIR, f"{src_base}.{n}{ext}")
                        n += 1
                    os.rename(p, dest)
                    moved += 1
            _log_event(f"trashed {name}")
            return self._send_json({"ok": moved > 0})

        if path == "/api/maps/import":
            # v5.6: load a map JSON someone sends you (validated on the way in)
            name = _safe_name(body.get("filename"))
            data = body.get("data")
            if not name or not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "filename + data required"}, 400)
            if not name.endswith(".json"):
                name += ".json"
            try:
                w, h = int(data["width"]), int(data["height"])
                assert 1 <= w <= 256 and 1 <= h <= 256
                for key in ("tiles", "objects", "collision"):
                    rows = data[key]
                    assert isinstance(rows, list) and len(rows) == h
                    for row in rows:
                        assert isinstance(row, list) and len(row) == w
                        for v in row:
                            assert v is None or isinstance(v, (int, bool))
            except (KeyError, TypeError, ValueError, AssertionError):
                return self._send_json({"ok": False, "error": "bad map shape"}, 400)
            try:
                json.dump({"version": data.get("version", 3.0), "width": w, "height": h,
                           "tiles": data["tiles"], "objects": data["objects"],
                           "collision": data["collision"]},
                          open(os.path.join(SCRIPT_DIR, name), "w"))
            except OSError:
                return self._send_json({"ok": False, "error": "cannot write"}, 500)
            _log_event(f"imported {name}")
            return self._send_json({"ok": True, "file": name})

        if path == "/api/maps/meta":
            # v5.6: author/description for a map (stored in its rules sidecar)
            name = _safe_name(body.get("file"))
            if not name:
                return self._send_json({"ok": False, "error": "file required"}, 400)
            rp = _rules_path(name)
            try:
                saved = json.load(open(rp)) or {}
            except (OSError, ValueError):
                saved = {}
            meta = saved.get("meta") or {}
            if "author" in body:
                meta["author"] = str(body["author"])[:60]
            if "description" in body:
                meta["description"] = str(body["description"])[:280]
            saved["meta"] = meta
            try:
                json.dump(saved, open(rp, "w"))
                ok = True
            except OSError:
                ok = False
            if ok and name == _current_map:
                map_meta.update(meta)
            return self._send_json({"ok": ok})

        if path == "/api/slots/save":
            # v5.6: snapshot a play session — hero pos, traits, world
            try:
                slot = int(body.get("slot"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "slot int required"}, 400)
            label = str(body.get("label") or f"Slot {slot}")[:40]
            snap = {"slot": slot, "label": label,
                    "saved_at": time.strftime("%Y-%m-%d %H:%M"),
                    "hero": [play["tx"], play["ty"]] if play["active"]
                            else list(_find_spawn()),
                    "traits": [row[:] for row in traits_grid],
                    "world": copy.deepcopy(world_profile)}
            slots = [s for s in _load_slots()
                     if s.get("slot") != slot] + [snap]
            ok = _save_slots(slots)
            if ok:
                _log_event(f"slot {slot} saved ({label})")
            return self._send_json({"ok": ok})

        if path == "/api/slots/load":
            # v5.6: restore a play session — traits + world now, hero at next Play
            try:
                slot = int(body.get("slot"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "slot int required"}, 400)
            snap = next((s for s in _load_slots() if s.get("slot") == slot), None)
            if not snap:
                return self._send_json({"ok": False, "error": "slot empty"}, 404)
            try:
                rows = snap["traits"]
                assert isinstance(rows, list) and len(rows) == world.height
                traits_grid = [list(r[:world.width]) for r in rows]
                wblk = snap.get("world") or {}
                if isinstance(wblk.get("meters"), dict):
                    for k in world_profile["meters"]:
                        if isinstance(wblk["meters"].get(k), bool):
                            world_profile["meters"][k] = wblk["meters"][k]
                if wblk.get("weather") in WEATHERS:
                    world_profile["weather"] = wblk["weather"]
                hx, hy = snap.get("hero") or [None, None]
                hero_override = [hx, hy] if isinstance(hx, int) and isinstance(hy, int) else None
            except (AssertionError, TypeError, KeyError):
                return self._send_json({"ok": False, "error": "slot corrupt"}, 400)
            _save_traits(_current_map)
            _save_rules(_current_map)
            _log_event(f"slot {slot} loaded ({snap.get('label', '')})")
            return self._send_json({"ok": True})

        if path == "/api/play/start":
            sx, sy = _find_spawn()
            if hero_override:  # v5.6: a loaded save slot picks the hero's start
                hx, hy = hero_override
                if isinstance(hx, int) and isinstance(hy, int) and _walkable(hx, hy):
                    sx, sy = hx, hy
                hero_override = None
            play["active"] = True
            play["tx"], play["ty"] = sx, sy
            _reset_rule_session()  # v3.9: fresh keys, messages, win/lose
                                   # v4.0: fresh meters + inventory
            active = next((m for m in _missions if m.get("active")), None)
            if active:  # v5.12: Melody's mission run starts here
                _mission_start_run(active)
            else:
                mission_run = None
            _log_event("play started")
            return self._send_json({"ok": True, "x": sx, "y": sy,
                                    "nature": _nature_state(),
                                    "mission": _mission_run_text()})

        if path == "/api/play/move":
            if not play["active"]:
                return self._send_json({"ok": False, "error": "play mode not active"}, 400)
            x, y = body.get("x"), body.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                return self._send_json({"ok": False, "error": "x/y ints required"}, 400)
            cells, swim, deep = _find_path(play["tx"], play["ty"], x, y,
                                           ghost=rules["ghost"])
            # v3.9: walk the path step by step on the server — game rules fire
            # in order, and a win/lose ends the walk where it happens.
            events = []
            kept = 0
            for i, (cx, cy) in enumerate(cells):
                ev = _check_rules(cx, cy)
                ev += _apply_nature(cx, cy)  # v4.0: the world's nature
                ev += _check_mission(cx, cy)  # v5.12: Melody's objectives
                ev += _check_items(cx, cy)  # v5.13: pick up gear
                ev += _check_npcs(cx, cy)  # v5.13: say hi
                events.append(ev)
                kept = i + 1
                if _rule_over:
                    break
                if mission_run and (mission_run["won"] or  # v5.12: a win or
                                    mission_run["failed"]):  # fail ends walk
                    break
            cells = cells[:kept]
            if cells:
                play["tx"], play["ty"] = cells[-1]
            return self._send_json({"ok": True, "path": [list(c) for c in cells],
                                    "swim": swim[:kept], "deep": deep[:kept],
                                    "events": events, "nature": _nature_state(),
                                    "x": play["tx"], "y": play["ty"]})

        if path == "/api/play/step":
            # v3.7: single-step hero movement for the D-pad / controller.
            # {dx, dy} must be one of the 4 cardinal directions.
            if not play["active"]:
                return self._send_json({"ok": False, "error": "play mode not active"}, 400)
            dx, dy = body.get("dx"), body.get("dy")
            if (dx, dy) not in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                return self._send_json({"ok": False, "error": "dx/dy must be cardinal"}, 400)
            nx, ny = play["tx"] + dx, play["ty"] + dy
            in_bounds = 0 <= nx < world.width and 0 <= ny < world.height
            can = in_bounds and (rules["ghost"] or _walkable(nx, ny))
            if can:
                play["tx"], play["ty"] = nx, ny
            # v3.9: game rules fire when the hero actually arrives
            events = _check_rules(play["tx"], play["ty"]) if can else []
            if can:
                events += _apply_nature(play["tx"], play["ty"])  # v4.0
                events += _check_mission(play["tx"], play["ty"])  # v5.12
                events += _check_items(play["tx"], play["ty"])  # v5.13
                events += _check_npcs(play["tx"], play["ty"])  # v5.13
            return self._send_json({"ok": True, "x": play["tx"], "y": play["ty"],
                                    "swim": _swim_at(play["tx"], play["ty"]),
                                    "deep": _deep_at(play["tx"], play["ty"]),
                                    "events": events, "nature": _nature_state(),
                                    "blocked": not can})

        if path == "/api/rules":
            # v3.7: per-build game rules. POST sets any of walk_ms
            # (90/140/220), swim_mult (2/3/4), ghost, touch.
            new_vals = {}
            wms = body.get("walk_ms")
            if wms in (90, 140, 220):
                new_vals["walk_ms"] = wms
            sm = body.get("swim_mult")
            if sm in (2, 3, 4):
                new_vals["swim_mult"] = sm
            for k in ("ghost", "touch"):
                if isinstance(body.get(k), bool):
                    new_vals[k] = body[k]
            ht = body.get("hero_tile", "unset")   # v4.8: the inspector's PC pick
            if ht is None or (isinstance(ht, int) and ht in assets.tiles):
                new_vals["hero_tile"] = ht
            # v5.0: no-op changes don't take up an undo step
            new_vals = {k: v for k, v in new_vals.items() if rules.get(k) != v}
            if new_vals:
                def _do():
                    rules.update(new_vals)
                    _save_rules(_current_map)
                    _mark_dirty()  # autosave persists the sidecar
                _undoable("rules", _do)  # v5.0
                return self._send_json({"ok": True, "rules": rules})
            return self._send_json({"ok": True, "rules": rules, "noop": True})

        if path == "/api/game-rules":
            # v3.9: the build's game rules — goals, hazards, keys & doors,
            # messages. {action: "add", rule: {...}} or {action: "delete", id}.
            action = body.get("action")
            if action == "add":
                r = _valid_game_rule(body.get("rule"))
                if r is None:
                    return self._send_json({"ok": False,
                                            "error": "that rule doesn't make sense"}, 400)
                r["id"] = _game_seq["next"]
                def _do():
                    _game_seq["next"] += 1
                    game_rules.append(r)
                    _save_rules(_current_map)
                    _mark_dirty()
                _undoable("add game rule", _do)  # v5.0
                return self._send_json({"ok": True, "rule": r,
                                        "rules": game_rules})
            if action == "delete":
                try:
                    rid = int(body.get("id"))
                except (TypeError, ValueError):
                    return self._send_json({"ok": False, "error": "bad id"}, 400)
                if not any(r["id"] == rid for r in game_rules):
                    return self._send_json({"ok": False, "error": "not found"}, 404)
                def _do():
                    game_rules[:] = [r for r in game_rules if r["id"] != rid]
                    _save_rules(_current_map)
                    _mark_dirty()
                _undoable("delete game rule", _do)  # v5.0
                return self._send_json({"ok": True, "rules": game_rules})
            return self._send_json({"ok": False, "error": "action?"}, 400)

        if path == "/api/traits":
            # v4.0: stamp a nature trait on one tile — {x, y, trait}
            # (trait id, or null to clear). Stamping saves the sidecar.
            if play["active"]:
                return self._send_json({"ok": False,
                                        "error": "leave play mode first"}, 400)
            x, y, t = body.get("x"), body.get("y"), body.get("trait")
            if not isinstance(x, int) or not isinstance(y, int):
                return self._send_json({"ok": False,
                                        "error": "x/y ints required"}, 400)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False, "error": "off the map"}, 400)
            if t is not None and t not in TRAITS:
                return self._send_json({"ok": False, "error": "unknown trait"}, 400)
            if traits_grid[y][x] == t:
                return self._send_json({"ok": True, "noop": True})
            def _do():
                traits_grid[y][x] = t
                _save_traits(_current_map)
                _mark_dirty()
            _undoable("stamp trait", _do)  # v5.0
            return self._send_json({"ok": True})

        if path == "/api/object-name":
            # v5.1: name THAT placed instance — {x, y, name}
            # (empty/missing name clears it). Renaming the tile in the
            # palette still renames the definition for everywhere.
            if play["active"]:
                return self._send_json({"ok": False,
                                        "error": "leave play mode first"}, 400)
            try:
                x, y = int(body.get("x")), int(body.get("y"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False,
                                        "error": "x/y ints required"}, 400)
            if not (0 <= x < world.width and 0 <= y < world.height):
                return self._send_json({"ok": False, "error": "off the map"}, 400)
            if world.object_layer[y][x] is None:
                return self._send_json({"ok": False,
                                        "error": "nobody there to name"}, 400)
            name = body.get("name")
            name = str(name).strip()[:40] if name is not None else ""
            key = _name_key(x, y)
            if object_names.get(key, "") == name:
                return self._send_json({"ok": True, "noop": True})
            def _do():
                if name:
                    object_names[key] = name
                else:
                    object_names.pop(key, None)
                _save_names(_current_map)
                _mark_dirty()
            _undoable("name " + (name or "unnamed"), _do)
            return self._send_json({"ok": True, "name": name or None})

        if path == "/api/world":
            # v4.0: this build's world profile — which meters exist.
            # POST {meters: {health: bool, warmth: bool, belly: bool}}.
            # v4.1: also {weather: "clear"|"rain"|"fog"|"snow"|"storm"}.
            changed = False
            m = body.get("meters", {})
            new_meters = {}
            for k in DEFAULT_WORLD["meters"]:
                if isinstance(m.get(k), bool):
                    new_meters[k] = m[k]
                    changed = True
            new_weather = None
            if isinstance(body.get("weather"), str) \
                    and body["weather"] in WEATHERS:
                new_weather = body["weather"]
                changed = True
            if changed:
                def _do():
                    for k, v in new_meters.items():
                        world_profile["meters"][k] = v
                    if new_weather is not None:
                        world_profile["weather"] = new_weather
                    _save_rules(_current_map)
                    _mark_dirty()
                _undoable("world profile", _do)  # v5.0
            return self._send_json({"ok": True, "world": world_profile})

        if path == "/api/play/tick":
            # v4.0: ambient nature — the client pings this every couple of
            # seconds in play mode so cold bites even standing still.
            if not play["active"]:
                return self._send_json({"ok": False,
                                        "error": "play mode not active"}, 400)
            events = _apply_nature(play["tx"], play["ty"])
            events += _check_mission(play["tx"], play["ty"])  # v5.12: the
            # clock runs even standing still — survive/timed keep counting
            return self._send_json({"ok": True, "events": events,
                                    "nature": _nature_state(),
                                    "over": bool(_rule_over)})

        if path == "/api/play/fire":
            # v4.0: spend 2 gathered wood to build a fire — the 8 tiles
            # around the hero turn hot for the rest of the run.
            if not play["active"]:
                return self._send_json({"ok": False,
                                        "error": "play mode not active"}, 400)
            if _inv["wood"] < 2:
                return self._send_json({"ok": False, "error":
                                        "need 2 wood — walk over some 🪵 first"},
                                       400)
            _inv["wood"] -= 2
            hx, hy = play["tx"], play["ty"]
            lit = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    x, y = hx + dx, hy + dy
                    if 0 <= x < world.width and 0 <= y < world.height \
                            and traits_grid[y][x] is None:
                        _nature_mods.append((x, y, None, "fire"))  # v4.1
                        traits_grid[y][x] = "hot"
                        lit += 1
            return self._send_json({"ok": True, "lit": lit,
                                    "events": [{"t": "toast",
                                                "text": "Fire built — stay warm."}],
                                    "nature": _nature_state()})

        if path == "/api/play/stop":
            play["active"] = False
            _reset_rule_session()  # v3.9: put picked-up keys / opened doors back
            _log_event("play stopped")  # v5.6
            return self._send_json({"ok": True})

        if path == "/api/jslog":
            # remote JS debugging: page posts its errors here, we print them
            # to the terminal next to everything else. Never fails the page.
            try:
                msg = str(body.get("msg", "?"))[:300]
                src = str(body.get("src", ""))[:120]
                line = body.get("line", "?")
                print(f"[js] {msg} @ {src}:{line}")
            except Exception:
                pass
            return self._send_json({"ok": True})

        if path == "/api/restore":
            # v5.16: roll a map or sidecar back to its .backup snapshot.
            name = _safe_name(body.get("file"))
            if not name:
                return self._send_json({"ok": False,
                                        "error": "file required"}, 400)
            ok, msg = _restore_backup(name)
            return self._send_json({"ok": ok,
                                    "error": None if ok else msg,
                                    "message": msg if ok else None})
        if path == "/api/bundle/import":
            # v5.16: install a shared .crumbs.zip under a fresh name.
            dz = str(body.get("zip", ""))
            if "," in dz:
                dz = dz.split(",", 1)[1]
            try:
                raw = base64.b64decode(dz, validate=True)
            except Exception:
                return self._send_json({"ok": False,
                                        "error": "zip data unreadable"}, 400)
            ok, payload = _import_bundle(raw, body.get("name"))
            if not ok:
                return self._send_json({"ok": False, "error": payload}, 400)
            return self._send_json({"ok": True, **payload})
        if path == "/api/shutdown":
            # v1.8: stop the server from the page. Answer first, then shut
            # down from another thread (shutdown() can't run inside the
            # handler thread). Saves dirty work, hands the prompt back.
            def _stop():
                time.sleep(0.3)  # let the "ok" reach the page first
                if _save_state["dirty"]:
                    _save_now()
                print("\n[hud] stopped from the page — prompt is yours again")
                srv.shutdown()
            threading.Thread(target=_stop, daemon=True).start()
            return self._send_json({"ok": True})
        if path == "/api/restart":
            # v5.19: restart the server from the page. Same safe path as
            # shutdown (answer first, save dirty work), then re-exec the
            # process in place — the page polls /api/status and reloads
            # when the new process is up.
            def _restart():
                time.sleep(0.3)  # let the "ok" reach the page first
                if _save_state["dirty"]:
                    _save_now()
                print("\n[hud] restarting from the page — back in a moment")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            threading.Thread(target=_restart, daemon=True).start()
            return self._send_json({"ok": True})

        return self._send_json({"ok": False, "error": "not found"}, 404)


def _lan_ip():
    # v1.9: the phone's Wi-Fi address, so a friend can open the page.
    # Opens a UDP socket without sending anything — just asks the OS
    # which interface would carry the traffic.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


if __name__ == "__main__":
    args = sys.argv[1:]
    public = "--public" in args  # v1.9: serve the Wi-Fi network
    share_key = (os.environ.get("CRUMBS_SHARE_KEY") or "").strip()
    for a in args:
        if a.startswith("--share-key="):
            share_key = a.split("=", 1)[1].strip()
    if public and not share_key:
        share_key = secrets.token_urlsafe(12)
    PUBLIC_MODE = public
    PUBLIC_WRITE_KEY = share_key if public else ""
    host = "0.0.0.0" if public else HOST
    srv = ThreadingHTTPServer((host, PORT), Handler)
    threading.Thread(target=_autosave_loop, daemon=True).start()
    print("=" * 52)
    print(f"  Crumbs HUD v{APP_VERSION} — Menu > Check for updates keeps it fresh")
    if public:
        ip = _lan_ip()
        print("  PUBLIC mode: anyone on your Wi-Fi can open the HUD (read-only by default).")
        print(f"  Write key: {PUBLIC_WRITE_KEY}")
        if ip:
            print(f"  Friend opens:  http://{ip}:{PORT}")
            print(f"  Builder URL:   http://{ip}:{PORT}/?{WRITE_KEY_QUERY}={PUBLIC_WRITE_KEY}")
        else:
            print(f"  Friend opens:  http://<this-device's-WiFi-IP>:{PORT}")
            print(f"  Builder URL:   http://<this-device's-WiFi-IP>:{PORT}/?{WRITE_KEY_QUERY}={PUBLIC_WRITE_KEY}")
        print(f"  You open:      http://{HOST}:{PORT}/?{WRITE_KEY_QUERY}={PUBLIC_WRITE_KEY}")
    else:
        print(f"  Open this on the phone:  http://{HOST}:{PORT}")
        print("  Share on Wi-Fi with:  python3 crumbs_hud.py --public")
    print("  Autosave: every 30s to hud_map.json when dirty")
    print("=" * 52)
    try:
        # v1.6: on a real computer this opens the page by itself.
        # On iPhone/a-Shell it quietly does nothing — open the URL by hand.
        import webbrowser
        open_url = f"http://{HOST}:{PORT}/?{WRITE_KEY_QUERY}={PUBLIC_WRITE_KEY}" if public else f"http://{HOST}:{PORT}"
        webbrowser.open(open_url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        if _save_state["dirty"]:
            _save_now()
            print(f"\n[hud] saved {DEFAULT_SAVE} on exit")
        print("[hud] stopped")
