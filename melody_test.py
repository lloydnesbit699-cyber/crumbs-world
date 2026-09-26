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

print("== demo mode (pre-profile taste) ==")
res = ma.demo_answer("how do I paint tiles on the map?")
check("demo kb hit", res.get("ok") and res.get("source") == "knowledge-demo",
      str(res)[:80])
res = ma.demo_answer("tell me about quantum flibbertigibbet economics")
check("demo graceful beyond-scope",
      res.get("ok") and "beyond the demo" in res.get("reply", ""))
res = ma.demo_answer("   ")
check("demo empty rejected", not res.get("ok"))
# demo burns no quota and writes no history
tmp4 = fresh_dir()
ma.demo_answer("how do I undo?")
_, remaining, _, _ = ma.quota_check(tmp4, "alice", "free")
check("demo burns no quota", remaining == 200)
check("demo writes no history",
      ma.history_load(tmp4, "alice") == [])
shutil.rmtree(tmp4, ignore_errors=True)

print("== brain order: Qwen on Groq first (Lloyd's call) ==")
old_env = {k: os.environ.get(k) for k in
           ("MELODY_BRAIN", "GROQ_API_KEY", "GEMINI_API_KEY", "GROQ_MODEL")}
os.environ["MELODY_BRAIN"] = "groq"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_MODEL", None)
backs = ma.brain_backends()
check("groq+qwen primary",
      backs and backs[0][0] == "groq+qwen"
      and backs[0][1] == "https://api.groq.com/openai/v1/chat/completions"
      and backs[0][3] == "qwen/qwen3.6-27b",
      str([(b[0], b[3]) for b in backs]))
check("no llama default anywhere",
      all("llama" not in b[3] for b in backs))
st = ma.brain_status()
check("default mode groq", st["mode"] == "groq" and st["primary"] == "groq+qwen")
os.environ["MELODY_BRAIN"] = "gemini"
os.environ["GEMINI_API_KEY"] = "test-key-2"
backs = ma.brain_backends()
check("MELODY_BRAIN=gemini flips order",
      backs[0][0] == "gemini" and backs[1][0] == "groq+qwen")
for k, v in old_env.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v

print("== voice input: /api/melody/stt (agent half) ==")
# whisper runs on the chat brain's GROQ_API_KEY — set a dummy so backends
# exist; the "no key" test below pops it
_saved_groq_key = os.environ.get("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = "test-speech-key"
# stub the HTTP call — never hits the network in tests
stt_posted = {}


def fake_stt_post(url, body, content_type, key, timeout=60):
    stt_posted["url"] = url
    stt_posted["key"] = key
    stt_posted["content_type"] = content_type
    return {"text": "  hello melody  "}


ma._stt_post = fake_stt_post
tmp5 = fresh_dir()
res = ma.handle_stt(tmp5, "alice", b"x" * 5000, "voice.webm", "free")
check("stt ok, text trimmed", res.get("ok") and res.get("text") == "hello melody",
      str(res))
check("stt hits whisper endpoint",
      stt_posted.get("url") == "https://api.groq.com/openai/v1/audio/transcriptions",
      str(stt_posted.get("url")))
check("stt posts multipart",
      "multipart/form-data" in stt_posted.get("content_type", ""))
_, remaining, _, _ = ma.quota_check(tmp5, "alice", "free")
check("stt burns one brain-call quota", remaining == 199,
      f"remaining={remaining}")
# Law 18: quota + audit live under vaults/<user>/melody only
qpath = os.path.join(tmp5, "vaults", "alice", "melody", "quota.json")
check("stt quota under vaults/alice", os.path.isfile(qpath), qpath)
with open(os.path.join(tmp5, "vaults", "alice", "melody", "audit.jsonl")) as f:
    alines = f.read()
check("stt audit recorded", '"action": "stt"' in alines)
check("stt audit never keeps the words", "hello melody" not in alines)
# audio never touches disk anywhere
leftovers = []
for r, ds, fs in os.walk(tmp5):
    leftovers += [f for f in fs
                  if f.rsplit(".", 1)[-1].lower() in
                  ("webm", "mp4", "m4a", "wav", "ogg")]
check("audio never touches disk", not leftovers, str(leftovers))

# demo / no session -> login required (zero model calls pre-login)
res = ma.handle_stt(tmp5, None, b"x" * 5000)
check("stt unauthenticated -> login required",
      not res.get("ok") and res.get("error") == "login required", str(res))
res = ma.handle_stt(tmp5, "", b"x" * 5000)
check("stt empty username -> login required",
      not res.get("ok") and res.get("error") == "login required")
res = ma.handle_stt(tmp5, "../../etc", b"x" * 5000)
check("stt traversal username rejected", not res.get("ok"), str(res))
res = ma.handle_stt(tmp5, "__commons__", b"x" * 5000)
check("stt commons id rejected", not res.get("ok"))

# bad audio handling
res = ma.handle_stt(tmp5, "alice", b"")
check("stt empty audio rejected",
      not res.get("ok") and "empty" in res.get("error", "").lower(),
      str(res))
res = ma.handle_stt(tmp5, "alice", b"x" * (ma._STT_MAX_BYTES + 1))
check("stt oversize rejected",
      not res.get("ok") and "long" in res.get("error", "").lower(),
      str(res))
res = ma.transcribe_audio(b"")
check("transcribe_audio empty -> clear error", not res.get("ok"))

# no key configured -> clear, honest error (no hardcoding, env only)
saved_key = os.environ.pop("GROQ_API_KEY", None)
res = ma.transcribe_audio(b"x" * 5000)
check("stt no key -> clear error",
      not res.get("ok") and "key" in res.get("error", "").lower(),
      res.get("error"))
check("stt no key -> no backends", ma.stt_backends() == [])
if saved_key is not None:
    os.environ["GROQ_API_KEY"] = saved_key

# backend failure -> clear error, no quota burned
def fake_stt_fail(url, body, content_type, key, timeout=60):
    raise RuntimeError("boom")


ma._stt_post = fake_stt_fail
_, before, _, _ = ma.quota_check(tmp5, "alice", "free")
res = ma.handle_stt(tmp5, "alice", b"x" * 5000, "voice.mp4")
check("stt backend failure -> clear error", not res.get("ok"), str(res))
_, after, _, _ = ma.quota_check(tmp5, "alice", "free")
check("stt failure burns no quota", before == after,
      f"before={before} after={after}")

# cross-vault: bob's stt writes only under vaults/bob (Law 18)
ma._stt_post = fake_stt_post
res = ma.handle_stt(tmp5, "bob", b"x" * 5000)
check("stt for bob ok", res.get("ok"), str(res))
check("stt bob quota under vaults/bob",
      os.path.isfile(os.path.join(tmp5, "vaults", "bob", "melody",
                                   "quota.json")))
check("stt bob touched no alice paths",
      not os.path.exists(os.path.join(tmp5, "vaults", "bob", "melody",
                                       "alice")))
shutil.rmtree(tmp5, ignore_errors=True)
# voice tests are done — restore whatever GROQ_API_KEY the env had before
if _saved_groq_key is None:
    os.environ.pop("GROQ_API_KEY", None)
else:
    os.environ["GROQ_API_KEY"] = _saved_groq_key

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
