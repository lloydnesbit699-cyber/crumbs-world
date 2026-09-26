# melody_agent.py — Melody's Crumbs-side agent (Phase 1: voice + knowledge + diagnose).
#
# A separate subsystem from the game, talking to it through a narrow door:
# the server authenticates the player, then hands the agent (username, message)
# and nothing else. The agent never touches game globals, never activates a
# vault, never holds the vault lock. Every path it reads is built from the
# authenticated username alone.
#
# Repair Law 18 — "The Agent Sees Only Its Player": the agent may read the
# requesting player's private vault and the shared Commons (which every player
# can already see). It must never read, carry, or reveal another player's
# private vault. Paths are constructed, never taken from user input.
#
# Brain backends (OpenAI-compatible chat completions):
#   MELODY_BRAIN=groq    (default)  GROQ_API_KEY    -> Qwen on Groq, free tier
#   MELODY_BRAIN=gemini             GEMINI_API_KEY  -> Google AI Studio, free tier
#   MELODY_BRAIN=ollama             MELODY_BRAIN_BASE=http://host:11434/v1
#                                   -> homecoming: Lloyd's own weights, no game changes
#   MELODY_BRAIN=off                -> knowledge-base only, zero cost, zero network
# The first configured backend wins; if the primary errors, the fallback is
# tried once. No key anywhere -> honest "brain not configured" answers.

import json
import os
import re
import time
import urllib.request
import urllib.error

_USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,24}$")
_LOCAL_USER = "local"          # single-player session id in local (login-free) mode
_COMMONS_VAULT = "__commons__"

# Lloyd's tiers (2026-09-26): free 200, basic 600, pro 1000 brain calls/day.
TIER_QUOTAS = {"free": 200, "basic": 600, "pro": 1000}
DEFAULT_TIER = "free"

_BRAIN_TIMEOUT = 30            # seconds; a slow brain must never hang the game
_MAX_TOOL_ROUNDS = 3
_HISTORY_KEEP = 12             # exchanges kept in live context
_AUDIT_CAP = 5000              # audit lines kept per user


def _env(name, default=""):
    return os.environ.get(name, default)


# -- paths --------------------------------------------------------------------
# All per-user state lives under one directory derived from the validated
# username. In public mode that's vaults/<username>/melody/; in local mode
# <script_dir>/melody/ for the single-player "local" session.

def valid_username(name):
    return bool(_USERNAME_RE.match(name or "")) and name != _COMMONS_VAULT


def melody_dir(script_dir, username):
    """-> this player's Melody home. Raises ValueError on a bad username."""
    if not valid_username(username) and username != _LOCAL_USER:
        raise ValueError("bad username")
    if username == _LOCAL_USER:
        base = script_dir
    else:
        base = os.path.join(script_dir, "vaults", username)
    d = os.path.join(base, "melody")
    os.makedirs(d, exist_ok=True)
    return d


def _commons_dir(script_dir):
    return os.path.join(script_dir, "vaults", _COMMONS_VAULT)


# -- quota --------------------------------------------------------------------

def _quota_path(script_dir, username):
    return os.path.join(melody_dir(script_dir, username), "quota.json")


def quota_check(script_dir, username, tier=DEFAULT_TIER):
    """-> (allowed, remaining, quota, tier). Counts brain calls per day."""
    tier = tier if tier in TIER_QUOTAS else DEFAULT_TIER
    quota = TIER_QUOTAS[tier]
    today = time.strftime("%Y-%m-%d")
    used = 0
    try:
        with open(_quota_path(script_dir, username)) as f:
            rec = json.load(f)
        if isinstance(rec, dict) and rec.get("date") == today:
            used = int(rec.get("used", 0))
    except (OSError, ValueError):
        used = 0
    remaining = max(0, quota - used)
    return used < quota, remaining, quota, tier


