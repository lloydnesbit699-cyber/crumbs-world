#!/usr/bin/env python3
r"""Apply the in-game bug report + 30s replay clip feature (v5.63).

Edits editor.html (menu button, overlay CSS+HTML, recorder+form JS) and
crumbs_hud.py (POST /api/bug-report endpoint, storage + retention).
See bug-report-spec.md for the design.

Run on Harley in the game folder:
    cd C:\Users\lloyd\OneDrive\Desktop\Vault\crumbs-world
    python apply-bug-report.py

Idempotent: safe to re-run.
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def replace_once(path, old, new, label, marker):
    # marker: a string present ONLY after applying (the new content's fingerprint).
    # Checking it first is what makes insert-style edits idempotent — the new
    # text contains the anchor, so "old in src" stays true after applying.
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if marker in src:
        print(f"  [skip] {label} — already applied")
        return True
    if old not in src:
        print(f"  [MISS] {label} — anchor not found")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new, 1))
    print(f"  [ok] {label}")
    return True

ok = True

# ---------------------------------------------------------------- editor.html
e = "editor.html"

BUG_CSS = r"""/* v5.63: bug report overlay */
#bug-overlay { position: fixed; inset: 0; z-index: 300; display: none;
  align-items: center; justify-content: center; background: rgba(5,5,12,.92); }
#bug-overlay.show { display: flex; }
#bug-box { background: #14141c; border: 1px solid #2a2a38; border-radius: 12px;
  padding: 24px; width: min(86vw, 380px); }
#bug-box h2 { color: #ffd75f; margin: 0 0 8px; font-size: 20px; }
#bug-box textarea { display: block; width: 100%; box-sizing: border-box;
  margin: 8px 0; padding: 10px; border-radius: 8px; border: 1px solid #333;
  background: #0d0d12; color: #eee; font-size: 15px; min-height: 90px; resize: vertical; }
#bug-box select { display: block; width: 100%; box-sizing: border-box;
  margin: 8px 0; padding: 10px; border-radius: 8px; border: 1px solid #333;
  background: #0d0d12; color: #eee; font-size: 15px; }
#bug-box .bug-row { display: flex; gap: 8px; margin: 8px 0; }
#bug-box button { padding: 10px 16px; border-radius: 8px; border: 1px solid #333;
  background: #222; color: #eee; font-size: 15px; cursor: pointer; }
#bug-box .bug-send { background: #2a4a2a; border-color: #3a6a3a; }
#bug-box .bug-err { color: #f88; font-size: 13px; min-height: 18px; }
#bug-box .bug-note { color: #888; font-size: 12px; margin-top: 8px; }

"""

ok &= replace_once(e,
    "  /* v5.27: login overlay + user menu */",
    BUG_CSS + "  /* v5.27: login overlay + user menu */",
    "bug overlay CSS", "#bug-overlay {")

ok &= replace_once(e,
    '  <button id="menu-log" title="Server event log (debugging)">Server log</button>',
    '  <button id="menu-log" title="Server event log (debugging)">Server log</button>\n'
    '  <button id="menu-bug" title="Report a bug (includes last 30s gameplay clip)">&#x1F41B; Report bug</button>',
    "menu bug button", 'id="menu-bug"')

BUG_HTML = r"""<!-- v5.63: in-game bug report -->
<div id="bug-overlay">
  <div id="bug-box">
    <h2>&#x1F41B; Report a bug</h2>
    <label for="bug-text">What happened?</label>
    <textarea id="bug-text" maxlength="2000" placeholder="What were you doing when it broke?"></textarea>
    <label for="bug-priority">How bad is it?</label>
    <select id="bug-priority">
      <option value="critical">Can't play — blocks me</option>
      <option value="annoying" selected>Annoying — I can work around it</option>
      <option value="minor">Minor — cosmetic / small</option>
    </select>
    <label><input type="checkbox" id="bug-clip" checked> Include last 30 seconds of gameplay clip</label>
    <div class="bug-row">
      <button id="bug-send" class="bug-send">Send report</button>
      <button id="bug-cancel">Cancel</button>
    </div>
    <div id="bug-err" class="bug-err"></div>
    <div class="bug-note">The clip records only your game screen, stays on your device, and is sent only when you hit Send.</div>
  </div>
</div>

