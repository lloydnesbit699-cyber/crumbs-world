# Building in Crumbs HUD — Creator Guide

You make the maps. Everything here is undoable — paint boldly.

## Setup

Copy the Crumbs folder into a-Shell (via the Files app), run
`python3 crumbs_hud.py`, and open http://127.0.0.1:8778 in Safari.
Never open editor.html directly — it only works served. Tip: Share →
Add to Home Screen for a one-tap icon. To share over Wi-Fi so a friend
can open it in their browser: `python3 crumbs_hud.py --public` (only on
networks you trust).

## Painting

Pick a tile from the palette and paint with your finger. Two-finger
drag pans, pinch zooms, and there are zoom buttons plus a fit-view
control. Tools include paint, erase (restores the seed's original ground
on generated maps), and a move tool for panning without painting. If
taps seem to do the wrong thing, check which tool is highlighted first.

Layers: tiles, objects, collision. Undo/redo covers painting,
generation, and rules.

## The tile palette

- **Starter pack:** a curated set that ships with the app — the fun
  default, no download needed.
- **Full library:** the 6,038-cell Project Utumno master sheet (CC0) is
  opt-in — load it when you want everything.
- **Custom tiles:** import your own PNG sprite sheets (8/16/32px,
  PICO-8 preset supported); imported art can be animated and keeps
  animating on the canvas.
- **Drop-in packs:** any `*.pack.json` in the tiles folder loads as its
  own collapsible group. Search the palette to find a sprite fast.

The selected-tile panel holds the selected tile: rename it, set its
height, assign roles.

## Height and elevation

Every tile has a numeric height (deep water −2 up to mountains +2,
walls add +1), editable per tile. Height drives shadows, tall 2.5D
faces, climb costs, cliff blocking, and line of sight. There's a height
overlay for planning and a sight toggle in play mode to preview what the
hero can see.

## Game rules

Messages, keys and doors, hazards, win/lose goals, and a nature layer
(gather/build traits, health/warmth/belly meters, weather). NPC patrols
can be assigned routes and re-routed per instance.

## Melody's mission workshop

Missions are built in the editor, where Melody helps: pick a preset
(reach, waypoints, gatherer, survivor, beat-the-clock), answer a short
questionnaire (name, difficulty 1–5, reward, targets, counts, ticks),
and she places hazard patrols and critters to match the difficulty —
then playtests every objective herself (including cliff reachability)
and reports blockers in plain language. Missions live in the map's
sidecar file.

## Items and NPCs

- **Items sheet:** create tile-based items — weapons, tools, food,
  trinkets — with name, power, effect, stack limit, and price. Place
  ground stacks on the map.
- **Folks sheet:** place villagers and merchants with names, greetings,
  and positions. Give NPCs an equipped weapon or tool. For merchants,
  edit their stock: finite quantities or endless shelves, with prices.

## Validation and map management

The one-tap validator checks spawn points, reachability, and tile IDs
before you share a build. Maps can be renamed, duplicated, deleted to
trash, imported, and exported as PNG. Play sessions use save slots.
Your maps and sidecars live on your device and are never uploaded
anywhere.

## Generation

Seeded biome generation (dungeon, grassland, desert, arctic, forest,
ocean) gives you a starting map to paint over. Deterministic presets
with stronger biome identity are on the roadmap.
