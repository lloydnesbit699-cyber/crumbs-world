#!/usr/bin/env python3
"""melody_suggest_test.py — v5.54 Melody suggestion QUEUE tests. Run: python3 melody_suggest_test.py
Covers: the suggest_map_change tool lifecycle (queue -> accept head -> next
surfaces), the 5-deep queue cap, decline/accept by id, idempotent clears,
kind validation, where parsing, vault isolation (Law 18 — the Agent Sees Only
Its Player), migration from the old single-suggestion file, run_tool dispatch,
and the never-paints-silently contract (the tool writes a proposal, never tiles).
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MELODY_BRAIN"] = "off"  # default: no network in tests

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
    return tempfile.mkdtemp(prefix="melody-suggest-test-")


print("== suggestion queue lifecycle (v5.54) ==")
tmp = fresh_dir()
try:
    check("nothing pending at first", ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "Walls around the floor?")
    check("wall_ring accepted", "Suggestion saved" in r, r)
    sug = ma.suggestion_pending(tmp, "alice")
    check("pending now", sug is not None and sug["kind"] == "wall_ring")
    check("label kept", sug["label"] == "Walls around the floor?", sug.get("label"))
    check("status pending", sug["status"] == "pending")
    check("unique id assigned", bool(sug.get("id")), sug.get("id"))
    r2 = ma.tool_suggest_map_change(tmp, "alice", "connect_patrols", "Join them?")
    check("second suggestion QUEUES", "Suggestion saved" in r2 and "#2 in the queue" in r2, r2)
    check("head is still the first one",
          ma.suggestion_pending(tmp, "alice")["kind"] == "wall_ring")
    check("two pending in order",
          [s["kind"] for s in ma.suggestions_pending_all(tmp, "alice")] ==
          ["wall_ring", "connect_patrols"])
    ids = [s["id"] for s in ma.suggestions_pending_all(tmp, "alice")]
    check("ids unique", len(set(ids)) == 2, ids)
    check("accept marks the head",
          ma.suggestion_set_status(tmp, "alice", "accepted") is True)
    check("next surfaces as head",
          ma.suggestion_pending(tmp, "alice")["kind"] == "connect_patrols")
    check("decline by id",
          ma.suggestion_set_status(tmp, "alice", "declined", ids[1]) is True)
    check("nothing pending after decline", ma.suggestion_pending(tmp, "alice") is None)
    check("bad status rejected", ma.suggestion_set_status(tmp, "alice", "maybe") is False)
    check("idempotent: unknown id still True",
          ma.suggestion_set_status(tmp, "alice", "declined", "nope") is True)
    check("idempotent: empty queue still True",
          ma.suggestion_set_status(tmp, "alice", "accepted") is True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== queue cap ==")
tmp = fresh_dir()
try:
    for i in range(5):
        r = ma.tool_suggest_map_change(tmp, "alice", "wall_ring", f"idea {i}")
        check(f"slot {i + 1} queues", "Suggestion saved" in r, r)
    r = ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "one too many")
    check("6th refused", "queue is full" in r, r)
    check("still 5 pending",
          len(ma.suggestions_pending_all(tmp, "alice")) == 5)
    ma.suggestion_set_status(tmp, "alice", "declined")  # head answered
    r = ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "room again")
    check("room after one answered", "Suggestion saved" in r and "#5 in the queue" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== migration from the old single file ==")
tmp = fresh_dir()
try:
    d = ma.melody_dir(tmp, "alice")
    os.makedirs(d, exist_ok=True)
    old = os.path.join(d, "suggestion.json")
    with open(old, "w") as f:
        json.dump({"kind": "wall_ring", "label": "old walls",
                   "status": "pending", "created": 111}, f)
    check("old file migrates to head",
          ma.suggestion_pending(tmp, "alice")["label"] == "old walls")
    check("new queue file written",
          os.path.exists(os.path.join(d, "suggestions.json")))
    check("old file removed", not os.path.exists(old))
    r = ma.tool_suggest_map_change(tmp, "alice", "connect_patrols", "new one")
    check("queues behind the migrant", "#2 in the queue" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== answered history is trimmed ==")
tmp = fresh_dir()
try:
    items = [{"kind": "wall_ring", "label": f"old {i}", "status": "declined",
              "created": i, "id": f"id-{i}"} for i in range(30)]
    check("save ok", ma._suggestions_save(tmp, "alice", items) is True)
    loaded = ma._suggestions_load(tmp, "alice")
    check("history trimmed to 20", len(loaded) == 20, len(loaded))
    check("newest kept", loaded[-1]["label"] == "old 29", loaded[-1]["label"])
    # pending entries are never trimmed
    items = ([{"kind": "wall_ring", "label": "keep me", "status": "pending",
               "created": 1, "id": "p1"}] +
             [{"kind": "wall_ring", "label": f"old {i}", "status": "declined",
               "created": i, "id": f"id-{i}"} for i in range(30)])
    ma._suggestions_save(tmp, "alice", items)
    loaded = ma._suggestions_load(tmp, "alice")
    check("pending survives the trim",
          loaded[0]["label"] == "keep me" and len(loaded) == 21, len(loaded))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== kind validation ==")
tmp = fresh_dir()
try:
    r = ma.tool_suggest_map_change(tmp, "alice", "paint_house", "x")
    check("unknown kind refused", "I can only suggest" in r, r)
    check("refusal names the kinds",
          "wall_ring" in r and "connect_patrols" in r, r)
    check("nothing stored on refusal", ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "WALL_RING", "x")
    check("kind case-insensitive", "Suggestion saved" in r, r)
    ma.suggestion_set_status(tmp, "alice", "declined")
    r = ma.tool_suggest_map_change(tmp, "alice", "connect_patrols", "")
    check("empty label gets a default", "Suggestion saved" in r, r)
    sug = ma.suggestion_pending(tmp, "alice")
    check("default label non-empty", bool(sug["label"]), sug)
    ma.suggestion_set_status(tmp, "alice", "declined")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== where parsing ==")
check("'12, 34' parses", ma._parse_where("12, 34") == [12, 34])
check("'0,0' parses", ma._parse_where("0,0") == [0, 0])
check("garbage -> None", ma._parse_where("near the door") is None)
check("empty -> None", ma._parse_where("") is None)
check("None -> None", ma._parse_where(None) is None)
check("three numbers -> None", ma._parse_where("1,2,3") is None)
tmp = fresh_dir()
try:
    ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "x", where="12, 34")
    sug = ma.suggestion_pending(tmp, "alice")
    check("where_xy recorded", sug.get("where_xy") == [12, 34], sug)
    ma.suggestion_set_status(tmp, "alice", "declined")
    ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "x", where="garbage")
    sug = ma.suggestion_pending(tmp, "alice")
    check("bad where not recorded", "where_xy" not in sug, sug)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== vault isolation (Law 18) ==")
tmp = fresh_dir()
try:
    ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "alice's idea")
    check("bob sees nothing of alice's",
          ma.suggestion_pending(tmp, "bob") is None)
    check("bob can still suggest", "Suggestion saved" in
          ma.tool_suggest_map_change(tmp, "bob", "wall_ring", "bob's idea"))
    check("alice's untouched",
          ma.suggestion_pending(tmp, "alice")["label"] == "alice's idea")
    check("bob declining doesn't touch alice",
          ma.suggestion_set_status(tmp, "bob", "declined") is True and
          ma.suggestion_pending(tmp, "alice") is not None)
    r = ma.tool_suggest_map_change(tmp, "../../etc", "wall_ring", "x")
    check("traversal username refused", "Couldn't save" in r, r)
    check("nothing escaped the vault dir",
          not os.path.exists(os.path.join(tmp, "etc")) and
          ma.suggestion_pending(tmp, "alice") is not None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== run_tool dispatch ==")
check("suggest_map_change is a known tool", "suggest_map_change" in ma._KNOWN_TOOLS)
tmp = fresh_dir()
try:
    r = ma.run_tool(tmp, "alice", "suggest_map_change",
                    {"kind": "wall_ring", "label": "dispatch works"})
    check("dispatch reaches the tool", "Suggestion saved" in r, r)
    r = ma.run_tool(tmp, "alice", "paint_tiles", {"x": "1"})
    check("unknown tool declined", "don't have a tool" in r, r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== never paints silently ==")
tmp = fresh_dir()
try:
    before = set()
    for root, dirs, files in os.walk(tmp):
        for f in files:
            before.add(os.path.join(root, f))
    ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "x")
    after = set()
    for root, dirs, files in os.walk(tmp):
        for f in files:
            after.add(os.path.join(root, f))
    new_files = after - before
    allowed = {os.path.join("melody", "suggestions.json"),
               os.path.join("melody", "audit.jsonl")}
    check("only the proposal + audit files are written",
          len(new_files) == 2 and all(
              any(f.endswith(a) for a in allowed) for f in new_files),
          new_files)
    content = open(list(new_files)[0], encoding="utf-8").read()
    check("no tile/cell writes in the proposal",
          "cells" not in content and "tiles" not in content, content[:120])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("== animation_preset kind (v5.47.1) ==")
tmp = fresh_dir()
try:
    r = ma.tool_suggest_map_change(tmp, "alice", "animation_preset",
                                   "Make the torch flicker?",
                                   where="5, 6", preset="pulse")
    check("animation_preset accepted", "Suggestion saved" in r, r)
    sug = ma.suggestion_pending(tmp, "alice")
    check("preset recorded", sug.get("preset") == "pulse", sug)
    check("where recorded", sug.get("where_xy") == [5, 6], sug)
    ma.suggestion_set_status(tmp, "alice", "declined")
    r = ma.tool_suggest_map_change(tmp, "alice", "animation_preset", "x",
                                   preset="explode")
    check("bad preset refused", "pick one of" in r, r)
    check("nothing stored on bad preset",
          ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "animation_preset", "x")
    check("missing preset refused", "pick one of" in r, r)
    check("nothing stored on missing preset",
          ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "animation_preset", "",
                                   preset="float")
    check("empty label gets a default", "Suggestion saved" in r, r)
    check("default label non-empty",
          bool(ma.suggestion_pending(tmp, "alice")["label"]))
    ma.suggestion_set_status(tmp, "alice", "declined")
    r = ma.tool_suggest_map_change(tmp, "alice", "ANIMATION_PRESET", "x",
                                   preset="FLOAT")
    check("kind+preset case-insensitive", "Suggestion saved" in r, r)
    check("preset normalized",
          ma.suggestion_pending(tmp, "alice")["preset"] == "float")
    ma.suggestion_set_status(tmp, "alice", "declined")
    ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "x", preset="pulse")
    check("preset not stored for wall_ring",
          "preset" not in ma.suggestion_pending(tmp, "alice"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