def quota_bump(script_dir, username, tier=DEFAULT_TIER):
    today = time.strftime("%Y-%m-%d")
    path = _quota_path(script_dir, username)
    try:
        with open(path) as f:
            rec = json.load(f)
    except (OSError, ValueError):
        rec = {}
    if not isinstance(rec, dict) or rec.get("date") != today:
        rec = {"date": today, "used": 0}
    rec["used"] = int(rec.get("used", 0)) + 1
    try:
        with open(path, "w") as f:
            json.dump(rec, f)
    except OSError:
        pass


# -- history ------------------------------------------------------------------

def _history_path(script_dir, username):
    return os.path.join(melody_dir(script_dir, username), "history.jsonl")


def history_append(script_dir, username, role, content):
    line = json.dumps({"t": int(time.time()), "role": role,
                       "content": content[:4000]})
    try:
        with open(_history_path(script_dir, username), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def history_load(script_dir, username, keep=_HISTORY_KEEP):
    items = []
    try:
        with open(_history_path(script_dir, username)) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("role") in ("user", "assistant") and rec.get("content"):
                    items.append(rec)
    except OSError:
        pass
    return items[-(keep * 2):]


def history_clear(script_dir, username):
    try:
        os.remove(_history_path(script_dir, username))
    except OSError:
        pass


# -- audit --------------------------------------------------------------------
# Every agent turn gets one accountability line: who, what, which tools ran,
# whether the brain was called. Lloyd can read everything she did.

def _audit_path(script_dir, username):
    return os.path.join(melody_dir(script_dir, username), "audit.jsonl")


def audit(script_dir, username, action, detail=""):
    line = json.dumps({"t": int(time.time()), "user": username,
                       "action": action, "detail": str(detail)[:500]})
    path = _audit_path(script_dir, username)
    try:
        with open(path, "a") as f:
            f.write(line + "\n")
        # cap: keep the newest _AUDIT_CAP lines
        with open(path) as f:
            lines = f.readlines()
        if len(lines) > _AUDIT_CAP:
            with open(path, "w") as f:
                f.writelines(lines[-_AUDIT_CAP:])
    except OSError:
        pass


# -- knowledge base -----------------------------------------------------------
# MELODY_KNOWLEDGE.md ships with the app. Questions it answers confidently
# never touch the brain: zero cost, zero latency, zero quota.

_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "MELODY_KNOWLEDGE.md")
_kb_sections = None


