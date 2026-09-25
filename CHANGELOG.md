# Changelog — Crumbs HUD

All notable changes, newest first. Phone-verified means Lloyd ran it on
his iPhone; anything else is verified on desktop/server only.

## v5.26 — 2026-09-25

Lloyd's direction: harden the categorization, and give straight colors
their own tab.

- **Thumbnails stop hanging.** Every `/api/thumb` request re-cropped and
  re-encoded the PNG — ~3s each on a slow host, so a full tab never
  finished loading. Thumbnails are now cached in server memory and the
  browser is told to cache them for a day (only successes are cached, and
  backfill only adds art, so the cache can't go stale). First paint is
  progressive, every revisit is instant. Repair Law 16: Cache What You Crop.
- **One tile, one home.** A new `SUBCATEGORY_TABS` routing table (shared by
  server and client): walls/floors/doors/roofs/materials/natural → Tiles,
  furniture/containers/props/lighting/other → Objects,
  characters/creatures → Characters. "Starter Dark floor" now lives in the
  Tiles tab under the Floors chip instead of leaking into Objects — a floor
  is a floor. Imports land on their home tab automatically. Repair Law 15:
  One Tile, One Home.
- **Colors tab.** Straight flat colors get their own tab (no chips, just
  swatches) — the Tiles tab stays pure art tiles. Colors paints onto the
  tiles layer, and the app boots on Colors so open-and-paint works exactly
  like the old Tiles tab did.
- **Automatic display names.** `display_name()` derives one clean label
  from the raw name: `dungeon_wall_dark` → "Dark Wall", "Starter Dark
  floor" → "Starter Dark Floor". Palette labels, swatch titles, and search
  all use it (raw names kept for identity).
- Laws 15 and 16 added to REPAIR_LAWS.md.
- Server-verified only (API fields, cache timing, syntax); no phone run yet.

## v5.25.1 — 2026-09-25

Hotfix: v5.25 shipped a typo (`customes` for `customs`) that crashed the
palette the moment the Objects or Characters tab opened — Lloyd caught it
on his phone within the hour. One-line fix, tabs render again.
(Server-verified only: syntax check; no phone run yet.)

## v5.25 — 2026-09-25

The missing thumbnails, fixed at the root (Lloyd's call — stop patching
symptoms): the updater shipped code only, so phones carried registry
entries for art that never arrived — every one of those tiles painted a
permanently blank swatch. The update now ships the art too
(`shared_library.json`, the starter-pack strip, the built-in sprite art),
validates downloads by magic bytes, and a boot-time backfill fetches any
art an older install missed, then re-registers the shared shelf; the page
reloads the strip when the backfill lands. Thumbnails that still can't
load now paint an honest "?" placeholder (with a missing-art count in the
palette) instead of blank. And the palette grows the Minecraft-style
separation Lloyd sketched: every tile auto-categorizes from name hints
(the docs' "automatic categorization" TODO, done — imports included),
tiles filter by walls/floors/doors/roofs/materials/natural, objects by
furniture/containers/props/lighting, and characters & creatures get their
own menu tab (its brush paints onto the objects layer, where characters
live). The v5.23.2 grid and virtualized pack scrolling are untouched.
(Server-verified only: syntax-checked all files, live API checks, no
phone run yet.)

## v5.24 — 2026-09-25

The update finishes the job (Lloyd's diagnosis): the old flow swapped the
files and left the app waiting on a manual restart — the "stuck between
commits" state. Now installing an update (or a repair, or a rollback)
makes the server re-exec itself into the new files automatically, after
saving dirty map work and purging `__pycache__` (stale bytecode under a new
version number was the same ghost wearing a different coat). The page no
longer accepts any 200 as "back": every server boot mints an instance id,
and the page waits for a *different* instance id at the expected version
before reloading — the Restart button uses the same handshake, so it can
never falsely declare success. New Python files are compile-checked before
they touch the disk, so a bad download can't brick the server with no page
left to roll it back. If the new instance never appears, the page says so
honestly with recovery steps instead of pretending. (Server-verified only:
syntax-checked both files, logic walkthrough, no phone run yet.)

## v5.23.2 — 2026-09-24

Palette strip becomes a scrollable grid (Lloyd's call): the sideways strip
left dead space at the bottom of the left tray. Swatches now flow in a
76px-column grid that scrolls with the tray; pack headers span full width.
The 6k-tile virtualized pack window was reworked from horizontal to vertical
windowing (pages by row off the tray's scrollTop, re-measures columns on
rotation). Search, selection, lazy thumbnails, and collapse behavior
unchanged. (Server-verified only: syntax-checked, no logic touched beyond
the windowing math.)

## v5.23.1 — 2026-09-24

Narrow-phone topbar fix: the v5.22.8 status pills re-broke the 390px fit and
Setup/undo were clipping again on tall phones. Pills are dot-only under
520px (color still shows status, tap still opens them); menu buttons and
undo tightened so the whole bar fits without swiping.
(Server-verified only: CSS change, no logic touched.)

## v5.23 — 2026-09-24 — "Wren's hardening patch"

Animator and GUI/rendering hardening, merged from Lloyd's phone (v5.23.3)
onto the v5.22.11 base — the phone had diverged at v5.22.9, so the merge
kept the Recovery Reset button/endpoint, hosted write-key mode, and boot
census from v5.22.11 while bringing in the hardening changes.
- Hero selection is explicit-only: `RULES.hero_tile` or nothing. The old
  `/hero/i` name-guess fallback is gone — maps that relied on it need the
  hero set explicitly.
- No implicit object/hero brush: the objects layer no longer auto-selects
  a brush. Painting with nothing selected stamps nothing.
- Existing objects are directly tappable in Objects mode — tap inspects
  instead of painting over. Erase first (or tap an empty cell) to replace.
- Sheet/animator imports auto-select the first tile and switch to the
  right layer, ready to place immediately.
- New "Apply biome" overlay: `/api/generate-overlay` adds a biome to the
  current map (empty tiles only, or replace ground) without rebuilding —
  objects, collision, rules, nature and names are preserved. Undoable.
(Server-verified only: overlay painted 375 tiles, reset archived cleanly.)

## v5.22.11 — 2026-09-23

v5.22.10's Reset only stopped counting old failures — the next boot still
hit NO_VERIFIED_CHECKPOINT_AND_PRIMARY_UNUSABLE → CRITICAL, because the
old journal and heartbeat/dirty/clean evidence kept prior_state_known true.
Reset is now a true fresh start: the journal is archived (never deleted),
last_report.json and the evidence files are cleared, and the next boot
assesses FIRST_RUN_NO_PRIOR_STATE (LOW) — shield goes green. Checkpoints
and saves are untouched. (Server-verified only.)

## v5.22.10 — 2026-09-23

The shield stayed red forever after one bad day: recovery failures never
decayed, so stale 9/21 RECOVERY_FAILED events kept risk CRITICAL with no
verified checkpoint and no save file. Failures now decay after 24h, and
the Recovery sheet has a Reset button (write-key gated) that records a
RECOVERY_RESET marker — counting stops there, so one tap clears the stale
history. Checkpoints and saves are untouched. (Server-verified only.)

## v5.22.9 — 2026-09-21

The default tile library never reached Lloyd's phone: the updater and the
pull script shipped only the four app files, so shared_library.json +
shared_library/starter_pack.png were absent and the palette loaded empty
(silently). pull_crumbs.py v2.0 now fetches and validates both library
files; the server prints a boot census ("tile shelf: N local, M shared")
and says out loud when the shared registry is missing. (The in-app
updater still ships only the four app files — library gap stays open for
phone-local mode; hosted mode gets everything via git.)

Hosted mode (Lloyd's call — "host online free", no more server
babysitting): in public mode the owner's write key now unlocks
/api/update/apply, /api/update/apply-blobs, and /api/restart (was: blanket
403 / ungated), so a Replit-hosted HUD updates and restarts from the page
exactly like a local one; replit.md is now the real setup recipe and the
cloudrun [deployment] block is gone (ephemeral disk would eat map saves —
use the workspace repl). Verified on desktop/server; not yet run on
Lloyd's iPhone.

## v5.22.8 — 2026-09-21

Header status pills (Lloyd's "signs of life" ask): an update pill (live
version + green/gold/red dot, tap opens the updater) fed by the quiet
update check, and a recovery pill (shield + risk level, dot breathes
while healthy, tap opens the Recovery sheet) fed by a new lightweight
`recovery` brief on /api/status. Verified on desktop/server; not yet run
on Lloyd's iPhone.
## v5.22.7 — 2026-09-21

Client-side fallback for the version placeholder: a new editor.html
served by a not-yet-restarted older server leaked the raw
%%CRUMBS_VERSION%% onto the banner/splash (seen on Lloyd's phone). The
quiet update check now patches it from the running server's version.
Verified on desktop/server; not yet run on Lloyd's iPhone.

## v5.22.6 — 2026-09-21

The banner/splash version was hardcoded as v5.21.11 in editor.html and
went stale on every bump (Lloyd's running 5.22.5 showed 5.21.11). Now
the HTML carries a %%CRUMBS_VERSION%% placeholder and the server stamps
the real APP_VERSION when serving `/`. Verified on desktop/server; not
yet run on Lloyd's iPhone.

## v5.22.5 — 2026-09-21

Launching `python3 crumbs_hud.py` while the old server still holds port
8778 used to die with a raw "Address already in use" traceback. Now it
probes the port and says what's actually up: the HUD is already running,
just reload the page — or stop the old server (Ctrl-C in its a-Shell tab)
to run the new version. Verified on desktop/server; not yet run on
Lloyd's iPhone.

## v5.22.4 — 2026-09-21

The share-key prompt and Setup → Key… now trim the entered key. iPhone
keyboards auto-capitalize the first letter and trail spaces, both of
which silently failed the key check and left the HUD read-only. Verified
on desktop/server; not yet run on Lloyd's iPhone.

## v5.22.3 — 2026-09-21

A wrong share key on a public HUD used to nag the key prompt on *every*
action: the bad key was saved and re-asked forever. Now a rejected key is
cleared immediately with a plain message pointing at Setup → Key…, so it
asks once and stays quiet. Verified on desktop/server; not yet run on
Lloyd's iPhone.

## v5.22.2 — 2026-09-21

The in-app updater's file list missed `crumbs_recovery.py`, so phones that
updated to v5.22.x started with "recovery core unavailable" and the whole
Phase 3B recovery layer stayed dark. The updater now ships all four app
files, and Check for updates offers a *repair* install when a file never
arrived — even when the version is already current. Verified on
desktop/server; not yet run on Lloyd's iPhone.

- Server `UPDATE_FILES` and the page-side download list both include
  `crumbs_recovery.py`, with the same truncated-download sanity checks.
- Same-version installs are allowed as repairs when an update file is
  missing from disk; true downgrades are still refused.
- The update dialog and the quiet hourly nudge both explain the repair
  case instead of pretending a new version is out.

## v5.21.15 — 2026-09-21

Made the sprite-sheet picker less fragile when the imported image is
smaller than the default 16px cell size. Verified on desktop/server; not
yet run on Lloyd's iPhone.

- The picker now chooses a smaller starting cell size automatically when a
  sheet is too short or too narrow for 16px cells, instead of silently
  producing zero selectable cells.
- If it has to fall back, the sheet hint says `auto-fit to image` so the
  phone can tell us that sizing fallback is active.

## v5.21.14 — 2026-09-21

Stopped the sprite-sheet animator from going blank when the editor thinks
every cell is empty. Verified on desktop/server; not yet run on Lloyd's
iPhone.

- The sheet picker now auto-shows all cells if non-empty-cell detection
  finds zero solid cells, instead of leaving the grid empty while asking
  you to select tiles.
- The picker hint now says when it's in that fallback mode, so the next
  debugging pass can tell whether the issue is bad empty-cell detection or
  something deeper in the import pipeline.

## v5.21.13 — 2026-09-21

Added a visible palette probe so the phone can report what Safari thinks
the selected swatch color is. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- Under the tile palette, the editor now shows the selected swatch's
  expected hex color, `data-color`, inline `backgroundColor`, and computed
  CSS color.
- If the swatch still looks black on iPhone, this readout should tell us
  whether the color is missing before paint, getting rewritten by CSS, or
  surviving into computed style while the visual box still renders wrong.

## v5.21.12 — 2026-09-21

Chased the "palette API is right but the swatch fill turns black" bug on
the HTML side. Verified on desktop/server; not yet run on Lloyd's iPhone.

- Tile palette swatches no longer depend on inline HTML strings for their
  color fill. The editor now builds each swatch node directly and sets the
  chip color through DOM style assignment (`backgroundColor`), which is the
  path most likely to survive Safari's quirks here.
- Added a `data-color` copy on each chip too, so if it still goes black on
  iPhone the next chase can inspect the rendered HTML and see whether the
  color made it into the DOM.

## v5.21.11 — 2026-09-21

Brightened the grassland palette too — the dark blues/greens were reading
as black. Verified on desktop/server; not yet run on Lloyd's iPhone.

- deep_water #2a6b9e, water #3d8bce, sand #d2c290, grass_dark #4a8c2e,
  grass #5a9c33, grass_light #6ab844, dirt #7b5233, stone #6a6a6a.
- If the swatches still show black after updating, the color isn't
  reaching the HTML — that's a different bug to chase.

## v5.21.10 — 2026-09-21

The dungeon palette was unusable — four near-black grays you couldn't
tell apart. Verified on desktop/server; not yet run on Lloyd's iPhone.

- **Lloyd's call:** "the thumbs are way too dark you can't tell any
  difference." Brightened the dungeon colorset: floor #757575, floor_dark
  #555555, wall #9a9a9a, wall_dark #6a6a6a, door #8b5a2b, chest #c9a227.
  Still reads as dungeon, now actually distinguishable.
- **Selection highlight** made impossible to miss: thicker gold border,
  stronger glow, plus a gold tint behind the whole selected swatch.

## v5.21.9 — 2026-09-21

"Setup" was still clipped to "Set" on Lloyd's narrow portrait phone.
Verified on desktop/server; not yet run on Lloyd's iPhone.

- **Fix:** the v5.21.7 tightening wasn't enough — went more compact on
  screens under 520px: 12px menu text, 6px button padding, tighter
  topbar gaps, smaller undo/redo. All six menus (File–Setup) now fit in
  ~390px without scrolling.
- The gold dot on File in Lloyd's screenshot confirmed the v5.21.8
  hourly check works — it was notifying him v5.21.8 was ready.

## v5.21.8 — 2026-09-21

Updates now come to you instead of waiting to be checked. Verified on
desktop/server; not yet run on Lloyd's iPhone.

- **Lloyd's call:** "instead of pulling we should have it push like most
  apps get updates." True push (App Store style) needs Apple servers and
  certs — not possible for a self-hosted app — but the page now
  re-checks GitHub silently every hour while it's open. When a new build
  appears you get the gold dot on File + one toast, same as the boot
  check. No manual Menu → Check needed, no nagging (one notice per
  version).
- The quiet boot check was refactored into a reusable function; the
  hourly timer shares it.

## v5.21.7 — 2026-09-21

The Build / Play / Setup menus were invisible on Lloyd's phone — not
missing, just scrolled off-screen. Verified on desktop/server; not yet run
on Lloyd's iPhone.

- **Root cause:** on narrow phones the top-bar title ("Crumbs HUD · tile
  painter") ate the menu bar's width. The menubar scrolls sideways by
  design, but with the scrollbar hidden there was no hint — File/Edit/View
  showed, Build/Play/Setup hid off-screen. That's why Play, map generation
  (Setup sheet), and the rest were "no shows".
- **Fix:** the title hides on screens under 520px wide and the menu buttons
  get tighter padding, so all six menus fit without swiping.
- Also bumped the hardcoded title/splash version stamp (was stale at
  v5.21.3).

## v5.21.6 — 2026-09-21

The `itemCells` ReferenceError is finally dead — root cause found and fixed.
Verified on desktop/server; not yet run on Lloyd's iPhone.

- **Root cause:** since v5.13, the entire gear section (items, NPCs, pack,
  shop, mission HUD) was accidentally defined *inside* `init()`'s try block,
  but `render()`/`renderBase()`, `refreshAll()`, `playTap()`, `natureTick()`,
  `doStep()` and `playEvents()` are global and call into it. Every render
  threw `ReferenceError: Can't find variable: itemCells`, and every D-pad
  step / NPC shop event / mission-HUD sync threw its own sibling error
  (`itemById`, `npcsReal`, `loadItems`, `loadNpcs`, `syncMissionHud`,
  `syncInv`, `openShop`). The map still painted because the throw happened
  after the tiles were drawn — so it looked like "just" log spam.
- **Fix:** the whole gear + mission-HUD block (state and 19 functions) moved
  to top level, above `init()`; `missionDanger` hoisted with it. No
  behavior change besides the errors going away — gear items and NPC folks
  now actually draw on the map, and file-switch reloads, D-pad mission
  sync, and shop events call real functions instead of throwing.
- Verified with an AST scope audit (no global function references an
  init-scoped name anymore) plus the usual syntax, server, and endpoint
  smoke tests.

## v5.21.5 — 2026-09-21

Freezer-proof updater. Verified on desktop/server; not yet run on Lloyd's
iPhone.

- **Updates now download in the page, not on the server.** iOS freezes
  a-Shell in the background, so a server-side download from GitHub could
  die mid-file and the update would loop forever. The browser is
  foreground — it fetches the three files itself (raw.githubusercontent.com
  allows it) and hands them to the server, whose only job is the guarded
  atomic swap. Falls back to the old server-side download if the page
  fetch fails.
- **No more "same update" loop.** If the files were swapped but the server
  was never restarted, Check for updates now says "vX is downloaded —
  restart the server to finish" (with a Restart button) instead of
  offering the install again. The check compares the on-disk version
  against the running one.

## v5.21.4 — 2026-09-21

Extension-noise filter + no-stale-page. Verified on desktop/server; not yet
run on Lloyd's iPhone.

- **Theme-extension errors are silenced.** Dark-mode/theme browser
  extensions inject scripts into the page and their internal errors
  (`createThemeAndWatchForUpdates`, `hostsWithOddScrollbars`, `e.copyright`)
  were flooding the on-page debug panel and the server log. The error
  reporter now drops them silently — those strings never appear in our code.
- **`Cache-Control: no-store` on the HUD page.** The server sent no cache
  headers, so Safari could keep serving a stale editor.html after an
  update. The page is 180KB over localhost — always fetch it fresh.

## v5.21.3 — 2026-09-21

Full functionality audit + the sticky server banner. Verified on
desktop/server; not yet run on Lloyd's iPhone.

- **Audit: nothing was lost.** Checked every control against its handler
  (31 buttons, 22 menu items, 6 menu drops) and every `api()` call against
  its server endpoint (85/85) — all wired, all answered. The undo/redo
  buttons, menus, and history stack survived every upgrade intact.
- **Undo/redo diagnosis.** They are server-side (`/api/undo`), and the
  request helper *threw* on a dead server — an unhandled rejection, so
  the tap did literally nothing. With iOS freezing a-Shell's server on
  every app switch, undo/redo looked broken when the real problem was
  the frozen server. The wiring was never the bug.
- **Sticky "Server isn't running" banner.** Any failed request now raises
  a persistent banner under the menu bar ("Server isn't running — in
  a-Shell: `python3 crumbs_hud.py`, then reload. Tap to retry."). It
  stays until the server answers again — no more silent dead buttons,
  and undo/redo fail loudly instead of mysteriously.

## v5.21.2 — 2026-09-21

Stale-cache armor for the updater. Verified on desktop/server; not yet run
on Lloyd's iPhone.

- **Cache-buster on every GitHub fetch.** raw.githubusercontent.com is a
  CDN whose edge nodes can serve an older copy for a while after a push —
  a phone install pulled v5.18 files minutes after v5.21.1 was released.
  Every updater fetch (version check, changelog, file downloads) now
  carries a unique `?t=` query string, so each request misses the cache
  and hits origin.
- **Install-time version guard.** Before swapping files, the updater now
  reads `APP_VERSION` out of the downloaded `crumbs_hud.py` and requires
  it to be numerically newer than the running build. If a stale copy
  slips through anyway, the install aborts cleanly — old files untouched,
  with a "try again in a bit" message instead of a silent downgrade.

## v5.21.1 — 2026-09-21

Update-check honesty fix. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **No more phantom "updates".** The check compared versions with `!=`,
  so a stale GitHub cache (or any mismatch) offered a *downgrade* as an
  update — 5.21 was told 5.20 was "available". Now it's a numeric
  comparison: an update is offered only when the remote build is strictly
  newer than the running one.

## v5.21 — 2026-09-21

The updater says what it means. Verified on desktop/server; not yet run
on Lloyd's iPhone.

- **Honest errors.** The old "couldn't reach GitHub" toast lied: half the
  time the page couldn't reach the *local* server (iOS froze a-Shell),
  not GitHub. Now each failure names its leg — "HUD server isn't
  answering" vs "this server couldn't reach GitHub" — with a fix hint
  (e.g. `pip install certifi` for a-Shell's missing CA certificates).
- **What's-new in the update prompt.** Check for updates now fetches the
  changelog and shows every version between yours and latest, so the
  install decision happens with the notes in front of you.
- **Quiet update badge.** One silent check after boot: if a newer build
  is out, the File menu gets a gold dot and one toast — no nagging,
  and silence when offline.
- **Save before updating.** Apply saves dirty map work first, then
  sanity-checks each download (right file, not truncated) before the
  atomic swap. A bad download can no longer replace a good file.
- **File → Roll back update.** The `.update-backup` files from the last
  install can be put back in one tap (restart the server after). The
  button stays dimmed when there's nothing to roll back to.
- **Auto-certifi.** If `certifi` is installed, the updater uses its CA
  bundle automatically — no `SSL_CERT_FILE` env dance on a-Shell.

## v5.20 — 2026-09-21

Windows-style menu bar + Reset map. Verified on desktop/server; not yet
run on Lloyd's iPhone.

- **Menu bar: File Edit View Build Play Setup.** Lloyd's call — the 26
  items from the old hamburger pile are grouped the way he approved:
  File holds saves, New map, updates and the server controls; Edit is
  undo/redo; View holds the display toggles; Build holds rules, world,
  Melody, items, folks and Check map; Play holds play + record; Setup
  holds setup, key and the server log. The bar scrolls sideways on
  narrow phones so the title and thumb undo/redo stay put.
- **File → New map… (Reset map).** Answers his reset question: Restart
  never clears the map (it saves dirty work first — that's the point).
  New map archives the current build to its `.backup` first, then starts
  a fresh blank map with default rules, nature and names. One undo
  step, and Load can bring the old build back.

## v5.19 — 2026-09-21

Restart server button. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **Menu → Restart server.** Lloyd wanted start/stop/reset controls next
  to Stop server. A page can't start a dead server, so restart does both
  halves in one move: the server saves dirty work, re-execs itself in
  place, and the page polls `/api/status` and reloads when the new
  process answers (60s timeout, then it tells you to use a-Shell).
  Stop server stays for a full shutdown to the a-Shell prompt.

## v5.18.1 — 2026-09-21

Tap-during-boot race, part two. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **Fixed `itemPlace`/`npcPlace` boot race.** Same bug as the v5.17.1
  `melodyPick` fix: the map tap handler reads the item/npc placement
  flags, but they were declared down in the v5.13 gear section, which
  runs after init's awaits. A tap during boot threw `Can't find
  variable: itemPlace` — Lloyd caught it on his phone at 4:18am. The
  flags are now hoisted next to the melody state above init.
  (The `hostsWithOddScrollbars` error in the same screenshot is his
  browser's dark-mode extension, not Crumbs.)

## v5.18 — 2026-09-20

In-app self-update. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **Menu → Check for updates.** Lloyd's rule, now a feature: updates
  overwrite the old files in place — no more downloading a suffixed copy
  and renaming it by hand. The app asks GitHub for the latest build,
  shows current vs latest, and on confirm pulls editor.html,
  crumbs_hud.py and crumbs_core.py from the repo's main branch, backing
  up each current file as `.update-backup` first and swapping the bytes
  in atomically. Local mode only; a public link can never rewrite the
  server. After install, stop and restart `python3 crumbs_hud.py`.
- **Banner reads APP_VERSION** so the printed version can't drift from
  the real one again.

## v5.17.1 — 2026-09-20

Tap-during-boot race fix. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **Fixed `melodyPick` unhandled rejection.** Tapping the map while the
  app was still booting threw "Can't find variable: melodyPick" — the
  tap handler could run during init's awaits, before the `let` that
  declares it executed (Safari reports the temporal dead zone that way).
  Melody's state now declares before boot starts, so early taps are safe.

## v5.17 — 2026-09-20

Crumbs World splash + honest boot progress. Verified on desktop/server;
not yet run on Lloyd's iPhone.

- **Crumbs World splash.** The signature shield now fills the whole
  title screen as the background (dark scrim keeps the title readable),
  in a Crumbs World variant — same shield, red/blue neon, planet ring,
  compass star and crossed wrenches, but the shield reads CRUMBS WORLD
  instead of the Nesbits business text. The Fixit site's logo is untouched.
- **Boot progress bar.** The splash used to vanish on a fixed timer, so a
  slow or stuck load looked dead. Now a progress bar advances through
  real boot milestones (server → biomes → recipes → tiles → sprites →
  your tiles → map data → painting), the splash fades only when boot
  actually finishes, and if it's still stuck after 12s the label says
  so and reminds that a-Shell must stay awake.

## v5.16 — 2026-09-20

Trust + sellable outputs. Verified on desktop/server; not yet run on
Lloyd's iPhone.

- **Public-mode share key.** `--share-key=VALUE` or `$CRUMBS_SHARE_KEY`
  (a random key is generated and printed if you share without one).
  With a key, write actions need `X-Crumbs-Key` — the editor takes it
  from the Builder URL (`?key=…`), asks once, and remembers it on the
  device. Without a valid key, public mode is read-only. Local mode
  stays editable. Wrong key → 403, non-JSON POSTs → 415,
  cross-site POSTs → 403.
- **Rate limits + size limits.** 120 POST / 600 GET per IP per minute;
  64 MiB JSON cap (base64 inflates bundles), 48 MiB decoded-bundle cap,
  2048px image bounds.
- **Backup/restore.** Load sheet lists every `.backup` with one-tap
  restore; restore snapshots the replaced file first (`.pre-restore-*`),
  and reloads live state when the file belongs to the current map.
- **Corrupt-sidecar recovery.** Broken sidecar JSON is quarantined as
  `*.corrupt-*` (logged, never silently discarded, never fatal).
- **Schema versioning.** Map saves and all sidecars stamp `schema: 1`;
  old unstamped docs migrate forward; bundles needing a newer app
  refuse with a clear "update the app" message.
- **Tiled export.** `/api/export/tiled` (Tiled JSON, gid = used-tile
  order) + `/api/export/tileset.png` (the 8-column art strip).
- **Shareable bundles.** `/api/bundle/export` builds `.crumbs.zip`
  (map + sidecars + Tiled + tileset + manifest with app version and
  schema); `/api/bundle/import` installs under a fresh unique name,
  validates JSON, rejects path traversal and unexpected members.
- **Template starters.** `/api/templates` lists `template-*` maps.
- **Generation presets.** Six named recipes (Archipelago, Highlands,
  Dune Sea, Frostwild, Deepwood, Undercrypt); same seed + preset =
  same map, verified byte-identical. Picker in Setup, preset rides the
  map's saved metadata.
- **Entitlement-aware packs.** `*.pack.json` may declare
  `"entitlement": "paid"`; paid packs load only when `entitlements.json`
  (user data, gitignored) grants them. `/api/entitlements` catalog.
- Packaging docs: LICENSE (Free/Creator/Pro), COMMERCIAL_TERMS.md,
  POSITIONING.md, persona docs, roadmap (Now/Next/Later), landing draft.
- `requirements.txt` pins `pillow==12.3.0` (security fix, via the
  merged hardening PR).

## v5.15 — 2026-09-20

- Lloyd's signature shield on the splash screen (embedded art, no extra
  file to carry).

## v5.14 — 2026-09-20

- Drop-in art packs: any `custom_tiles/*.pack.json` loads additively;
  pack entries never merge into `custom_tiles.json`, and removing the
  pack files cleanly uninstalls it.
- Large pack groups auto-collapse in the palette.
- Minecraft InvSprite pack sliced (3,647 sprites, personal use only —
  not in the repo, not licensed for redistribution).

## v5.13 — 2026-09-20

- Items: weapons, tools, food, trinkets. Tile-based, named, stackable
  (99 max; weapons/tools don't stack).
- Ground placement, pickup, eat/use, drop, equip/unequip. Hero pack,
  gold, equipped weapon and tool — persisted per map, survives restart.
- NPCs: villagers and merchants with names, greetings, positions,
  equipped weapon/tool, and per-map records.
- Merchants: finite and endless stock, prices, buy/sell with gold
  checks, sold-out handling. Shops open from adjacent interaction.
- Editor: Items sheet, Folks sheet, placement tools, NPC gear and stock
  editors, play-mode Pack sheet, gold/equipment HUD, shop sheet.

## v5.12 — 2026-09-20

- Melody's mission workshop: she lives in the editor, not the game.
- Preset library (reach, waypoints, gatherer, survivor, beat-the-clock)
  with a short questionnaire per preset: name, difficulty 1–5, reward,
  targets, counts, ticks.
- Difficulty tiers drive enemy flow: hazard patrols near objectives
  (0–4 by tier), mean critters, hazard ground that costs health.
- She playtests every objective herself (reachability including cliffs)
  and reports blockers in plain language.
- Objective HUD, per-step checks in play mode, win/fail messages.
  Missions ride the map sidecar. Tier 0: deterministic and offline.

## v5.11 — 2026-09-20

- Sprite-sheet importer: 8/16/32px slicing, PICO-8 preset, role
  assignments, animation strips, nearest-neighbor upscale, multi-sheet
  per-layer mixing.

## v5.10 — 2026-09-20

- Height/elevation system: numeric tile heights (deep water −2, water
  −1, plains 0, hills 1, mountains 2; walls +1), editable per tile.
- Drives shadows, scaled tall faces, climb costs, cliff blocking, line
  of sight, height overlay, and a play-mode sight toggle.
- Starter pack grows 92 → 100 with hills and mountains.

## v5.9 — 2026-09-19

- Curated starter tile pack (92 Utumno cells); the full 6,038-cell
  library becomes opt-in instead of the default.

## v5.8 — 2026-09-19

- Synthesized sound effects via Web Audio (zero audio files) plus Setup
  sound controls.
