#!/usr/bin/env python3
"""melody_playtest_test.py — v5.49 AI playtester tests. Run: python3 melody_playtest_test.py
Covers: the playtest tool's QA findings on synthetic maps (reachability,
walled-off paint, unwinnable/missing goals, hazard exposure, dead zones),
seed determinism (same map -> same report), malformed input handling, and
Law 18 vault isolation. Read-only by contract: the tool must never modify
the map files it reads.
No server, no network, no user data.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MELODY_BRAIN"] = "off"  # no network in tests

import melody_agent as ma

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def fresh_env():
    tmp = tempfile.mkdtemp(prefix="melody-playtest-test-")
    vdir = os.path.join(tmp, "vaults", "alice")
    os.makedirs(vdir)
    return tmp, vdir


def write_map(vdir, name, w, h, walls=(), hazards=(), hero=None, goals=()):
    """walls/hazards: (x,y) cells. hero: (tid, x, y). goals: [(x,y)]."""
    tiles = [[1] * w for _ in range(h)]
    collision = [[0] * w for _ in range(h)]
    for x, y in walls:
        collision[y][x] = 1
    hz = [[0] * w for _ in range(h)]
    for x, y in hazards:
        hz[y][x] = 1
    objects = [[0] * w for _ in range(h)]
    tweaks = {}
    if hero:
        tid, hx, hy = hero
        objects[hy][hx] = {"tid": tid}
        tweaks = {"hero_tiles": [tid]}
    doc = {"width": w, "height": h, "tiles": tiles, "objects": objects,
           "collision": collision, "hazard": hz}
    with open(os.path.join(vdir, name), "w", encoding="utf-8") as f:
        json.dump(doc, f)
    game = [{"kind": "goal", "x": gx, "y": gy} for gx, gy in goals]
    with open(os.path.join(vdir, name[:-5] + ".rules.json"), "w",
              encoding="utf-8") as f:
        json.dump({"tweaks": tweaks, "game": game}, f)
    return os.path.join(vdir, name)


def snapshot(vdir):
    out = {}
    for f in sorted(os.listdir(vdir)):
        with open(os.path.join(vdir, f), "rb") as fh:
            out[f] = hashlib.sha256(fh.read()).hexdigest()
    return out


print("== happy path: open room, reachable goal ==")
tmp, vdir = fresh_env()
try:
    write_map(vdir, "arena_map.json", 9, 9, hero=(42, 1, 1), goals=[(7, 7)])
    before = snapshot(vdir)
    r = ma.tool_playtest_map(tmp, "alice", trials="30")
    check("verdict: looks playable", "looks playable" in r, r.split("\n")[0])
    check("goals all reachable", "all 1 reachable" in r, r)
    check("spawn found via hero", "your hero (tile #42)" in r, r)
    check("read-only: files untouched", snapshot(vdir) == before)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== walled-off paint ==")
tmp, vdir = fresh_env()
try:
    # vertical wall splits the 9x9 room; paint on the far side is unreachable.
    walls = [(4, y) for y in range(9)]
    write_map(vdir, "split_map.json", 9, 9, walls=walls,
              hero=(42, 1, 1), goals=[(1, 7)])
    r = ma.tool_playtest_map(tmp, "alice", trials="20")
    check("walled-off cells reported", "Walled-off paint:" in r, r)
    check("verdict counts the issue", "issue(s)" in r, r.split("\n")[0])
    check("reachable goal still fine", "UNWINNABLE" not in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== unwinnable + missing goals ==")
tmp, vdir = fresh_env()
try:
    walls = [(4, y) for y in range(9)]
    write_map(vdir, "nowin_map.json", 9, 9, walls=walls,
              hero=(42, 1, 1), goals=[(7, 7)])
    r = ma.tool_playtest_map(tmp, "alice", trials="20")
    check("unwinnable goal called out", "UNWINNABLE" in r, r)
    write_map(vdir, "nogoal_map.json", 7, 7, hero=(42, 1, 1))
    r = ma.tool_playtest_map(tmp, "alice", map_name="nogoal_map.json",
                             trials="20")
    check("missing goal noted", "nothing to win yet" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== hazards ==")
tmp, vdir = fresh_env()
try:
    write_map(vdir, "hot_map.json", 9, 9, hazards=[(3, 3), (4, 4), (5, 5)],
              hero=(42, 1, 1), goals=[(7, 7)])
    r = ma.tool_playtest_map(tmp, "alice", trials="30")
    check("hazard cells counted", "3 hazard cell(s)" in r, r)
    check("exposure averaged per walk", "hazard steps per walk" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== dead zones (unit level, fixed seed) ==")
# a long 1-wide corridor: few short walks can't reach the far end.
w, h = 200, 1
walkable = lambda x, y: 0 <= x < w and y == 0
hazard = [[0] * w for _ in range(h)]
visits, _ = ma._pt_walk(walkable, hazard, (0, 0), w, h, 5, seed=7)
far = sum(1 for x in range(100, 200) if visits[0][x] > 0)
check("far corridor cells unvisited on short walks", far == 0,
      f"{far} far cells visited")
# tiny open room, plenty of walks: every cell gets visited.
w2, h2 = 4, 4
walk2 = lambda x, y: 0 <= x < w2 and 0 <= y < h2
v2, _ = ma._pt_walk(walk2, [[0] * w2 for _ in range(h2)], (1, 1),
                    w2, h2, 40, 7)
unvisited = sum(1 for y in range(h2) for x in range(w2) if v2[y][x] == 0)
check("small room fully covered", unvisited == 0, f"{unvisited} unvisited")

print("== determinism: same map, same report ==")
tmp, vdir = fresh_env()
try:
    write_map(vdir, "det_map.json", 11, 11, hero=(42, 2, 2), goals=[(8, 8)],
              hazards=[(5, 5)])
    r1 = ma.tool_playtest_map(tmp, "alice", trials="40")
    r2 = ma.tool_playtest_map(tmp, "alice", trials="40")
    check("re-run agrees", r1 == r2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== malformed input ==")
tmp, vdir = fresh_env()
try:
    check("empty vault", "don't have any saved maps" in
          ma.tool_playtest_map(tmp, "alice"))
    with open(os.path.join(vdir, "bad_map.json"), "w") as f:
        f.write("{not json")
    check("bad json", "can't be read" in
          ma.tool_playtest_map(tmp, "alice", map_name="bad_map.json"))
    with open(os.path.join(vdir, "weird_map.json"), "w") as f:
        json.dump({"width": 0, "height": 9}, f)
    check("bad dims", "odd dimensions" in
          ma.tool_playtest_map(tmp, "alice", map_name="weird_map.json"))
    check("unknown map", "can't find a map called" in
          ma.tool_playtest_map(tmp, "alice", map_name="ghost_map.json"))
    check("trials clamped, not crashed",
          isinstance(ma.tool_playtest_map(tmp, "alice", trials="abc"), str))
    # every cell blocked: nothing can move.
    write_map(vdir, "solid_map.json", 5, 5,
              walls=[(x, y) for y in range(5) for x in range(5)])
    r = ma.tool_playtest_map(tmp, "alice", map_name="solid_map.json")
    check("all-blocked map", "no walkable cell at all" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== Law 18: vault isolation ==")
tmp, vdir = fresh_env()
try:
    write_map(vdir, "arena_map.json", 7, 7, hero=(42, 1, 1))
    # bob's vault has the only copy of secret_map; alice must not see it.
    bdir = os.path.join(tmp, "vaults", "bob")
    os.makedirs(bdir)
    write_map(bdir, "secret_map.json", 7, 7, hero=(9, 1, 1))
    r = ma.tool_playtest_map(tmp, "alice", map_name="secret_map.json")
    check("other player's map invisible", "can't find a map called" in r, r)
    check("no vault dir -> plain message",
          "couldn't find your vault" in ma.tool_playtest_map(tmp, "nobody"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
