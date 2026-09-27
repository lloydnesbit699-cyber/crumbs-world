#!/usr/bin/env python3
"""scale_hardening_test.py — v5.42.1 scale-hardening tests. Run: python3 scale_hardening_test.py
Covers:
  - diff-based undo: small paint round-trip (undo + redo restore cells)
  - diff-based undo: large-map stroke round-trip, retained diff stays small
  - metadata-only undo (grids=False) retains no grid diffs
  - full snapshots still used for generate-style ops (full=True)
  - height-grid cache: hits on repeat GETs, misses after mutation,
    hits across undo/redo via rev restore
  - natural-grid cache: hits on repeat GETs, invalidated by clear()
  - HistoryManager.set_max_steps: shrink keeps newest, grow works
  - _user_history: narrower stacks on wide maps, idle eviction
  - /api/map/thumb disk cache: hit, mtime invalidation, stale sweep
  - WorldMap.save writes compact JSON (no indent=2)
Temp world + temp vault dir only — no server, no network, no user data.
"""
import copy
import json
import os
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


# ---- isolated world/history/vault -------------------------------------------
tmp = tempfile.mkdtemp(prefix="crumbs-scale-hard-")
_old_world, _old_traits = h.world, h.traits_grid
_old_history, _old_base = h.history, h._vault_base
h._vault_base = lambda: tmp


def fresh_world(w, hh):
    h.world = core.WorldMap(w, hh, h.assets)
    h.traits_grid = h._blank_traits()
    h.history = core.HistoryManager()
    h._height_cache.clear()
    h._clear_natural_cache()


def paint_cells(cells, label="paint"):
    def _do():
        for (x, y, v) in cells:
            h.world.data[y][x] = v
        h._mark_dirty()
    h._undoable(label, _do)


def diff_cell_count(cmd):
    return sum(len(v) for v in cmd.diffs.values())


print("== diff undo: small paint round-trip ==")
fresh_world(32, 32)
paint_cells([(1, 1, 7), (2, 3, 7), (5, 5, 9)])
check("cells painted", h.world.data[1][1] == 7 and h.world.data[5][5] == 9)
cmd = h.history.undo_stack[-1]
check("step is a diff command", isinstance(cmd, h._StateDiffCommand),
      type(cmd).__name__)
check("diff retains only touched cells", diff_cell_count(cmd) == 3,
      f"got {diff_cell_count(cmd)}")
check("no full grid retained",
      all(len(v) < 32 * 32 for v in cmd.diffs.values()))
check("undo ok", h.history.undo() is True)
check("undo restores cells",
      h.world.data[1][1] == 0 and h.world.data[5][5] == 0)
check("redo ok", h.history.redo() is True)
check("redo re-applies cells",
      h.world.data[1][1] == 7 and h.world.data[5][5] == 9)

