#!/usr/bin/env python3
"""stage8_roster_test.py — Stage 8 (Ball Room item 22): the starter roster,
server side. The creation-time hero pick is stamped into the new world's
rules as hero_tiles by /api/maps/create, sanitized by the same
_valid_hero_list the /api/rules endpoint uses. These tests prove every
roster tid (parsed out of the client's STARTER_ROSTER table) exists in
the server's real tile registry and survives the sanitizer, that junk
picks sanitize to nothing (creation proceeds heroless, as before), and
that the untouched default (DEFAULT_RULES) still starts heroless.
Pure functions + source reads only — no server, no network, no user data.
Run: python3 stage8_roster_test.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
sys.path.insert(0, HERE)

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


html = open(os.path.join(HERE, "editor.html"), encoding="utf-8").read()
hud_src = open(os.path.join(HERE, "crumbs_hud.py"), encoding="utf-8").read()

# ---- parse the client's roster table -------------------------------------
m = re.search(r"const STARTER_ROSTER = \[(.*?)\];", html, re.S)
check("STARTER_ROSTER table found in editor.html", m is not None)
rows = []
if m:
    for row in re.findall(r"\{([^{}]*)\}", m.group(1)):
        tid = re.search(r"tid:\s*(\d+)", row)
        starter = re.search(r"starter:\s*(true|false)", row)
        name = re.search(r'name:\s*"([^"]+)"', row)
        if tid and starter and name:
            rows.append({"tid": int(tid.group(1)),
                         "starter": starter.group(1) == "true",
                         "name": name.group(1)})
offered = [r for r in rows if r["starter"]]
reserved = [r for r in rows if not r["starter"]]

print("== roster tids against the server's real registry ==")
check("roster parsed: ~10 offered + reserved rows",
      len(offered) >= 9 and len(reserved) >= 1,
      f"offered={len(offered)} reserved={len(reserved)}")
for r in rows:
    t = h.assets.tiles.get(r["tid"])
    check(f"{r['name']} (tid {r['tid']}) exists in assets.tiles", t is not None)
    if t is not None:
        check(f"{r['name']} is a character tile named for its kind",
              "starter" in str(t.get("name", "")).lower()
              and r["name"].split()[0].lower() in str(t.get("name", "")).lower(),
              f"registry name={t.get('name')!r}")
    check(f"{r['name']} survives the hero sanitizer",
          h._valid_hero_list([r["tid"]]) == [r["tid"]])

print("== the pick contract: junk sanitizes to heroless, never an error ==")
check("unknown tid dropped", h._valid_hero_list([999999]) == [])
check("string tid dropped", h._valid_hero_list(["70064"]) == [])
check("missing pick (None) dropped", h._valid_hero_list([None]) == [])
check("duplicates collapse, order kept",
      h._valid_hero_list([70064, 70064, 70074]) == [70064, 70074])

print("== defaults untouched: a world with no pick starts heroless ==")
check("DEFAULT_RULES still ships hero_tiles empty",
      h.DEFAULT_RULES.get("hero_tiles") == [])

print("== the create handler stamps the designation (source) ==")
c0 = hud_src.index('if path == "/api/maps/create":')
c1 = hud_src.index('if path == "/api/maps/meta":', c0)
create_src = hud_src[c0:c1]
check("create sanitizes via _valid_hero_list([body.get(\"hero_tile\")])",
      '_valid_hero_list([body.get("hero_tile")])' in create_src)
check("both paths stamp hero_tiles",
      create_src.count('["hero_tiles"] = [hero_tile]') == 2)
check("both paths stamp the legacy hero_tile mirror",
      create_src.count('["hero_tile"] = hero_tile') == 2)
check("both responses report hero_tile",
      create_src.count('"hero_tile": hero_tile') == 2)
check("stamps are gated on a valid pick (skip path writes nothing)",
      create_src.count("if hero_tile is not None:") == 2)

print(f"\nstage8_roster_test: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