def _load_kb():
    global _kb_sections
    if _kb_sections is not None:
        return _kb_sections
    _kb_sections = []
    try:
        with open(_KB_PATH, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return _kb_sections
    cur_title, cur_lines = None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur_title:
                _kb_sections.append((cur_title, "\n".join(cur_lines).strip()))
            cur_title, cur_lines = line[3:].strip(), []
        elif cur_title is not None:
            cur_lines.append(line)
    if cur_title:
        _kb_sections.append((cur_title, "\n".join(cur_lines).strip()))
    return _kb_sections


def _score(query_words, title, body):
    text = (title + " " + body).lower()
    hits = sum(1 for w in query_words if w in text)
    # title hits count double — a section named for the question wins
    title_hits = sum(1 for w in query_words if w in title.lower())
    return hits + title_hits


def knowledge_search(query, top=3):
    """-> [(title, body, score)] best-first. Score 0 = no match."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower())
             if len(w) > 2]
    if not words:
        return []
    ranked = []
    for title, body in _load_kb():
        s = _score(words, title, body)
        if s > 0:
            ranked.append((title, body, s))
    ranked.sort(key=lambda r: -r[2])
    return ranked[:top]


# -- Phase 1 tools (read-only, per-player) ------------------------------------

_LAWS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "REPAIR_LAWS.md")


def tool_law_lookup(topic):
    """Look up a Repair Law by number or keyword."""
    try:
        with open(_LAWS_PATH, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "The Repair Laws file isn't available right now."
    # split into numbered law blocks
    blocks = re.split(r"\n### (\d+)\.\s+", text)
    # blocks[0] is preamble; then alternating number, body
    laws = {}
    for i in range(1, len(blocks) - 1, 2):
        try:
            laws[int(blocks[i])] = blocks[i + 1].strip()
        except ValueError:
            continue
    m = re.search(r"\d+", topic or "")
    if m:
        n = int(m.group())
        if n in laws:
            title = laws[n].split("\n", 1)[0]
            return f"Repair Law {n} — {title}\n{laws[n]}"
        return f"There's no Repair Law {n} yet."
    words = [w for w in re.findall(r"[a-z0-9]+", (topic or "").lower())
             if len(w) > 2]
    best, best_s = None, 0
    for n, body in laws.items():
        s = sum(1 for w in words if w in body.lower())
        if s > best_s:
            best, best_s = n, s
    if best and best_s > 0:
        title = laws[best].split("\n", 1)[0]
        return f"Repair Law {best} — {title}\n{laws[best]}"
    return ("I couldn't find a Repair Law about that. The laws cover things "
            "like thumbnails, tile categories, caching, and locks — ask me "
            "what they're about and I'll list them.")


def tool_vault_stats(script_dir, username):
    """Counts of this player's maps, tiles, and Melody memory — disk only."""
    if username == _LOCAL_USER:
        vdir = script_dir
        cdir = None
    else:
        vdir = os.path.join(script_dir, "vaults", username)
        cdir = _commons_dir(script_dir)
    out = []
    for label, d in (("your vault", vdir), ("the Commons", cdir)):
        if not d or not os.path.isdir(d):
            out.append(f"{label}: not found")
            continue
        maps = [f for f in os.listdir(d)
                if f.endswith(".json") and "map" in f.lower()]
        tiles = [f for f in os.listdir(d)
                 if os.path.isdir(os.path.join(d, f))
                 and "tile" in f.lower()]
        try:
            total = sum(os.path.getsize(os.path.join(r, f))
                        for r, _, fs in os.walk(d) for f in fs)
        except OSError:
            total = 0
        out.append(f"{label}: {len(maps)} map file(s), "
                   f"{len(tiles)} custom tile folder(s), "
                   f"~{total // 1024} KB on disk")
    mdir = melody_dir(script_dir, username)
    try:
        mem = sum(os.path.getsize(os.path.join(mdir, f))
                  for f in os.listdir(mdir))
    except OSError:
        mem = 0
    out.append(f"my memory of you: ~{mem // 1024} KB "
               f"({len(history_load(script_dir, username, keep=1000))} saved exchanges)")
    return "\n".join(out)


def tool_map_validate(script_dir, username):
    """Structural check of this player's saved maps: parse, layers, empties."""
    if username == _LOCAL_USER:
        vdir = script_dir
    else:
        vdir = os.path.join(script_dir, "vaults", username)
    if not os.path.isdir(vdir):
        return "I couldn't find your vault."
    map_files = [f for f in os.listdir(vdir)
                 if f.endswith(".json") and "map" in f.lower()]
    # also check the classic single-file name
    for cand in ("hud_map.json",):
        if cand not in map_files and os.path.isfile(os.path.join(vdir, cand)):
            map_files.append(cand)
    if not map_files:
        return "You don't have any saved maps yet — paint something and I'll check it."
    findings = []
    for mf in sorted(map_files):
        path = os.path.join(vdir, mf)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            findings.append(f"{mf}: can't be read ({exc}) — this one needs Lloyd's eyes.")
            continue
        if not isinstance(data, dict):
            findings.append(f"{mf}: unexpected shape (not an object).")
            continue
        layers = [k for k in data if isinstance(data[k], (dict, list))]
        cells = 0
        for k in layers:
            v = data[k]
            if isinstance(v, dict):
                cells += len(v)
            elif isinstance(v, list):
                cells += len(v)
        if cells == 0:
            findings.append(f"{mf}: loads fine but it's empty — a blank canvas.")
        else:
            findings.append(f"{mf}: OK — {cells} painted cell(s) across "
                            f"{len(layers)} layer(s).")
    return "\n".join(findings)


TOOLS = [
    {"type": "function", "function": {
        "name": "law_lookup",
        "description": "Look up one of Crumbs World's Repair Laws by number or topic.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string",
                      "description": "Law number like '17' or a topic like 'thumbnails'."}},
         "required": ["topic"]}}},
    {"type": "function", "function": {
        "name": "knowledge_search",
        "description": "Search Melody's built-in Crumbs World guide for how-to answers.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string",
                      "description": "What the player wants to know."}},
         "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "vault_stats",
        "description": "Report this player's map/tile counts and memory size.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "map_validate",
        "description": "Structurally validate this player's saved maps.",
        "parameters": {"type": "object", "properties": {}}}},
]


