#!/usr/bin/env python3
"""
Crumbs HUD — touch-friendly web tile painter for the Crumbs Vault dungeon editor.

Serves editor.html and a small JSON API backed by crumbs_core (headless engine).
Stdlib only — no pip installs. Do NOT modify crumbs_core.py.

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

Run:   python3 crumbs_hud.py
Open:  http://127.0.0.1:8778   (same phone's browser)
"""
import json
import io
import os
import base64
import copy
import random
import socket
import sys
import threading
import time
import heapq
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import crumbs_core as core

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", 8778))  # v1.9: $PORT for cloud hosts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(SCRIPT_DIR, "editor.html")
DEFAULT_SAVE = "hud_map.json"
LAYERS = ("tiles", "objects", "collision")

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
    "wall":  {"label": "Wall",  "hint": "solid",    "solid": True,  "height": "tall"},
    "floor": {"label": "Floor", "hint": "walkable", "solid": False, "height": "short"},
    "water": {"label": "Water", "hint": "swim — slow", "solid": False, "height": "short",
              "swim": True},
    # v3.6: deep water — impassable WITHOUT the swim animation. Passable WITH
    # it once SWIM_UNLOCKED flips (see the SWIM HOOK below). Shallow water's
    # ripple wading is untouched.
    "deepwater": {"label": "Deep water", "hint": "needs swim", "solid": True,
                  "height": "short", "deep": True},
    "door":  {"label": "Door",  "hint": "walkable", "solid": False, "height": "short"},
    "decor": {"label": "Decor", "hint": "walkable", "solid": False, "height": "short"},
    "character": {"label": "Character", "hint": "walkable sprite", "solid": False,
                  "height": "short"},
}

_custom_tiles = []  # registry mirror: [{id,name,preset,solid,frame_ms,files,scope}]
_shared_tiles = []  # v3.8: the shared shelf — same shape, scope="shared"


def _custom_public(entry):
    return {"id": entry["id"], "name": entry["name"], "preset": entry["preset"],
            "solid": entry["solid"], "height": entry.get("height", "short"),
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
    tid = int(entry["id"])
    assets.add_tile(tid, "custom", {
        "name": entry["name"],
        "category": "custom",
        "preset": entry.get("preset", "decor"),
        "height": entry.get("height", "short"),
        "frames": frames,
        "frame_ms": int(entry.get("frame_ms", 400)),
    })
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
                if _register_custom_tile(entry, tile_dir):
                    store.append(entry)
            except Exception as e:
                print(f"[hud] skipping {scope} tile {entry.get('id')}: {e}")
    if _custom_tiles or _shared_tiles:
        print(f"[hud] loaded {len(_custom_tiles)} local + {len(_shared_tiles)} shared tile(s)")
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
            json.dump({"patrols": _patrols, "next": _patrol_seq["next"]}, f)
    except Exception as e:
        print(f"[hud] could not save patrols: {e}")


def _load_patrols():
    if not os.path.exists(PATROL_SAVE):
        return
    try:
        reg = json.load(open(PATROL_SAVE))
    except Exception as e:
        print(f"[hud] patrol registry unreadable: {e}")
        return
    for p in reg.get("patrols", []):
        try:
            pts = [[int(a), int(b)] for a, b in p["points"]]
            tid = int(p["tile_id"])
            if len(pts) >= 2 and tid in assets.tiles:
                _patrols.append({"id": int(p["id"]), "tile_id": tid, "points": pts})
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
_inv = {"wood": 0}
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
    try:
        saved = json.load(open(_traits_path(name)))
    except (OSError, ValueError):
        return
    rows = (saved or {}).get("traits", [])
    for y in range(min(world.height, len(rows))):
        for x in range(min(world.width, len(rows[y]))):
            t = rows[y][x]
            traits_grid[y][x] = t if t in TRAITS else None

def _save_traits(name):
    try:
        with open(_traits_path(name), "w") as f:
            json.dump({"traits": traits_grid}, f)
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
    try:
        saved = json.load(open(_names_path(name)))
    except (OSError, ValueError):
        return
    rows = (saved or {}).get("names", {})
    if isinstance(rows, dict):
        for k, v in rows.items():
            if isinstance(v, str) and v.strip():
                object_names[k] = v.strip()[:40]

def _save_names(name):
    try:
        with open(_names_path(name), "w") as f:
            json.dump({"names": object_names}, f)
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
    sx, sy = _find_spawn()
    if not _walkable(sx, sy):
        issues.append({"kind": "no_spawn", "msg": "No walkable spawn point found."})
    else:
        seen = {(sx, sy)}
        dq = deque([(sx, sy)])
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if (0 <= nx < world.width and 0 <= ny < world.height
                        and (nx, ny) not in seen and _walkable(nx, ny)):
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
            for ext in (".json", ".rules.json", ".traits.json", ".names.json")]

def _slots_path():
    base = _current_map or DEFAULT_SAVE
    base = base[:-5] if base.endswith(".json") else base
    return os.path.join(SCRIPT_DIR, base + ".slots.json")

def _load_slots():
    try:
        return (json.load(open(_slots_path())) or {}).get("slots", [])
    except (OSError, ValueError):
        return []