"""

ok &= replace_once(e,
    '<div id="splash">',
    BUG_HTML + '<div id="splash">',
    "bug overlay HTML", 'id="bug-overlay"')

BUG_JS = r"""<script>
// ---- v5.63: in-game bug report + 30s replay clip ---------------------
// Rolling recorder: captures the map canvas, keeps only the last 30s.
// Nothing leaves the device until the player submits a report.
var bugClipChunks = [];   // [{t, blob}]
var bugRecorder = null;
var bugErrLog = [];       // last 20 console errors/warnings

(function bugErrCapture() {
  function push(kind, args) {
    try {
      var msg = Array.prototype.map.call(args, function (a) {
        try { return typeof a === "string" ? a : JSON.stringify(a); }
        catch (e) { return String(a); }
      }).join(" ").slice(0, 300);
      bugErrLog.push(new Date().toISOString().slice(11, 19) + " " + kind + ": " + msg);
      if (bugErrLog.length > 20) bugErrLog.shift();
    } catch (e) {}
  }
  var _err = console.error, _warn = console.warn;
  console.error = function () { push("ERR", arguments); return _err.apply(console, arguments); };
  console.warn = function () { push("WARN", arguments); return _warn.apply(console, arguments); };
})();

function bugClipMime() {
  var types = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", ""];
  for (var i = 0; i < types.length; i++) {
    try {
      if (!types[i] || (window.MediaRecorder && MediaRecorder.isTypeSupported(types[i]))) return types[i];
    } catch (e) {}
  }
  return "";
}

function bugClipStart() {
  try {
    var canvas = document.getElementById("grid");
    if (!canvas || !canvas.captureStream || !window.MediaRecorder) return;
    var stream = canvas.captureStream(10);
    var mime = bugClipMime();
    var opts = { videoBitsPerSecond: 500000 };
    if (mime) opts.mimeType = mime;
    bugRecorder = new MediaRecorder(stream, opts);
    bugRecorder.ondataavailable = function (ev) {
      if (ev.data && ev.data.size > 0) {
        bugClipChunks.push({ t: Date.now(), blob: ev.data });
        var cutoff = Date.now() - 30000;
        while (bugClipChunks.length && bugClipChunks[0].t < cutoff) bugClipChunks.shift();
      }
    };
    bugRecorder.onerror = function () { bugRecorder = null; };
    bugRecorder.start(1000);
  } catch (e) { bugRecorder = null; }
}

function bugShowForm() {
  $("bug-overlay").classList.add("show");
  var clipBox = $("bug-clip");
  if (clipBox) {
    clipBox.checked = !!(bugRecorder && bugClipChunks.length);
    clipBox.disabled = !(bugRecorder && bugClipChunks.length);
  }
  setTimeout(function () { var t = $("bug-text"); if (t) t.focus(); }, 50);
}
function bugHideForm() { $("bug-overlay").classList.remove("show"); }

function bugBlobToB64(blob) {
  return new Promise(function (resolve, reject) {
    var r = new FileReader();
    r.onload = function () {
      var s = String(r.result || "");
      resolve(s.indexOf(",") >= 0 ? s.split(",")[1] : s);
    };
    r.onerror = reject;
    r.readAsDataURL(blob);
  });
}

async function bugSubmit() {
  var btn = $("bug-send");
  var text = ($("bug-text").value || "").trim();
  if (!text) { $("bug-err").textContent = "Say a little about what happened."; return; }
  if (text.length > 2000) { $("bug-err").textContent = "Keep it under 2000 characters."; return; }
  if (btn) btn.disabled = true;
  $("bug-err").textContent = "Sending…";
  try {
    var clipB64 = null;
    if ($("bug-clip").checked && bugClipChunks.length) {
      var blob = new Blob(bugClipChunks.map(function (c) { return c.blob; }), { type: "video/webm" });
      if (blob.size <= 8 * 1024 * 1024) clipB64 = await bugBlobToB64(blob);
    }
    var meta = {
      version: "%%CRUMBS_VERSION%%",
      userAgent: navigator.userAgent,
      viewport: window.innerWidth + "x" + window.innerHeight,
      url: location.pathname,
      errors: bugErrLog.slice()
    };
    var r = await fetch("/api/bug-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, priority: $("bug-priority").value, meta: meta, clip_b64: clipB64 })
    });
    var j = await r.json();
    if (!j.ok) throw new Error(j.error || "server said no");
    bugHideForm();
    $("bug-text").value = "";
    toast("Bug report sent — thanks! (clip " + (clipB64 ? "attached" : "not attached") + ")");
  } catch (e) {
    $("bug-err").textContent = "Couldn't send: " + (e && e.message ? e.message : e);
  } finally {
    if (btn) btn.disabled = false;
  }
}

