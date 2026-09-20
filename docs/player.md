# Playing in Crumbs HUD — Player Guide

You're the hero. Someone built a map; now you get to walk through it.

## Getting into play mode

Open the HUD in your browser (http://127.0.0.1:8778 when the server is
running), then switch to Play. Your hero spawns at the map's spawn
point. Tap a tile to walk there — the hero pathfinds around walls and
cliffs, and pays climb costs on height differences.

## Missions

If the map has a mission, an objective panel shows what to do: reach a
place, hit waypoints, gather items, survive, or beat the clock. Each
completed step checks off. Win or fail messages appear when the mission
resolves. Watch out for hazard ground (costs health) and patrolling
critters — difficulty 1–5 sets how mean the map is.

## Your pack

- **Items:** pick up gear from the ground by walking onto it (or tapping
  it). Food stacks up to 99; weapons and tools don't stack.
- **Eat/use:** food restores you; tools and weapons have effects when
  equipped or used.
- **Equip:** put a weapon or tool in your hands from the Pack sheet.
  The right tool can even clear hazards.
- **Drop:** leave something on the ground for later.
- **Gold:** earn and spend it at merchants.

Everything in your pack, your gold, and your equipped gear is saved per
map — quit and come back, it's all still there.

## Shops

Walk up to a merchant to open their shop. Buy from their stock (some
shelves are endless, some run out), sell your own goods for gold. If
you're short on gold, the shop tells you — no silent failures.

## NPCs

Villagers stand around with names and greetings. Merchants sell. Some
NPCs carry visible weapons or tools.

## Save slots

Play sessions can be saved to slots and reloaded later — your position,
pack, gold, and mission progress come back with them.

## Tips

- iOS freezes background apps: if the page stops responding, reopen
  a-Shell, restart the server, reload the page.
- If a mission step seems impossible, the map's builder was supposed to
  have it playtested — tell them which step broke.
