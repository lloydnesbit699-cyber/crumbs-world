#!/usr/bin/env python3
"""semantic_test.py — v5.46 semantic painting tests. Run: python3 semantic_test.py
Covers: the pure mask engine (edges incl. corners, wall masks, shadow sides
+ inner corners), the FNV-1a hash vector, deterministic variant picks, decor
density + interior-only rules, the stroke/automap planners (tags, physics,
decor replacement), save/load + resize round trips, SetTileCommand on the new
layers, LOGICAL_LAYERS, and settings sanitization.
Pure core only — no server, no network, no user data.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

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


def blank_tags(w, h, fill=None):
    return [[fill] * w for _ in range(h)]


POOLS = {"floor": [11, 12, 13], "wall": [21, 22], "water": [31],
         "decor": [41, 42]}
SETTINGS = {"seed": 1234, "shadow_strength": 70, "decor_density": 100,
            "auto_decor": True, "auto_edges": True,
            "styles": {"floor": "mixed", "wall": "mixed", "water": "mixed"}}


def make_world(w=7, h=7):
    world = core.WorldMap(w, h, {})
    return world


print("== hash ==")
check("sem_hash(3,5,1234) == 3495858765",
      core.sem_hash(3, 5, 1234) == 3495858765,
      f"got {core.sem_hash(3, 5, 1234)}")
check("hash is deterministic",
      core.sem_hash(3, 5, 1234) == core.sem_hash(3, 5, 1234))
check("hash differs by seed", core.sem_hash(3, 5, 1234) != core.sem_hash(3, 5, 999))
check("hash differs by cell", core.sem_hash(3, 5, 1234) != core.sem_hash(4, 5, 1234))

print("== edge masks ==")
g = blank_tags(3, 3, "floor")
check("uniform floor: center mask 0", core.sem_edge_mask(g, 1, 1, 3, 3) == 0)
g[1][1] = "wall"
check("lone wall: mask 255", core.sem_edge_mask(g, 1, 1, 3, 3) == 255,
      f"got {core.sem_edge_mask(g, 1, 1, 3, 3)}")
check("floor touching wall from below: N + off-map border bits",
      core.sem_edge_mask(g, 1, 2, 3, 3) ==
      (core.SEM_N | core.SEM_SE | core.SEM_S | core.SEM_SW),
      f"got {core.sem_edge_mask(g, 1, 2, 3, 3)}")
# diagonal corner: wall at NW of the floor cell
g2 = blank_tags(3, 3, "floor")
g2[0][0] = "wall"
check("diagonal neighbour sets NW bit",
      core.sem_edge_mask(g2, 1, 1, 3, 3) == core.SEM_NW,
      f"got {core.sem_edge_mask(g2, 1, 1, 3, 3)}")
# off-map reads as different (border cells get edge seams)
g3 = blank_tags(3, 3, "floor")
check("corner cell: off-map borders read as edges",
      core.sem_edge_mask(g3, 0, 0, 3, 3) ==
      (core.SEM_N | core.SEM_NE | core.SEM_SW | core.SEM_W | core.SEM_NW),
      f"got {core.sem_edge_mask(g3, 0, 0, 3, 3)}")
check("untagged cell mask 0", core.sem_edge_mask(blank_tags(3, 3), 1, 1, 3, 3) == 0)

print("== wall masks ==")
check("wall mask: only wall neighbours set",
      core.sem_wall_mask(g, 1, 2, 3, 3) == core.SEM_N,
      f"got {core.sem_wall_mask(g, 1, 2, 3, 3)}")
check("wall mask ignores floor neighbours",
      core.sem_wall_mask(g, 1, 1, 3, 3) == 0)
g4 = blank_tags(3, 3, "floor")
g4[0][1] = "wall"; g4[1][0] = "wall"; g4[1][2] = "wall"
check("orthogonal trio", core.sem_wall_mask(g4, 1, 1, 3, 3) == (core.SEM_N | core.SEM_W | core.SEM_E))

print("== shadow sides + inner corners ==")
check("N wall -> shadow side N",
      core.sem_shadow_sides(core.SEM_N) == ["N"])
check("N+S walls -> two sides",
      core.sem_shadow_sides(core.SEM_N | core.SEM_S) == ["N", "S"])
check("no walls -> no sides", core.sem_shadow_sides(0) == [])
check("lone NE diagonal -> inner corner NE",
      core.sem_shadow_corners(core.SEM_NE) == ["NE"])
check("NE + N ortho -> not a corner (adjacent wall)",
      core.sem_shadow_corners(core.SEM_NE | core.SEM_N) == [])
check("NE + E ortho -> not a corner",
      core.sem_shadow_corners(core.SEM_NE | core.SEM_E) == [])
check("SW diagonal alone -> SW",
      core.sem_shadow_corners(core.SEM_SW) == ["SW"])
check("two diagonals -> two corners",
      core.sem_shadow_corners(core.SEM_NE | core.SEM_SW) == ["NE", "SW"])

print("== base tile variants ==")
t1 = core.sem_base_tile("floor", 2, 3, POOLS, "mixed", 1234)
t2 = core.sem_base_tile("floor", 2, 3, POOLS, "mixed", 1234)
check("mixed pick is deterministic", t1 == t2 and t1 in POOLS["floor"])
check("mixed pick varies across the map",
      len({core.sem_base_tile("floor", x, 3, POOLS, "mixed", 1234)
           for x in range(12)}) > 1)
check("explicit style wins", core.sem_base_tile("floor", 2, 3, POOLS, 12, 1234) == 12)
check("unknown style id falls back to hash",
      core.sem_base_tile("floor", 2, 3, POOLS, 999, 1234) == t1)
check("empty pool -> None", core.sem_base_tile("floor", 2, 3, {"floor": []}, "mixed", 1) is None)
check("seed changes the pattern",
      any(core.sem_base_tile("floor", x, 3, POOLS, "mixed", 1) !=
          core.sem_base_tile("floor", x, 3, POOLS, "mixed", 2)
          for x in range(12)))

print("== decor picks ==")
big = blank_tags(9, 9, "floor")
check("interior floor @100% gets decor",
      core.sem_decor_pick(big, 4, 4, 9, 9, 100, POOLS["decor"], 1234) in POOLS["decor"])
check("density 0 -> None",
      core.sem_decor_pick(big, 4, 4, 9, 9, 0, POOLS["decor"], 1234) is None)
check("edge cell (not interior) -> None",
      core.sem_decor_pick(big, 0, 4, 9, 9, 100, POOLS["decor"], 1234) is None)
big[4][5] = "wall"
check("cell beside a wall is not interior -> None",
      core.sem_decor_pick(big, 4, 4, 9, 9, 100, POOLS["decor"], 1234) is None)
big2 = blank_tags(9, 9, "water")
check("non-floor -> None",
      core.sem_decor_pick(big2, 4, 4, 9, 9, 100, POOLS["decor"], 1234) is None)
check("empty decor pool -> None",
      core.sem_decor_pick(big, 4, 4, 9, 9, 100, [], 1234) is None)
check("density 50 sprinkles some, not all",
      0 < sum(1 for x in range(1, 8) for y in range(1, 8)
              if core.sem_decor_pick(big, x, y, 9, 9, 50, POOLS["decor"], 1234)
              is not None) < 49)

print("== physics ==")
check("floor walkable", core.sem_cell_physics("floor") == (False, False))
check("wall blocked", core.sem_cell_physics("wall") == (True, False))
check("water blocked+hazard", core.sem_cell_physics("water") == (True, True))
check("None walkable", core.sem_cell_physics(None) == (False, False))

print("== terrain + settings sanitization ==")
check("valid terrains pass", core.sem_valid_terrain("wall") == "wall")
check("lava rejected", core.sem_valid_terrain("lava") is None)
check("None stays None", core.sem_valid_terrain(None) is None)
s = core.sanitize_semantic_settings(None)
check("defaults", s["shadow_strength"] == 70 and s["decor_density"] == 35
      and s["auto_decor"] is True and s["auto_edges"] is True)
s2 = core.sanitize_semantic_settings({"shadow_strength": 500, "decor_density": -3,
                                      "styles": {"floor": 12, "wall": "bogus"}})
check("shadow clamps to 100", s2["shadow_strength"] == 100)
check("density clamps to 0", s2["decor_density"] == 0)
check("good style kept", s2["styles"]["floor"] == 12)
check("bad style -> mixed", s2["styles"]["wall"] == "mixed")
check("non-dict -> defaults", core.sanitize_semantic_settings("nope")["auto_decor"] is True)

print("== stroke planner ==")
nat = lambda x, y: 7
world = make_world()
world.hazard_layer[3][3] = True   # stale hazard — the planner must clear it
changes = core.sem_plan_stroke(world, [(3, 3)], "wall", POOLS, SETTINGS, nat)
by_layer = {}
for (x, y, layer, nv) in changes:
    by_layer.setdefault(layer, []).append((x, y, nv))
check("wall stroke tags the cell", by_layer.get("semantic") == [(3, 3, "wall")],
      f"got {by_layer.get('semantic')}")
check("wall stroke sets collision", (3, 3, True) in by_layer.get("collision", []))
check("wall stroke clears hazard", (3, 3, False) in by_layer.get("hazard", []))
check("wall stroke resolves a tile",
      any(x == 3 and y == 3 and v in POOLS["wall"] for (x, y, v) in by_layer.get("tiles", [])),
      f"got {by_layer.get('tiles')}")
# a multi-cell stroke sees its own tags (one consistent resolution)
world2 = make_world()
ch2 = core.sem_plan_stroke(world2, [(1, 1), (2, 2)], "floor", POOLS, SETTINGS, nat)
check("multi-cell stroke tags both",
      sorted((x, y) for (x, y, l, v) in ch2 if l == "semantic") == [(1, 1), (2, 2)])
check("out-of-bounds cells skipped",
      core.sem_plan_stroke(world2, [(-1, 0), (99, 99)], "floor", POOLS, SETTINGS, nat) == [])
check("garbage cells skipped",
      core.sem_plan_stroke(world2, ["nope", (None, 2)], "floor", POOLS, SETTINGS, nat) == [])
check("empty stroke -> no changes",
      core.sem_plan_stroke(world2, [], "floor", POOLS, SETTINGS, nat) == [])

world3 = make_world()
ch3 = core.sem_plan_stroke(world3, [(3, 3)], "water", POOLS, SETTINGS, nat)
lay3 = {}
for (x, y, layer, nv) in ch3:
    lay3.setdefault(layer, []).append((x, y, nv))
check("water is blocked+hazard",
      (3, 3, True) in lay3.get("collision", []) and (3, 3, True) in lay3.get("hazard", []))

# meaning-erase: tag cleared, seed-natural tile, collision/hazard cleared
world4 = make_world()
world4.semantic_layer[3][3] = "wall"
world4.collision_layer[3][3] = True
world4.hazard_layer[3][3] = True   # stale — erase must clear it
ch4 = core.sem_plan_stroke(world4, [(3, 3)], None, POOLS, SETTINGS, nat)
lay4 = {}
for (x, y, layer, nv) in ch4:
    lay4.setdefault(layer, []).append((x, y, nv))
check("erase clears the tag", (3, 3, None) in lay4.get("semantic", []))
check("erase restores the natural tile", (3, 3, 7) in lay4.get("tiles", []),
      f"got {lay4.get('tiles')}")
check("erase clears collision+hazard",
      (3, 3, False) in lay4.get("collision", []) and (3, 3, False) in lay4.get("hazard", []))

# invalid terrain behaves like erase
world5x = make_world()
world5x.semantic_layer[3][3] = "wall"
ch5 = core.sem_plan_stroke(world5x, [(3, 3)], "lava", POOLS, SETTINGS, nat)
check("lava sanitizes to erase",
      any(l == "semantic" and v is None for (x, y, l, v) in ch5))

print("== decor replacement ==")
world5 = make_world(9, 9)
# paint a floor room at density 100 -> auto-decor appears on interiors
s100 = dict(SETTINGS)
ch5a = core.sem_plan_stroke(world5, [(x, y) for y in range(9) for x in range(9)],
                            "floor", POOLS, s100, nat)
obj_adds = [(x, y) for (x, y, l, v) in ch5a if l == "objects" and v is not None]
check("density 100 sprinkles interiors", len(obj_adds) > 0, f"got {len(obj_adds)}")
# apply, then re-plan the same stroke: decor must survive (re-added, not lost)
for (x, y, layer, nv) in ch5a:
    {"semantic": world5.semantic_layer, "tiles": world5.data,
     "collision": world5.collision_layer, "hazard": world5.hazard_layer,
     "objects": world5.object_layer}[layer][y][x] = nv
ch5b = core.sem_plan_stroke(world5, [(4, 4)], "floor", POOLS, s100, nat)
readded = [(x, y) for (x, y, l, v) in ch5b if l == "objects" and v is not None]
check("re-plan re-adds cleared auto-decor", len(readded) > 0,
      f"got {len(readded)} re-added")
# user-placed objects are never clobbered
world6 = make_world(9, 9)
world6.semantic_layer[4][4] = "floor"
world6.object_layer[4][4] = core.make_obj_cell(999)   # the user's chest
ch6 = core.sem_plan_stroke(world6, [(4, 3)], "floor", POOLS, s100, nat)
check("user object untouched",
      not any(l == "objects" and x == 4 and y == 4 for (x, y, l, v) in ch6))
check("auto_decor marker detected",
      core.obj_is_auto_decor(core.make_obj_cell(41, {"auto_decor": True})))
check("plain cell is not auto_decor",
      not core.obj_is_auto_decor(core.make_obj_cell(41)))
check("None is not auto_decor", not core.obj_is_auto_decor(None))

print("== automap ==")
world7 = make_world(9, 9)
for yy in range(9):
    for xx in range(9):
        world7.semantic_layer[yy][xx] = "floor"
world7.semantic_layer[2][2] = "wall"
world7.semantic_layer[5][5] = "water"
world7.data[2][2] = 999   # stale tile — automap must fix it
ch7 = core.sem_plan_automap(world7, POOLS, s100)
lay7 = {}
for (x, y, layer, nv) in ch7:
    lay7.setdefault(layer, []).append((x, y, nv))
check("automap fixes the stale wall tile",
      any(x == 2 and y == 2 and v in POOLS["wall"] for (x, y, v) in lay7.get("tiles", [])))
check("automap sets water hazard",
      (5, 5, True) in lay7.get("hazard", []))
check("automap re-sprinkles decor", len([1 for (x, y, l, v) in ch7
                                        if l == "objects" and v is not None]) > 0)
# deterministic: same settings, same plan
ch7b = core.sem_plan_automap(world7, POOLS, s100)
check("automap deterministic", ch7 == ch7b)

print("== save/load + resize round trips ==")
world8 = make_world(6, 6)
world8.semantic_layer[1][1] = "wall"
world8.hazard_layer[2][2] = True
world8.collision_layer[1][1] = True
world8.semantic_settings = core.sanitize_semantic_settings({"decor_density": 80})
with tempfile.TemporaryDirectory() as td:
    fp = os.path.join(td, "sem.json")
    check("save ok", world8.save(fp))
    w8b = core.WorldMap(1, 1, {})
    check("load ok", w8b.load(fp))
    check("tag survives", w8b.semantic_layer[1][1] == "wall")
    check("hazard survives", w8b.hazard_layer[2][2] is True)
    check("settings survive", w8b.semantic_settings["decor_density"] == 80)
    # malformed tags sanitize to None on load
    raw = open(fp).read().replace('"wall"', '"lava"')
    open(fp, "w").write(raw)
    w8c = core.WorldMap(1, 1, {})
    check("load ok (malformed)", w8c.load(fp))
    check("lava sanitizes to None", w8c.semantic_layer[1][1] is None)
world8.resize(8, 8)
check("resize keeps tags", world8.semantic_layer[1][1] == "wall")
check("resize keeps hazards", world8.hazard_layer[2][2] is True)
world8.resize(4, 4)
check("shrink keeps in-bounds tags", world8.semantic_layer[1][1] == "wall")

print("== csv import clears meaning ==")
world_csv = make_world(4, 4)
world_csv.semantic_layer[0][0] = "wall"
world_csv.hazard_layer[0][0] = True
with tempfile.TemporaryDirectory() as td:
    fp = os.path.join(td, "m.csv")
    open(fp, "w").write("1,2\n3,4\n")
    check("csv load ok", world_csv.load_csv(fp))
    check("csv clears tags", world_csv.semantic_layer[0][0] is None)
    check("csv clears hazards", world_csv.hazard_layer[0][0] is False)
    check("csv resets settings",
          world_csv.semantic_settings["decor_density"] == 35)

print("== SetTileCommand on the new layers ==")
world9 = make_world()
cmd = core.SetTileCommand(world9, 2, 2, None, "floor", "semantic")
cmd.execute()
check("semantic command executes", world9.semantic_layer[2][2] == "floor")
cmd.undo()
check("semantic command undoes", world9.semantic_layer[2][2] is None)
cmd2 = core.SetTileCommand(world9, 2, 2, False, True, "hazard")
cmd2.execute()
check("hazard command executes", world9.hazard_layer[2][2] is True)
cmd2.undo()
check("hazard command undoes", world9.hazard_layer[2][2] is False)

print("== logical layers ==")
check("five logical layers", set(core.LOGICAL_LAYERS) ==
      {"ground", "walls", "objects", "routes", "fx"})
for name, spec in core.LOGICAL_LAYERS.items():
    check(f"{name} has grids+brushes+hint",
          all(k in spec for k in ("grids", "brushes", "hint")))
check("ground brushes", core.LOGICAL_LAYERS["ground"]["brushes"] ==
      ("floor", "water", "erase-meaning"))
check("fx brushes are big modes, not polygon tools",
      core.LOGICAL_LAYERS["fx"]["brushes"] == ("walk", "block", "hazard", "decor"))

print("== hud integration: validation, one-undo, pools ==")
import crumbs_hud as h

old_world = h.world
h.world = core.WorldMap(9, 9, h.assets)
try:
    w = h.world
    check("validate: good cells pass",
          h._validate_stroke_cells([{"x": 1, "y": 2}, {"x": 3, "y": 4}], w) ==
          [(1, 2), (3, 4)])
    check("validate: dedups", h._validate_stroke_cells(
        [{"x": 1, "y": 1}, {"x": 1, "y": 1}], w) == [(1, 1)])
    check("validate: drops garbage",
          h._validate_stroke_cells(
              ["nope", {"x": 1.5, "y": 2}, {"x": -1, "y": 0},
               {"x": 99, "y": 99}, {"x": 2}], w) == [])
    check("validate: non-list -> []", h._validate_stroke_cells("nope", w) == [])

    # one-undo: a semantic stroke lands as a single history step
    depth0 = len(h.history.undo_stack)
    w.hazard_layer[4][4] = True   # stale hazard — the stroke must clear it
    changes = core.sem_plan_stroke(w, [(4, 4)], "wall", POOLS, SETTINGS, nat)

    def _do_sem():
        for (sx, sy, layer, nv) in changes:
            h._grid(layer)[sy][sx] = nv
        h._mark_dirty()
    h._undoable("semantic stroke", _do_sem)
    check("one history step per stroke", len(h.history.undo_stack) == depth0 + 1)
    check("tag applied", w.semantic_layer[4][4] == "wall")
    check("collision applied", w.collision_layer[4][4] is True)
    check("echo covers semantic+hazard layers",
          {c["layer"] for c in h._echo_changes(changes)} >= {"semantic", "hazard"})
    h.history.undo()
    check("undo restores tag", w.semantic_layer[4][4] is None)
    check("undo restores collision", w.collision_layer[4][4] is False)
    h.history.redo()
    check("redo re-applies tag", w.semantic_layer[4][4] == "wall")

    # collision-as-paint through the same one-undo path
    depth1 = len(h.history.undo_stack)
    coll_changes = [(5, 5, "collision", True), (5, 5, "hazard", True)]

    def _do_coll():
        for (sx, sy, layer, nv) in coll_changes:
            h._grid(layer)[sy][sx] = nv
        h._mark_dirty()
    h._undoable("collision stroke", _do_coll)
    check("collision stroke is one step", len(h.history.undo_stack) == depth1 + 1)
    check("hazard painted", w.hazard_layer[5][5] is True)
    h.history.undo()
    check("undo clears hazard", w.hazard_layer[5][5] is False)

    # settings round through the real helpers
    w.semantic_settings = core.sanitize_semantic_settings({"shadow_strength": 10})
    check("map state carries semantic grids",
          all(k in h._map_state() for k in
              ("semantic", "hazard", "sem_settings", "semantic_seed")))
    check("effective seed falls back to 0", h._sem_effective_seed() == 0)
    h.map_meta = getattr(h, "map_meta", {})
    check("pools have the four keys", set(h._semantic_pools()) ==
          {"floor", "wall", "water", "decor"})
    check("pools hold int ids",
          all(isinstance(i, int)
              for ids in h._semantic_pools().values() for i in ids))
    check("names cover pooled ids",
          all(i in h._semantic_names()
              for ids in h._semantic_pools().values() for i in ids))
finally:
    h.world = old_world

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
