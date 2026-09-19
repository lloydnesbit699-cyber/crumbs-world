#!/usr/bin/env python3
"""Crumbs HUD v5.6 content pack — the tutorial dungeon.

Builds tutorial-dungeon.json (30x20) from a readable ASCII floor plan plus
tutorial-dungeon.rules.json, the v2 sidecar shape _load_rules expects:
{"tweaks": {...}, "game": [...], "world": {...}, "meta": {...}}.

The lesson, west to east:
  entry room  -> message rule welcomes you, a chest sits in the corner
  the door    -> grabbing the chest fires the keydoor rule: the door ahead
                 swings open (visual + unlock event)
  flooded hall-> a water pit is a hazard rule: step in and the run ends,
                 so walk around it
  goal room   -> stepping on the marked stone fires the goal rule: you win

Tile ids are resolved by NAME through AssetManager — never hardcoded.
"""
import json
import os

import crumbs_core as core

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 30, 20

# legend: # wall | . floor | , dark floor (goal marker) | ~ water
#         E entry+hero | K chest (the key) | D door | W goal stone
PLAN = [
    "##############################",
    "#.........#.........#........#",
    "#.E.......#.........#........#",
    "#.........#.........#........#",
    "#.........D..................#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "#.........#..~~~~~..#...,,...#",
    "#.........#..~~~~~..#..,W,...#",
    "#.........#..~~~~~..#...,,...#",
    "#.........#..~~~~~..#...,,...#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "#......K..#.........#........#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "#.........#.........#........#",
    "##############################",
]

OBJECTS = {"E": "Hood Hero", "K": "dungeon_chest", "D": "dungeon_door"}


def main():
    assert len(PLAN) == H and all(len(r) == W for r in PLAN), "plan must be 30x20"
    assets = core.AssetManager()
    T = {t["name"]: tid for tid, t in assets.tiles.items()}

    wall, floor = T["dungeon_wall"], T["dungeon_floor"]
    dark, water = T["dungeon_floor_dark"], T["water"]

    world = core.WorldMap(W, H, assets)
    entry = key_xy = door_xy = goal_xy = None
    for y, row in enumerate(PLAN):
        for x, ch in enumerate(row):
            if ch == "#":
                world.data[y][x] = wall
                world.collision_layer[y][x] = True
            elif ch == ".":
                world.data[y][x] = floor
            elif ch == ",":
                world.data[y][x] = dark
            elif ch == "~":
                world.data[y][x] = water
            elif ch in "EKDW":
                world.data[y][x] = floor if ch != "W" else dark
                if ch in OBJECTS:
                    world.object_layer[y][x] = T[OBJECTS[ch]]
                if ch == "E":
                    entry = (x, y)
                elif ch == "K":
                    key_xy = (x, y)
                elif ch == "D":
                    door_xy = (x, y)
                else:
                    goal_xy = (x, y)
            else:
                raise ValueError("unknown plan glyph %r" % ch)
    assert entry and key_xy and door_xy and goal_xy, "plan must hold E, K, D, W"

    path = os.path.join(HERE, "tutorial-dungeon.json")
    assert world.save(path), path

    rules = {
        "tweaks": {"walk_ms": 140, "swim_mult": 3, "ghost": False,
                   "touch": True, "hero_tile": T["Hood Hero"]},
        "game": [
            {"kind": "message", "id": 1, "x": entry[0], "y": entry[1],
             "text": "Welcome to the Vault, wanderer. Grab the old chest, "
                     "then head east through the door."},
            {"kind": "keydoor", "id": 2, "key": T["dungeon_chest"],
             "door": T["dungeon_door"],
             "text": "The chest holds an iron key - ahead, a door swings open!"},
            {"kind": "hazard", "id": 3, "tile": T["water"],
             "text": "The floodwater was deeper than it looked..."},
            {"kind": "goal", "id": 4, "x": goal_xy[0], "y": goal_xy[1],
             "text": "You reached the heart of the vault - you win!"},
        ],
        "world": {"meters": {"health": True, "warmth": False, "belly": False},
                  "weather": "clear"},
        "meta": {"biome": "dungeon", "seed": None},
    }
    with open(os.path.join(HERE, "tutorial-dungeon.rules.json"), "w") as f:
        json.dump(rules, f, indent=2)
    print("wrote tutorial-dungeon.json (30x20) + sidecar")
    print("entry %s chest %s door %s goal %s" % (entry, key_xy, door_xy, goal_xy))


if __name__ == "__main__":
    main()
