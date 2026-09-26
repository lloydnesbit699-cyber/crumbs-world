#!/usr/bin/env python3
"""melody_test.py — Phase 1 agent tests. Run: python3 melody_test.py
Covers: username/path safety (Law 18), quota tiers, knowledge lookup,
law lookup, chat turns (knowledge-direct + brain-off + stubbed brain with
tools), history, audit, and cross-vault blindness.
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
    d = tempfile.mkdtemp(prefix="melody-test-")
    return d


print("== username + path safety (Law 18) ==")
check("good username", ma.valid_username("lloyd"))
check("bad: too short", not ma.valid_username("ab"))
check("bad: traversal", not ma.valid_username("../x"))
check("bad: commons id", not ma.valid_username("__commons__"))
check("bad: uppercase", not ma.valid_username("Lloyd"))
tmp = fresh_dir()
d = ma.melody_dir(tmp, "alice")
check("melody_dir under vaults/alice",
      d == os.path.join(tmp, "vaults", "alice", "melody"), d)
try:
    ma.melody_dir(tmp, "../../etc")
    check("melody_dir rejects traversal", False)
except ValueError:
    check("melody_dir rejects traversal", True)
dl = ma.melody_dir(tmp, "local")
check("local session dir", dl == os.path.join(tmp, "melody"), dl)
shutil.rmtree(tmp, ignore_errors=True)

print("== quota tiers (Lloyd's 200/600/1000) ==")
check("free=200", ma.TIER_QUOTAS["free"] == 200)
check("basic=600", ma.TIER_QUOTAS["basic"] == 600)
check("pro=1000", ma.TIER_QUOTAS["pro"] == 1000)
tmp = fresh_dir()
allowed, remaining, quota, tier = ma.quota_check(tmp, "alice", "free")
check("fresh quota allowed", allowed and remaining == 200 and tier == "free")
ma.quota_bump(tmp, "alice", "free")
allowed, remaining, quota, tier = ma.quota_check(tmp, "alice", "free")
check("bump decrements", remaining == 199, f"remaining={remaining}")
# exhaust it
for _ in range(199):
    ma.quota_bump(tmp, "alice", "free")
allowed, remaining, _, _ = ma.quota_check(tmp, "alice", "free")
check("quota exhausts at 200", not allowed and remaining == 0)
# bad tier coerces to free
_, _, _, tier = ma.quota_check(tmp, "alice", "platinum")
check("bad tier -> free", tier == "free")
shutil.rmtree(tmp, ignore_errors=True)

print("== knowledge base ==")
hits = ma.knowledge_search("how do I paint tiles on the map")
check("painting query hits", bool(hits) and "paint" in hits[0][0].lower(),
      str([h[0] for h in hits]))
hits = ma.knowledge_search("repair law thumbnails")
check("law-ish query hits guide", bool(hits))
check("empty query -> []", ma.knowledge_search("!!!") == [])
check("kb has melody section",
      any("melody" in t.lower() for t, _ in ma._load_kb()))

print("== law lookup ==")
r18 = ma.tool_law_lookup("18")
check("law 18 by number", "only its player" in r18.lower(), r18[:80])
rc = ma.tool_law_lookup("commons shared world")
check("law 18 by topic", "18" in rc, rc[:80])
check("no such law", "no repair law 99" in ma.tool_law_lookup("99").lower())

print("== chat: knowledge-direct (zero brain, zero quota) ==")
tmp = fresh_dir()
res = ma.handle_chat(tmp, "alice", "how do I paint tiles?")
check("kb-direct ok", res.get("ok") and res.get("source") == "knowledge")
_, remaining, _, _ = ma.quota_check(tmp, "alice", "free")
check("kb-direct burns no quota", remaining == 200, f"remaining={remaining}")
hist = ma.history_load(tmp, "alice")
check("history saved", len(hist) == 2 and hist[0]["role"] == "user")

print("== chat: brain off, unknown question (honest, free) ==")
res = ma.handle_chat(tmp, "alice", "what is the airspeed velocity of an unladen swallow?")
check("brain-off ok", res.get("ok") and res.get("source") == "knowledge",
      str(res)[:100])
check("brain-off honest",
      "isn't connected" in res.get("reply", ""), res.get("reply", "")[:80])

print("== chat: stubbed brain with tool call ==")
calls = []


def fake_brain(messages, tools=None):
    calls.append(messages)
    last = messages[-1]
    if last.get("role") == "tool":
        return ("Your maps look great — 2 saved, all valid!", [], "fake")
    # first round: call map_validate
    return ("", [{"id": "call_1",
                 "function": {"name": "map_validate",
                              "arguments": "{}"}}], "fake")


ma.brain_chat = fake_brain
tmp2 = fresh_dir()
os.makedirs(os.path.join(tmp2, "vaults", "bob"), exist_ok=True)
with open(os.path.join(tmp2, "vaults", "bob", "my-map.json"), "w") as f:
    json.dump({"tiles": {"0,0": 5}}, f)
res = ma.handle_chat(tmp2, "bob", "hey mel do a deep scan thing on my stuff")
check("tool turn ok", res.get("ok") and res.get("source") == "brain")
check("tool ran", res.get("tools_used") == ["map_validate"],
      str(res.get("tools_used")))
check("tool result in reply", "valid" in res.get("reply", "").lower(),
      res.get("reply", "")[:100])
_, remaining, _, _ = ma.quota_check(tmp2, "bob", "free")
check("brain turn burns one quota", remaining == 199, f"remaining={remaining}")
# audit line exists
audit_path = os.path.join(tmp2, "vaults", "bob", "melody", "audit.jsonl")
with open(audit_path) as f:
    lines = f.readlines()
check("audit recorded", any("map_validate" in l for l in lines))

print("== Law 18: cross-vault blindness ==")
tmp3 = fresh_dir()
os.makedirs(os.path.join(tmp3, "vaults", "alice"), exist_ok=True)
os.makedirs(os.path.join(tmp3, "vaults", "mallory"), exist_ok=True)
with open(os.path.join(tmp3, "vaults", "mallory", "secret-map.json"), "w") as f:
    json.dump({"tiles": {}}, f)
stats = ma.tool_vault_stats(tmp3, "alice")
check("alice stats mention no mallory", "mallory" not in stats, stats)
check("alice stats mention no secret-map", "secret-map" not in stats, stats)
mv = ma.tool_map_validate(tmp3, "alice")
check("alice validate sees no mallory maps", "mallory" not in mv and "secret" not in mv, mv)
for d in (tmp, tmp2, tmp3):
    shutil.rmtree(d, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
