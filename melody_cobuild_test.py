#!/usr/bin/env python3
"""melody_cobuild_test.py — v5.48 co-build tests. Run: python3 melody_cobuild_test.py
Covers: tile_lookup (shared registry + Law 18 isolation), the world-snapshot
cleaner (untrusted client data stays data: unknown keys dropped, numbers
clamped, strings capped), the two new suggestion kinds (room_draft,
patrol_draft — validation + record shape), the tool-registry invariant
(every known tool is declared AND dispatched), and the handle_chat world
kwarg plumbing (the snapshot never lands in saved history).
No server, no network, no user data.
"""
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


def fresh_dir():
    return tempfile.mkdtemp(prefix="melody-cobuild-test-")


print("== tile_lookup ==")
r = ma.tool_tile_lookup(HERE, "alice", "floor")
check("finds shared-library tiles", "#70000" in r and "floor" in r.lower(), r[:80])
r = ma.tool_tile_lookup(HERE, "alice", "zzzznope")
check("no-match says so plainly", "No tiles matching" in r, r[:80])
r = ma.tool_tile_lookup(HERE, "alice", "   ")
check("empty query asks for a word", "Give me a word" in r, r[:80])
r = ma.tool_tile_lookup(HERE, "alice", "a")
check("results capped at 8", len(r.strip().split("\n")) <= 8,
      f"{len(r.strip().split(chr(10)))} lines")
r = ma.tool_tile_lookup(HERE, "not a user!!", "floor")
check("bad username can't break it", isinstance(r, str) and len(r) > 0, r[:80])

print("== world snapshot cleaner ==")
check("non-dict -> None", ma._clean_world("nope") is None)
check("garbage dims -> None",
      ma._clean_world({"w": 0, "h": 15}) is None)
check("oversize dims -> None",
      ma._clean_world({"w": 501, "h": 15}) is None)
snap = ma._clean_world({
    "w": 25, "h": 15, "evil": "drop me",
    "sel": {"x": 3, "y": 4}, "tool": "suggest",
    "budget": {"painted": 100, "npcs": 2, "junk": "x"},
    "counts": {"patrols": 1},
    "npcs": [{"id": 5, "x": 1, "y": 1}, {"id": 6, "x": 99, "y": 99}],
})
check("keeps known keys", snap and snap["w"] == 25 and snap["tool"] == "suggest",
      json.dumps(snap)[:120])
check("drops unknown keys", snap and "evil" not in snap)
check("drops out-of-bounds npc", snap and len(snap["npcs"]) == 1)
check("drops non-numeric budget junk",
      snap and "junk" not in snap.get("budget", {}))
big = {"w": 25, "h": 15,
       "npcs": [{"id": i, "x": 1, "y": 1} for i in range(40)]}
check("npcs capped at 12", len(ma._clean_world(big)["npcs"]) == 12)
t = ma._world_text(snap)
check("renders compact lines", "map 25x15" in t and "cursor at 3,4" in t, t[:100])

print("== room_draft ==")
tmp = fresh_dir()
try:
    r = ma.tool_suggest_map_change(tmp, "alice", "room_draft", "",
                                   room="castle")
    check("bad room kind rejected", "pick one of" in r, r)
    check("nothing saved on rejection",
          ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "ROOM_DRAFT", "",
                                   where="10,12", room="Boss_Arena")
    check("room draft saved (case-insensitive)", "Suggestion saved" in r, r)
    s = ma.suggestion_pending(tmp, "alice")
    check("record carries room+spot",
          s["room"] == "boss_arena" and s["where_xy"] == [10, 12],
          json.dumps(s)[:120])
    check("default label names the room", "boss arena" in s["label"])
    ma.suggestion_set_status(tmp, "alice", "declined")
    r = ma.tool_suggest_map_change(tmp, "alice", "room_draft", "tavern?",
                                   room="dungeon_room")
    s = ma.suggestion_pending(tmp, "alice")
    check("custom label kept", s["label"] == "tavern?")
    check("no spot needed", "where_xy" not in s)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== patrol_draft ==")
