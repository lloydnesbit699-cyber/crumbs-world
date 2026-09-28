# Changelog — Crumbs HUD

All notable changes, newest first. Phone-verified means Lloyd ran it on
his iPhone; anything else is verified on desktop/server only.

## v5.50.14 — 2026-09-28

**Budget strip rests during play.** It sat at the exact top-left corner the
meters pill covers in play mode (z-58 under z-60) — dead UI peeking out from
behind the pill. It now hides when a run starts and returns when editing
resumes, budget counts and tap-to-undo intact. Top-bar undo/redo untouched.
Still open: two-finger pinch zoom.

## v5.50.13 — 2026-09-28

**Undo/redo unburied.** The play-mode pills sat on top of the top bar
(z-60 over z-45): the 🪙🎒 gear pill covered the undo/redo cluster at the
bar's right end, and the ❤️✨ meters pill could overlap the bar on notched
screens. Both now hang just below the bar (notch-aware).
Still open: two-finger pinch zoom.

## v5.50.12 — 2026-09-28

**Pack stops piling onto the zoom buttons.** Its default spot (bottom:96px)
sat in the middle of the zoom cluster (−/+/Fit/Move own the bottom ~230px
on the right). It now parks above the cluster by default; drag still moves
it anywhere and the spot persists. (Lloyd's screenshot: Pack on +/Fit, Mel
on PANELS — Mel's been draggable since v5.34, so that's his parked spot.)
Still open: two-finger pinch zoom.

## v5.50.11 — 2026-09-28

**Starter gear kit.** Every map now begins with seven defined, pickup-able
items: Rusty Sword, Worn Dagger, Old Shield (ward), Smoked Meat, Apple, Red
Potion, Traveler's Scroll — all using curated starter-pack tiles. Seeded
once, when the map's items sidecar doesn't exist yet; a library the
builder empties on purpose stays empty. Still open: two-finger pinch zoom.

## v5.50.10 — 2026-09-28

**The Pack button drags.** It kept sitting under Lloyd's thumb in play
mode. Tap still opens the pack sheet; a drag parks it anywhere on
screen, and the spot persists per device like the Play and Melody
buttons. Still open: two-finger pinch zoom.

## v5.50.9 — 2026-09-28

**D-pad taps step once.** A quick tap could outrun its own release: the
step's repeat timer was scheduled after the server answered, by which
time the finger was already up and the clear had missed it — so a tap
kept walking on its own. The repeat chain now only continues while the
button is physically still held. Hold still walks, double-tap-hold still
runs. Still open: two-finger pinch zoom.

## v5.50.8 — 2026-09-28

**Play button stops burying tiles.** The draggable Play button now dodges
open panels like the Melody button does (steps right of the left tray,
left of the right tray, above the bottom sheet) and hands back its parked
spot when they close — it can no longer be dropped somewhere that traps
tiles underneath it. The tray dodge also learned about the left tray, so
both floating buttons clear it. The palette's subcategory chip row
(All/Walls/Floors/Doors/…) gets the same scroll hardening as the File
menu so chips past the tray edge stay reachable. Still open: two-finger
pinch zoom.

## v5.50.7 — 2026-09-28

**File menu scrolls.** The top-bar dropdowns get a `100vh` max-height
fallback (an unsupported `100dvh` silently dropped the height cap, leaving
no scroll container at all) plus an explicit `touch-action: pan-y` so the
scroll gesture can't be negotiated away. Still open: two-finger pinch zoom.

## v5.50.6 — 2026-09-28

**Map size, findable.** The Tools panel's leftover "Setup" section heading
(a ghost of the retired Setup menu) is now "Map" — the width × height +
Resize row lives there, under the map file name. Still open: two-finger
pinch zoom.

## v5.50.5 — 2026-09-28

**Scatter toast points at the open panel.** Arming the scatter brush with
an empty mix now opens the Tiles panel itself (both tray and sheet
layouts) so the ＋ and the palette are on screen — the old "tap + below"
toast was pointing at a closed tray. Still open: two-finger pinch zoom.

## v5.50.4 — 2026-09-28

**Play button drags; paint panel fits; look defaults exist.** Three of
Lloyd's phone reports in one pass: (1) the green Play button is draggable
now — long-press still compares animation, tap still plays, but a drag
moves it anywhere and the spot persists per device; (2) the paint tray's
layer row (Ground/Walls/Objects/Routes/FX) no longer clips at the tray
edge — the five buttons share the width; (3) the Advanced drawer has a
⭐ Save as defaults button — Floor/Wall/Water looks, shadows and decor
become every new map's starting point (per-map settings still win once a
map has its own; saved per vault, never in the repo). Still open: the
stale popup text pointing at the retired panel (need the exact words),
and two-finger pinch zoom.

## Unreleased

## v5.50.0 — 2026-09-28

