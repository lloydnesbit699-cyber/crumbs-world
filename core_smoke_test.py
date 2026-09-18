#!/usr/bin/env python3
"""Smoke test for crumbs_core.py — the headless Crumbs Vault core.
Prints PASS/FAIL per check. Exits 0 only if every check passes.
Run from the crumbs-vault-dungeon folder:  python3 core_smoke_test.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crumbs_core as core
from crumbs_core import (
    NoiseGenerator, WorldMap, Player, AssetManager, HistoryManager,
    SetTileCommand, MapSnapshotCommand, ImageProcessor, PIL_AVAILABLE,
)

results = []


def check(name, fn):
    try:
        fn()
    except AssertionError as e:
        results.append((name, False, str(e)))
        print(f"FAIL: {name} — {e}")
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"FAIL: {name} — {type(e).__name__}: {e}")
    else:
        results.append((name, True, ""))
        print(f"PASS: {name}")


# 1. Noise determinism: same seed -> identical output
def t_noise_determinism():
    a = NoiseGenerator(seed=1234)
    b = NoiseGenerator(seed=1234)
    vals_a = [a.noise2d(x * 0.37, y * 0.61) for y in range(8) for x in range(8)]
    vals_b = [b.noise2d(x * 0.37, y * 0.61) for y in range(8) for x in range(8)]
    assert vals_a == vals_b, "same seed gave different noise"
    c = NoiseGenerator(seed=9999)
    vals_c = [c.noise2d(x * 0.37, y * 0.61) for y in range(8) for x in range(8)]
    assert vals_a != vals_c, "different seeds gave identical noise (suspicious)"

check("noise determinism (same seed -> same output)", t_noise_determinism)


# 2. AssetManager loads the real sprite_library.json (PNGs missing -> preserved)
def t_library_load():
    lib_path = os.path.join(HERE, "sprite_library.json")
    assert os.path.exists(lib_path), "sprite_library.json not found next to core"
    am = AssetManager()
    assert len(am._preserved_entries) == 2, (
        f"expected 2 preserved entries (hero4.png/3.png missing), got {len(am._preserved_entries)}")
    ids = sorted(e.get("id") for e in am._preserved_entries)
    assert ids == [13, 24], f"preserved IDs wrong: {ids}"
    # default color tiles + biome tiles exist
    assert am.tiles[0]["type"] == "color", "default tile 0 missing"
    assert len(am.tiles) > 6, "biome tiles were not created"

check("sprite library loads; missing-PNG entries preserved", t_library_load)


# 3. vault_map.txt loads via load_csv
def t_csv_load():
    am = AssetManager()
    wm = WorldMap(1, 1, am)
    assert wm.load_csv(os.path.join(HERE, "vault_map.txt")), "load_csv failed"
    assert (wm.width, wm.height) == (25, 15), f"expected 25x15, got {wm.width}x{wm.height}"
    assert all(v == 0 for row in wm.data for v in row), "starter map should be all zeros"

check("vault_map.txt loads (25x15, all zeros)", t_csv_load)


# 4. Biome generation fills the map with valid tile IDs
def t_biome_gen():
    am = AssetManager()
    for biome in ("dungeon", "grassland", "desert"):
        wm = WorldMap(15, 25, am)
        wm.generate_biome(biome, seed=7)
        assert len(wm.data) == 25 and len(wm.data[0]) == 15, f"{biome}: wrong dims"
        bad = [v for row in wm.data for v in row if v not in am.tiles]
        assert not bad, f"{biome}: {len(bad)} cells reference unknown tile IDs"
        assert len(set(v for row in wm.data for v in row)) > 1, f"{biome}: map is one flat tile"

check("biome generation (dungeon/grassland/desert) -> valid tiles", t_biome_gen)


# 5. Map save/load round-trip (all three layers)
def t_map_roundtrip():
    am = AssetManager()
    wm = WorldMap(12, 10, am)
    wm.generate_biome("dungeon", seed=42)
    wm.object_layer[3][4] = 24
    wm.collision_layer[5][5] = True
    path = os.path.join(tempfile.gettempdir(), "crumbs_core_test_map.json")
    assert wm.save(path), "save failed"
    wm2 = WorldMap(1, 1, am)
    assert wm2.load(path), "load failed"
    assert (wm2.width, wm2.height) == (12, 10), "dims changed"
    assert wm2.data == wm.data, "tile layer changed"
    assert wm2.object_layer == wm.object_layer, "object layer changed"
    assert wm2.collision_layer == wm.collision_layer, "collision layer changed"
    os.remove(path)

check("map save/load round-trip (tiles/objects/collision)", t_map_roundtrip)


# 6. Undo/redo cycle
def t_undo_redo():
    am = AssetManager()
    wm = WorldMap(10, 10, am)
    hist = HistoryManager()
    old = wm.data[2][2]
    cmd = SetTileCommand(wm, 2, 2, old, 99)
    cmd.execute()
    hist.push(cmd)
    assert wm.data[2][2] == 99, "execute did not apply"
    assert hist.undo(), "undo returned False"
    assert wm.data[2][2] == old, "undo did not restore old value"
    assert hist.redo(), "redo returned False"
    assert wm.data[2][2] == 99, "redo did not re-apply"
    # snapshot command (map generation undo)
    before = [row[:] for row in wm.data]
    wm.generate_biome("grassland", seed=5)
    after = [row[:] for row in wm.data]
    snap = MapSnapshotCommand(wm, (before, wm.object_layer, wm.collision_layer),
                              (after, wm.object_layer, wm.collision_layer))
    hist.push(snap)
    assert hist.undo() and wm.data == before, "snapshot undo failed"

check("undo/redo cycle (tile edit + generation snapshot)", t_undo_redo)


# 7. Sprite-library save/load round-trip via preserved entries
def t_library_roundtrip():
    am = AssetManager()
    assert len(am._preserved_entries) == 2
    tmp = os.path.join(tempfile.gettempdir(), "crumbs_core_test_lib.json")
    am.sprite_library_path = tmp
    am.save_sprite_library()
    with open(tmp) as f:
        saved = json.load(f)
    assert len(saved) == 2 and {e["id"] for e in saved} == {13, 24}, (
        f"saved library wrong: {[e.get('id') for e in saved]}")
    am2 = AssetManager(sprite_library_path=tmp)
    assert len(am2._preserved_entries) == 2, "reload lost preserved entries"
    assert {e["id"] for e in am2._preserved_entries} == {13, 24}
    os.remove(tmp)

check("sprite-library save/load round-trip (entries survive)", t_library_roundtrip)


# 8. Player movement + collision
def t_player():
    am = AssetManager()
    wm = WorldMap(10, 10, am)
    wm.generate_biome("dungeon", seed=3)
    p = Player(wm, am)
    p.move_dx, p.move_dy = 1, 0
    x0 = p.x
    p.update()
    assert p.x != x0 or not p.can_move_to(x0 + p.speed, p.y), "player did not attempt move"
    # wall of collision must block
    tx, ty = int(p.x // 64), int(p.y // 64)
    nx = min(tx + 1, wm.width - 1)
    wm.collision_layer[ty][nx] = True
    blocked = not p.can_move_to((nx * 64) + 1, (ty * 64) + 1)
    assert blocked, "collision layer did not block the player"

check("player movement respects collision layer", t_player)


# 9. Works with NO Pillow installed (stdlib-only import)
def t_no_pil():
    blocker = (
        "import sys\n"
        "class _B:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'PIL' or name.startswith('PIL.'):\n"
        "            raise ImportError('blocked for smoke test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _B())\n"
        f"sys.path.insert(0, {HERE!r})\n"
        "import crumbs_core as c\n"
        "assert c.PIL_AVAILABLE is False, 'PIL should be blocked'\n"
        "try:\n"
        "    c.ImageProcessor.crop(None, (0, 0, 1, 1))\n"
        "    print('NO-RAISE')\n"
        "except RuntimeError as e:\n"
        "    assert 'Pillow' in str(e), 'error message should name Pillow'\n"
        "    print('CLEAR-ERROR')\n"
        "n = c.NoiseGenerator(1); n.noise2d(0.5, 0.5)\n"
        "am = c.AssetManager(); wm = c.WorldMap(5, 5, am)\n"
        "wm.generate_biome('dungeon', seed=1)\n"
        "print('STDLIB-OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", blocker],
                       capture_output=True, text=True, timeout=60)
    out = r.stdout + r.stderr
    assert r.returncode == 0, f"subprocess crashed: {out[-500:]}"
    assert "CLEAR-ERROR" in r.stdout, f"no clear Pillow error: {out[-500:]}"
    assert "STDLIB-OK" in r.stdout, f"core broke without PIL: {out[-500:]}"

check("imports + runs with Pillow missing (clear error, no crash)", t_no_pil)


# 10. Pillow-dependent paths (only if Pillow is present here)
def t_pil_paths():
    if not PIL_AVAILABLE:
        print("SKIP: Pillow-dependent paths (Pillow not installed here)")
        return
    from PIL import Image as PImage
    img = PImage.new("RGBA", (128, 64), (255, 0, 0, 255))
    frames = ImageProcessor.slice_sprite_sheet(img, 1, 2)
    assert len(frames) == 2 and frames[0].size == (64, 64), "slice failed"
    assert ImageProcessor.auto_detect_grid(img) == (1, 2, (64, 64)), "grid detect failed"
    assert ImageProcessor.flip(img).size == (128, 64)
    assert ImageProcessor.rotate(img, 90).size == (64, 128)
    assert ImageProcessor.resize(img, 32, 32).size == (32, 32)
    assert ImageProcessor.crop(img, (0, 0, 10, 10)).size == (10, 10)
    am = AssetManager()
    thumb = am.get_thumbnail(0)
    assert thumb is not None and thumb.size == (40, 40), "thumbnail failed"
    # not a Tk PhotoImage — must be a plain PIL image
    assert type(thumb).__name__ == "Image", f"thumbnail wrong type: {type(thumb)}"

check("Pillow paths: slice/detect/transform/thumbnail", t_pil_paths)


print()
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"{passed}/{total} checks passed")
sys.exit(0 if passed == total else 1)
