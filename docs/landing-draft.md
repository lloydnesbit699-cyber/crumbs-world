# Landing Page Draft — Crumbs HUD

Markdown draft for the future landing page. No fake testimonials, no
invented links.

---

## Hero

**Paint a dungeon on your phone. Walk through it ten seconds later.**

Crumbs HUD is a touch-first tile map painter with a tiny game engine
inside. One Python script, one page in your browser — no installs, no
accounts, no cloud. Paint with your finger, hit Play, and walk the hero
through the map you just drew.

[Get Crumbs — Free] [See demo maps]

*Runs on iPhone via the free a-Shell app, or any laptop with Python 3.*

## Who it's for

**Solo devs** — Sketch real, walkable levels anywhere: the couch, the
bus, a lunch break. Paint, play, fix, repeat — then export the good
ones into your real engine.

**Classrooms** — Teach game design, not toolchain wrangling. No accounts
to provision, nothing in the cloud. Students paint levels and play each
other's work in the same period.

**Game-jam creators** — From blank grid to a playtested dungeon with
objectives, items, NPCs, and shops in an evening — on the device already
in your hand.

## Demo map gallery

Playable starter maps that ship with Crumbs — each one is a finished
little outcome, not a blank grid:

- **Starter Dungeon** — the classic: rooms, corridors, doors, a goal.
- **Starter Maze** — pathfinding and hazard play.
- **Starter Village** — NPCs, merchants, and shops.
- **Tutorial Dungeon** — guided first build: paint, add a mission, play.

## How it works (first map in 5 minutes)

1. **Install** — Copy the Crumbs folder into a-Shell, run
   `python3 crumbs_hud.py`, open http://127.0.0.1:8778 in Safari.
2. **Paint** — Pick a tile, paint with your finger. Pinch to zoom,
   two-finger drag to pan.
3. **Play** — Hit Play and tap tiles to walk your hero through it.
4. **Make it a game** — Add a mission, items, NPCs, and a shop.
5. **Share** — Run with `--public` and a friend on the same Wi-Fi can
   open your map in their browser. Nothing for them to install.

## FAQ

**Is it really phone-first?**
Yes. It's designed for the phone and tested on iPhone. iOS freezes
background apps, so if the page stalls, reopen a-Shell, restart the
script, reload. That's the whole troubleshooting guide.

**Can I use it commercially?**
The Free edition is personal/non-commercial. Creator ([PRICE]) unlocks
commercial use of your maps up to $[REVENUE CAP]/yr; Pro ([PRICE]) has
no cap and covers redistributing exported bundles. See LICENSE and
COMMERCIAL_TERMS.md.

**Is my art safe?**
Your maps and imported art live on your device — nothing uploads
anywhere. Your maps are yours in every edition. Note: the optional
Minecraft InvSprite pack is personal-use only (Mojang/Microsoft art)
and must never ship in a published game.

**Do I need to know how to code?**
No. You never have to see code. But it's all there — one readable
Python file — if you want to.

**What about my existing engine?**
Tiled JSON export is in progress, with Godot and Unity bundles after.
Crumbs is the sketchbook before the engine, not a replacement for it.

## Footer

Crumbs HUD — built by Lloyd David Nesbit.
[License] [Commercial terms] [Changelog] [Roadmap] [Docs: Player · Creator · Publisher]
