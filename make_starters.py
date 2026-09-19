#!/usr/bin/env python3
"""Crumbs HUD v5.6 content pack — three seeded starter maps.

  starter-dungeon.json  40x30  real biome generator (dungeon), fixed seed
  starter-village.json  40x30  grassland biome + hand-carved plaza, well,
                               and supply chests
  starter-maze.json     40x30  hand-built recursive-backtracker maze with a
                               chest waiting at the exit

Everything is deterministic: same seeds, same maps, every run. Tile ids are
resolved by NAME through AssetManager — never hardcoded — and each map gets
a .rules.json sidecar (defaults + seed meta, the v5.0 shape _load_rules
expects) so the eraser can restore the seed's ground.
"""
import json
import os
import random

import crumbs_core as core

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 40, 30

DEFAULT_TWEAKS = {"walk_ms": 140, "swim_mult": 3, "ghost": False,
                  "touch": True, "hero_tile": None}
DEFAULT_WORLD = {"meters": {"health": True, "warmth": False, "belly": False},
                 "weather": "clear"}


def tile_ids():
    assets = core.AssetManager()
    return assets, {t["name"]: tid for tid, t in assets.tiles.items()}


def write(world, fname, biome, seed):
    path = os.path.join(HERE, fname)
    assert world.save(path), fname
    sidecar = os.path.join(HERE, fname.replace(".json", ".rules.json"))
    with open(sidecar, "w") as f:
        json.dump({"tweaks": dict(DEFAULT_TWEAKS), "game": [],
                   "world": json.loads(json.dumps(DEFAULT_WORLD)),
                   "meta": {"biome": biome, "seed": seed}}, f, indent=2)
    print("wrote %s (%dx%d) biome=%s seed=%s" % (fname, world.width,
                                                world.height, biome, seed))


def make_dungeon(assets):
    world = core.WorldMap(W, H, assets)
    world.generate_biome("dungeon", 20260919)   # same call /api/generate makes
    return world, "dungeon", 20260919


def make_village(assets, T):
    world = core.WorldMap(W, H, assets)
    world.generate_biome("grassland", 20260920)
    dirt, stone, water = T["grassland_dirt"], T["stone"], T["water"]
    chest = T["dungeon_chest"]
    for y in range(12, 18):                    # the plaza
        for x in range(15, 25):
            world.data[y][x] = dirt
    for dy in range(3):                        # the well: stone ring, water heart
        for dx in range(3):
            world.data[13 + dy][18 + dx] = stone if (dx, dy) != (1, 1) else water
    for x, y in ((16, 13), (23, 16), (19, 17)):  # supply caches
        world.object_layer[y][x] = chest
    return world, "grassland", 20260920


def make_maze(assets, T):
    rnd = random.Random(20260921)
    wall, floor = T["dungeon_wall"], T["dungeon_floor"]
    world = core.WorldMap(W, H, assets)
    for y in range(H):
        for x in range(W):
            world.data[y][x] = wall
            world.collision_layer[y][x] = True
    cw, ch = W // 2, H // 2

    def open_cell(x, y):
        world.data[y][x] = floor
        world.collision_layer[y][x] = False

    visited = [[False] * cw for _ in range(ch)]
    stack = [(0, 0)]
    visited[0][0] = True
    open_cell(1, 1)
    while stack:                               # recursive backtracker
        cx, cy = stack[-1]
        nbs = [(cx + dx, cy + dy, dx, dy) for dx, dy in
               ((1, 0), (-1, 0), (0, 1), (0, -1))
               if 0 <= cx + dx < cw and 0 <= cy + dy < ch
               and not visited[cy + dy][cx + dx]]
        if not nbs:
            stack.pop()
            continue
        nx, ny, dx, dy = rnd.choice(nbs)
        visited[ny][nx] = True
        open_cell(cx * 2 + 1 + dx, cy * 2 + 1 + dy)
        open_cell(nx * 2 + 1, ny * 2 + 1)
        stack.append((nx, ny))
    for _ in range(14):                        # knock a few loops in — a perfect
        x = rnd.randrange(1, W - 1)             # maze is a lonely maze
        y = rnd.randrange(1, H - 1)
        if world.data[y][x] == wall:
            open_cell(x, y)
    open_cell(1, 0)                            # entry notch (top edge)
    open_cell(W - 2, H - 1)                    # exit notch (bottom edge)
    world.object_layer[H - 2][W - 2] = T["dungeon_chest"]  # prize at the exit
    return world, "dungeon", 20260921


def main():
    assets, T = tile_ids()
    for maker, fname in ((lambda: make_dungeon(assets), "starter-dungeon.json"),
                         (lambda: make_village(assets, T), "starter-village.json"),
                         (lambda: make_maze(assets, T), "starter-maze.json")):
        world, biome, seed = maker()
        write(world, fname, biome, seed)


if __name__ == "__main__":
    main()