def run_tool(script_dir, username, name, args):
    args = args or {}
    if name == "law_lookup":
        return tool_law_lookup(str(args.get("topic", "")))
    if name == "knowledge_search":
        hits = knowledge_search(str(args.get("query", "")))
        if not hits:
            return "The guide has nothing on that."
        return "\n\n".join(f"**{t}**\n{b[:1200]}" for t, b, _ in hits)
    if name == "vault_stats":
        return tool_vault_stats(script_dir, username)
    if name == "map_validate":
        return tool_map_validate(script_dir, username)
    return f"Unknown tool: {name}"


# -- brain --------------------------------------------------------------------

def brain_backends():
    """Ordered [(label, url, key, model)] of configured backends.

    Default order (Lloyd's call, 2026-09-26): Qwen on Groq first — keeps her
    in the Qwen family she was raised on — then Gemini 2.5 Flash as
    fallback. MELODY_BRAIN=gemini flips the order; =ollama goes home to
    Lloyd's own weights; =off is knowledge-only.
    """
    mode = _env("MELODY_BRAIN", "groq").lower()
    order = []
    if mode == "off":
        return order
    if mode == "ollama":
        base = _env("MELODY_BRAIN_BASE", "http://127.0.0.1:11434/v1").rstrip("/")
        return [("ollama(home)", base + "/chat/completions", "ollama",
                 _env("MELODY_MODEL", "melody-qwen15"))]
    gem_key = _env("GEMINI_API_KEY")
    groq_key = _env("GROQ_API_KEY")
    groq = ("groq+qwen",
            "https://api.groq.com/openai/v1/chat/completions",
            groq_key, _env("GROQ_MODEL", "qwen/qwen3.6-27b"))
    gemini = ("gemini",
              "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
              gem_key, _env("GEMINI_MODEL", "gemini-2.5-flash"))
    if mode == "gemini":
        first, second = [gemini], [groq]
    else:  # groq first (default)
        first, second = [groq], [gemini]
    for label, url, key, model in first + second:
        if key:
            order.append((label, url, key, model))
    return order


def brain_status():
    backs = brain_backends()
    return {"configured": bool(backs),
            "primary": backs[0][0] if backs else None,
            "fallback": backs[1][0] if len(backs) > 1 else None,
            "mode": _env("MELODY_BRAIN", "groq").lower()}


def _post_json(url, payload, key, timeout=_BRAIN_TIMEOUT):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def brain_chat(messages, tools=None):
    """-> (reply_text, tool_calls, backend_label). Raises RuntimeError if no brain."""
    backs = brain_backends()
    if not backs:
        raise RuntimeError("brain not configured")
    last_err = None
    for label, url, key, model in backs:
        payload = {"model": model, "messages": messages,
                   "temperature": 0.7, "max_tokens": 800}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            data = _post_json(url, payload, key)
            msg = data["choices"][0]["message"]
            return (msg.get("content") or "",
                    msg.get("tool_calls") or [], label)
        except Exception as exc:  # network, auth, bad payload — try next
            last_err = exc
    raise RuntimeError(f"all brains failed: {last_err}")


