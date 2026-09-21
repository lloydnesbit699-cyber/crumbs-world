# Changelog — Crumbs HUD

All notable changes, newest first. Phone-verified means Lloyd ran it on
his iPhone; anything else is verified on desktop/server only.

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
