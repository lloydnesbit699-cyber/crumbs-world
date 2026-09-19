# itch.io page draft — Crumbs HUD (v5.6)

## Title
**Crumbs HUD** — touch-first dungeon map painter & playtester

## Tagline
Paint a dungeon on your phone. Walk through it ten seconds later.

## Description

Crumbs HUD is a tile painter that runs entirely on your phone — no installs,
no accounts, no cloud. One Python script serves a touch-first editor in your
browser: pick a tile, paint with your finger, pinch to zoom, then hit Play and
walk your hero through the map you just drew, collision and all.

It grew out of a vault-dungeon pixel-art project and kept the builder's
priorities: everything undoable, everything on-device, nothing that needs
permission from a server farm. The sprite pipeline swallows whole sheets —
the bundled Project Utumno set alone is 6,038 tiles — and imported art becomes
animated tiles that keep animating on the canvas. Builders get game rules
(messages, keys and doors, hazards, win/lose goals), a nature layer with
meters and weather, assigned NPC patrols, and a one-tap map validator that
checks spawn points, reachability, and tile ids before you share a build.

## Features
- Touch-first editor: finger painting, two-finger pan, pinch zoom, edge trays
- Playtest mode: tap-to-walk hero with pathfinding, sprite rendering, collision
- Universal undo/redo across painting, generation, and rules
- Game rules: messages, key-and-door unlocks, hazards, win/lose goals
- Nature layer: gather/build traits, health/warmth/belly meters, weather
- NPC patrols: assign routes to characters, re-route, per-instance names
- Sprite pipeline: import PNG sheets, multi-frame animated tiles, 6,038-tile
  Project Utumno library (CC0) bundled
- Seeded biome generator (dungeon, grassland, desert, arctic, forest, ocean)
- Map management: rename, duplicate, delete-to-trash, import, metadata,
  thumbnails, PNG export, play-session save slots
- One-tap map validator: spawn, reachability, tile-id checks
- Server event log for debugging without watching a terminal
- Stdlib-only Python server — runs on a phone, a laptop, anywhere

## Controls
- **Paint:** tap / drag with one finger
- **Pan:** Move tool, or drag with two fingers
- **Zoom:** pinch, or the floating -/+ buttons (Fit re-fits)
- **Play:** Play button — tap a tile to walk the hero there
- **Undo / Redo:** header buttons, or shake-free keyboard on desktop
- **Eraser:** restores the seed's original ground on generated maps

## Pricing note (draft)
Free web build; paid download bundles the sprite packs and the tutorial
dungeon. itch.io "pay what you want" fits the audience.
