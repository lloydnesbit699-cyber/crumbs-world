#!/usr/bin/env python3
"""Crumbs HUD — build the curated starter tile pack (v5.9).

Curates ~92 cells from the Project Utumno master sheet into
shared_library/starter_pack.png (one horizontal 32px strip) and registers
them in shared_library.json as pack "starter" (ids 70000+).

  python3 build_starter_pack.py --contact   # contact sheet of candidates -> /tmp/starter_contact.png
  python3 build_starter_pack.py             # build strip + rewrite shared_library.json

Entries use {"cell": i} to crop cell i from the strip; crumbs_hud.py
understands it. Utumno entries already in shared_library.json are kept.
"""
import base64
import io
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "shared_library", "utumno_sheet.png")
STRIP = os.path.join(HERE, "shared_library", "starter_pack.png")
REG = os.path.join(HERE, "shared_library.json")
BASE_ID = 70000

# (name, preset, solid, swim, row, col) — row/col are 32px cells on the sheet
PICKS = [
    # ---- ground (12) ----
    ("Dark floor", "floor", False, False, 4, 0),
    ("Teal tiles", "floor", False, False, 4, 4),
    ("Red rock", "floor", False, False, 4, 8),
    ("Sand", "floor", False, False, 4, 12),
    ("Grass", "floor", False, False, 9, 12),
    ("Meadow", "floor", False, False, 9, 16),
    ("Dune sand", "floor", False, False, 9, 28),
    ("Cobblestone", "floor", False, False, 4, 28),
    ("Pale sand", "floor", False, False, 5, 0),
    ("Dirt", "floor", False, False, 6, 2),
    ("Blue mosaic", "floor", False, False, 20, 0),
    ("Red mosaic", "floor", False, False, 20, 6),
    # ---- walls (12) ----
    ("Stone wall", "wall", True, False, 3, 20),
    ("Gray wall", "wall", True, False, 14, 10),
    ("Mossy wall", "wall", True, False, 3, 0),
    ("Dark wall", "wall", True, False, 3, 4),
    ("Blood wall", "wall", True, False, 3, 16),
    ("Brick wall", "wall", True, False, 5, 6),
    ("Moss brick", "wall", True, False, 5, 14),
    ("Pale bricks", "wall", True, False, 7, 9),
    ("Clay bricks", "wall", True, False, 14, 0),
    ("Old stone", "wall", True, False, 3, 36),
    ("Sandstone", "wall", True, False, 14, 24),
    ("Obsidian", "wall", True, False, 3, 28),
    # ---- water (8) ----
    ("Water", "water", False, True, 5, 18),
    ("Water", "water", False, True, 5, 20),
    ("Water", "water", False, True, 5, 22),
    ("Water", "water", False, True, 5, 24),
    ("Deep water", "deepwater", True, False, 5, 26),
    ("Deep water", "deepwater", True, False, 5, 28),
    ("Lava", "decor", True, False, 7, 0),
    ("Lava", "decor", True, False, 6, 31),
    # ---- doors (8) ----
    ("Wooden door", "door", False, False, 1, 38),
    ("Wooden door", "door", False, False, 1, 39),
    ("Oak door", "door", False, False, 1, 41),
    ("Blue door", "door", False, False, 1, 45),
    ("Green gate", "door", False, False, 1, 48),
    ("Blue door", "door", False, False, 1, 51),
    ("Green gate", "door", False, False, 1, 53),
    ("Wooden door", "door", False, False, 1, 54),
    # ---- objects (12) ----
    ("Gold chest", "decor", False, False, 0, 5),
    ("Chest", "decor", False, False, 0, 6),
    ("Open chest", "decor", False, False, 0, 7),
    ("Fountain", "decor", False, False, 0, 8),
    ("Blue fountain", "decor", False, False, 0, 2),
    ("Blood fountain", "decor", False, False, 0, 0),
    ("Statue", "decor", True, False, 1, 0),
    ("Tombstone", "decor", False, False, 0, 19),
    ("Brazier", "decor", False, False, 0, 47),
    ("Altar", "decor", False, False, 0, 24),
    ("Gold altar", "decor", False, False, 0, 58),
    ("Blue altar", "decor", False, False, 0, 59),
    # ---- nature (10) ----
    ("Oak tree", "decor", False, False, 13, 15),
    ("Birch tree", "decor", False, False, 13, 16),
    ("Autumn tree", "decor", False, False, 13, 17),
    ("Golden tree", "decor", False, False, 13, 18),
    ("Willow", "decor", False, False, 13, 13),
    ("Yellow tree", "decor", False, False, 13, 19),
    ("Rose", "decor", False, False, 68, 3),
    ("Lotus", "decor", False, False, 68, 4),
    ("Vines", "decor", False, False, 68, 0),
    ("Bushes", "decor", False, False, 13, 24),
    # ---- creatures (12) ----
    ("Pig", "character", False, False, 64, 0),
    ("Hound", "character", False, False, 64, 6),
    ("Spider", "character", False, False, 64, 22),
    ("Rat", "character", False, False, 64, 19),
    ("Sheep", "character", False, False, 65, 1),
    ("Bee", "character", False, False, 65, 4),
    ("Goblin", "character", False, False, 66, 10),
    ("Orc warrior", "character", False, False, 66, 40),
    ("Orc knight", "character", False, False, 66, 42),
    ("Hydra", "character", False, False, 67, 8),
    ("Treant", "character", False, False, 68, 5),
    ("Skeleton", "character", False, False, 66, 39),
    # ---- heroes (8) ----
    ("Knight", "character", False, False, 27, 0),
    ("Wizard", "character", False, False, 27, 1),
    ("Angel warrior", "character", False, False, 80, 10),
    ("Fighter", "character", False, False, 80, 14),
    ("Red guard", "character", False, False, 80, 18),
    ("Tide warrior", "character", False, False, 80, 22),
    ("Paladin", "character", False, False, 80, 1),
    ("Merfolk", "character", False, False, 80, 36),
    # ---- items (10) ----
    ("Potion", "decor", False, False, 27, 52),
    ("Sword", "decor", False, False, 28, 28),
    ("Scroll", "decor", False, False, 29, 40),
    ("Apple", "decor", False, False, 30, 49),
    ("Meat", "decor", False, False, 30, 50),
    ("Shield", "decor", False, False, 28, 35),
    ("Kite shield", "decor", False, False, 86, 3),
    ("Skull", "decor", False, False, 28, 32),
    ("Elixir", "decor", False, False, 27, 54),
    ("Dagger", "decor", False, False, 29, 46),
]