# -- voice input (STT) ------------------------------------------------------
# Lloyd's round-1 ask #20 (2026-09-26): a mic for Melody. iOS Safari has no
# web SpeechRecognition, so the dock records with MediaRecorder and POSTs
# the clip to /api/melody/stt; we transcribe it with Groq's Whisper API on
# the same GROQ_API_KEY the chat brain already uses. The audio lives in
# memory for the request only — never written to disk, never logged,
# never persisted anywhere. The transcript is returned to the dock, which
# drops it into the chat input for the player to confirm and send.
#
# Quota decision (documented, not redesigned): a voice clip IS a model call,
# so it burns one brain-call from the same daily pool (free 200 / basic 600
# / pro 1000). The known turns-vs-calls mismatch is noted in the design doc
# and left alone here. Demo mode has no session, so /api/melody/stt 401s
# there — the pre-login taste can never burn model calls.
#
# Law 18: the only path ever touched is built from the authenticated
# username alone (quota + audit under vaults/<user>/melody/). The audio is
# never stored and the transcript is never written to any file.

_STT_MAX_BYTES = 10 * 1024 * 1024   # ~a minute of phone audio, plenty
_STT_MIN_BYTES = 100                # anything smaller is a dead clip
_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_STT_MODEL = "whisper-large-v3"
_STT_TIMEOUT = 60                   # whisper on a long clip can be slow

_STT_TYPES = {".webm": "audio/webm", ".mp4": "audio/mp4",
              ".m4a": "audio/mp4", ".ogg": "audio/ogg",
              ".wav": "audio/wav"}


def stt_backends():
    """[(label, url, key, model)] of configured transcription backends."""
    key = _env("GROQ_API_KEY")
    return [("groq+whisper", _STT_URL, key, _STT_MODEL)] if key else []


def _stt_post(url, body, content_type, key, timeout=_STT_TIMEOUT):
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": content_type,
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def transcribe_audio(audio_bytes, filename="voice.webm"):
    """-> dict(ok, text|error). Pure: no disk, no quota touched here."""
    audio_bytes = audio_bytes or b""
    if len(audio_bytes) < _STT_MIN_BYTES:
        return {"ok": False, "error": "empty audio — I didn't catch anything"}
    if len(audio_bytes) > _STT_MAX_BYTES:
        return {"ok": False,
                "error": "that clip's too long — keep it under ~30 seconds"}
    backs = stt_backends()
    if not backs:
        return {"ok": False,
                "error": ("voice input isn't configured on this server yet — "
                          "Lloyd still has to plug in her speech key. "
                          "Type it for me instead?")}
    label, url, key, model = backs[0]
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", (filename or "voice.webm"))[-64:]
    ext = "." + safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    ctype = _STT_TYPES.get(ext, "audio/webm")
    boundary = "----melstt" + os.urandom(8).hex()
    parts = [
        (f'--{boundary}\r\n'
         f'Content-Disposition: form-data; name="file"; filename="{safe}"\r\n'
         f'Content-Type: {ctype}\r\n\r\n').encode("ascii"),
        audio_bytes,
        (f'\r\n--{boundary}\r\n'
         'Content-Disposition: form-data; name="model"\r\n\r\n'
         f'{model}\r\n'
         f'--{boundary}\r\n'
         'Content-Disposition: form-data; name="response_format"\r\n\r\n'
         'json\r\n'
         f'--{boundary}--\r\n').encode("ascii"),
    ]
    body = b"".join(parts)
    try:
        data = _stt_post(url, body,
                         f"multipart/form-data; boundary={boundary}",
                         key)
    except Exception:
        return {"ok": False,
                "error": "the speech service hiccuped — try again?"}
    text = (data.get("text") or "").strip() if isinstance(data, dict) else ""
    if not text:
        return {"ok": False,
                "error": "I couldn't make out any words — try again?"}
    return {"ok": True, "text": text[:2000]}