**Melody walks into the dungeon.** She is a character in Play mode now: when
a run starts she spawns on the nearest walkable tile to your spawn (new
read-only `/api/play/melody_spot` endpoint — ring-by-ring search, no run
state touched) and waits there. No patrol — she's waiting for *you*. Walk
within 2 tiles and she says hello (once per run); a 💬 Talk to Mel chip
appears while you're close. Three doors into the same conversation: the
chip, tapping her tile while standing next to her, or the 💜 FAB — all open
her dock through one `openMelDock()`. On screen she's unmistakable: purple
glow ring, 💜 overhead, "Melody" nameplate, drawn even if her body tile is
missing (she wears a "melody"-named tile if the map has one, else a fellow
character, else your hero's tile). Pockets keep their own cast — she stays
in her home world and walks back in when you return through a portal.
Chat-only in the world: Law 18 holds, she never touches the map from play.

## v5.49.5 — 2026-09-28

**The little [x] on every panel.** Lloyd wanted tap-the-map-to-close back —
with the side trays it already rides along (the scrim eats the tap and closes
the tray, same as the old days) — plus a small [x] as the explicit backup.
Both trays now end their module tab bars with an × that closes the overlays,
and the bottom sheet carries an × in its grabber row that dismisses it to the
closed detent; the × stops its own pointer so the grabber never mistakes the
tap for a resize/drag. Reopening is unchanged: edge tabs summon trays, TILES
summons the sheet.

## v5.49.4 — 2026-09-28

**The panels stop caring where they live.** Lloyd liked the side panels
better, and patching the bottom sheet had turned into surgery on surgery —
so the panels got modularized instead. Tiles, Paint, Inspector, Animation,
NPC/Patrol, Melody-suggest and Tools are now self-contained content modules;
the bottom sheet and the side trays are interchangeable renderers behind one
`PanelSys` facade (open, close, mount, render). Layout is a saved per-player
setting in the panel visibility sheet — **Sides ◀▶** (Lloyd's pick, and the
default) or **Bottom ▲** — instead of a structural rewrite. Same DOM nodes
move between renderers: no duplicate controls, state, listeners, or Melody
backend. Sheet-only behavior (detents, dismiss drag, brush-bar docking, Mel
FAB dodge) stays inside the sheet renderer; the tray renderer gives each
side its own tab bar and steps the Mel button left of an open tray. Play mode
closes/restores whichever renderer is active. Static client test
`panel_system_test.js`: 39/39; all 20 neighboring JS suites green.

## v5.49.3 — 2026-09-28

**The Mel button waits its turn.** `melodyInit` unhides the button mid-boot,
so on every logged-in load it floated over the splash/title screen (its
z-240 sat above the splash's z-200). The button now lives at z-190 — below
the splash and below the login/2FA/users overlays — and only appears once
boot hands the screen over. The open chat dock stays above everything, so a
tapped-open conversation is never trapped behind a boot screen. Static
client test `melody_fabdodge_test.js`: 16/16 (4 new layering checks).

## v5.49.2 — 2026-09-27

**The tile panel minds its manners.** Two real defects Lloyd caught on his
phone: (1) the bottom sheet could never be dismissed — tapping the grabber
cycled peek/half/full forever and dragging down clamped at peek, so the only
way out was Play mode; now a deliberate drag down past peek closes it, and
the TILES edge tab reopens it. (2) Modal dialogs (update, save slots, server
log, recovery) and the scrim rendered *under* the tile panel, so the update
dialog's "Install update" couldn't be tapped while any panel was open — the
layer stack is now menus (75) > modal sheets/trays (70) > scrim (66) > tile
panel (60). Static client test `sheet_dismiss_test.js`: 10/10.

## v5.49.1 — 2026-09-27

**The Mel button gets out of the sheet's way.** The draggable Mel button's
parked spot persisted even when it sat on top of the open bottom sheet,
covering brush sizes, tabs, and panel buttons. Now every sheet open, detent
change, and page load checks: if the button would cover sheet content, it
steps just above the sheet's top edge (aimed at the detent's target, since
the sheet animates). The dodge is never saved — the parked spot survives
underneath and returns when the sheet closes — and a manual drag always
wins. Static client test `melody_fabdodge_test.js`: 12/12.

## v5.49.0 — 2026-09-27

**Melody the playtester (Lloyd's favorite).** Ask her "is this playable" and
she walks your dungeon dozens of times: a flood-fill from spawn over the
collision layer (unreachable painted cells, unwinnable goals), plus seeded
Monte Carlo random walks (dead zones no walk ever visits, hazard exposure
per walk). The seed comes from the map file, so a re-run on an unchanged
map reports the same numbers. Read-only by contract — she never edits the
map she tests; Law 18 (your vault only). New `melody_playtest_test.py`:
22/22.

## v5.48.0 — 2026-09-27

**Melody moves in: hands, eyes, and a proposal pen (co-build).** She was a
charming teacher who couldn't see your game — now the HUD posts a compact
snapshot of the live game with every chat message (map dims, cursor, open
panel, budget, placed characters), and the agent treats it as labeled data,
never instructions. New `tile_lookup` tool (shared library + your customs).
Two new ghost-suggestion kinds: `room_draft` (she drafts a dungeon_room or
boss_arena with the HUD's own room layout — the ghost preview and the accept
stroke come from the same `roomPresetCells`, so the preview never lies) and
`patrol_draft` (she drafts a 2–8 stop route for a placed character; the
server re-validates anchor, stops, and walkability at accept time). Both
accept through the existing undoable endpoints — no new server routes, no
silent edits, Law 18 throughout. New `melody_cobuild_test.py`.

## v5.47.4 — 2026-09-27

**Panel transparency reaches the bottom sheet.** The v5.29 ◨ panel-visibility
control (opacity slider + hide-all) drives a `--panel-op` var and a
`body.panels-hidden` class, but both stylesheet selector lists keyed off
`.sheet` — and `#hud-sheet` never carried that class (its classes are the
peek/half/full detents). The sheet, the docked brush bar, and the ••• tools
silently ignored the transparency slider and survived hide-all. Both lists now
name `#hud-sheet` explicitly; children inherit, so the docked bar and
more-sheet ride along. New `panelvis_test.js`: 9/9.

**Signup 2FA row no longer blows out the card.** The "Protect with
authenticator app" checkbox was hit by `#login-box input { width: 100% }`
(ID specificity beat the 18px class rule) plus the global 44px touch sizing,
so it rendered card-wide and shoved its label text off the card on Lloyd's
phone. The full-width rule now excludes checkboxes, and the opt-in checkbox
resets the touch sizing and pins itself at 18px with `flex: 0 0 auto`.
New `logincard_test.js`: 8/8. Also made `hud_pass_test.js`'s version checks
read the newest CHANGELOG entry instead of a hardcoded string, so releases
stop tripping on stale expectations.

## v5.47.3 — 2026-09-27

**Brush bar docks above the bottom sheet.** The Phase-3 floating brush bar
(Stamp/Paint/Erase/•••) still sat at viewport-bottom with z-31 while the
Phase-5 sheet claimed z-60 — only the buttons' tops peeked out above the
sheet's grabber and the tools were unreachable. The bar (and the •••
more-tools sheet) now move inside `#hud-sheet` at boot and ride it as
absolutely-positioned children 12px above its top edge, so they stay fully
visible and tappable in peek/half/full and slide off-screen with the sheet
in play mode (correct — paint tools rest while playing). The always-visible
Play FAB steps up to 144px in peek so it never overlaps the docked bar; it
keeps its classic 84px spot in half/full/closed. Safe-area handling is
unchanged: the sheet keeps its `env(safe-area-inset-bottom)` padding and the
docked tools anchor above it, never under Safari's toolbar. Touch
arbitration is untouched (canvas gesture logic is independent of the bar's
parent).

## v5.47.2 — 2026-09-27

**Boot black-map fix + last map per player.** v5.47.1 shipped a boot-killing
`ReferenceError`: the new `peekInfo()` (bottom-sheet peek line) read
`semLayer`, a variable that was never declared anywhere. Every launch died
inside `initHudSheet()` → `renderSheet()` → `peekInfo()`, so `refresh()`
never ran — the map canvas stayed blank over the near-black `#stage` and the
budget strip kept its placeholders. The peek line now reads the dock's real
layer, `logicalLayer`. Also at boot: the budget strip (always visible since
v5.47) is populated via `refreshBudget()` instead of showing dashes until the
first undo/paint.

Lloyd's other ask: **the map you were on comes back on login/reload.** The
current map file is remembered per player in localStorage
(`crumbs.lastMap.<username>`, `"local"` in single-user mode — Repair Law 18:
one player's key never steers another's vault), updated on every map switch,
portal enter/warp, save, and Save As. At boot — after auth, before the first
refresh — the stored map is reloaded; a stored name that no longer exists is
forgotten and the default `hud_map.json` keeps the previous behavior. New
regression tests: `lastmap_test.js` (23 checks: the `semLayer`
ReferenceError, per-user key isolation, stale-map fallback, boot wiring).
Full boot verified end-to-end against the live server (map paints, canvas
sized, zero console errors).

## v5.47.1 — 2026-09-27

**Melody's animation suggestions.** The ghost-suggestion system grows a third
kind: `animation_preset`. She can now propose a motion for the tile under a
spot ("make the torch flicker") — the preset merges onto the tile and PLAYS
on the map as the ghost, ringed in violet. ✅ Do it saves through the same
endpoint a manual card tap uses (hold ▶ still compares before/after), Not now
evaporates the ghost back to the old motion, and an accepted suggestion leaves
a one-tap ↩ Revert motion card until the next sketch or a manual edit. She
suggests — she never paints silently, and animation stays outside the tile
undo stack by design (motion has its own before/after). Server:
`_suggest_animation_target` (topmost instance whose tile is an imported tile
with frames, else the suggestion stays unmaterialized) + the
`animation_preset` branch of `_melody_suggestion_view`; Melody's
`suggest_map_change` takes a `preset` (alive/bounce/float/pulse/shake/magic),
validated before anything is recorded.

Not phone-verified yet — desktop/server verified; Lloyd's iPhone run pending.

## v5.47.0 — 2026-09-27

**The HUD pass: one bottom sheet, budget strip, always-visible Play.** Phase 5
of the roadmap — everything floats into a single context-sensitive bottom
sheet with peek / half / full heights (tap the grab to cycle, drag to snap):
the tile tray, the object inspector, the animation panel, and the v5.46
conceptual-layer ribbon now switch by selection like a Godot/Unity inspector,
and the old permanent left tray + semantic dock retire. The map stays
tappable under the sheet — it's non-modal.

- **Budget strip** — a slim persistent bar: tiles placed, NPC count, FX
  budget, undo/redo depth. Tap it to undo. Budgets are SOFT (400 animated
  cells, 20 patrols): the strip warns, never blocks.
- **Always-visible Play** — one floating button, bottom-left. Tap to walk
  the map (camera AND selection are snapshotted on entry and handed back
  exactly on exit); hold for a quick before/after of the current animation.
- **NPC event cards** — patrol routes render as numbered pins joined by a
  route line; tapping a pin opens a plain-words card ("wait here: sleep,
  30s", "at stop 3 → Talk") with two fat buttons per stop (cycle the wait,
  flip the pose). Raw timers stay off the beginner surface.
- **Room presets** — one-tap 🏠 Dungeon room (11×9, 2-wide south door) and
  🏰 Boss arena (15×13, four pillar stubs, north+south doors), planned as
  semantic strokes so edges/collision resolve; editable after, one undo.
- **Melody's ghost suggestions** — she can now propose a reversible ghost
  preview (`suggest_map_change`: wall rings around floor regions with a
  south door gap, or joining two near-touching patrol routes). The ghost
  renders on the map in violet; ✅ Do it paints through the normal undoable
  endpoints (one tap on ↩ reverses it), Not now declines. She proposes —
  she never paints silently. One pending suggestion per vault (Law 18:
  vault-scoped, the Agent Sees Only Its Player).
- Server: `/api/semantic/stroke` batch mode (≤8 strokes, one undo),
  `/api/patrols/merge` (two routes become one, pauses ride by coordinate,
  atomic), `/api/melody/suggestion` (+ decline), undo/redo depths on
  `/api/status`.

Not phone-verified yet — desktop/server verified; Lloyd's iPhone run pending.

## v5.46.0 — 2026-09-27

**Semantic painting: paint MEANING, the engine resolves the tiles.** Phase 4
of the roadmap. A new conceptual-layer dock (Ground / Walls / Objects /
Routes / FX) sits above the brush bar — five fat buttons name what you're
painting, and the palette row under them carries only that layer's brushes:
Floor / Water / Clear on Ground, Wall / Clear on Walls, Walkable / Blocked /
Hazard on FX (collision as paint — big modes, never polygons), while Objects
and Routes hand off to the existing object palette and patrol flow. Two faces,
same grids: the logical layers map onto the tiles/objects/collision grids
underneath, never a forked data model.

Underneath, a deterministic engine (mirrored bit-for-bit in JS so ghost
previews match what the server commits — the node suite asserts parity over
thousands of cases): paint a wall and the engine tags the cell, picks a
concrete wall tile from the starter pool (FNV-1a hash of seed+x,y), blocks
collision, derives 8-neighbour edge masks into light-catching wall faces and
gradient shadows with inner corners on neighbouring floor, and sprinkles
auto-decor (pebbles, flowers — never chests) on floor interiors only, at a
density control. Meaning-erase restores the seed's natural tile. Shadow
strength, decor density, per-terrain variant selects (Mixed or one concrete
tile), and a re-paint-details automap live in the ⚙ Advanced drawer; the
👶/🛠 face toggle keeps plain words for beginners. One stroke is one undo
step, including settings changes; undo/redo, resize, and save/load carry
the tag + hazard grids and the rule controls (old saves load clean).

Not phone-verified — the dock layout, ghost shadow previews, and the
10×10-room speed target need Lloyd's on-device testing.

## v5.45.3 — 2026-09-27

**Brush-bar polish + a real tool-state bug fix.** The stamp shape
default was keyed `"2x2"` while the shape table uses `"b2"` — the
picker silently fell back every boot; it now defaults to the 2×2
footprint for real. Fixed a sneakier one: arming Height, Traits, or
Portal while the eraser or select brush was active silently switched
the new tool back off (the brush-resting path re-rested the tool being
activated). Tool activation now skips the modal rest, so the tapped
tool is the armed tool.

Smaller phone touches: the magnifier now tracks the fingertip on every
move (not just on new cells), haptic ticks confirm tool switches, the
more sheet, the long-press menu, and stroke commits (guarded — iPhones
simply ignore vibrate), the undo button is a full 44px thumb target,
and the scatter density clamps a stale 0% back to the 60% default
instead of silently painting nothing.

Not phone-verified — haptics and the magnifier tracking especially
need Lloyd's on-device testing.

## v5.45.2 — 2026-09-27

**Height sculpting joins the ghost club.** The height/depth tool was the
last brush still painting live into the grid mid-drag — it now
ghost-buffers like every other brush. Drag to sculpt and the pending
levels render as a tinted preview (warm for raise, cool for lower, gray
for clear) with the same gold footprint outline; the terrain underneath
stays untouched until the finger lifts, when the whole drag commits as
one server call and one undo step. A two-finger pan mid-sculpt now drops
the preview with no map refresh at all — there is nothing to revert.

Not phone-verified — the sculpt preview especially needs Lloyd's
on-device testing.

## v5.45.1 — 2026-09-27

**Touch arbitration + the long-press menu.** The gesture language is now
one rule everywhere: one finger paints through the armed brush, two
fingers always win (pan/zoom, any ghost dropped), a quick tap fires
one-shot tools, and holding still ~half a second opens a contextual
menu at the fingertip — pick the tile here, inspect here, undo. Fill,
eyedropper, and the select inspector now commit on the quick lift
instead of on press, so a long-press can claim the gesture for the menu
instead of firing a fill you didn't want. The arbitration lives as pure,
unit-tested logic (tap vs drag vs hold vs pan, fat-finger thresholds).

**Animated palette tiles.** Torches, water, portals, and anything with
FX-layer motion now dance in the left tray — with zero new animation UI.
They repaint on the same 150ms heartbeat as the tray preview, only when
the tray is open, only for swatches actually on screen, and only when
their frame signature changed, so the 6k-tile lazy loading is untouched.

Not phone-verified — the long-press timing and menu placement especially
need Lloyd's on-device testing.

## v5.45.0 — 2026-09-27

**The touch painting toolkit — stamp brush as the hero.** The map keeps
exactly 4 tools visible now: a floating brush bar with Stamp, Paint,
Erase, and ••• More (tap or long-press ••• for the rest). Stamp is the
default: pick a footprint in the tray's stamp picker — Single, 2×2, 3×3,
Corner, Ring, Plus — and it stamps whatever tile is selected, clipped
cleanly at map edges. Drag to stamp continuously; one stroke is always
one undo step.

**Commit-on-release + the brush scope.** The fingertip occludes its
target, so every brush now buffers into a ghost preview (65% + gold
footprint outline) and lands on the grid only when the finger lifts.
While you drag, a magnifier floats above the fingertip showing the
footprint at 3× over the real map. Bonus: a two-finger pan/zoom can no
longer catch a half-painted stroke, and cancelling one no longer costs a
full map re-download.

**Scatter brush.** Random texture without repetitive taps: build a mix
of up to 6 palette tiles in the tray (tap ＋, then palette tiles; tap a
chip to drop it), set the density slider (10–100%), and drag. The mix,
density, stamp shape, and rectangle-fill choice persist on the device.

**More tools, one long-press away.** Fill (bucket — flood-fills the
matching area, one tap, capped at 100k cells), Eyedropper (picks the
tile off the map, then hands the brush straight back), Line and
Rectangle (press-drag-release with a live ghost; rectangle has an
outline/filled toggle), and Select (inspect instead of painting).

Not phone-verified — the gesture and magnifier work especially needs
Lloyd's on-device testing.

## v5.44.0 — 2026-09-27

**Advanced animation Phase 2: the filmstrip.** The Animation menu's
Advanced mode grew an Aseprite-style, phone-first filmstrip — a
horizontal row of big 96px cards, one per frame, each with its own
duration badge. Tap a card to pick the frame up; ⧉ duplicates it, 🗑
deletes it, and the frame editor below moves it earlier/later, retimes
just that frame, or gives it its own tint (hidden behind an explicit
"tint: off/on" advanced switch). A scrubber and play/pause transport
sit under the strip, and onion skinning (off by default) ghosts the
previous frame red and the next green — never during playback.

**Non-destructive FX layers.** Bounce, Float, Pulse, Shake, and Aura are
now stackable layers under the state controls: tap ＋ to add, 👁 to
eye-toggle, ▲▼ to reorder, drag the strength slider, and Aura's color
chip cycles the palette. Layers render non-destructively on top of the
base art — the tray preview, the map, and the exports all run the same
stack, and a tile with layers counts as animated everywhere. Up to 8
per state.

**Auto tweening.** A per-state tween slider (0–4) adds in-between frames
between poses — rendered as crossfades in the preview, the map, and
exports. Each frame's time slot splits into equal ticks, so the loop
keeps its total duration and just gets smoother.

**Export the animation, share it whole.** Four export buttons render the
state through the full stack (per-frame mods → H/S/B → act → FX layers
→ tween): animated GIF, PNG-sequence zip, sprite-sheet PNG, and a
single-file JSON doc. The JSON doc carries the tile's raw base frames
plus the full anim record — importing it on another Crumbs install is
a lossless round-trip (pixel-identical art, identical record).

**Beginner and Advanced still share one record.** A beginner card tap is
now a merge, not a wipe: the card dresses idle+walk while every Advanced
edit (frame lists, per-frame mods, FX layers, tweening, other states,
transitions) survives — and Advanced edits show up when you flip back.
Records stamp v2 when the new filmstrip fields are present; old v1
records keep working untouched.

## v5.43.0 — 2026-09-27

**Beginner animation: six live preset cards, and every result stays
editable.** The Animation menu's Beginner mode grew six big tap-target
cards — 🌿 Still Alive (subtle breathing), 🦘 Bounce (squash & stretch),
🎈 Float (gentle hover), 💓 Pulse (soft color throb), 📳 Shake (tiny
tremble), ✨ Magic Aura (colored glow). Each card shows a LIVE thumbnail
of the target tile dancing that motion, plus one feel slider (0–100)
that retunes him in place as you drag. Tapping a card dresses the tile
in real frames + settings — flip to Advanced and every knob it wrote is
there to tweak. Nothing is a dead-end render.

**Bring to life bakes the motion in.** The one-button flow now takes the
picked card along: a single picture gets tweened in-between frames of
the preset's motion generated on the server (6 real, editable frames —
breathing, squash & stretch, drift, color throb, tremble, or a baked
aura glow); a real multi-pose sheet keeps its sliced poses and the
preset rides on top as editable parameters. The last-tapped card is
remembered for the next import.

