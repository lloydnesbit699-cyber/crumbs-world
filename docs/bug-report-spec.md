# Bug Report with 30s Replay Clip — Spec (v5.63)
Built 2026-10-14. Player hits "Report bug" in the menu, describes what happened,
picks a priority, and the last 30 seconds of gameplay go with it to Harley.

## Player flow
1. Menu → **🐛 Report bug**.
2. Panel: "What happened?" (free text, 2000 chars max), priority, clip checkbox.
3. Send → toast confirms → panel closes.
4. Nothing is recorded to disk or sent anywhere until the player hits Send.

## The 30-second recorder (client)
- Starts silently on page load. `canvas.captureStream(10)` on the map canvas
  (`#grid`) + `MediaRecorder`, 1-second slices, 500 kbps.
- Rolling buffer: keeps only slices from the last 30 seconds, drops older ones.
  Memory cost is a few MB at most.
- Codec fallback: VP9 → VP8 → browser default. If MediaRecorder or
  `captureStream` is missing, the form still works — clip checkbox disables
  itself with no error.
- Clip cap: if the assembled clip is over 8 MB raw, it sends without the clip
  rather than failing the whole report.
- Privacy: game canvas only. No mic, no camera, no screen outside the game.
  The form says so in plain text.

## The form (client)
- Priority: **Can't play** (blocks me) / **Annoying** (workaround exists) /
  **Minor** (cosmetic/small). Default: Annoying.
- Auto-attached metadata: game version, browser, viewport, page, last 20
  console errors/warnings (captured by a `console.error/warn` wrapper).
- Username comes from the server session, not the client — no spoofing.
- Submit button disables during send; errors show in the panel, not a crash.

## The endpoint (server)
- `POST /api/bug-report`, JSON only (fits the existing POST pattern —
  the dispatcher rejects multipart, so the clip travels base64 inside JSON).
- Auth: logged-in session required in public mode; local mode accepts
  (local mode has no accounts — the game itself is open, so reporting
  is no more exposure than playing).
- Validation: text 1–2000 chars; priority must be one of the three;
  clip base64 must decode and stay under 12 MB decoded.
- Storage: `bug-reports/` next to `crumbs_hud.py`. One `.json` (report +
  metadata) + one `.webm` (clip) per report.
- Filename: `YYYYMMDD-HHMMSS-N-PRIORITY-USER-RAND.json`
  (`N` = 1 critical / 2 annoying / 3 minor, so a plain file listing
  sorts critical first). Username sanitized to `[a-z0-9_-]`.
- Retention: each new report prunes files older than 30 days (best effort).
- Response: `{"ok": true, "id": "<filename base>"}`.

## On Harley's desktop
- Reports land in `C:\Users\lloyd\OneDrive\Desktop\Vault\crumbs-world\bug-reports\`.
- Put a shortcut to that folder on the desktop. Open a `.json` to read the
  report, play the matching `.webm` to see the bug happen.

## Limits & edge cases
- 16 MB JSON ceiling on the server; clip kept well under it.
- Rate limit: the existing POST rate gate (120/min/IP) applies.
- No clip + no text edge: text is required; clip is optional.
- Server write failure → 500, client shows "couldn't save — try again."
- Duplicate submits blocked by the disabled button.

## What it deliberately does NOT do
- No email, no third-party service, no cloud upload.
- No mic/camera/screen recording beyond the game canvas.
- No auto-reporting or crash telemetry — the player chooses to send.
- No moderation queue — reports go straight to the folder; the owner
  deletes junk by hand.