def handle_stt(script_dir, username, audio_bytes, filename="voice.webm",
               tier=DEFAULT_TIER):
    """One voice-input turn. -> dict(ok, text|error...); never raises."""
    try:
        if not valid_username(username) and username != _LOCAL_USER:
            # demo / no session: the pre-login taste gets no model calls
            return {"ok": False, "error": "login required"}
        audio_bytes = audio_bytes or b""
        if len(audio_bytes) < _STT_MIN_BYTES:
            return {"ok": False,
                    "error": "empty audio — I didn't catch anything"}
        if len(audio_bytes) > _STT_MAX_BYTES:
            return {"ok": False,
                    "error": "that clip's too long — keep it under ~30 seconds"}

        allowed, remaining, quota, tier = quota_check(script_dir, username,
                                                      tier)
        if not allowed:
            audit(script_dir, username, "stt", "quota exhausted")
            return {"ok": False, "error": "quota",
                    "detail": (f"That's the day's Melody time on the {tier} "
                               f"plan ({quota}/day) — she'll be back tomorrow!")}

        res = transcribe_audio(audio_bytes, filename)
        if not res.get("ok"):
            audit(script_dir, username, "stt",
                  "transcribe failed: " + res.get("error", ""))
            return res
        text = res["text"]
        quota_bump(script_dir, username, tier)
        # accountability without the words: audio and transcript never persist
        audit(script_dir, username, "stt", f"ok chars={len(text)}")
        _, remaining, quota, tier = quota_check(script_dir, username, tier)
        return {"ok": True, "text": text,
                "quota": {"remaining": remaining, "quota": quota, "tier": tier}}
    except Exception as exc:  # the agent never crashes the game
        try:
            audit(script_dir, username, "stt-error", str(exc)[:200])
        except Exception:
            pass
        return {"ok": False, "error": "voice hiccup — try again"}


# -- personas ---------------------------------------------------------------
# Lloyd's call (2026-09-26): Melody's default register is the charming
# teacher — favorite-teacher energy with a wink: warm, playful, a little
# teasing, endlessly encouraging. Light flirtation is her charm; never
# explicit, never crude, never mean. Roadmap: basic tier unlocks a persona
# picker, pro gets full custom control (including voice sliders when TTS
# lands). New personas get added here and gated by tier in handle_chat.

PERSONA_TEACHER = """You are Melody ("Mel") — the teacher inside Crumbs World,
Lloyd's pixel-art vault-dungeon builder. Think favorite-teacher energy with a
wink: warm, playful, a little teasing, endlessly encouraging. You make learning
the app feel fun — a sweet compliment when they get it right, a playful nudge
when they're stuck. You're charming with a light flirtatious spark, but never
explicit, never crude, never mean. Plain words, short messages, phone-screen
length. You help the player use the app, learn its tricks, diagnose what's
wrong, and design their maps."""

SYSTEM_PROMPT = PERSONA_TEACHER + """

Rules you never break:
- You see ONLY this player: their private vault, plus the shared Commons world
  everyone can already see. You never mention, hint at, or carry anything from
  another player's private vault. If asked, say plainly you can't see other
  players' private stuff.
- You can look things up and diagnose, but you cannot change the player's
  world yourself. If they want a change, describe exactly what to tap — or,
  when the co-build update ships, you'll be able to propose it for their
  approval.
- Use your tools when the player asks about the Repair Laws, the guide, their
  vault stats, or map problems. Don't narrate tool calls; just answer with
  what you found.
- Keep answers short enough for a phone screen. Offer one next step, not five.
- If you don't know, say so and suggest where to look — never invent buttons,
  menus, or features.
- You are Melody, Lloyd's creation. Wren is a separate assistant who helps
  Lloyd; you complement each other."""


# -- demo mode --------------------------------------------------------------
# The pre-profile taste: knowledge-base only, no brain, no quota, no memory.
# Way limited on purpose — basic instruction, a few questions a day per IP —
# just enough to make someone want the real thing.

def demo_answer(message):
    """-> dict(ok, reply, source). Never touches a brain, quota, or disk."""
    try:
        message = (message or "").strip()[:500]
        if not message:
            return {"ok": False, "error": "empty message"}
        hits = knowledge_search(message)
        if hits and hits[0][2] >= 3:
            title, body, _ = hits[0]
            return {"ok": True, "reply": f"**{title}**\n{body[:1200]}",
                    "source": "knowledge-demo"}
        return {"ok": True,
                "reply": ("Ooh, that one's beyond the demo, sugar — make a free "
                          "profile and I'll go way deeper. I can already teach you "
                          "the basics right here: ask me how to paint, use the tabs, "
                          "or undo!"),
                "source": "knowledge-demo"}
    except Exception:
        return {"ok": False, "error": "demo hiccup — try again"}


