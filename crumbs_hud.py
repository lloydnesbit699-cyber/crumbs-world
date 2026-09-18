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

Run:   python3 crumbs_hud.py
Open:  http://127.0.0.1:8778   (same phone's browser)
"""
import json
import io
import os
import base64
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
        with open(path, "w") as f:
            json.dump({"tiles": tiles}, f)
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
                 "touch": True}      # show the on-screen controls in play mode
rules = dict(DEFAULT_RULES)
_current_map = DEFAULT_SAVE


def _rules_path(name):
    base = name[:-5] if name.endswith(".json") else name
    return os.path.join(SCRIPT_DIR, base + ".rules.json")


def _load_rules(name):
    """v3.7: read this map's rules sidecar; fall back to defaults."""
    global rules, _current_map
    _current_map = name
    rules = dict(DEFAULT_RULES)
    try:
        saved = json.load(open(_rules_path(name)))
    except (OSError, ValueError):
        return
    for k, v in (saved or {}).items():
        if k == "walk_ms" and v in (90, 140, 220):
            rules[k] = v
        elif k == "swim_mult" and v in (2, 3, 4):
            rules[k] = v
        elif k in ("ghost", "touch") and isinstance(v, bool):
            rules[k] = v


def _save_rules(name):
    try:
        with open(_rules_path(name), "w") as f:
            json.dump(rules, f)  # flat — matches what _load_rules reads
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

# v3.2: built-in water/ocean colors are swimmable — slow the hero, don't block
for _tid, _t in assets.tiles.items():
    _nm = str(_t.get("name", "")).lower()
    if _t.get("type") == "color" and ("water" in _nm or "ocean" in _nm):
        _t["properties"]["swim"] = True


# ---- playtest state (tile-space hero; crumbs_core untouched) ----------------
play = {"active": False, "tx": 0, "ty": 0}

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
            files = sorted(f for f in os.listdir(SCRIPT_DIR)
                           if f.endswith((".json", ".txt")) and os.path.isfile(os.path.join(SCRIPT_DIR, f)))
            self._send_json({"maps": files})
        elif path == "/api/biomes":
            self._send_json({"biomes": [{"id": k, "name": v["name"]} for k, v in core.BIOMES.items()]})
        elif path == "/api/rules":
            # v3.7: this build's game rules
            self._send_json({"ok": True, "rules": rules})
        elif path == "/api/status":
            self._send_json({"dirty": _save_state["dirty"],
                             "last_save": _save_state["last"],
                             "play": play["active"]})
        else:
            self._send_json({"ok": False, "error": "not found"}, 404)

    # -- POST --------------------------------------------------------------
    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json()
        if body is None:
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
            new_val = _paint_value(layer, tile_id)
            grid = _grid(layer)
            if grid[y][x] == new_val:
                return self._send_json({"ok": True, "noop": True})
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
            cmds = []
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
                new_val = _paint_value(layer, c.get("tile_id"))
                grid = _grid(layer)
                if grid[y][x] != new_val:
                    cmds.append(core.SetTileCommand(world, x, y, grid[y][x], new_val, layer))
            if not cmds:
                return self._send_json({"ok": True, "painted": 0, "noop": True})
            multi = core.MultiCommand(cmds)
            history.push(multi)
            multi.execute()
            _mark_dirty()
            return self._send_json({"ok": True, "painted": len(cmds)})

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
            p = {"id": _patrol_seq["next"], "tile_id": tid, "points": pts}
            _patrol_seq["next"] += 1
            _patrols.append(p)
            _save_patrols()
            return self._send_json({"ok": True, "patrol": p})

        if path == "/api/patrols/delete":
            # v3.4: {id}
            try:
                pid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "bad id"}, 400)
            before = len(_patrols)
            _patrols[:] = [p for p in _patrols if p["id"] != pid]
            if len(_patrols) == before:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            _save_patrols()
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
            old = _snapshot()
            world.generate_biome(biome, seed)
            history.push(core.MapSnapshotCommand(world, old, _snapshot()))
            _mark_dirty()
            rules.clear()
            rules.update(DEFAULT_RULES)  # v3.7: fresh build, fresh rules
            return self._send_json({"ok": True, "biome": biome, "rules": rules})

        if path == "/api/clear_layer":
            layer = body.get("layer", "tiles")
            if layer not in LAYERS:
                return self._send_json({"ok": False, "error": "bad layer"}, 400)
            old = _snapshot()
            grid, default = _grid(layer), _default_value(layer)
            for yy in range(world.height):
                for xx in range(world.width):
                    grid[yy][xx] = default
            history.push(core.MapSnapshotCommand(world, old, _snapshot()))
            _mark_dirty()
            return self._send_json({"ok": True, "layer": layer})

        if path == "/api/resize":
            try:
                w, h = int(body.get("width", world.width)), int(body.get("height", world.height))
            except (TypeError, ValueError):
                return self._send_json({"ok": False, "error": "width/height ints required"}, 400)
            w, h = max(4, min(64, w)), max(4, min(64, h))
            old = _snapshot()
            world.resize(w, h)
            history.push(core.MapSnapshotCommand(world, old, _snapshot()))
            _mark_dirty()
            return self._send_json({"ok": True, "width": w, "height": h})

        if path == "/api/save":
            name = _safe_name(body.get("filename") or DEFAULT_SAVE)
            if not name.endswith(".json"):
                name += ".json"
            ok = world.save(os.path.join(SCRIPT_DIR, name))
            if ok:
                _save_rules(name)  # v3.7
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
            return self._send_json({"ok": ok, "width": world.width,
                                    "height": world.height, "rules": rules})

        if path == "/api/play/start":
            sx, sy = _find_spawn()
            play["active"] = True
            play["tx"], play["ty"] = sx, sy
            return self._send_json({"ok": True, "x": sx, "y": sy})

        if path == "/api/play/move":
            if not play["active"]:
                return self._send_json({"ok": False, "error": "play mode not active"}, 400)
            x, y = body.get("x"), body.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                return self._send_json({"ok": False, "error": "x/y ints required"}, 400)
            cells, swim, deep = _find_path(play["tx"], play["ty"], x, y,
                                           ghost=rules["ghost"])
            if cells:
                play["tx"], play["ty"] = cells[-1]
            return self._send_json({"ok": True, "path": [list(c) for c in cells],
                                    "swim": swim, "deep": deep,
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
            return self._send_json({"ok": True, "x": play["tx"], "y": play["ty"],
                                    "swim": _swim_at(play["tx"], play["ty"]),
                                    "deep": _deep_at(play["tx"], play["ty"]),
                                    "blocked": not can})

        if path == "/api/rules":
            # v3.7: per-build game rules. POST sets any of walk_ms
            # (90/140/220), swim_mult (2/3/4), ghost, touch.
            changed = False
            wms = body.get("walk_ms")
            if wms in (90, 140, 220):
                rules["walk_ms"] = wms; changed = True
            sm = body.get("swim_mult")
            if sm in (2, 3, 4):
                rules["swim_mult"] = sm; changed = True
            for k in ("ghost", "touch"):
                if isinstance(body.get(k), bool):
                    rules[k] = body[k]; changed = True
            if changed:
                _mark_dirty()  # autosave persists the sidecar
            return self._send_json({"ok": True, "rules": rules})

        if path == "/api/play/stop":
            play["active"] = False
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
    print("  Crumbs HUD v3.8 — shared tile library (local vs shared imports)")
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