(function bugWire() {
  try {
    var b = document.getElementById("menu-bug");
    if (b) b.onclick = bugShowForm;
    var c = document.getElementById("bug-cancel");
    if (c) c.onclick = bugHideForm;
    var s = document.getElementById("bug-send");
    if (s) s.onclick = bugSubmit;
    bugClipStart();
  } catch (e) {}
})();
</script>
</body>"""

ok &= replace_once(e,
    "</body>",
    BUG_JS,
    "bug recorder + form JS", "bugClipStart")

# -------------------------------------------------------------- crumbs_hud.py
p = "crumbs_hud.py"

ok &= replace_once(p,
    'MAX_JSON_BYTES = 16 * 1024 * 1024   # ordinary API requests',
    'MAX_JSON_BYTES = 16 * 1024 * 1024   # ordinary API requests\n'
    'BUG_REPORT_DIR = "bug-reports"          # v5.63: in-game bug reports land here\n'
    'BUG_REPORT_RETENTION_DAYS = 30          # v5.63: prune reports older than this',
    "bug report constants", "BUG_REPORT_DIR")

BUG_ENDPOINT = r'''        if path == "/api/bug-report":
            # v5.63: in-game bug report + 30s replay clip. Logged-in session
            # required in public mode; local mode accepts (no accounts there —
            # the game itself is open, so reporting is no more exposure).
            u = self._session_user()
            if PUBLIC_MODE and not u:
                return self._send_json({"ok": False, "error": "log in first"}, 401)
            text = str(body.get("text") or "").strip()
            if not text or len(text) > 2000:
                return self._send_json({"ok": False, "error": "report text must be 1-2000 chars"}, 400)
            priority = str(body.get("priority") or "annoying").strip().lower()
            if priority not in ("critical", "annoying", "minor"):
                priority = "annoying"
            meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
            clip_b64 = body.get("clip_b64") or ""
            clip_bytes = b""
            if clip_b64:
                try:
                    clip_bytes = base64.b64decode(clip_b64, validate=True)
                except Exception:
                    return self._send_json({"ok": False, "error": "bad clip encoding"}, 400)
                if len(clip_bytes) > 12 * 1024 * 1024:
                    return self._send_json({"ok": False, "error": "clip too big"}, 413)
            safe_user = re.sub(r"[^a-z0-9_-]", "_", (u or "local").lower())[:24] or "player"
            stamp = time.strftime("%Y%m%d-%H%M%S")
            order = {"critical": "1", "annoying": "2", "minor": "3"}[priority]
            rand = "%04x" % random.randrange(0x10000)
            base = f"{stamp}-{order}-{priority}-{safe_user}-{rand}"
            try:
                os.makedirs(BUG_REPORT_DIR, exist_ok=True)
                report = {
                    "id": base, "at": int(time.time()),
                    "user": u or "local", "priority": priority, "text": text,
                    "meta": meta, "has_clip": bool(clip_bytes),
                    "version": APP_VERSION,
                }
                with open(os.path.join(BUG_REPORT_DIR, base + ".json"), "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=1)
                if clip_bytes:
                    with open(os.path.join(BUG_REPORT_DIR, base + ".webm"), "wb") as f:
                        f.write(clip_bytes)
                # retention: prune reports older than 30 days (best effort)
                try:
                    cutoff = time.time() - BUG_REPORT_RETENTION_DAYS * 86400
                    for fn in os.listdir(BUG_REPORT_DIR):
                        fp = os.path.join(BUG_REPORT_DIR, fn)
                        if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                            os.remove(fp)
                except Exception:
                    pass
            except Exception:
                return self._send_json({"ok": False, "error": "couldn't save report"}, 500)
            return self._send_json({"ok": True, "id": base})

'''

ok &= replace_once(p,
    '        if path == "/api/auth/logout":',
    BUG_ENDPOINT + '        if path == "/api/auth/logout":',
    "/api/bug-report endpoint", 'if path == "/api/bug-report":')

print()
if ok:
    print("All applied. Next: git add -A && git commit -m \"bug report + 30s replay clip (v5.63)\" && git push, then restart the server.")
else:
    print("Some edits MISSED — send Wren the [MISS] lines.")
    sys.exit(1)
