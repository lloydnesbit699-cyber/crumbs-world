#!/usr/bin/env python3
"""hud_sheet_test.py — v5.47 HUD-pass server tests. Run: python3 hud_sheet_test.py
Covers: the shared patrol validators (points + anchor), Melody's suggestion
materializers (open-cell test, region flood, wall ring with its south door
gap, patrol-endpoint connect), and merge pause carry-by-coordinate.
No server, no network, no user data — the world is swapped like
semantic_test.py does.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crumbs_core as core
import crumbs_hud as h

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
h.world = core.WorldMap(9, 9, h.assets)
try:
    print("== patrol point validation ==")
    pts, err = h._validate_patrol_points([[1, 1], [3, 3], [5, 5]])
    check("good points pass", err is None and pts == [[1, 1], [3, 3], [5, 5]], err)
    _, err = h._validate_patrol_points([[1, 1]])
    check("one stop rejected", err == "tap 2-8 stops", err)
    _, err = h._validate_patrol_points([[x, 0] for x in range(9)])
    check("nine stops rejected", err == "tap 2-8 stops", err)
    _, err = h._validate_patrol_points([[1, 1], [99, 99]])
    check("off-map stop rejected", err == "stop off the map", err)
    _, err = h._validate_patrol_points("nope")
    check("garbage rejected", err == "bad points", err)
    _, err = h._validate_patrol_points([[1, 1], ["a", "b"]])
    check("non-int points rejected", err == "bad points", err)
    h.world.collision_layer[3][3] = 1
    _, err = h._validate_patrol_points([[1, 1], [3, 3]])
    check("blocked stop rejected", err == "a stop is blocked", err)
    h.world.collision_layer[3][3] = 0

    print("== patrol anchor validation ==")
    ax, ay, err = h._validate_patrol_anchor(42, "x", 2)
    check("bad anchor x rejected", err == "anchor x/y required", err)
    ax, ay, err = h._validate_patrol_anchor(42, 99, 2)
    check("off-map anchor rejected", err == "anchor off the map", err)
    h.world.object_layer[2][3] = 42
    ax, ay, err = h._validate_patrol_anchor(42, 3, 2)
    check("matching character anchors", err is None and (ax, ay) == (3, 2), err)
    _, _, err = h._validate_patrol_anchor(43, 3, 2)
    check("wrong tile id rejected", err is not None, err)
    h.world.object_layer[2][3] = None

    print("== suggestion open-cell test ==")
    check("open cell", h._suggest_open_cell(4, 4) is True)
    check("off-map not open", h._suggest_open_cell(9, 4) is False)
    h.world.collision_layer[4][4] = 1
    check("collision not open", h._suggest_open_cell(4, 4) is False)
    h.world.collision_layer[4][4] = 0
    h.world.semantic_layer[4][4] = "wall"
    check("existing wall not open", h._suggest_open_cell(4, 4) is False)
    h.world.semantic_layer[4][4] = None
    h.world.object_layer[4][4] = 7
    check("character cell not open", h._suggest_open_cell(4, 4) is False)
    h.world.object_layer[4][4] = None

    print("== suggestion region flood ==")
    region = h._suggest_region()
    check("fresh map is one region", len(region) == 81, len(region))
    # a wall-tagged column splits the map in two
    for y in range(9):
        h.world.semantic_layer[y][4] = "wall"
    left = h._suggest_region((1, 1))
    check("seed picks its side", len(left) == 36, len(left))
    check("seed cell inside", (1, 1) in left)
    check("wall column excluded", all(x != 4 for x, y in left))
    for y in range(9):
        h.world.semantic_layer[y][4] = None

    print("== wall-ring suggestion ==")
    cells = h._suggest_wall_ring()
    check("ring found", cells is not None, cells)
    ring = set(map(tuple, cells))
    # boundary of a 9x9 = 32 cells, minus the 2-wide south door gap
    check("ring size 30", len(ring) == 30, len(ring))
    check("all on the map edge",
          all(x in (0, 8) or y in (0, 8) for x, y in ring))
    south_row = sorted(x for x, y in ring if y == 8)
    check("south row keeps a 2-wide door gap",
          south_row == [0, 1, 2, 5, 6, 7, 8], south_row)
    check("no cell holds a character", all(
        core.obj_tid(h.world.object_layer[y][x]) is None for x, y in ring))
    # a character in the middle keeps walls away from him
    h.world.object_layer[4][4] = 7
    cells2 = h._suggest_wall_ring()
    ring2 = set(map(tuple, cells2))
    near = {(4, 3), (4, 5), (3, 4), (5, 4)}
    check("ring avoids the character", not (ring2 & near), ring2 & near)
    h.world.object_layer[4][4] = None
    # a closet (under 9 open cells) gets no suggestion
    for y in range(9):
        for x in range(9):
            h.world.collision_layer[y][x] = 1
    for x, y in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        h.world.collision_layer[y][x] = 0
    check("tiny region -> None", h._suggest_wall_ring() is None)
    for y in range(9):
        for x in range(9):
            h.world.collision_layer[y][x] = 0

    print("== connect-patrols suggestion ==")
    old_patrols = h._patrols
    h._patrols = [
        {"id": 1, "tile_id": 5, "points": [[1, 1], [2, 2]]},
        {"id": 2, "tile_id": 6, "points": [[3, 3], [4, 4]]},
    ]
    conn = h._suggest_connect_patrols()
    check("near endpoints connect", conn is not None, conn)
    check("ids carried", conn["keep_id"] == 1 and conn["drop_id"] == 2, conn)
    check("routes join end to end",
          conn["points"] == [[1, 1], [2, 2], [3, 3], [4, 4]], conn["points"])
    h._patrols = [
        {"id": 1, "tile_id": 5, "points": [[1, 1], [2, 2]]},
        {"id": 2, "tile_id": 6, "points": [[2, 2], [5, 5]]},
    ]
    conn2 = h._suggest_connect_patrols()
    check("a truly shared stop appears once",
          conn2 is not None and conn2["points"] == [[1, 1], [2, 2], [5, 5]],
          conn2)
    h._patrols = [{"id": 1, "tile_id": 5, "points": [[1, 1], [2, 2]]}]
    check("one patrol -> None", h._suggest_connect_patrols() is None)
    # 5 + 5 stops would exceed the 8-stop cap
    h._patrols = [
        {"id": 1, "tile_id": 5, "points": [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]},
        {"id": 2, "tile_id": 6, "points": [[4, 1], [3, 1], [2, 1], [1, 1], [0, 1]]},
    ]
    check("over-cap merge refused", h._suggest_connect_patrols() is None)
    h._patrols = old_patrols

    print("== merge pause carry ==")
    keep = {"id": 1, "points": [[1, 1], [2, 2]],
            "pauses": [{"secs": 30, "mode": "sleep"}, {"secs": 0, "mode": "stand"}]}
    drop = {"id": 2, "points": [[2, 2], [5, 5]],
            "pauses": [{"secs": 0, "mode": "stand"}, {"secs": 60, "mode": "stand"}]}
    merged = h._merge_pauses(keep, drop, [[1, 1], [2, 2], [5, 5]])
    check("length matches merged points", len(merged) == 3, merged)
    check("keep's wait rides along", merged[0]["secs"] == 30 and
          merged[0]["mode"] == "sleep", merged[0])
    check("drop's wait rides along", merged[2]["secs"] == 60, merged[2])
    check("fresh stops wait nothing", merged[1]["secs"] == 0, merged[1])
    check("state preserved when set",
          h._merge_pauses(
              {"points": [[0, 0]], "pauses": [{"secs": 10, "mode": "sleep",
                                               "state": "sleep"}]},
              {"points": [[9, 9]], "pauses": []},
              [[0, 0]])[0].get("state") == "sleep")

    print("== animation suggestion target + view (v5.47.1) ==")
    _real_find_custom = h._find_custom
    _real_pending = h._melody_agent.suggestion_pending
    try:
        h._find_custom = lambda tid: ({"id": tid, "name": "Torch",
                                       "frames": ["f1.png"]}, "local") \
            if tid == 77 else (None, None)
        h.world.object_layer[4][4] = 77
        tgt = h._suggest_animation_target([4, 4])
        check("animatable instance resolves",
              tgt == {"tile_id": 77, "tile_name": "Torch", "x": 4, "y": 4}, tgt)
        check("empty cell -> None", h._suggest_animation_target([0, 0]) is None)
        check("no where -> None", h._suggest_animation_target(None) is None)
        check("off-map -> None", h._suggest_animation_target([99, 99]) is None)
        h.world.object_layer[5][5] = 78
        check("non-custom tile -> None",
              h._suggest_animation_target([5, 5]) is None)
        h._find_custom = lambda tid: ({"id": tid, "name": "Statue",
                                       "frames": []}, "local") \
            if tid == 77 else (None, None)
        check("frameless tile -> None",
              h._suggest_animation_target([4, 4]) is None)
        h._find_custom = _real_find_custom

        h._melody_agent.suggestion_pending = lambda d, u: {
            "kind": "animation_preset", "label": "Make it flicker?",
            "status": "pending", "where_xy": [4, 4], "preset": "pulse"}
        h._find_custom = lambda tid: ({"id": tid, "name": "Torch",
                                       "frames": ["f1.png"]}, "local") \
            if tid == 77 else (None, None)
        view = h._melody_suggestion_view("alice")
        check("animation view materializes",
              view and view["kind"] == "animation_preset" and
              view["preset"] == "pulse" and view["preset_label"] == "Pulse" and
              view["target"]["tile_id"] == 77, view)
        h._melody_agent.suggestion_pending = lambda d, u: {
            "kind": "animation_preset", "label": "x", "status": "pending",
            "where_xy": [4, 4], "preset": "explode"}
        check("bad preset -> None",
              h._melody_suggestion_view("alice") is None)
        h._melody_agent.suggestion_pending = lambda d, u: {
            "kind": "animation_preset", "label": "x", "status": "pending",
            "where_xy": [0, 0], "preset": "pulse"}
        check("no target -> None",
              h._melody_suggestion_view("alice") is None)
        h._melody_agent.suggestion_pending = lambda d, u: None
        check("no suggestion -> None",
              h._melody_suggestion_view("alice") is None)
    finally:
        h._find_custom = _real_find_custom
        h._melody_agent.suggestion_pending = _real_pending
finally:
    h.world = old_world

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
