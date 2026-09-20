# Publishing with Crumbs HUD — Publisher Guide

You made something in Crumbs and you want to sell it, share it, or ship
it inside a bigger product. Here's how the pieces fit.

## Editions

- **Free:** core editor, personal and non-commercial use. Your maps stay
  personal.
- **Creator ([PRICE], one-time):** unlocks the starter art packs and
  advanced tools, and lets you commercially use maps you make, up to
  $[REVENUE CAP] gross per year.
- **Pro ([PRICE], one-time):** full commercial use with no revenue cap,
  including redistribution of exported bundles inside your own products,
  plus priority support.

Full terms: LICENSE and COMMERCIAL_TERMS.md in the repo root.

## What you can export today

- **PNG export** of your map — the finished picture, good for
  print, video overlays, and pitches.
- **Your map data** (JSON) plus its sidecars (missions, items, NPCs,
  gear) — the raw material for your own engine work.

## What's coming (v5.16, in progress)

- **Tiled JSON export** — a format real engines consume.
- **Godot-ready and Unity-friendly bundles** — after Tiled proves the
  pipeline.
- **Shareable map bundles** — map + embedded assets + version stamp in
  one file. This is the unit of "here, play my level."
- **Template starter projects** — dungeon-crawler and survival starters
  so your players get an instant outcome.

## Art licensing in your products

This is the part that bites people — get it right before you publish:

- **Starter pack art** (original, made for Crumbs): safe for commercial
  use on Creator and Pro.
- **Utumno sheet** (CC0 public domain): safe everywhere, credit
  appreciated but not required.
- **Art you imported**: your responsibility. You need the rights to
  whatever sprite sheets you sliced.
- **InvSprite pack** (Minecraft sprites, Mojang/Microsoft): personal
  use only. Never ship it in a public repo, a paid bundle, or a
  published game. If any of it is on your map, swap those tiles before
  you publish.

Audit every map before it goes out. A per-tile provenance flag is on
the roadmap; until then, keep track yourself.

## Refunds and support

14-day no-questions refunds on paid editions. Support is solo-dev:
community for Free, best-effort email for Creator, priority for Pro.
See COMMERCIAL_TERMS.md.

## Selling tile packs and adventure packs

In-app storefront hooks are on the roadmap (the store itself can start
as a simple page). Pack loading is becoming entitlement-aware so free
and paid content can coexist cleanly.