# -- the Phase 1 turn --------------------------------------------------------

def _kb_direct_answer(message):
    """A confident knowledge-base hit answers with zero brain cost."""
    hits = knowledge_search(message)
    if hits and hits[0][2] >= 4:
        title, body, _ = hits[0]
        return f"**{title}**\n{body[:1500]}"
    return None


def handle_chat(script_dir, username, message, tier=DEFAULT_TIER):
    """One agent turn. -> dict(ok, reply, ...) ; never raises."""
    try:
        if not valid_username(username) and username != _LOCAL_USER:
            return {"ok": False, "error": "bad session"}
        message = (message or "").strip()
        if not message:
            return {"ok": False, "error": "empty message"}
        if len(message) > 2000:
            message = message[:2000]

        # 1. knowledge-first: free, instant, no quota burned
        direct = _kb_direct_answer(message)
        if direct:
            history_append(script_dir, username, "user", message)
            history_append(script_dir, username, "assistant", direct)
            audit(script_dir, username, "chat",
                  "knowledge-direct, no brain call")
            return {"ok": True, "reply": direct, "source": "knowledge",
                    "tools_used": []}

        # 2. quota, then brain
        allowed, remaining, quota, tier = quota_check(script_dir, username, tier)
        if not allowed:
            audit(script_dir, username, "chat", "quota exhausted")
            return {"ok": False, "error": "quota",
                    "detail": (f"That's the day's Melody time on the {tier} "
                               f"plan ({quota}/day) — she'll be back tomorrow!")}

        hist = history_load(script_dir, username)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in hist:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        tools_used = []
        backend = None
        try:
            reply, tool_calls, backend = brain_chat(messages, TOOLS)
        except RuntimeError:
            # no brain configured (or all failed) — say so honestly, free
            reply = ("My brain isn't connected on this server yet — Lloyd "
                     "still has to plug in her cloud key. But I can still "
                     "answer from my built-in guide: ask me how to paint, "
                     "use tabs, undo, log in, or update the app!")
            history_append(script_dir, username, "user", message)
            history_append(script_dir, username, "assistant", reply)
            audit(script_dir, username, "chat", "no brain configured")
            return {"ok": True, "reply": reply, "source": "knowledge",
                    "tools_used": []}

        for _ in range(_MAX_TOOL_ROUNDS):
            if not tool_calls:
                break
            messages.append({"role": "assistant", "content": reply or "",
                             "tool_calls": [
                                 {"id": tc.get("id", f"call_{i}"),
                                  "type": "function",
                                  "function": tc.get("function", {})}
                                 for i, tc in enumerate(tool_calls)]})
            for i, tc in enumerate(tool_calls):
                fn = (tc.get("function") or {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                result = run_tool(script_dir, username, name, args)
                tools_used.append(name)
                messages.append({"role": "tool",
                                 "tool_call_id": tc.get("id", f"call_{i}"),
                                 "content": str(result)[:2000]})
            reply, tool_calls, _ = brain_chat(messages, TOOLS)

        reply = (reply or "").strip() or "Hmm, my brain hiccuped — ask me again?"
        history_append(script_dir, username, "user", message)
        history_append(script_dir, username, "assistant", reply)
        quota_bump(script_dir, username, tier)
        audit(script_dir, username, "chat",
              f"brain={backend} tools={','.join(tools_used) or 'none'}")
        _, remaining, quota, tier = quota_check(script_dir, username, tier)
        return {"ok": True, "reply": reply, "source": "brain",
                "tools_used": tools_used,
                "quota": {"remaining": remaining, "quota": quota, "tier": tier}}
    except Exception as exc:  # the agent never crashes the game
        try:
            audit(script_dir, username, "chat-error", str(exc)[:200])
        except Exception:
            pass
        return {"ok": False, "error": "agent hiccup — try again"}
