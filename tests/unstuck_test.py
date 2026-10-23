#!/usr/bin/env python3
"""unstuck_test.py — "I'm stuck" rescue tests. Run: python3 unstuck_test.py
Covers: _safe_at landing rules (dry, standable, not hazard, not solid),
_near_safe ring search (lake shore, shallows skipped, boxed-in hero,
hazard rings, whole-map failure), and the client/server wiring contract
(/api/play/unstuck endpoint + the Play-menu button).
Pure functions + source reads only — no server, no network, no user data.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (tests live in tests/)
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


def _find_tid(label, **want):
    """First loaded tile whose properties match every want flag."""
    for tid in sorted(h.assets.tiles, key=str):
        p = h.assets.tiles[tid].get("properties", {})
        if all(bool(p.get(k)) == v for k, v in want.items()):
            return tid
    raise SystemExit(f"fixture tile missing: {label}")


LAND = _find_tid("dry land", swim=False, deep=False, solid=False)
LAND_B = None
for _tid in sorted(h.assets.tiles, key=str):
    _p = h.assets.tiles[_tid].get("properties", {})
    if (not _p.get("swim") and not _p.get("deep") and not _p.get("solid")
            and _tid != LAND):
        LAND_B = _tid
        break
WATER = _find_tid("shallow water", swim=True, deep=False)
DEEP = _find_tid("deep water", deep=True)
WALL = _find_tid("solid wall", solid=True)


def make_world(fill=LAND, size=12):
    w = core.WorldMap(size, size, h.assets)
    for y in range(size):
        for x in range(size):
            w.data[y][x] = fill
    return w


def paint(w, tid, x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            w.data[y][x] = tid


def ring(w, cx, cy, r, tid):
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if max(abs(dx), abs(dy)) == r:
                w.data[cy + dy][cx + dx] = tid


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


old_world, old_rules = h.world, h.game_rules
try:
    print("== fixtures ==")
    check("LAND_B fixture found (a second dry tile)", LAND_B is not None)
    check("deep water blocks while SWIM_UNLOCKED is False",
          h.SWIM_UNLOCKED is False)

    print("== _safe_at on open land ==")
    h.world = make_world()
    h.game_rules = []
    check("dry land is safe", h._safe_at(5, 5))
    check("off-map is not safe", not h._safe_at(-1, 0)
          and not h._safe_at(12, 0) and not h._safe_at(0, 12))

    print("== water is never a landing ==")
    h.world.data[5][5] = WATER
    check("shallow water is walkable (wading)", h._walkable(5, 5))
    check("shallow water is NOT safe (rescue lands dry)", not h._safe_at(5, 5))
    h.world.data[5][5] = DEEP
    check("deep water is not walkable", not h._walkable(5, 5))
    check("deep water is NOT safe", not h._safe_at(5, 5))
    h.world.data[5][5] = WALL
    check("a wall is NOT safe", not h._safe_at(5, 5))
    h.world.data[5][5] = LAND
    h.world.collision_layer[5][5] = True
    check("a collision-blocked tile is NOT safe", not h._safe_at(5, 5))

    print("== hazards are never a landing ==")
    h.world = make_world()
    h.world.hazard_layer[5][5] = True
    check("painted hazard cell still walks (layer alone does not block)",
          h._walkable(5, 5))
    check("painted hazard cell is NOT safe", not h._safe_at(5, 5))
    h.world = make_world()
    check("rule-hazard precondition: ring tile is dry land",
          h._walkable(5, 4) and h._safe_at(5, 4))
    ring(h.world, 5, 5, 1, LAND_B)
    h.game_rules = [{"kind": "hazard", "tile": LAND_B, "text": "boom"}]
    check("rule-hazard tile still walks (rules kill on arrival, not by block)",
          h._walkable(5, 4))
    check("rule-hazard tile is NOT safe", not h._safe_at(5, 4))
    spot = h._near_safe(5, 5)
    check("rescue steps over a hazard ring", spot is not None
          and cheb(spot, (5, 5)) == 2, f"got {spot}")
    h.game_rules = []

    print("== the lake: nearest shore, straight from the middle ==")
    h.world = make_world()
    paint(h.world, DEEP, 3, 3, 7, 7)   # 5x5 deep lake, hero at its center
    spot = h._near_safe(5, 5)
    check("a shore is found", spot is not None)
    check("the shore is the closest ring (3)", spot is not None
          and cheb(spot, (5, 5)) == 3, f"got {spot}")
    check("the landing is safe", spot is not None
          and h._safe_at(spot[0], spot[1]))
    check("the landing is dry land, not water", spot is not None
          and h.world.data[spot[1]][spot[0]] == LAND)

    print("== shallows do not count as shore ==")
    h.world = make_world()
    paint(h.world, WATER, 3, 3, 7, 7)  # shallow apron…
    paint(h.world, DEEP, 4, 4, 6, 6)   # …around a deep heart
    spot = h._near_safe(5, 5)
    check("rescue skips the shallows to dry land", spot is not None
          and cheb(spot, (5, 5)) == 3
          and h.world.data[spot[1]][spot[0]] == LAND, f"got {spot}")

    print("== boxed in on safe ground ==")
    h.world = make_world()
    ring(h.world, 5, 5, 1, WALL)
    check("hero's own tile is safe ground", h._safe_at(5, 5))
    spot = h._near_safe(5, 5)
    check("own cell is never the answer — rescue leaves the box",
          spot is not None and cheb(spot, (5, 5)) == 2, f"got {spot}")

    print("== corner lake (bounds) ==")
    h.world = make_world()
    paint(h.world, DEEP, 0, 0, 2, 2)
    spot = h._near_safe(1, 1)
    check("corner rescue stays on the map", spot is not None
          and cheb(spot, (1, 1)) == 2 and h._safe_at(spot[0], spot[1]),
          f"got {spot}")

    print("== no safe ground ==")
    h.world = make_world(fill=DEEP)
    check("a whole map of deep water has no rescue", h._near_safe(5, 5) is None)
    h.world.data[5][5] = LAND
    check("only the hero's own tile safe still means no rescue",
          h._near_safe(5, 5) is None)

    print("== bad input ==")
    check("non-int origin -> None", h._near_safe("a", None) is None)
    check("off-map origin -> None", h._near_safe(-3, 99) is None)
finally:
    h.world = old_world
    h.game_rules = old_rules

print("== wiring contract ==")
with open(os.path.join(HERE, "crumbs_hud.py")) as f:
    py_src = f.read()
with open(os.path.join(HERE, "editor.html")) as f:
    html_src = f.read()
check("server registers /api/play/unstuck", '"/api/play/unstuck"' in py_src)
check("server rescue is gated on an active run",
      'play mode not active' in py_src)
check("Play menu carries the stuck button", 'id="btn-unstuck"' in html_src)
check("button is labelled for a stuck player",
      "I'm stuck — nearest safe ground" in html_src)
check("client calls the rescue endpoint",
      'api("/api/play/unstuck"' in html_src)
check("no new floating HUD button (control lives in the Play menu)",
      html_src.count('id="btn-unstuck"') == 1)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
