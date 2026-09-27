#!/usr/bin/env python3
"""melody_suggest_test.py — v5.47 Melody suggestion tests. Run: python3 melody_suggest_test.py
Covers: the suggest_map_change tool lifecycle (pending -> accepted/declined),
the one-pending-suggestion rule, kind validation, where parsing, vault
isolation (Law 18 — the Agent Sees Only Its Player), run_tool dispatch, and
the never-paints-silently contract (the tool writes a proposal, never tiles).
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


print("== suggestion lifecycle ==")
tmp = fresh_dir()
try:
    check("nothing pending at first", ma.suggestion_pending(tmp, "alice") is None)
    r = ma.tool_suggest_map_change(tmp, "alice", "wall_ring", "Walls around the floor?")
    check("wall_ring accepted", "Suggestion saved" in r, r)
    sug = ma.suggestion_pending(tmp, "alice")
    check("pending now", sug is not None and sug["kind"] == "wall_ring")
    check("label kept", sug["label"] == "Walls around the floor?", sug.get("label"))
    check("status pending", sug["status"] == "pending")
    r2 = ma.tool_suggest_map_change(tmp, "alice", "connect_patrols", "Join them?")
    check("second suggestion refused while one pends", "already a suggestion" in r2, r2)
    check("still the first one", ma.suggestion_pending(tmp, "alice")["kind"] == "wall_ring")
    check("accept clears", ma.suggestion_set_status(tmp, "alice", "accepted") is True)
    check("nothing pending after accept", ma.suggestion_pending(tmp, "alice") is None)
    r3 = ma.tool_suggest_map_change(tmp, "alice", "connect_patrols", "Join them?")
    check("new suggestion after accept", "Suggestion saved" in r3, r3)
    check("decline clears", ma.suggestion_set_status(tmp, "alice", "declined") is True)
    check("nothing pending after decline", ma.suggestion_pending(tmp, "alice") is None)
    check("bad status rejected", ma.suggestion_set_status(tmp, "alice", "maybe") is False)
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
    allowed = {os.path.join("melody", "suggestion.json"),
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
