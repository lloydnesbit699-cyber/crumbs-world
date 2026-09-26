# Traits redesign — proposal (not built)

Feedback item 9 (2026-09-26): *"Traits menu is confusing and doesn't make sense — redesign."*
This doc is the proposal. No traits code was changed.

## What traits are today (grounded in the code)

- Server (`crumbs_hud.py`, `TRAITS`): five stamps —
  - 🔥 hot — "warms you up"
  - ❄️ cold — "chills you to the bone"
  - 🗡️ sharp — "hurts to step on"
  - 🪵 wood — "pick it up by walking over"
  - 🍖 food — "eat it by walking over"
- The builder picks one of five abstract buttons in the Traits sheet, taps map
  cells to stamp it ("Clear traits instead" is a separate mode), and the map
  shows a small emoji in the cell corner. The inspector repeats all five
  buttons inline per cell.
- One trait per cell. Traits + meters save with the map.

## Why the current mental model breaks (5 concrete problems)

1. **Two different ideas share one menu.** hot/cold/sharp are *hazards* —
   things the ground does TO you, every time you step there. wood/food are
   *pickups* — things you TAKE from the ground, which are consumed when you
   do. The UI presents them as five equal siblings, so nothing tells the
   builder which kind he's stamping.
2. **The words don't say what happens.** "Warms you up" is the whole
   description of hot — but what does that mean in play? Which meter moves?
   By how much? Does it fire every step or once? Does the trait get used up?
   The builder has to playtest to find out.
3. **Cause and effect are separated.** The thing that decides the outcome
   (the World's meters — health/warmth/belly) lives in a different sheet
   from the thing that triggers it (the trait stamp). If warmth is off,
   stamping 🔥 does nothing and the UI never says so.
4. **The map can't tell you what a trait does.** A corner emoji is a badge,
   not an explanation. 🔥 on a cell doesn't say "warmth +1 per step" or
   "fire, burns out after 5 steps" — and two cells with the same emoji can
   behave differently if the world's meters differ.
5. **Clear is a mode, not an action.** "Clear traits instead" is a toggle
   that changes what tapping does, in a different visual area from the five
   stamps. It's easy to stamp when you meant to clear, and the undo burden
   lands on the builder.

## Proposed information architecture

Split the five stamps into the two families they already are, and say the
effect out loud:

**Hazards** — the ground acts on you, every step, never consumed:
- 🔥 Hot ground — "warmth +1 each step you stand here" (needs the Warmth meter on)
- ❄️ Cold ground — "warmth −1 each step" (needs Warmth)
- 🗡️ Sharp ground — "health −1 each step" (needs Health)

**Pickups** — you take it by walking over, it's gone after:
- 🪵 Wood — "adds 1 🪵 to your pack, disappears from the map"
- 🍖 Food — "belly +2, disappears from the map" (needs the Belly meter on)

Every stamp's card answers four questions in plain words: **what gets it**
(the tile under the hero), **when it fires** (every step / once, on pickup),
**whether it's consumed** (stays / disappears), **which meter it moves**
(and a warning when that meter is off in this world's profile — the card
grays out with "Warmth is off in this world — this stamp does nothing
until you turn it on").

## Mockup-level UI

**Traits sheet (replaces the five-button row):**

```
Traits — what the ground does
┌ Hazards — act on you, every step, stay put ──────────┐
│ [🔥 Hot ground]      warmth +1 / step   ⚠ Warmth off │
│ [❄️ Cold ground]     warmth −1 / step   ⚠ Warmth off │
│ [🗡️ Sharp ground]    health −1 / step                 │
└ Pickups — take by walking over, then they're gone ───┘
│ [🪵 Wood]            +1 wood to pack                  │
│ [🍖 Food]            belly +2           ⚠ Belly off  │
[ 🧹 Clear ]  ← an action button, not a mode; erases traits under the brush
```

- Tapping a card arms the brush (same as today). Tapping Clear arms the
  eraser for traits only — no mode toggle to forget about.
- Cards that do nothing under the current world profile are visibly dimmed
  with the ⚠ note, instead of silently stamping dead traits.

**Map badges:** keep the corner emoji, but color the cell corner — red tint
for hazards, green tint for pickups — so the *kind* reads at a glance, not
just the identity.

**Inspector:** replace the five repeated buttons with one row —
"trait: 🔥 Hot ground — warmth +1/step [Change] [Clear]" — the words travel
with the cell instead of living only in the sheet.

## Data model note

No save-format change is needed. Trait ids (`hot`, `cold`, `sharp`, `wood`,
`food`) stay exactly as stored; the legend gains presentation fields
(`kind: hazard|pickup`, `meter`, `consumed: bool`, `effect_words`). Old
maps load unchanged — they just get clearer labels.

## Open questions for Lloyd

1. Should hazards be tunable per stamp (e.g. "this fire is hotter") or is
   one fixed strength per trait enough for now?
2. Pickups currently vanish on pickup — should the builder be able to make
   an infinite source (a berry bush that regrows)?
3. Does "Clear" need to be brush-sized, or is single-tap-erase enough?
