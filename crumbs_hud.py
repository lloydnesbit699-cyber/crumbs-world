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

Run:   python3 crumbs_hud.py
Open:  http://127.0.0.1:8778   (same phone's browser)
"""
import json
import io
import os
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import crumbs_core as core

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", 8778))  # v1.9: $PORT for cloud hosts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(SCRIPT_DIR, "editor.html")
DEFAULT_SAVE = "hud_map.json"
LAYERS = ("tiles", "objects", "collision")

# ---- in-memory session state ---------------------------------------------
assets = core.AssetManager()
world = core.WorldMap(25, 15, assets)
history = core.HistoryManager()

# try to resume: last HUD save, else the blank starter, else fresh 25x15
for _name, _loader in ((DEFAULT_SAVE, world.load), ("vault_map.txt", world.load_csv)):
    _p = os.path.join(SCRIPT_DIR, _name)
    if os.path.exists(_p) and _loader(_p):
        print(f"[hud] loaded starter map {_name} ({world.width}x{world.height})")
        break
else:
    print(f"[hud] fresh map {world.width}x{world.height}")


# ---- playtest state (tile-space hero; crumbs_core untouched) ----------------
play = {"active": False, "tx": 0, "ty": 0}


def _tile_solid(tx, ty):
    tile = assets.tiles.get(world.data[ty][tx])
    return bool(tile and tile.get("properties", {}).get("solid"))


def _walkable(tx, ty):
    if not (0 <= tx < world.width and 0 <= ty < world.height):
        return False
    if world.collision_layer[ty][tx]:
        return False
    return not _tile_solid(tx, ty)


def _find_spawn():
    cx, cy = world.width // 2, world.height // 2
    if _walkable(cx, cy):
        return cx, cy
    for r in range(1, max(world.width, world.height)):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = cx + dx, cy + dy
                if _walkable(x, y):
                    return x, y
    return 0, 0


def _find_path(sx, sy, tx, ty):
    """BFS over walkable tiles. Returns [(x,y), ...] excluding the start."""
    if (sx, sy) == (tx, ty) or not _walkable(tx, ty):
        return []
    prev = {(sx, sy): None}
    dq = deque([(sx, sy)])
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in prev or not _walkable(nx, ny):
                continue
            prev[(nx, ny)] = (x, y)
            if (nx, ny) == (tx, ty):
                path = [(tx, ty)]
                while path[-1] != (sx, sy):
                    path.append(prev[path[-1]])
                path.reverse()
                return path[1:]
            dq.append((nx, ny))
    return []


# ---- autosave state ----------------------------------------------------------
_save_state = {"dirty": False, "last": None}


def _mark_dirty():
    _save_state["dirty"] = True


def _save_now(name=DEFAULT_SAVE):
    p = os.path.join(SCRIPT_DIR, name)
    if world.save(p):
        _save_state["dirty"] = False
        _save_state["last"] = time.strftime("%H:%M:%S")
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
        return bool(tile_id)
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
        elif path.startswith("/api/thumb/"):
            try:
                tid = int(path.rsplit("/", 1)[1])
            except ValueError:
                return self._send_json({"ok": False, "error": "bad tile id"}, 400)
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
            return self._send_json({"ok": True, "biome": biome})

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
            return self._send_json({"ok": ok, "width": world.width, "height": world.height})

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
            cells = _find_path(play["tx"], play["ty"], x, y)
            if cells:
                play["tx"], play["ty"] = cells[-1]
            return self._send_json({"ok": True, "path": [list(c) for c in cells],
                                    "x": play["tx"], "y": play["ty"]})

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
    print("  Crumbs HUD v2.4 — smooth pinch at 64x64 + save/load menu")
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
