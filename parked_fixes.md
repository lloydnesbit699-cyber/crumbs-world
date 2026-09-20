# Parked fixes — speed run 2026-09-19

## BUILT in v5.7 (2026-09-19)

(1=generate busy indicator, 2=scrollable menu, 3=60dvh sheets, 9=atomic
linked-collision undo — all marked [DONE v5.7] below)

## QUEUED features (designed, not yet built)

1. [DONE v5.7] Generate button needs a busy indicator: at 64x64 the post-generate chain
   (refresh + traits + world + natural + palette + 4096-tile render) takes
   seconds on the phone with zero feedback — Lloyd thought it was broken.
   Fix: disable btn-gen + show "Generating..." toast/spinner until the chain
   completes; re-enable on done/fail.

2. [DONE v5.7] Top-bar dropdown menu isn't scrollable and runs off the bottom of the
   screen (photo 2026-09-19: Load/Export/Save slots/Check map/Walls/Server
   log/Stop server unreachable). Fix: #menu-dropdown gets
   max-height: min(88dvh, ...) + overflow-y: auto (+ overscroll-behavior:
   contain, -webkit-overflow-scrolling: touch). Menu must fit the viewport
   on small screens.

3. [DONE v5.7] Bottom sheet (Rules/Setup) opens way too tall — eats ~70% of the viewport
   and squeezes the map into a strip (photo 2026-09-19, laptop Chrome over
   Wi-Fi). Fix: cap sheet max-height (~70dvh) with internal scroll; consider
   half-height default + drag handle to expand/collapse.

4. FEATURE: height/elevation system. Derive a heightmap from the natural
   layer (deep water < water < plains < hills < mountains) plus walls
   (+levels on top). Feeds: render (shadows under tall things, tall
   wall/foliage faces already exist — make them height-driven), gameplay
   (movement cost, blocking, line of sight), playtest physics. Add a
   height overlay toggle to see it. Decided 2026-09-19: BOTH — visual (shadows/tall faces) and gameplay (movement cost, blocking, line of sight).

5. FEATURE: embedded Melody — a distilled part of her shipped INSIDE the
   game, working with zero server and zero network, on or off the phone.
   Constraint (be honest): a real neural small model (.gguf) can't run in
   a-Shell's iOS sandbox — no compiler, no pip wheels for iOS. So "parts of
   her" = her persona/voice lines, decision heuristics, memory patterns as
   data + a local engine. Tiered design: Tier 0 embedded always (distilled
   Melody core, no deps); Tier 1 full Melody via her phone server (8777)
   when reachable; Tier 2 on-device neural brain later. Tier 0 is a real
   citizen, not a stub fallback. Open: voices first or minds first.

6. FEATURE: curated starter tile pack ships WITH the default app. Not the
   full 6,038-cell Utumno library — a hand-picked 8-12 tiles per type
   (ground, wall, water, object, creature, ...) bundled with the standard
   file drop and auto-registered on first run. No separate download; the
   app is fully usable out of the box. Full library stays an optional add.

7. FEATURE: sound effects. UI feedback (taps, paint strokes, generate whoosh),
   ambient dungeon audio, per-biome touches. Approach: synthesize with Web
   Audio API — zero audio files to download, works offline on the phone.
   Master mute toggle + volume in Setup. Keep it subtle; game first.
   Expanded 2026-09-19: action sounds, nature ambience, animal sounds, and
   NPC voice mumbles (simlish-style gibberish, synthesized, not recorded).

8. FEATURE: sprite-sheet import + generate-with-sheet. User uploads a
   sprite sheet (like the PICO-8 sheet in his 2026-09-19 photo); HUD slices
   it on a configurable grid (8/16/32px cells), user tags tiles by role
   (ground, wall, water, object, creature...), and the Generate panel gains
   a "use this sheet" option so biome generation draws from the uploaded
   tiles. Builds on v5.6's custom PNG import, but sheet-aware and
   generation-aware. Handles the tagging UX — the make-or-break part.

9. [DONE v5.7] BUG: undo/redo ignore linked collision. Root cause (2026-09-19): when
   "stamp collision" is linked, endStroke() fires TWO /api/stroke calls —
   one for the tiles layer, one for collision — each pushing its own
   MultiCommand onto the history. One paint gesture = two undo steps, so a
   single undo reverts tiles but leaves the stamped collision behind.
   Fix: /api/stroke takes both cells + link_cells in ONE call and pushes a
   single combined MultiCommand, so linked paint/undo/redo stay atomic.