def cells():
    sheet = Image.open(SHEET).convert("RGBA")
    out = []
    for name, preset, solid, swim, r, c in PICKS:
        cell = sheet.crop((c * 32, r * 32, (c + 1) * 32, (r + 1) * 32))
        out.append((name, preset, solid, swim, r, c, cell))
    return out


def contact_sheet(out_path="/tmp/starter_contact.png"):
    items = cells()
    cols = 12
    rows = (len(items) + cols - 1) // cols
    s = 2
    sheet = Image.new("RGBA", (cols * 32 * s, rows * 32 * s), (10, 10, 10, 255))
    for i, (name, preset, solid, swim, r, c, cell) in enumerate(items):
        x, y = (i % cols) * 32 * s, (i // cols) * 32 * s
        sheet.paste(cell.resize((64, 64), Image.NEAREST), (x, y))
    sheet.save(out_path)
    print("contact sheet: %s (%d tiles)" % (out_path, len(items)))
    for i, (name, preset, solid, swim, r, c, cell) in enumerate(items):
        print("%3d %-14s r%2d c%2d" % (i, name, r, c))


def build():
    items = cells()
    strip = Image.new("RGBA", (len(items) * 32, 32), (0, 0, 0, 0))
    for i, (name, preset, solid, swim, r, c, cell) in enumerate(items):
        strip.paste(cell, (i * 32, 0))
    strip.save(STRIP)
    print("strip: %s (%dx%d, %d tiles)" % (STRIP, strip.width, strip.height, len(items)))

    entries = []
    for i, (name, preset, solid, swim, r, c, cell) in enumerate(items):
        entries.append({
            "id": BASE_ID + i,
            "name": "Starter " + name,
            "preset": preset,
            "solid": solid,
            "height": "tall" if preset == "wall" else "short",
            "swim": swim,
            "deep": preset == "deepwater",
            "frame_ms": 400,
            "files": ["starter_pack.png"],
            "cell": i,
            "scope": "shared",
            "pack": "starter",
            "src": "utumno r%02d c%02d" % (r, c),
        })
    try:
        reg = json.load(open(REG))
    except Exception:
        reg = {}
    tiles = [t for t in reg.get("tiles", []) if t.get("pack") != "starter"]
    reg["tiles"] = tiles + entries
    reg.setdefault("packs", {})
    reg["packs"]["starter"] = {
        "label": "Starter",
        "desc": "Curated starter set — Project Utumno (CC0)",
        "tiles": len(entries),
    }
    json.dump(reg, open(REG, "w"))
    print("registry: %s (%d starter + %d others)" % (REG, len(entries), len(tiles)))


if __name__ == "__main__":
    if "--contact" in sys.argv:
        contact_sheet()
    else:
        build()
