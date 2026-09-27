#!/usr/bin/env python3
"""scale_test.py — v5.41 map-capacity tests. Run: python3 scale_test.py
Covers: MAP_MAX == 500 and every clamp site that enforces it, the Dijkstra
visit guard, the visibility sight radius, and the PNG export dimension cap.
Pure functions + temp dirs only — no server, no network, no user data.
"""
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crumbs_hud as h
import crumbs_core as core

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


print("== capacity constants ==")
check("MAP_MAX is 500", h.MAP_MAX == 500, f"got {h.MAP_MAX}")
check("visit cap is 100k", h.PATHFIND_VISIT_CAP == 100_000)
check("sight radius is 40", h.SIGHT_RADIUS == 40)
check("export max dim is 4096", h.EXPORT_MAX_DIM == 4096)

print("== portal sanitize clamp ==")
old_world = h.world
h.world = core.WorldMap(64, 64, h.assets)
try:
    p = h._sanitize_portal({"target": "pocket.json", "x": 1, "y": 1,
                            "width": 9999, "height": 9999})
    check("portal width clamps to 500", p["width"] == 500, f"got {p['width']}")
    check("portal height clamps to 500", p["height"] == 500, f"got {p['height']}")
    p2 = h._sanitize_portal({"target": "pocket.json", "x": 1, "y": 1,
                             "width": 1, "height": 2})
    check("portal minimum still 4", p2["width"] == 4 and p2["height"] == 4)
finally:
    h.world = old_world

print("== pocket-map generation clamp ==")
tmp = tempfile.mkdtemp(prefix="crumbs-scale-")
old_base = h._vault_base
h._vault_base = lambda: tmp
try:
    t0 = time.time()
    ok = h._generate_map_file("scale-test-500", 1234, "dungeon", None,
                              9999, 9999)
    dt = time.time() - t0
    check("generate accepts oversize request", ok)
    found = [f for f in os.listdir(tmp) if f == "scale-test-500"]
    check("map file written to temp vault", len(found) == 1, f"found={found}")
    if found:
        with open(os.path.join(tmp, found[0])) as f:
            saved = json.load(f)
        check("saved map is 500x500",
              saved.get("width") == 500 and saved.get("height") == 500,
              f"got {saved.get('width')}x{saved.get('height')}")
    check("500x500 generate under 30s", dt < 30, f"{dt:.1f}s")
finally:
    h._vault_base = old_base
    shutil.rmtree(tmp, ignore_errors=True)

print("== Dijkstra visit guard ==")
h.world = core.WorldMap(30, 30, h.assets)
# vertical wall at x=15: (29,29) unreachable from (0,0), target walkable
for yy in range(30):
    h.world.collision_layer[yy][15] = True
try:
    old_cap = h.PATHFIND_VISIT_CAP
    h.PATHFIND_VISIT_CAP = 1  # absurdly small — the guard must trip
    path, swim, deep = h._find_path(0, 0, 1, 0)
    check("visit guard trips on tiny cap", path == [] and swim == [] and deep == [])
    h.PATHFIND_VISIT_CAP = old_cap
    t0 = time.time()
    path, _, _ = h._find_path(0, 0, 29, 29)  # unreachable behind the wall
    dt = time.time() - t0
    check("unreachable target returns empty path", path == [])
    check("bounded search stays fast", dt < 5, f"{dt:.2f}s")
    path, _, _ = h._find_path(0, 0, 5, 0)  # reachable, same side
    check("normal path still found", bool(path) and path[-1] == (5, 0),
          f"got {path[-1] if path else None}")
finally:
    h.PATHFIND_VISIT_CAP = old_cap
    h.world = old_world

print("== visibility sight radius ==")
small = core.WorldMap(20, 20, h.assets)
vis = h._visibility_grid(small, 10, 10)
check("small map keeps full-map sight", vis[0][0] is True)
big = core.WorldMap(200, 200, h.assets)
vis = h._visibility_grid(big, 100, 100)
check("viewer sees himself", vis[100][100] is True)
check("sees within radius", vis[100][140] is True)
check("dark beyond radius", vis[100][141] is False)
check("far corner dark", vis[0][0] is False)

print("== PNG export dimension cap ==")
if not core.PIL_AVAILABLE:
    print("  skip: Pillow not available")
else:
    data = [[0] * 500 for _ in range(500)]
    objs = [[None] * 500 for _ in range(500)]
    t0 = time.time()
    img = h._map_png(scale=4, data=data, objects=objs, w=500, h=500)
    dt = time.time() - t0
    # old code: 500*128 = 64000px (16GB) — new code shrinks tiles to fit 4096
    check("export capped at 4096px", max(img.size) <= h.EXPORT_MAX_DIM,
          f"got {img.size}")
    check("export keeps aspect", img.size[0] == img.size[1] == 4000,
          f"got {img.size}")
    check("export completes", dt < 60, f"{dt:.1f}s")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