print("== diff undo: large map, diff stays proportional ==")
fresh_world(200, 120)
cells = [(x % 200, 10 + x // 200, 4) for x in range(500)]
paint_cells(cells, "stroke")
cmd = h.history.undo_stack[-1]
check("500-cell stroke painted", h.world.data[12][99] == 4)
check("retained diff is 500 cells, not 24k",
      diff_cell_count(cmd) == 500, f"got {diff_cell_count(cmd)}")
check("undo ok", h.history.undo() is True)
check("undo restores all 500",
      all(h.world.data[10 + x // 200][x % 200] == 0 for x in range(500)))
check("redo ok", h.history.redo() is True)
check("redo re-applies all 500",
      all(h.world.data[10 + x // 200][x % 200] == 4 for x in range(500)))

print("== diff undo: height overrides + traits ride the diff ==")
fresh_world(32, 32)
def _do2():
    h.world.height_override[3][3] = 2
    h.traits_grid[4][4] = {"k": "v"}
    h._mark_dirty()
h._undoable("height+trait", _do2)
check("override set", h.world.height_override[3][3] == 2)
check("undo ok", h.history.undo() is True)
check("override undone", h.world.height_override[3][3] is None)
check("trait undone", h.traits_grid[4][4] != {"k": "v"})
check("redo ok", h.history.redo() is True)
check("override redone", h.world.height_override[3][3] == 2)

print("== metadata-only undo retains no grid diffs ==")
fresh_world(32, 32)
def _do3():
    h._patrols.append({"id": 1, "route": [(0, 0)]})
    h._mark_dirty()
h._undoable("assign patrol", _do3, grids=False)
cmd = h.history.undo_stack[-1]
check("step is a diff command", isinstance(cmd, h._StateDiffCommand))
check("no grid diffs retained", cmd.diffs == {}, f"got {cmd.diffs.keys()}")
check("patrol added", any(p["id"] == 1 for p in h._patrols))
check("undo ok", h.history.undo() is True)
check("patrol removed by undo", not any(p["id"] == 1 for p in h._patrols))

print("== full snapshots reserved for generate-style ops ==")
fresh_world(32, 32)
h._undoable("generate x", lambda: h._mark_dirty(), full=True)
cmd = h.history.undo_stack[-1]
check("full=True keeps StateSnapshotCommand",
      isinstance(cmd, core.StateSnapshotCommand), type(cmd).__name__)

print("== height-grid cache ==")
fresh_world(48, 48)
h._height_cache.clear()
g1 = h._height_grid_cached()
g2 = h._height_grid_cached()
check("repeat GET hits cache (same object)", g1 is g2)
check("grid shape sane", len(g1) == 48 and len(g1[0]) == 48,
      f"{len(g1)}x{len(g1[0]) if g1 else '?'}")
paint_cells([(0, 0, 5)])
g3 = h._height_grid_cached()
check("mutation invalidates (recompute)", g3 is not g1)
# undo/redo rev-restore: stepping back must HIT, not recompute
h.history.undo()
h._sync_rev_from_stack(h.history.redo_stack, "before")
g4 = h._height_grid_cached()
check("undo restores rev, cache hits", g4 is g1)
h.history.redo()
h._sync_rev_from_stack(h.history.undo_stack, "after")
g5 = h._height_grid_cached()
check("redo restores rev, cache hits", g5 is g3)
check("height cache bounded", len(h._height_cache) <= h._HEIGHT_CACHE_MAX,
      f"got {len(h._height_cache)}")

print("== natural-grid cache ==")
fresh_world(40, 40)
h.map_meta["biome"] = "dungeon"
h.map_meta["seed"] = 4242
n1 = h._natural_grid()
n2 = h._natural_grid()
check("repeat GET hits cache (same object)", n1 is n2)
check("grid shape sane", len(n1) == 40 and len(n1[0]) == 40)
h._clear_natural_cache()  # what generate/resize/reset/registry-save do
n3 = h._natural_grid()
check("clear() invalidates (recompute)", n3 is not n1)
check("recompute matches", n3 == n1)

print("== history depth tuning ==")
hm = core.HistoryManager()
for _ in range(15):
    hm.push(object())
hm.set_max_steps(10)
check("shrink keeps newest 10", len(hm.undo_stack) == 10,
      f"got {len(hm.undo_stack)}")
check("deque maxlen follows", hm.undo_stack.maxlen == 10)
hm.set_max_steps(20)
check("grow works", hm.undo_stack.maxlen == 20 and len(hm.undo_stack) == 10)

print("== _user_history: wide maps get shorter stacks ==")
fresh_world(200, 120)
hw = h._user_history("depth_u", "depth_v")
check("wide map -> 25 steps", hw.undo_stack.maxlen == 25,
      f"got {hw.undo_stack.maxlen}")
fresh_world(32, 32)
hn = h._user_history("depth_u2", "depth_v2")
check("narrow map -> 50 steps", hn.undo_stack.maxlen == 50,
      f"got {hn.undo_stack.maxlen}")

print("== _user_history: idle eviction ==")
h1 = h._user_history("idle_u", "idle_v")
h._histories_last[("idle_u", "idle_v")] = time.time() - 4000
h._user_history("other_u", "other_v")
check("idle stack evicted", ("idle_u", "idle_v") not in h._histories)
check("active stack kept", ("other_u", "other_v") in h._histories)
for k in [("depth_u", "depth_v"), ("depth_u2", "depth_v2"),
          ("other_u", "other_v")]:
    h._histories.pop(k, None)
    h._histories_last.pop(k, None)

print("== map thumbnail disk cache ==")
if not core.PIL_AVAILABLE:
    print("  skip: Pillow unavailable")
else:
    name = "scale-thumb-test.json"
    mp = os.path.join(tmp, name)

    def write_map(w, hh, fill):
        with open(mp, "w") as f:
            json.dump({"tiles": [[fill] * w for _ in range(hh)],
                       "objects": [[None] * w for _ in range(hh)],
                       "width": w, "height": hh}, f)

    def cache_pngs():
        cdir = os.path.join(tmp, h._THUMB_CACHE_DIR)
        if not os.path.isdir(cdir):
            return []
        return sorted(f for f in os.listdir(cdir) if f.endswith(".png"))

    write_map(8, 8, 0)
    b1 = h._map_thumb_bytes(name)
    check("renders PNG", b1 is not None and b1[:8] == b"\x89PNG\r\n\x1a\n")
    files1 = cache_pngs()
    check("one cached file", len(files1) == 1, f"got {files1}")
    mtime1 = os.path.getmtime(os.path.join(tmp, h._THUMB_CACHE_DIR, files1[0]))
    b2 = h._map_thumb_bytes(name)
    check("second fetch hits disk (same bytes)", b2 == b1)
    mtime2 = os.path.getmtime(os.path.join(tmp, h._THUMB_CACHE_DIR, files1[0]))
    check("disk hit does not rewrite", mtime1 == mtime2)
    # mutate the map file with a forced newer mtime
    write_map(10, 10, 0)
    st = os.stat(mp)
    os.utime(mp, ns=(st.st_atime_ns, st.st_mtime_ns + 50_000_000))
    b3 = h._map_thumb_bytes(name)
    files3 = cache_pngs()
    check("mtime change re-renders", b3 is not None)
    check("stale render swept, one file remains",
          len(files3) == 1 and files3[0] != files1[0],
          f"got {files3}")
    check("missing map -> None", h._map_thumb_bytes("nope.json") is None)

print("== WorldMap.save is compact ==")
wm = core.WorldMap(8, 8, h.assets)
sp = os.path.join(tmp, "compact.json")
wm.save(sp)
raw = open(sp, "rb").read()
check("no pretty-print indent", b"\n" not in raw.strip(), f"{len(raw)} bytes")
check("still loads", json.loads(raw)["width"] == 8)

# ---- restore globals ---------------------------------------------------------
h.world, h.traits_grid = _old_world, _old_traits
h.history, h._vault_base = _old_history, _old_base
h.map_meta.pop("biome", None)
h.map_meta.pop("seed", None)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