**Animation as states, one model for both modes.** Underneath, every
tile's motion is now Rive-style states — Idle / Walk / Sleep / Talk /
Hurt / Magic — with transitions (idle↔walk blends over ~150–200ms), all
stored in one `anim` record that Beginner and Advanced read and write
together (Phase 2's filmstrip will build on the same record — the modes
were not forked). The Advanced panel gained a state picker (which moment
you're dressing up) and an intensity slider; the old per-tile color /
action / magic controls now edit the tile's default state and stay in
step with it, so old saves render the same. One deliberate redefinition:
Pulse is now the conservative H/S/B throb from the spec — the old
scale-throb lives on as the Still Alive motion (new `alive` action).

**Patrol stops trigger states.** A sleeping pause now puts the walker in
the Sleep animation state; a standing pause maps to Idle; walking
resumes the Walk state with a blend. Each stop row also has its own
state picker — "at stop 3 → Sleep" (or Talk, Hurt, Magic…) — saved with
the pauses. The 💤 still bobs over sleepers.

Nothing phone-verified yet — desktop/server tests only (54 new
animation-preset checks, 32 client state-model checks, 11 new patrol
state checks pass; see below). iPhone behavior unverified.

## v5.42.1 — 2026-09-27

**Scale hardening: undo, caches, and history depth.** Big maps
(500x500) used to keep two full copies of every grid per undo step
across a never-evicted 50-deep stack — close to a gigabyte of retained
state. Undo steps are now cell diffs: only the cells a stroke actually
touched are kept (plus the small design state), with full snapshots
reserved for generate / reset / resize. Patrols, rules, portals,
neighbors, names, and world-profile edits keep metadata-only steps with
no grid data at all.

**Cached expensive grids.** The height grid (~1s at 500x500) is cached
by a grid revision that bumps on every mutation; undo/redo restore the
revision, so stepping back and forth is a cache hit instead of a
recompute. The seed's natural-color grid is cached by
biome/seed/dimensions/noise-recipe (4 entries) and cleared on
generate, overlay, reset, resize, tile-art changes, and vault switches.
Map thumbnails for the picker are cached on disk (`.map_thumb_cache/`,
gitignored) keyed by map file + mtime — editing a map invalidates its
thumbnail automatically.

**History depth follows map size, and idle stacks are evicted.** Maps
wider than 80 tiles keep 25 undo steps instead of 50; undo stacks idle
for 30 minutes are dropped. `WorldMap.save` also writes compact JSON
now (no more `indent=2`).

Nothing phone-verified yet — desktop/server tests only (52 new
scale-hardening checks pass; see below). iPhone behavior unverified.

## v5.42.0 — 2026-09-27

**Portals link to any map, with a landing spot (Lloyd's call).** The
portal editor now offers every existing map in a picker (or a typed
filename), plus optional Land-at X/Y coordinates — the hero arrives
exactly where you say, or on an automatic walkable spot when blank.
Blank target still generates a seeded pocket map with a return portal,
as before. Legacy `return_xy` portals migrate to `spawn` on load and
are written back in both forms, so old saves keep working.

**N/S/E/W neighbor maps.** Each map can link one neighbor per edge
(North, South, East, West) in the new Neighbors section of the Load
sheet. Walking off a linked edge (D-pad) crosses into that map on the
opposite edge, keeping your along-edge position (clamped when the maps
are different sizes). An unlinked edge is a wall; a link to a deleted
map toasts a clear "broken link" message instead of moving.

**Pocket/interior map flags + grouped map picker.** Maps carry a kind
(overworld / pocket / interior), changeable from the Load sheet's Kind
button; the picker lists Worlds first, then Pockets & interiors.
Generated pocket maps are flagged automatically.

**Phone-first map manager.** The Load sheet grew a + New button
(name + W×H prompt, creates a blank map without touching the live one),
kind badges, and the neighbor editor — all fat-finger friendly.

**Robustness.** Neighbors live in a `.neighbors.json` sidecar that
rides rename/copy/delete-to-trash with the map; portals and neighbors
are now vault-scoped (no cross-vault leaks) and undoable; `/api/maps`
entries carry `kind`; `/api/maps/import` accepts up to `MAP_MAX`
(500, was 256).

**Tests.** New `portal_test.py` (32) and `portal_client_test.js` (25)
cover spawn sanitize/legacy migration, neighbor sanitize, edge-arrival
math, nearest-walkable, broken-link notices, pocket kind flags, sidecar
round-trips, and client wiring. Existing suites still green
(auth 96, melody 84, hardening 48, patrol 23, scale 23, scale-client
20; core smoke 9/10 — the one failure is the pre-existing
sprite-library round-trip on the pristine tree).

Not phone-verified: iPhone behavior is unverified until Lloyd updates
and tests on-device.

## v5.41.0 — 2026-09-27

**Map cap raised to 500×500 (Lloyd's call) with full scale hardening.**
The old 64×64 ceiling is gone: `MAP_MAX = 500` is now the single source of
truth (was hardcoded in four places — resize dialog, `/api/resize`,
generate/pocket-map endpoint, portal sanitize). A 500×500 map holds 250k
cells; measured save is ~12MB / ~0.5s, generate ~0.8s.

**Renderer rebuilt for huge maps (client).** The old renderer redrew all
250k cells and ran a full-grid checksum on every frame — unusable past
64×64. Now: the static base layer redraws only the dirty rect a stroke
touched (expanded 1 cell for tall faces/shadows); every per-frame overlay
(animated tiles, collision, height, traits, fog, object markers) walks
only the visible cells; the hero-flag scan is cached and invalidated on
paint/undo/refresh. Zoom is capped so the full-map backing canvas never
exceeds 4096px per side (8px tiles on a 500×500 map — the largest canvas
safe on every iPhone); the zoom button says so when it stops.

**Painting no longer re-downloads the map.** `/api/stroke` echoes the
server's resolved cells (authoritative values, incl. linked collision
stamps); the client applies them to its optimistic preview. The old
"full refresh after every stroke" (~12MB at 500×500) now runs only when
a stroke fails or comes back without an echo.

**Server-side guards.** Dijkstra pathfinding is bounded (100k visited
nodes — a walled-off target on a huge map can't hang a patrol leg);
fog-of-war sight is radius-limited (40 tiles) on maps wider than 80
(full-map sight was ~13s at 500×500); PNG export shrinks tile size to fit
4096px instead of building a 64k image (~16GB RAM).

Tests: scale_test.py 23/23, scale_client_test.js 20/20. iPhone
verification pending — nothing here is proven on his phone yet.

## v5.40.1 — 2026-09-27

**Removed the duplicate Bring-to-life button from the import block.**
The v5.37.0 redesign made the top Animation menu the animator's one home,
but a leftover `#import-animate` button (same handler) stayed behind in the
import block. It's gone now — CSS rule, element, and both JS references
removed; the Animation menu's beginner button is the only path and still
shares the same `bringToLife()` handler. Import block keeps: file picker,
previews, background-removal row, frame-timing row, name, presets, scope,
Add/Cancel. No behavior change.

**Map size verification (no change):** the enforced maximum is **64×64
tiles** — client resize dialog (`max="64"`), `/api/resize` server clamp,
and the generate/pocket-map endpoint all agree. Resize dialog defaults to
25×15; the generate endpoint defaults to 16×16. No "148" exists anywhere
in the code; changing the limit is Lloyd's call.

## v5.40.0 — 2026-09-27

**Patrol stop pauses with user-settable timers (stand/sleep) + pause-to-interact.**
Lloyd's spec: every patrol stop gets a pause timer — tap ⏸ on the
character's inspect card to cycle off → 3s → 10s → 30s → 1m → 2m → 5m —
and a pose: 🧍 stand (holds the spot, idle) or 😴 sleep (long rest, with a
bobbing 💤 overhead). The timer runs on the wall clock, applies whichever
direction the walker arrives from, and survives slept tabs; tapping him
mid-pause never disturbs it. While he rests he's **interactable**: walk up
(or tap him while adjacent) and he says hello — his set-text, his mentor
line, or a simlish mumble if nothing's scripted — once per stop-visit, then
he walks on when the timer ends. Pauses persist with the route (new
`/api/patrols/pauses`, undoable, survives restarts). The anchor cell stays
the server's territory so greetings never double-fire.

## v5.39.0 — 2026-09-27

**Automatic background removal on import (Melody-gated).** Lloyd's rule in
code: automatic when the subject is clear, never a guess when it isn't.
Every imported picture now runs a corner/edge flood-fill with a conservative
tolerance (4-connected, pixel-art-safe). Confident cuts apply themselves and
offer an **Undo** that restores the exact original bytes; ambiguous pictures
(noisy corners, dirty edges, all-background) are left untouched with a
**Remove background** button instead. The same algorithm lives server-side
in `melody_agent.py` as the `remove_background` tool, so Melody can cut the
background of any of the player's own tiles on request — it declines on its
own when it can't tell the subject from the background, and never touches
the shared library. A refresh hook re-registers the tile's in-memory art
under the vault lock so the cut shows immediately.

## v5.38.1 — 2026-09-27

**Thumbnail privacy hardened.** The v5.27.3 lock-skipping race was fixed in
v5.29, but two holes remained in the thumbnail path: (1) `/api/thumb`
answered `Cache-Control: public` on vault-scoped bytes — two users can hold
different private art for the same tile id at the same URL, so a shared
cache could have cross-served them; now `private`. (2) A write-key request
with no session and no owner record sailed through `_auth_activate` on
whichever vault happened to be active — now denied with 403 instead of
inheriting the ambient vault. 13 new tests pin the interleave (snapshot
under vault A, serve after vault B activates — bytes still land in A's
dict), the private header, and the deny.

## v5.38.0 — 2026-09-27

**QR code for 2FA enrollment.** The signup-time "Protect with authenticator
app" step now shows a scannable QR code (the standard `otpauth://totp/`
URI) alongside the manual key — both encode the same server-issued secret.
Same treatment in Setup → 2FA, which had the same manual-key-only gap. The
QR encoder is hand-rolled and dependency-free (byte mode, EC level M,
versions 1–10): no external QR API is ever called, so the TOTP secret never
leaves the device/server. The rest of the flow is untouched — 10-minute
single-use pending ticket, six-digit confirmation, eight one-time recovery
codes, wrong codes don't consume the ticket, manual key remains as fallback.

## v5.37.0 — 2026-09-27

**The animator redesign.** The Animation menu is now the one home for every
animator control, with a 😊 Beginner / 🛠 Advanced toggle (remembered between
visits). Beginner keeps the one-button ✨ Bring to life. Advanced adds, for
the selected imported tile: frame timing (retimes his animation), color
(hue / saturation / brightness), action effects (bounce, float, pulse,
shake), and colored magic auras — changes apply live and save themselves,
so old tiles without these fields keep working untouched. The Tiles tray
grew a large live preview in its upper portion showing the selected tile
animated with his FX; the selected card, import, and palette still scroll
below it. FX renders everywhere the tile does: map, NPCs, objects, hero,
and preview, all through one drawing helper.

## v5.36.3 — 2026-09-27

**Inspector sheet fits the phone again.** The trait rows' value column can now
shrink (`min-width: 0`), so long descriptions wrap and the segmented buttons
compress instead of pushing the sheet wider than the screen — no more text
clipped off the right edge.

## v5.36.2 — 2026-09-27

**Update/repair can no longer lose vault data.** Every destructive git move
(`./ops.sh repair`, and the divergence repair inside `./ops.sh update`) now
snapshots `vaults/`, `users.json`, `.crumbs_secret` to `backups/` first (Law
of Three), and a new vault integrity check fingerprints the live data before
the risky part and verifies it after: custom-tile file count, user count, and
secret presence. Anything shrank or vanished prints a loud warning naming
exactly what changed and pointing at `./ops.sh rollback` — it never
auto-restores. The "your real work is safe" platitude is gone, replaced by
the actual check result. The user-count check also guards the fresh-empty-
vault scenario (accounts dissociated from their vaults).

## v5.36.1 — 2026-09-27

**Smooth dragging on content-heavy maps.** The two 150ms timers (weather and
sprite animation) used to force a full canvas redraw ~13×/sec even mid-drag;
on a large dungeon that saturated the main thread and made pan and paint
lurch. Timer redraws now pause while a finger is down on the canvas and one
catch-up redraw fires on lift. Drag/paint/render code itself is unchanged.

## v5.36.0 — 2026-09-27

**Phase 3: signup-time optional 2FA enrollment.**
- The signup form has a "Protect with authenticator app" checkbox (opt-in,
  never required, never SMS).
- Checked: the server validates the signup and parks it (10-minute
  single-use ticket, password never leaves the server), shows the TOTP key
  for the authenticator app, and only creates the account after a valid
  6-digit code — no confirmation, no account, no enrollment. The 8 one-use
  recovery codes are shown once, same as the Setup flow.
- Unchecked: signup works exactly as before; post-signup 2FA enrollment in
  Setup is untouched. Login enforces TOTP for signup-enrolled accounts
  through the existing 5-minute challenge path.

## v5.35.0 — 2026-09-27

**Phase 2: the morphing selection-aware Tools panel.**
- The right Tools tray now morphs into a traits editor for the current
  selection — palette brush or a placed instance the select tool parked on.
  Nothing selected: the tray shows exactly its old contents, unchanged.
- Per-tile-type traits, server-side and vault-wide (`tile_traits.json` at
  the vault root, Law 18 intact): weapons get damage, magic effect,
  magic cost/tradeoff, combos, attack and sneak behavior; characters get
  health, history/backstory, carry capacity and inventory; terrain gets
  exact elevation; every kind gets collision/environment exceptions and a
  "write your own rule" field.
- Per-instance overrides ride on the object cell (`traits` key, merge-patched
  through `/api/object-attrs`); resolution is instance > type > global.
- The rules are real, not cosmetic: a wall typed "walkable" opens for
  pathing (hidden doors), an "ethereal" walker patrols straight through
  walls (ghosts) via ghost legs on `/api/patrol-paths`.
- New **Weapons** chip leading the Objects group — seeded from the Gear
  sheet's weapon-kind items and import name hints, never hardcoded ids.

## v5.31.0 — 2026-09-26

Hardened Melody (both servers):

**Crumbs World Melody**
- Quota honesty: every real brain call burns one quota unit (was per-turn).
  Tool-heavy turns cost what they cost; mid-turn exhaustion says so honestly.
- Per-user rate limits: 20 chat/min, 10 voice clips/min (429 + retry_after).
- Prompt-injection tripwire: blatant override phrases get a fixed decline —
  no brain call, no quota burned, attack text kept out of her history.
- Tool allowlist + argument validation + Law 18 path choke point: every
  vault path is built from the authenticated username alone.
- Server-side input caps (32KB chat / 8KB demo); 8 tool calls max per round.
- melody_hardening_test.py: 48/48. melody_test.py: 66/66.

**Chromebook melody_server.py**
- Timing-safe token compare; empty key file now denies everyone (was an
  auth bypass). Request bodies capped at 256KB. Chat input validated.
- Errors no longer leak internals to clients. History bounded per client.
  Concurrent turns capped at 4. Slowloris socket timeout. Static path
  traversal fixed (encoded forms too). Boring Server header.
- melody-revive.sh / melody-tunnel.sh: stale pidfiles reaped, real ssh pid
  pinned, port-held-by-stuck-process reported instead of blind respawn.


## v5.30.0 — 2026-09-26

Public accounts — signup, sign-in, optional 2FA:

- **Sign up tab** on the login overlay: username + **email (required)** +
  password. Signed up means logged in. `DISABLE_OPEN_SIGNUP=1` closes public
  signup; the owner's Users panel still works as before.
- **Email** is validated and unique per account (one account per email).
- **Optional TOTP two-factor auth** (Setup → Two-factor auth…): authenticator
  apps, stdlib-only RFC 6238, ±30s clock-skew window. Setup shows the secret
  once; enabling shows 8 single-use recovery codes once (hashed at rest).
  Disabling needs password + a current code. 2FA secrets live in users.json
  next to the password hashes — server-side only, never logged or echoed.
- Login with 2FA on: password first, then a 6-digit code step (recovery codes
  work there too). A 🔐 marks 2FA accounts in the Setup menu.

## v5.29.3 — 2026-09-26

The Charter (Lloyd's founding document — non-negotiable across Melody,
Crumbs Vault, and Nesbits Fixit):

- **CHARTER.md** ships with the app: prevent harm > keep confidences >
  be helpful. She never seeks, stores, or repeats private intimate details
  (politely declines when asked); overheard words are unprivileged (not
  stored, repeated, or used); no leverage ever; the harm duty overrides
  confidence — silence about abuse is complicity.
- Melody now **lives by it**: the Charter is written into her system prompt,
  and she has a `charter` tool so she can quote it when asked what she
  believes. Morals before capabilities — the container doesn't loosen as
  she grows.

- **ops.sh: backup + rollback (Law of Three, law #19).** `./ops.sh backup`
  snapshots your live data (`vaults/`, `users.json`, `.crumbs_secret`) into
  `backups/`, keeping the 3 newest. `./ops.sh update` now backs up *before*
  pulling, so a bad update can immediately pull the last working state.
  `./ops.sh rollback` restores the newest snapshot (asks for RESTORE first)
  and snapshots the current state first, so the rollback itself is undoable.
  Three copies, each runnable: the server's rolling snapshots, the repo's
  history, and a snapshot downloaded to your phone.

## v5.29.2 — 2026-09-26

Melody bootloader (Lloyd's spec: she warms up before she thinks):

- **Boot phases.** `boot → warmup → ready` (plus `offline` if the health
  check fails). A status dot (🟡/🟢/⚫) in her panel header and a status
  line ("Melody is waking up…", "💄 Putting her makeup on…") show where
  she is — no more dead "initiating" box.
- **Governor.** Send and the mic refuse while she isn't ready, with a
  gentle "she's still getting ready" nudge instead of firing into the void.
- **No more re-reading everything every boot.** Her remembered
  conversation is cached per user (localStorage) — the panel paints
  instantly from cache, then refreshes from the server behind her back.
  Clearing the chat wipes the cache too.
- The makeup beat is ~1s (0.7s for the pre-login demo) — character without
  the wait.

## v5.29.1 — 2026-09-26

Melody voice fixes (iPhone-only bugs Lloyd caught on-device):

- **Her voice choked on iPhone.** The greeting tried to speak at login,
  before any tap — iOS Safari refuses speech synthesis without a user
  gesture, so it died instead of playing. Her voice is now gated behind a
  first-tap unlock (Mel button, Send, speaker toggle, or demo button all
  prime it); until then she stays text-only instead of glitching.
- **Panel vs keyboard.** Tapping Mel force-focused the text box, slamming
  the keyboard up over the bottom-fixed panel. Touch screens no longer
  auto-focus — tap the box when you want to type.
- Speaker toggle (🔊, mutes her voice) and mic button (🎙️, voice input)
  both live inside her chat panel.

## v5.29 — 2026-09-26

Editor-feedback batch (seven workstreams, all workspace-tested — NOT yet
phone-verified; iPhone/Chromebook/Replit checks are Lloyd's):

- **Thumbnails + painting.** Vault-scoped thumbnail cache (no more
  cross-vault tile-ID collisions); thumbnail fetch runs unlocked and in
  parallel; failed thumbs retry after 15s instead of staying `?`.
  Serialized paint queue — an old refresh can't wipe newer optimistic
  painting. Root-caused the "characters poof": the client sent palette
  *tab* names, the server only knows wire *layer* names — tab aliases
  (`characters → objects`, `colors → tiles`) now translate both sides.
- **Taxonomy.** Server-authoritative (`GET /api/taxonomy`); imports
  auto-correct and explain with a toast instead of rejecting. New
  **Animals** category; conservative migration; cleaner import names
  (`giant_rat.png → Giant Rat`).
- **Entities.** Any placed tile gets per-instance size (0.25–3×), a ⭐
  hero flag (many allowed — first flagged walks as the PC), 🌿/🏛
  world-vs-decor flavor, interactive toggle, and explicit ⚔️ enemy / 🛡
  mentor insert roles — all badged on the map and editable from the
  inspector. Schema 1→2; legacy integer cells still load.
- **Modes.** Paint-during-play: the sim pauses (gold chip shows), you
  paint, it resyncs and resumes — no session wipe. Hero persists across
  modes with a ⭐ ring in paint mode; `rules["hero_tiles"]` list with a
  legacy `hero_tile` mirror.
- **Maps.** Loading veil/spinner; friendlier map picker (name, size,
  modified date, description, current marker). Height as stacked bands;
  raise/lower/clear brush (one undo step per stroke); deterministic seed
  input + biome elevation. Pocket maps through portals, with return
  portals and anti-bounce. Known follow-ups: portals aren't restricted
  to door/cave art yet; generate/reset clears height but not portal links.
- **Panels.** Persistent ◨ panel control: 20–100% opacity + hide-all,
  per-player prefs. D-pad can't fall offscreen anymore — coordinates
  clamp while dragging, before saving, on load, and on resize.
- **Melody voice.** Spoken answers (warm female English voice, toggle in
  the dock) and 🎤 voice input — Groq Whisper transcribes into the input
  box for confirmation, never auto-sends. Audio stays in memory, never
  saved or logged. Mic is off pre-login (demo stays zero-cost); one STT
  request = one brain-call quota unit.
- Tests: Melody 66/66 (22 new voice tests), core smoke 9/10 (known
  pre-existing sprite-library round-trip failure), recovery smoke PASS.

- **ops.sh** — Lloyd's permanent Replit workflow (committed to the repo):
  `./ops.sh update` stops the server, stashes local changes (including
  untracked files), pulls `--rebase`, re-applies the stash, and restarts —
  aborting cleanly on conflicts with nothing lost. Also `status`, `start`,
  `stop`, `restart`, `logs`, `cherry-pick <sha>`, `stash`/`stash-pop`/
  `stash-list`. Supersedes the stop/start half of the old `sync.sh`
  (which stays for plain syncs).

## v5.28.1 — 2026-09-26

Melody Phase 1 refinements from Lloyd's answers:

- **Brain: Qwen on Groq first, Gemini fallback.** Lloyd's call — keeps her
  in the Qwen family she was raised on. `GROQ_MODEL` defaults to
  `qwen/qwen3.6-27b` (env-overridable; Groq is retiring the old Llama
  defaults, so the previous `llama-3.3-70b-versatile` default is gone).
  `MELODY_BRAIN=gemini` flips the order; `ollama`/`off` unchanged. Lloyd
  needs a free `GROQ_API_KEY` (console.groq.com, no card) as a server
  secret — he has Groq on his phone already.
- **Pre-profile demo mode.** The login overlay has a "Try Melody — free
  demo" button: no account needed, knowledge-base answers only (zero brain
  cost), 5 questions/day/IP, nothing remembered. Beyond-scope questions get
  a nudge to make a free profile. The demo dock floats above the login
  overlay and hands off cleanly to the full dock after login.
- **Persona: the charming teacher.** Melody's default register is now
  favorite-teacher energy with a wink — warm, playful, a little teasing,
  never explicit. `PERSONA_TEACHER` scaffold in the agent for the roadmap:
  basic tier unlocks a persona picker, pro gets full custom control
  (voice sliders when TTS lands).
- **Local mode is tier-based too** (`MELODY_LOCAL_TIER`, default free).
- Tests: 44/44 pass. Live-server verified: demo 200×5 then 429 with the
  limit message, health, chat, history.

## v5.28 — 2026-09-26

**Melody Phase 1: she has a voice.** A "Mel" chat dock now lives in the HUD
for every logged-in player (and in login-free local mode as a single-player
session). She teaches the app, looks up Repair Laws, reports vault stats,
and validates saved maps — read-only for now.

- **New agent module `melody_agent.py`.** Separate subsystem behind a narrow
  door: the server authenticates the player, then hands the agent (username,
  message) and nothing else. Per-user memory under `vaults/<user>/melody/`
  (history, quota, append-only audit log). Lloyd's tiers: 200/600/1000 brain
  calls/day for free/basic/pro; tier stored on the user record.
- **Knowledge-first answers cost nothing.** `MELODY_KNOWLEDGE.md` ships with
  the app; confident matches answer with zero brain call, zero quota burned.
  No brain key configured (or all brains down) → she says so honestly and
  still answers from the guide.
- **Brain backends, swappable.** `MELODY_BRAIN=gemini` (default, free AI
  Studio key) → `groq` fallback → `ollama` (`MELODY_BRAIN_BASE`) for the
  homecoming to Lloyd's own weights with zero game changes → `off` for
  knowledge-only mode.
- **`/api/melody/*` skips the vault lock** (health/chat/history/clear) — the
  agent is fully file-based and never touches game globals, so serializing
  it would stall the server through every multi-second brain call (Law 17).
  Auth is still checked: 401 without a session in public mode.
- **Repair Law 18 — "The Agent Sees Only Its Player."** Every agent path is
  built from the authenticated username alone, never from request input;
  she sees the player's vault plus the shared Commons (visible to everyone
  anyway), never another player's private vault. Enforced in path
  construction, not in the prompt.
- **New tests `melody_test.py`: 35/35 pass** — path-traversal rejection,
  quota tiers/exhaustion, knowledge + law lookup, knowledge-direct and
  brain-off turns, stubbed-brain tool loop, audit lines, cross-vault
  blindness. Live-server verified: local-mode chat/history/health,
  public-mode 401 when logged out, dock served in editor.html.
- Known pre-existing: `core_smoke_test.py` sprite-library round-trip fails
  on v5.27.3 too (9/10) — unrelated to this release.

## v5.27.3 — 2026-09-25

Root-caused from Lloyd's screenshot: palette thumbnails were blank — not
failed (no "?"), just never arriving. v5.27's vault lock serialized ALL
`/api/*` requests, so ~80 thumbnail images loaded single-file; on a slow
host the palette stayed blank for a long while.

- **`/api/thumb/*` skips the vault lock in public mode.** Thumbnails render
  from the global art registry and never touch vault globals, so they
  didn't need the lock at all. Auth is still checked (401 without a
  session); no vault is activated and no session cookie is reissued for
  them. Worst case under a concurrent vault switch is a transient "?" for
  a per-vault custom tile — 404s are never cached, so it heals on reload.
  Verified: 12 concurrent thumbs finish in ~0.1s wall time (previously
  strictly serialized).

## v5.27.2 — 2026-09-25

Root-caused from Lloyd's live `sync.sh` conflict: the first-boot owner
migration MOVED shipped starter maps (tracked in git) into the owner vault,
leaving the repo tree dirty and breaking every later `git pull --rebase`.

- **Migration copies git-tracked files instead of moving them.** The
  owner's vault still gets the starter maps; the repo copies stay put, so
  git stays clean forever. Untracked/personal files still move as before;
  non-git installs (phone) are unaffected. `/api/maps` only lists the
  vault dir, so the leftover root copies are never double-listed.

## v5.27.1 — 2026-09-25

Lloyd's call, from John's first login: the throttle just said "slow down"
with no timer, so he kept tapping and extending his own lockout.

- **Login try counter + cooldown timer.** Failed logins now report tries
  left ("bad login — 3 tries left"); hitting the 5/min limit returns
  `retry_after` seconds and the login page shows a live countdown,
  disables the button until it clears, and ignores taps/Enter during the
  cooldown. Server-verified; not phone-verified.

## v5.27 — 2026-09-25

Lloyd's direction: multiple accounts, each with a private vault, plus one
shared Commons world. Server-verified; not phone-verified.

- **Accounts.** Public mode (`--public`) now has real logins: an owner
  account is created on first boot (password printed once — write it
  down), and the owner can register more accounts from the server side.
  Sessions are signed cookies (`crumbs_sid`, HttpOnly, SameSite=Lax,
  30-day sliding refresh). Login is rate-limited to 5 tries/minute/IP
  with a generic "bad login" that never says whether the username exists.
  Existing top-level user data (maps, sidecars, custom tiles, patrols,
  backups, trash, recovery) migrates into the owner's vault on first boot.
- **Private vaults + the Commons.** Every account gets its own vault —
  its own maps, custom tiles, patrols, backups, everything. The Commons
  is one shared world every logged-in user can paint in: you save, they
  refresh, they see it. (Refresh-based for now — no live cursors or
  real-time tile sync yet; that's the next multiplayer step.) Switching
  between My vault and Commons saves the dirty vault first, so nothing
  is ever lost in the swap. World names are strictly `private`/`commons`.
- **Per-player undo.** Undo/redo stacks are keyed by (player, world): in
  the Commons, your undo only ever reverts your own paints. A private
  undo can never leak across a world switch either.
- **Custom tiles stay home.** Each vault has its own custom shelf; the
  Commons has its own, writable by everyone logged in. Private imports
  never appear in the Commons and vice versa. The shipped starter library
  stays available everywhere.
- **New UI.** Public mode parks on a login overlay until you log in (any
  expired session re-opens it). The Setup menu shows your name, current
  world, a world switcher, change-password, and logout — the owner also
  gets a Users… panel for managing accounts. The old share-key
  flow still works as an owner master bypass.
- **Owner safety.** The owner can reset any user's password (old sessions
  die immediately) and clear the Commons without touching private vaults.
  Setup → Users… (owner only) is the account desk: a create-user form
  with username/password fields (same rules as the server — 3–24 chars,
  a–z 0–9 _ -), an instant user list with created dates and the ⭐ owner
  badge, and per-user reset-password and delete. New accounts work the
  moment they're created — no approval queue, no pending state. Deleting
  a user kills their sessions at once and archives their vault under
  `vaults/.deleted/` so a mistake is recoverable; the owner account
  itself can't be deleted. Non-owners never see the panel or its menu
  entry — the server re-checks owner on every one of these calls.
  Break-glass: if the owner password is lost, set the `CRUMBS_OWNER_PASSWORD`
  environment variable to a new password and restart the server — the
  owner password resets and all owner sessions are invalidated. Unset the
  variable afterwards. (Access-gate security, not encryption: anyone with
  the server's files can read the vaults.)
- **Local mode unchanged.** Without `--public` there are no accounts, no
  logins, no vaults — the classic single-user HUD, exactly as before.

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