tmp = fresh_dir()
try:
    r = ma.tool_suggest_map_change(tmp, "alice", "patrol_draft", "x",
                                   points="1,1")
    check("one stop rejected", "2-8 stops" in r, r)
    r = ma.tool_suggest_map_change(tmp, "alice", "patrol_draft", "x",
                                   points=";".join(f"{i},{i}" for i in range(9)))
    check("nine stops rejected", "2-8 stops" in r, r)
    r = ma.tool_suggest_map_change(tmp, "alice", "patrol_draft", "x",
                                   points="a,b;1,2")
    check("non-int stops rejected", "2-8 stops" in r, r)
    r = ma.tool_suggest_map_change(tmp, "alice", "patrol_draft", "x",
                                   points="1,1;2,2")
    check("missing anchor rejected", "tile id" in r, r)
    r = ma.tool_suggest_map_change(tmp, "alice", "patrol_draft", "",
                                   points="1,1; 2,2 ;3,3",
                                   anchor_tile="42", anchor_xy="1,1")
    check("patrol draft saved", "Suggestion saved" in r, r)
    s = ma.suggestion_pending(tmp, "alice")
    check("record carries route+anchor",
          s["points"] == [[1, 1], [2, 2], [3, 3]] and
          s["tile_id"] == 42 and s["anchor_xy"] == [1, 1],
          json.dumps(s)[:160])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== tool registry invariant ==")
declared = {t["function"]["name"] for t in ma.TOOLS}
check("declared == known", declared == ma._KNOWN_TOOLS,
      f"declared={sorted(declared)} known={sorted(ma._KNOWN_TOOLS)}")
tmp = fresh_dir()
try:
    for name in sorted(ma._KNOWN_TOOLS):
        out = ma.run_tool(tmp, "alice", name, {})
        check(f"run_tool dispatches {name}",
              "don't have a tool" not in out, out[:70])
    desc = next(t["function"]["description"] for t in ma.TOOLS
                if t["function"]["name"] == "suggest_map_change")
    check("all kinds documented for the brain",
          all(k in desc for k in ma._SUGGEST_KINDS), desc[:80])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== handle_chat world plumbing ==")
tmp = fresh_dir()
try:
    res = ma.handle_chat(tmp, "alice", "hello",
                         world={"w": 25, "h": 15,
                                "npcs": [{"id": 7, "x": 2, "y": 2}]})
    check("world kwarg accepted", res.get("ok") is True, str(res)[:80])
    hist = ma.history_load(tmp, "alice")
    leaked = any("LIVE GAME" in h["content"] or "placed characters" in h["content"]
                 for h in hist)
    check("snapshot never lands in saved history", not leaked)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== suggestion line (v5.53.3: she never guesses) ==")
tmp = fresh_dir()
try:
    line = ma._suggestion_line(tmp, "alice")
    check("no file -> none yet", line == "ghost suggestion: none yet.", line)
    p = os.path.join(ma.melody_dir(tmp, "alice"), "suggestion.json")
    with open(p, "w") as f:
        json.dump({"kind": "wall_ring", "label": "Add walls around this floor?",
                   "status": "pending"}, f)
    line = ma._suggestion_line(tmp, "alice")
    check("pending names the ghost", "wall_ring" in line and "Add walls" in line, line)
    check("pending points at the panel", "💡" in line and "Do-it" in line, line)
    check("pending says violet ghost", "violet ghost" in line, line)
    with open(p, "w") as f:
        json.dump({"kind": "wall_ring", "label": "x" * 200, "status": "pending"}, f)
    line = ma._suggestion_line(tmp, "alice")
    check("label capped at 80", len(line.split('"')[1]) <= 80, line[:100])
    # v5.53.6: she remembers what happened to the last one
    import time as _t
    with open(p, "w") as f:
        json.dump({"kind": "wall_ring", "label": "old walls",
                   "status": "accepted", "created": int(_t.time()) - 300}, f)
    line = ma._suggestion_line(tmp, "alice")
    check("accepted names the last one",
          "none pending" in line and "old walls" in line and "accepted" in line, line)
    check("accepted says when", "5 min ago" in line, line)
    check("accepted says don't re-propose", "don't propose it again" in line, line)
    with open(p, "w") as f:
        json.dump({"kind": "room_draft", "label": "old room",
                   "status": "declined", "created": int(_t.time()) - 9000}, f)
    line = ma._suggestion_line(tmp, "alice")
    check("declined reports too",
          "none pending" in line and "declined" in line and "2 h ago" in line, line)
    check("bad username can't break it",
          ma._suggestion_line(tmp, "not a user!!") == "ghost suggestion: none yet.")
    check("_ago just now", ma._ago(_t.time() - 5) == " just now")
    check("_ago days", ma._ago(_t.time() - 90000) == " 1 day ago")
    check("_ago garbage", ma._ago("nope") == "")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
