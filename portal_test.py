#!/usr/bin/env python3
"""portal_test.py — v5.42 portal/neighbor/pocket tests. Run: python3 portal_test.py
Covers: portal spawn sanitize (+ legacy return_xy), neighbor sanitize,
edge-arrival math, nearest-walkable search, broken-link graceful failure,
pocket kind flag on generated maps, neighbors sidecar round-trip.
Pure functions + temp dirs only — no server, no network, no user data.
"""
import json
import os
import sys
import tempfile

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


old_world = h.world
h.world = core.WorldMap(64, 64, h.assets)
try:
    print("== portal spawn sanitize ==")
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1,
                            "spawn": [3, 4]})
    check("spawn kept", p["spawn"] == [3, 4], f"got {p['spawn']}")
    check("return_xy mirrors spawn", p["return_xy"] == [3, 4])
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1,
                            "return_xy": [5, 6]})
    check("legacy return_xy migrates to spawn", p["spawn"] == [5, 6],
          f"got {p['spawn']}")
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1,
                            "spawn": [3, 4], "return_xy": [5, 6]})
    check("spawn wins over return_xy", p["spawn"] == [3, 4])
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1,
                            "spawn": ["a", "b"]})
    check("bad spawn -> None", p["spawn"] is None, f"got {p['spawn']}")
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1})
    check("no spawn -> None", p["spawn"] is None)
    p = h._sanitize_portal({"target": "cave.json", "x": 1, "y": 1,
                            "spawn": [7]})
    check("short spawn -> None", p["spawn"] is None)
finally:
    h.world = old_world

print("== neighbor sanitize ==")
n = h._sanitize_neighbors({"N": "north.json", "X": "bad.json", "S": "",
                           "E": None})
check("valid edges kept, bad dropped",
      n == {"N": "north.json"}, f"got {n}")
n = h._sanitize_neighbors({"W": "../evil.json"})
check("path traversal neutralized", n == {"W": "evil.json"}, f"got {n}")
check("non-dict -> {}", h._sanitize_neighbors(None) == {})
check("empty -> {}", h._sanitize_neighbors({}) == {})

print("== edge arrival math ==")
check("W exit arrives E edge", h._edge_arrival("W", 0, 5, 20, 10) == (19, 5))
check("E exit arrives W edge", h._edge_arrival("E", 19, 5, 20, 10) == (0, 5))
check("N exit arrives S edge", h._edge_arrival("N", 7, 0, 20, 10) == (7, 9))
check("S exit arrives N edge", h._edge_arrival("S", 7, 9, 20, 10) == (7, 0))
check("along-edge clamped to smaller neighbor",
      h._edge_arrival("E", 19, 9, 20, 4) == (0, 3))
check("along-edge clamped (N)", h._edge_arrival("N", 18, 0, 10, 10) == (9, 9))

print("== nearest walkable ==")
old_world = h.world
h.world = core.WorldMap(10, 10, h.assets)
try:
    for y in range(10):
        for x in range(10):
            h.world.collision_layer[y][x] = True
    h.world.collision_layer[7][7] = False
    check("finds the lone walkable cell",
          h._nearest_walkable(0, 0) == (7, 7),
          f"got {h._nearest_walkable(0, 0)}")
    h.world.collision_layer[2][2] = False
    check("walkable start returns itself",
          h._nearest_walkable(2, 2) == (2, 2))
    check("out-of-range start clamps in",
          h._nearest_walkable(99, 99) == (7, 7))
finally:
    h.world = old_world

print("== broken links fail gracefully ==")
tmp = tempfile.mkdtemp(prefix="crumbs-portal-")
old_base = h._vault_base
h._vault_base = lambda: tmp
try:
    ok, payload = h._warp_to({"target": "gone.json", "seed": None,
                              "biome": "dungeon"})
    check("missing portal target -> (False, error)",
          ok is False and isinstance(payload, dict) and "error" in payload,
          f"got {(ok, payload)}")
    check("error names the target",
          "gone.json" in payload.get("error", ""),
          f"got {payload.get('error')}")
    ok, payload = h._warp_to({"target": "", "seed": None})
    check("empty portal target -> error",
          ok is False and "error" in payload)

    h._neighbors = {"N": "gone.json"}
    h._current_map = "here.json"
    ok, payload = h._edge_cross("N", 5, 0)
    check("missing neighbor -> (False, error)",
          ok is False and isinstance(payload, dict) and "error" in payload,
          f"got {(ok, payload)}")
    err = payload.get("error", "")
    check("edge error names direction + target",
          "north" in err and "gone.json" in err, f"got {err!r}")
    h._neighbors = {}
    ok, payload = h._edge_cross("E", 5, 5)
    check("unlinked edge -> (False, None)", (ok, payload) == (False, None),
          f"got {(ok, payload)}")

    print("== _portal_warp_check ==")
    h.play["tx"], h.play["ty"] = 3, 3
    h._portals = {"3,3": {"target": "gone.json", "seed": None,
                          "x": 3, "y": 3}}
    h._warp_guard = None
    h._current_map = "here.json"
    warp, notice = h._portal_warp_check()
    check("broken portal -> notice, no warp",
          warp is None and notice is not None and "gone.json" in notice,
          f"got {(warp, notice)}")
    h._portals = {}
    warp, notice = h._portal_warp_check()
    check("no portal -> (None, None)", (warp, notice) == (None, None),
          f"got {(warp, notice)}")

    print("== neighbors sidecar round-trip ==")
    h._neighbors = {"N": "north.json", "W": "west.json"}
    check("save neighbors", h._save_neighbors("t.json") is True)
    h._neighbors = {}
    h._load_neighbors("t.json")
    check("load neighbors",
          h._neighbors == {"N": "north.json", "W": "west.json"},
          f"got {h._neighbors}")

    print("== pocket kind flag ==")
    ok = h._generate_map_file("kind-test.json", 42, "dungeon", None, 12, 12)
    check("pocket generates", ok is True)
    try:
        with open(os.path.join(tmp, "kind-test.rules.json")) as f:
            meta = (json.load(f) or {}).get("meta") or {}
        check("generated pocket flagged kind=pocket",
              meta.get("kind") == "pocket", f"got {meta.get('kind')}")
    except (OSError, ValueError) as e:
        check("generated pocket flagged kind=pocket", False, str(e))
finally:
    h._vault_base = old_base
    h._neighbors = {}
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{ PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
