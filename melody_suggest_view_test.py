#!/usr/bin/env python3
"""melody_suggest_view_test.py — v5.53.1 suggestion-view contract tests.
Run: python3 melody_suggest_view_test.py

Covers _melody_suggestion_view (crumbs_hud.py):
- the HUD gates the ghost on status == "pending" and tracks freshness by id:
  the view must carry both (missing since v5.47.0 = the phantom-approval bug)
- wall_ring materializes cells against the live world
- room_draft / patrol_draft pass through (the HUD renders them itself)
- unmaterializable kinds return a card-able dict, never None (no phantoms)
- no pending suggestion -> None
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MELODY_BRAIN"] = "off"  # default: no network in tests

import melody_agent as ma
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


def fresh_case(kind, user="bob", label="Test?", **kw):
    tmp = tempfile.mkdtemp(prefix="suggest-view-test-")
    r = ma.tool_suggest_map_change(tmp, user, kind, label, **kw)
    assert "Suggestion saved" in r, r
    h.SCRIPT_DIR = tmp
    return tmp


ORIG_SCRIPT_DIR = h.SCRIPT_DIR
try:
    print("== nothing pending -> None ==")
    tmp = tempfile.mkdtemp(prefix="suggest-view-test-")
    h.SCRIPT_DIR = tmp
    try:
        check("no pending -> None", h._melody_suggestion_view("nobody") is None)
    finally:
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)

    print("== wall_ring carries status + id + cells ==")
    tmp = fresh_case("wall_ring", label="Ring the floor?")
    try:
        v = h._melody_suggestion_view("bob")
        check("view not None", v is not None)
        check("status pending", v.get("status") == "pending", v.get("status"))
        check("id present", bool(v.get("id")), v.get("id"))
        check("kind kept", v.get("kind") == "wall_ring")
        check("cells materialized",
              isinstance(v.get("cells"), list) and len(v["cells"]) > 0,
              len(v.get("cells") or []))
        check("not unmaterializable", not v.get("unmaterializable"))
    finally:
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)

    print("== room_draft passes through ==")
    tmp = fresh_case("room_draft", label="Draft a room?",
                     room="dungeon_room", where="12,7")
    try:
        v = h._melody_suggestion_view("bob")
        check("status pending", v.get("status") == "pending")
        check("id present", bool(v.get("id")))
        check("room forwarded", v.get("room") == "dungeon_room", v.get("room"))
        check("where_xy forwarded", v.get("where_xy") == [12, 7],
              v.get("where_xy"))
    finally:
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)

    print("== patrol_draft passes through ==")
    tmp = fresh_case("patrol_draft", label="Walk this?",
                     points="1,1;5,5;9,2", anchor_tile="3", anchor_xy="1,1")
    try:
        v = h._melody_suggestion_view("bob")
        check("status pending", v.get("status") == "pending")
        check("points forwarded", v.get("points") == [[1, 1], [5, 5], [9, 2]],
              v.get("points"))
        check("anchor_xy forwarded", v.get("anchor_xy") == [1, 1],
              v.get("anchor_xy"))
    finally:
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)

    print("== unmaterializable -> card dict, not None ==")
    tmp = fresh_case("wall_ring", label="Ring it?")
    real_ring = h._suggest_wall_ring
    h._suggest_wall_ring = lambda where=None: None  # nothing sensible
    try:
        v = h._melody_suggestion_view("bob")
        check("not None", v is not None)
        check("status still pending", v.get("status") == "pending")
        check("flagged unmaterializable", v.get("unmaterializable") is True)
        check("reason given", bool(v.get("reason")), v.get("reason"))
    finally:
        h._suggest_wall_ring = real_ring
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)

    print("== queue materializes oldest-first (v5.54) ==")
    tmp = tempfile.mkdtemp(prefix="suggest-view-test-")
    h.SCRIPT_DIR = tmp
    try:
        ma.tool_suggest_map_change(tmp, "bob", "wall_ring", "First?")
        ma.tool_suggest_map_change(tmp, "bob", "wall_ring", "Second?")
        views = h._melody_suggestion_views("bob")
        check("two views", len(views) == 2, len(views))
        check("oldest first", [v["label"] for v in views] == ["First?", "Second?"])
        check("unique ids", views[0]["id"] != views[1]["id"],
              (views[0]["id"], views[1]["id"]))
        check("head compat", h._melody_suggestion_view("bob")["label"] == "First?")
        ma.suggestion_set_status(tmp, "bob", "declined")
        views = h._melody_suggestion_views("bob")
        check("answered drops out", len(views) == 1 and views[0]["label"] == "Second?",
              [v["label"] for v in views])
    finally:
        h.SCRIPT_DIR = ORIG_SCRIPT_DIR
        shutil.rmtree(tmp, ignore_errors=True)
finally:
    h.SCRIPT_DIR = ORIG_SCRIPT_DIR

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