def _save_slots(slots):
    try:
        json.dump({"slots": slots}, open(_slots_path(), "w"))
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
    _meters.update({"health": 10, "warmth": 10, "belly": 10})
    _inv["wood"] = 0
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
    elif t == "food" and m["belly"]:
        if _meters["belly"] < 10:
            bump("belly", 1)
            _nature_mods.append((x, y, "food", "gather"))
            traits_grid[y][x] = None
            notes.append({"t": "toast", "text": "Tasty."})
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
    try:
        saved = json.load(open(_rules_path(name)))
    except (OSError, ValueError):
        _load_game_rules([])
        return
    saved = saved or {}
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
            json.dump({"tweaks": rules, "game": game_rules,
                       "world": world_profile, "meta": map_meta}, f)  # v5.0: meta
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
_load_rules(DEFAULT_SAVE)  # v3.7: this build's rules (or defaults)
_load_traits(DEFAULT_SAVE)  # v4.0: this build's nature traits (or blank)
_load_names(DEFAULT_SAVE)   # v5.1: per-instance names (or none)

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
    while pq:
        d, x, y = heapq.heappop(pq)
        if d != dist[(x, y)]:
            continue
        if (x, y) == (tx, ty):
            break
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not _ok(nx, ny):
                continue
            nd = d + (1 if ghost else (SWIM_COST if (_swim_at(nx, ny) or _deep_at(nx, ny)) else 1))
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
    if world.save(p):
        _save_state["dirty"] = False
        _save_state["last"] = time.strftime("%H:%M:%S")
        _save_rules(name)  # v3.7: rules ride alongside the map
        return True
    return False


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

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return None

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
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
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/map":
            self._send_json(_map_state())
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
        path = urlparse(self.path).path
        body = self._read_json()
        if body is None or not isinstance(body, dict):
            # QA 2026-09-19: a JSON list/string/number parsed fine but has no
            # .get — reject it here instead of dying mid-handler with a bare
            # dropped connection and a terminal traceback.
            return self._send_json({"ok": False, "error": "bad JSON"}, 400)

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
                    pil_images.append(core.Image.open(io.BytesIO(raw)))
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
                frames = _autoslice_pil(core.Image.open(io.BytesIO(raw)))
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
                img = core.Image.open(io.BytesIO(raw))
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
            t = assets.tiles.get(tid)
            if t is not None:
                t["name"] = entry["name"]
                t["preset"] = entry["preset"]
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
            biome = str(body.get("biome", "dungeon"))
            if biome not in core.BIOMES:
                return self._send_json({"ok": False, "error": "unknown biome"}, 400)
            seed = body.get("seed")
            seed = int(seed) if isinstance(seed, int) or (isinstance(seed, str) and seed.strip().lstrip("-").isdigit()) else None
            if seed is None:
                # v5.0: a blank seed still gets a concrete one — otherwise the
                # build can't be reproduced or restored by the eraser.
                seed = random.randrange(1_000_000_000)
            def _do():
                world.generate_biome(biome, seed)
                map_meta["biome"] = biome  # v5.0: the eraser needs the seed
                map_meta["seed"] = seed
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
            ok = world.save(os.path.join(SCRIPT_DIR, name))
            if ok:
                _save_rules(name)  # v3.7
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
            global _current_map
            if _current_map == src:
                _current_map = dst
            _log_event(f"renamed {src} -> {dst}")
            return self._send_json({"ok": moved > 0, "file": dst})

        if path == "/api/maps/duplicate":
            # v5.6: copy a map + its sidecars
            import shutil
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
            _log_event("play started")
            return self._send_json({"ok": True, "x": sx, "y": sy,
                                    "nature": _nature_state()})

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
                events.append(ev)
                kept = i + 1
                if _rule_over:
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
    public = "--public" in sys.argv[1:]  # v1.9: serve the Wi-Fi network
    host = "0.0.0.0" if public else HOST
    srv = ThreadingHTTPServer((host, PORT), Handler)
    threading.Thread(target=_autosave_loop, daemon=True).start()
    print("=" * 52)
    print("  Crumbs HUD v5.6 — game rules: goals, hazards, keys & doors, messages")
    if public:
        ip = _lan_ip()
        print("  PUBLIC mode: anyone on your Wi-Fi can open the HUD.")
        if ip:
            print(f"  Friend opens:  http://{ip}:{PORT}")
        else:
            print(f"  Friend opens:  http://<this-device's-WiFi-IP>:{PORT}")
        print(f"  You open:      http://{HOST}:{PORT}")
    else:
        print(f"  Open this on the phone:  http://{HOST}:{PORT}")
        print("  Share on Wi-Fi with:  python3 crumbs_hud.py --public")
    print("  Autosave: every 30s to hud_map.json when dirty")
    print("=" * 52)
    try:
        # v1.6: on a real computer this opens the page by itself.
        # On iPhone/a-Shell it quietly does nothing — open the URL by hand.
        import webbrowser
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        if _save_state["dirty"]:
            _save_now()
            print(f"\n[hud] saved {DEFAULT_SAVE} on exit")
        print("[hud] stopped")
