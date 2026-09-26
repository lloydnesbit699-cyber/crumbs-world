# Melody's Crumbs World Guide

Zero-cost answers. Melody checks this first — if a section matches the
question confidently, she answers from here without calling her brain.

## How to paint tiles
Pick a tab (Tiles, Objects, Characters), pick a tile, then tap or drag on the
map. Drag-painting paints every cell your finger crosses. The brush paints on
the layer its tab owns: Tiles paint floors and walls, Objects paint furniture
and props, Characters paint creatures (they live on the objects layer).

## Tabs and categories
The palette is split like Minecraft: Tiles (walls, floors, doors, roofs,
materials, natural), Objects (furniture, containers, props, lighting), and
Characters & Creatures. Use the search box to find a tile by name, and the
pack groups collapse so the list stays short. Every tile has exactly one home
tab — a floor is always under Tiles, even if you built it yourself.

## Undo
The undo button reverses YOUR last strokes only. In the shared Commons world,
your undo can never revert another player's painting — undo stacks are
per-player. If undo seems to do nothing, check you actually painted since the
last undo.

## Accounts and logging in
On the public server everyone logs in. The first time the server boots, an
owner account is created and its password is printed once in the server log
(or set with the CRUMBS_OWNER_PASSWORD secret). Tapping login too many times
too fast triggers a short cooldown — wait for the timer, don't keep tapping.
The owner can create accounts for other players from the Users panel in Setup.

## Private vault vs the Commons
Every player gets a private vault: only you can see and paint there. The
Commons is one shared world everyone paints together — it's multiplayer by
refresh (no live cursors yet, so reload to see others' work). Your account
page shows which world you're in.

## Custom tiles and the shelf
Import your own art as custom tiles — they land on your shelf. Your private
vault has its own shelf; the Commons has a shared shelf everyone adds to.
Rename a tile by tapping its name under its picture in the palette.

## Missions and patrols
Missions are quest text with goals the game tracks. Patrols are routes you
draw for creatures to walk — pick the Patrol tool, tap waypoints, then turn
the Patrol tool OFF when you're done, or your taps will keep drafting routes
instead of painting. If taps "do the wrong thing," check which tool button is
highlighted first.

## Updating the app
Menu → Check for updates pulls the newest version and restarts. If the page
looks stale after an update, reload it — the page is set to never cache, but
an old tab can linger.

## Paint pauses then recovers
If painting freezes for about a minute and then comes back, that's the flood
guard: very fast drag-painting sends a burst of saves and the server asks you
to slow down briefly. Nothing is lost and nothing is broken — ease off for a
moment and keep going.

## Blank thumbnails
If palette pictures show "?" instead of art, the app is missing that art file
— say so honestly rather than showing a blank. Menu → Check for updates
re-fetches missing art automatically at boot.

## Running on iPhone with a-Shell
Run `python3 crumbs_hud.py` in a-Shell, then type http://127.0.0.1:8778 into
the browser's address bar. Never open editor.html itself in a file viewer —
that gives a black page. If the page stops responding, iOS probably froze
a-Shell in the background: wake a-Shell, restart the script, reload the page.

## What Melody can do right now
Melody (that's me!) can teach you the app, look up the Repair Laws, check
your vault stats, and validate your saved maps for problems. I can't change
your world myself yet — for now I'll tell you exactly what to tap. Soon I'll
be able to propose changes for you to approve with one tap.

## What Melody can't see
I see only you: your private vault, plus the shared Commons everyone can
already see. I can't see other players' private vaults, and I won't repeat
anything from them. That's Repair Law 18: the agent sees only its player.
