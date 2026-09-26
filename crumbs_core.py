#===========================================================================================
# Crumbs Core — headless game-logic core extracted from Vaults World Editor v3.0
#===========================================================================================
# Phone-safe, GUI-free. stdlib only, except an OPTIONAL Pillow import:
#   - everything except ImageProcessor and image loading works with bare python3
#     (e.g. iSH). Pillow is bundled with a-Shell, so image features work there.
#   - if Pillow is missing, importing this module still works and ImageProcessor
#     methods raise a clear error instead of breaking.
# The original Tkinter editor (vaults_editor.py) is untouched; this file shares
# its data formats (sprite_library.json, vault_map.txt / CSV maps).
#===========================================================================================

import os
import json
import random
import math
import re
import shutil
from collections import deque

try:
    from PIL import Image, ImageOps, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

__all__ = [
    "PIL_AVAILABLE",
    "SCRIPT_DIR", "ASSET_LIBRARY_PATH",
    "DEFAULT_TILE_SIZE", "DEFAULT_GRID_WIDTH", "DEFAULT_GRID_HEIGHT",
    "BIOMES",
    "ImageProcessor",
    "Command", "SetTileCommand", "MultiCommand", "MapSnapshotCommand",
    "HistoryManager",
    "NoiseGenerator",
    "AssetManager",
    "WorldMap",
    "Player",
]


# ==========================================
# CONFIGURATION
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_LIBRARY_PATH = os.path.join(SCRIPT_DIR, "asset_library")
DEFAULT_TILE_SIZE = 64
DEFAULT_GRID_WIDTH = 40
DEFAULT_GRID_HEIGHT = 40


# ==========================================
# BIOME DATA
# ==========================================
BIOMES = {
    "grassland": {
        "name": "Grassland",
        "colors": {
            "deep_water": "#2a6b9e", "water": "#3d8bce", "sand": "#d2c290",
            "grass_dark": "#4a8c2e", "grass": "#5a9c33", "grass_light": "#6ab844",
            "dirt": "#7b5233", "stone": "#6a6a6a", "snow": "#f0f8ff"
        },
        "noise_settings": {"water_level": 0.35, "sand_level": 0.42, "grass_level": 0.65, "stone_level": 0.85}
    },
    "desert": {
        "name": "Desert",
        "colors": {
            "deep_water": "#1a4d6b", "water": "#2d6b9e", "sand_dark": "#a0825a",
            "sand": "#c2b280", "sand_light": "#e6c88a", "rock": "#8b7355",
            "stone": "#6b5a4a", "cactus": "#2d5a2e"
        },
        "noise_settings": {"water_level": 0.25, "sand_level": 0.40, "grass_level": 0.70, "stone_level": 0.90}
    },
    "arctic": {
        "name": "Arctic",
        "colors": {
            "deep_water": "#1a3d5b", "water": "#2d5b8e", "ice": "#a8d8ea",
            "snow_dark": "#e8f4f8", "snow": "#ffffff", "ice_rock": "#6b7c85",
            "stone": "#4a5a6a"
        },
        "noise_settings": {"water_level": 0.30, "sand_level": 0.45, "grass_level": 0.60, "stone_level": 0.80}
    },
    "forest": {
        "name": "Forest",
        "colors": {
            "deep_water": "#0d3d5b", "water": "#1d5b7e", "mud": "#4a3728",
            "grass_dark": "#1d4a1a", "grass": "#2d5a1a", "grass_light": "#3d6a2a",
            "dirt": "#3d2818", "stone": "#2a2a2a"
        },
        "noise_settings": {"water_level": 0.30, "sand_level": 0.40, "grass_level": 0.70, "stone_level": 0.88}
    },
    "ocean": {
        "name": "Ocean",
        "colors": {
            "deep_ocean": "#0a1628", "ocean": "#1a3d5b", "water": "#2d6b9e",
            "shallow": "#4a90c2", "sand": "#f4d03f", "beach": "#e6c88a",
            "grass": "#3d8b3d", "stone": "#5a5a5a"
        },
        "noise_settings": {"water_level": 0.50, "sand_level": 0.60, "grass_level": 0.75, "stone_level": 0.90}
    },
    "dungeon": {
        "name": "Dungeon",
        "colors": {
            "floor": "#757575", "floor_dark": "#555555", "wall": "#9a9a9a",
            "wall_dark": "#6a6a6a", "door": "#8b5a2b", "chest": "#c9a227"
        },
        "noise_settings": {"water_level": 0.0, "sand_level": 0.0, "grass_level": 0.0, "stone_level": 0.0}
    }
}

# v5.16: deterministic generation presets — named recipes with a fixed biome
# plus noise overrides, so the same seed always rebuilds the same map with
# a distinct identity. {preset: {biome, noise overrides, label, blurb}}.
GENERATION_PRESETS = {
    "archipelago": {
        "label": "Archipelago", "biome": "ocean",
        "noise": {"water_level": 0.58, "sand_level": 0.66, "grass_level": 0.78},
        "blurb": "Scattered isles in open water — boats and bridges country.",
    },
    "highlands": {
        "label": "Highlands", "biome": "grassland",
        "noise": {"water_level": 0.30, "sand_level": 0.38, "grass_level": 0.58,
                  "stone_level": 0.78},
        "blurb": "Rolling ridges and rocky tors; cliffs everywhere.",
    },
    "dune-sea": {
        "label": "Dune Sea", "biome": "desert",
        "noise": {"water_level": 0.12, "sand_level": 0.45, "grass_level": 0.75,
                  "stone_level": 0.92},
        "blurb": "Endless sand with rare stone teeth. Bring water.",
    },
    "frostwild": {
        "label": "Frostwild", "biome": "arctic",
        "noise": {"water_level": 0.34, "sand_level": 0.48, "grass_level": 0.62,
                  "stone_level": 0.80},
        "blurb": "Frozen lakes, ice fields, and snow-drowned rock.",
    },
    "deepwood": {
        "label": "Deepwood", "biome": "forest",
        "noise": {"water_level": 0.32, "sand_level": 0.40, "grass_level": 0.68,
                  "stone_level": 0.86},
        "blurb": "Thick dark forest cut by muddy streams.",
    },
    "undercrypt": {
        "label": "Undercrypt", "biome": "dungeon",
        "noise": {},
        "blurb": "Classic dungeon floors, walls, and doors.",
    },
}


# ==========================================
# IMAGE PROCESSOR (requires Pillow)
# ==========================================
def _require_pil():
    if not PIL_AVAILABLE:
        raise RuntimeError(
            "ImageProcessor needs Pillow, which is not installed in this Python. "
            "On iSH: this Python can't do image work — use the map/text features only. "
            "On a-Shell: Pillow is bundled, so this should not happen. "
            "On a computer: pip install Pillow"
        )


class ImageProcessor:
    @staticmethod
    def crop(img, box):
        _require_pil()
        return img.crop((box[0], box[1], box[0]+box[2], box[1]+box[3]))

    @staticmethod
    def rotate(img, angle):
        _require_pil()
        return img.rotate(angle, expand=True, resample=Image.Resampling.NEAREST)

    @staticmethod
    def flip(img, horizontal=True, vertical=False):
        _require_pil()
        if horizontal and vertical:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif horizontal:
            return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif vertical:
            return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return img

    @staticmethod
    def resize(img, width, height):
        _require_pil()
        return img.resize((width, height), Image.Resampling.NEAREST)

    @staticmethod
    def slice_sprite_sheet(img, rows, cols, tile_size=None):
        _require_pil()
        frames = []
        w, h = img.size
        tile_w = tile_size[0] if tile_size else w // cols
        tile_h = tile_size[1] if tile_size else h // rows
        for row in range(rows):
            for col in range(cols):
                x, y = col * tile_w, row * tile_h
                frames.append(img.crop((x, y, x + tile_w, y + tile_h)))
        return frames

    @staticmethod
    def auto_detect_grid(img, min_tile=16, max_tile=256):
        _require_pil()
        # prefer grids that divide the image evenly into square tiles of a
        # sensible size, instead of an error term that is always zero
        w, h = img.size
        best_fit = None
        best_score = float('inf')
        for cols in range(1, 17):
            if w % cols != 0:
                continue
            tw = w // cols
            for rows in range(1, 17):
                if h % rows != 0:
                    continue
                th = h // rows
                if not (min_tile <= tw <= max_tile and min_tile <= th <= max_tile):
                    continue
                # prefer square tiles, tile sizes near 64px, modest grid counts
                score = abs(tw - th) + abs(tw - 64) * 0.5 + (cols + rows) * 0.1
                if score < best_score:
                    best_score = score
                    best_fit = (rows, cols, (tw, th))
        return best_fit if best_fit else (1, 1, (w, h))


# ==========================================
# UNDO/REDO SYSTEM
# ==========================================
class Command:
    def execute(self): pass
    def undo(self): pass


class SetTileCommand(Command):
    def __init__(self, world, x, y, old_val, new_val, layer='tiles'):
        self.world = world
        self.x, self.y = x, y
        self.old_val, self.new_val = old_val, new_val
        self.layer = layer

    def _grid(self):
        # collision painting edits the collision layer
        if self.layer == 'objects':
            return self.world.object_layer
        if self.layer == 'collision':
            return self.world.collision_layer
        return self.world.data

    def execute(self):
        self._grid()[self.y][self.x] = self.new_val

    def undo(self):
        self._grid()[self.y][self.x] = self.old_val


class MultiCommand(Command):
    """One undo step for a multi-cell brush stroke."""
    def __init__(self, commands):
        self.commands = commands

    def execute(self):
        for c in self.commands:
            c.execute()

    def undo(self):
        for c in reversed(self.commands):
            c.undo()


class MapSnapshotCommand(Command):
    """One undo step that restores whole map layers (used for generation)."""
    def __init__(self, world, old_layers, new_layers):
        self.world = world
        self.old_data, self.old_objects, self.old_collision = old_layers
        self.new_data, self.new_objects, self.new_collision = new_layers

    def _apply(self, data, objects, collision):
        self.world.data = [row[:] for row in data]
        self.world.object_layer = [row[:] for row in objects]
        self.world.collision_layer = [row[:] for row in collision]

    def execute(self):
        self._apply(self.new_data, self.new_objects, self.new_collision)

    def undo(self):
        self._apply(self.old_data, self.old_objects, self.old_collision)


class StateSnapshotCommand(Command):
    """v5.0: undo/redo for everything that isn't a map-layer paint —
    patrols, nature traits, rules, game rules, world profile, and the map
    itself. get_state/set_state are supplied by the host (crumbs_hud.py),
    which owns those stores; this command just carries before/after."""
    def __init__(self, get_state, set_state, label="edit"):
        self.get_state = get_state
        self.set_state = set_state
        self.before = get_state()
        self.after = None
        self.label = label

    def capture_after(self):
        self.after = self.get_state()

    def execute(self):
        self.set_state(self.after if self.after is not None else self.before)

    def undo(self):
        self.set_state(self.before)

    def redo(self):
        self.set_state(self.after)


class HistoryManager:
    def __init__(self, max_steps=50):
        self.undo_stack = deque(maxlen=max_steps)
        self.redo_stack = deque(maxlen=max_steps)

    def push(self, command):
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            cmd = self.undo_stack.pop()
            cmd.undo()
            self.redo_stack.append(cmd)
            return True
        return False

    def redo(self):
        if self.redo_stack:
            cmd = self.redo_stack.pop()
            cmd.execute()
            self.undo_stack.append(cmd)
            return True
        return False


# ==========================================
# NOISE GENERATOR
# ==========================================
class NoiseGenerator:
    def __init__(self, seed=None):
        self.seed = seed if seed is not None else random.randint(0, 10000)
        self.rng = random.Random(self.seed)  # private generator; never touches global random
        self.permutation = list(range(256)) * 2
        self.rng.shuffle(self.permutation)

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, t, a, b):
        return a + t * (b - a)

    def grad(self, hash, x, y):
        h = hash & 3
        return {0: x + y, 1: -x + y, 2: x - y, 3: -x - y}.get(h, x + y)

    def noise2d(self, x, y):
        X, Y = int(math.floor(x)) & 255, int(math.floor(y)) & 255
        x -= math.floor(x)
        y -= math.floor(y)
        u, v = self.fade(x), self.fade(y)
        A, B = self.permutation[X] + Y, self.permutation[X + 1] + Y
        return self.lerp(
            v,
            self.lerp(u, self.grad(self.permutation[A], x, y),
                         self.grad(self.permutation[B], x - 1, y)),
            self.lerp(u, self.grad(self.permutation[A + 1], x, y - 1),
                         self.grad(self.permutation[B + 1], x - 1, y - 1))
        )


# ==========================================
# SUBCATEGORY TAXONOMY (v5.25)
# Minecraft-style separation for the palette: tiles split into
# walls/floors/doors/roofs/materials/natural, objects into
# furniture/containers/props/lighting, and characters & creatures get
# their own group. Tiles carry a 'subcategory' field, guessed from the
# name when nothing explicit was assigned (this is the "automatic
# categorization" the asset docs called out as still needing work).
# (subcategory, [name-token keywords]); first match wins, so the
# specific comes before the general.
SUBCATEGORY_HINTS = [
    ("lighting",   ["torch", "lamp", "lantern", "candle", "brazier",
                    "chandelier", "glow"]),
    ("furniture",  ["chair", "table", "bed", "sofa", "stool", "desk",
                    "shelf", "throne", "bench", "cabinet", "dresser"]),
    ("containers", ["chest", "barrel", "crate", "box", "sack", "pot", "urn",
                    "coffer", "basket"]),
    ("walls",      ["wall"]),
    ("floors",     ["floor"]),
    ("doors",      ["door", "gate", "portal"]),
    ("roofs",      ["roof"]),
    ("materials",  ["brick", "stone", "wood", "plank", "metal", "marble"]),
    ("natural",    ["grass", "sand", "water", "dirt", "mud", "snow", "lava",
                    "swamp", "tree", "bush", "flower", "rock", "cactus",
                    "beach", "ocean", "ice"]),
    ("props",      ["statue", "pillar", "column", "rubble", "bones", "altar",
                    "fountain", "well", "sign", "banner", "rug", "carpet",
                    "stairs", "trap", "grid", "noise", "fade", "band",
                    "gradient"]),
]
# creature name-tokens — a character-preset tile matching one of these
# lands in "creatures", otherwise in "characters".
CREATURE_HINTS = ["goblin", "orc", "rat", "bat", "spider", "wolf", "snake",
                  "imp", "skeleton", "zombie", "dragon", "slime", "hound",
                  "scorpion", "troll", "ghost", "demon", "beast", "critter",
                  "serpent"]
# palette display order per tab ("other" is appended only when non-empty —
# Law 11: no dead buttons, so empty groups never render a chip).
SUBCATEGORY_ORDER = {
    "tiles": ["walls", "floors", "doors", "roofs", "materials", "natural"],
    "objects": ["furniture", "containers", "props", "lighting"],
    "characters": ["characters", "creatures"],
}


def guess_subcategory(name, preset=None, category="tiles"):
    """v5.25: filename/name-hint auto-categorization. Returns a subcategory
    string; never raises, never returns empty."""
    try:
        tokens = set(re.split(r"[^a-z0-9]+", (name or "").lower()))
        tokens.discard("")
        # characters & creatures are their own group — by preset, or by the
        # hero token for built-ins that predate presets (e.g. "Hood Hero").
        if preset == "character" or "hero" in tokens:
            for kw in CREATURE_HINTS:
                if kw in tokens:
                    return "creatures"
            return "characters"
        for sub, kws in SUBCATEGORY_HINTS:
            for kw in kws:
                if kw in tokens:
                    return sub
    except Exception:
        pass
    return "other"


# v5.26: hardened taxonomy — every subcategory has exactly ONE home tab.
# A floor is a floor: it lives in Tiles under the Floors chip, even though
# it's a "made thing" like an object. Imports keep the subcategory guessed
# at import time, so the routing is stable and automatic.
SUBCATEGORY_TABS = {
    "walls": "tiles", "floors": "tiles", "doors": "tiles",
    "roofs": "tiles", "materials": "tiles", "natural": "tiles",
    "furniture": "objects", "containers": "objects", "props": "objects",
    "lighting": "objects", "other": "objects",
    "characters": "characters", "creatures": "characters",
}
def tab_for_subcategory(sub):
    """v5.26: which palette tab a subcategory belongs to. Never raises,
    never returns empty — unknown subcategories are objects."""
    try:
        return SUBCATEGORY_TABS.get((sub or "other").lower(), "objects")
    except Exception:
        return "objects"


_BIOME_PREFIXES = ("dungeon", "grassland", "desert", "arctic", "forest",
                   "ocean", "core")
def display_name(name):
    """v5.26: the automatic name system — one clean human-readable label
    derived from the raw tile name. 'dungeon_wall_dark' -> 'Dark Wall',
    'Starter Dark floor' -> 'Starter Dark Floor', 'cell_4521' -> 'Cell 4521'.
    Never raises, never returns empty."""
    try:
        s = (name or "").replace("_", " ").strip()
        low = s.lower()
        for b in _BIOME_PREFIXES:
            if low.startswith(b + " ") and len(s) > len(b) + 1:
                s = s[len(b) + 1:].strip()
                break
        words = s.split()
        if words and words[-1].lower() in ("dark", "light"):
            words.insert(0, words.pop())
        labeled = " ".join(w[:1].upper() + w[1:] for w in words)
        return labeled or "Tile"
    except Exception:
        return "Tile"


# ==========================================
# ASSET MANAGER (headless — no Tkinter)
# ==========================================
class AssetManager:
    def __init__(self, sprite_library_path=None):
        self.tiles = {}
        self.selected_id = 0
        self.pil_available = PIL_AVAILABLE
        self.sprite_library_path = sprite_library_path or os.path.join(SCRIPT_DIR, "sprite_library.json")
        self.categories = {'tiles': [], 'objects': [], 'animations': []}
        self.next_tile_id = 0  # single shared tile-ID counter; never reuses a number
        # library entries whose files are missing (e.g. PNGs still on the old
        # PC) can't become tiles, but they must survive every later save
        self._preserved_entries = []
        self._reserved_ids = set()  # IDs owned by preserved entries; never handed out

        if not os.path.exists(ASSET_LIBRARY_PATH):
            os.makedirs(ASSET_LIBRARY_PATH, exist_ok=True)

        self.create_default_tiles()
        self.load_sprite_library()
        self.create_biome_tiles()

    def _next_id(self):
        """Hand out a tile ID that is not already in use."""
        while self.next_tile_id in self.tiles or self.next_tile_id in self._reserved_ids:
            self.next_tile_id += 1
        tid = self.next_tile_id
        self.next_tile_id += 1
        return tid

    def unique_asset_path(self, basename):
        """Pick a filename in asset_library/ that does not exist yet,
        appending _2, _3... on collision instead of silently reusing the old file."""
        name, ext = os.path.splitext(basename)
        dest = os.path.join(ASSET_LIBRARY_PATH, basename)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(ASSET_LIBRARY_PATH, f"{name}_{n}{ext}")
            n += 1
        return dest

    def _resolve_filepath(self, fp):
        """Resolve a library filepath for loading. Entries store paths relative
        to the sprite_library.json folder; fall back to CWD like the editor did."""
        if not fp:
            return None
        if os.path.isabs(fp) and os.path.exists(fp):
            return fp
        if os.path.exists(fp):
            return fp
        lib_dir = os.path.dirname(os.path.abspath(self.sprite_library_path))
        candidate = os.path.join(lib_dir, fp)
        if os.path.exists(candidate):
            return candidate
        return None

    def create_default_tiles(self):
        colors = [('#1a4d6b', 'deep_water'), ('#2d6b9e', 'water'), ('#c2b280', 'sand'),
                  ('#3d6b2e', 'grass_dark'), ('#4a7c23', 'grass'), ('#5a5a5a', 'stone')]
        for i, (color, name) in enumerate(colors):
            self.add_tile(i, 'color', {'color': color, 'name': name, 'category': 'tiles'})

    def create_biome_tiles(self):
        for biome_name, data in BIOMES.items():
            for color_name, color_hex in data['colors'].items():
                exists = False
                for tid, t in self.tiles.items():
                    if t.get('color') == color_hex and t.get('name') == f'{biome_name}_{color_name}':
                        exists = True
                        break
                if not exists:
                    self.add_tile(self._next_id(), 'color', {
                        'color': color_hex, 'name': f'{biome_name}_{color_name}', 'category': 'tiles'
                    })

    def add_tile(self, tid, ttype, data):
        self.tiles[tid] = {
            'type': ttype,
            'name': data.get('name', f'ID {tid}'),
            'category': data.get('category', 'tiles'),
            'properties': {'passable': True, 'solid': False, 'interactive': False},
            **data
        }
        # v5.25: every tile knows its subcategory — explicit assignment
        # wins, otherwise the name-hint guesser categorizes it.
        if not self.tiles[tid].get('subcategory'):
            self.tiles[tid]['subcategory'] = guess_subcategory(
                self.tiles[tid]['name'], data.get('preset'),
                self.tiles[tid]['category'])
        cat = self.tiles[tid]['category']
        if cat not in self.categories:
            self.categories[cat] = []
        if tid not in self.categories[cat]:
            self.categories[cat].append(tid)
        if tid >= self.next_tile_id:  # keep the counter ahead of every used ID
            self.next_tile_id = tid + 1

    def load_sprite_library(self):
        if not os.path.exists(self.sprite_library_path):
            return
        try:
            with open(self.sprite_library_path, 'r') as f:
                library = json.load(f)
            for entry in library:
                if not self.pil_available:
                    # keep entries we can't load so a save doesn't erase them
                    self._preserve_entry(entry)
                    continue
                tid = entry.get('id')
                if tid is None or tid in self.tiles:
                    tid = self._next_id()  # saved ID collides: remap, never clobber
                frames = []
                resolved = []  # resolved paths used for loading; originals stay saved
                for fp in entry.get('filepaths', []):
                    rp = self._resolve_filepath(fp)
                    if rp:
                        img = Image.open(rp).convert("RGBA")
                        img = img.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                        frames.append(img)
                        resolved.append(rp)
                if frames:
                    # frames load in filepath order; frame_order rebuilds
                    # the exact playing sequence the user chose
                    order = entry.get('frame_order')
                    if order:
                        ordered = [frames[i] for i in order if 0 <= i < len(frames)]
                        if len(ordered) == len(order):
                            frames = ordered
                    ttype = 'animation' if (entry.get('type') == 'animation' or len(frames) > 1) else 'image'
                    data = {'frames': frames, 'filepaths': entry.get('filepaths', []),
                            'frame_order': entry.get('frame_order', []),
                            'current_frame': 0, 'frame_delay': entry.get('frame_delay', 150)}
                    if ttype == 'image':
                        data['image'] = frames[0]
                    self.add_tile(tid, ttype, {'name': entry.get('name', f'Sprite {tid}'),
                                               'category': entry.get('category', 'objects'), **data})
                else:
                    # the entry's files are missing (PNGs still on the old PC):
                    # it can't become a tile, but it must survive later saves
                    self._preserve_entry(entry)
        except Exception as e:
            print(f"WARNING: library load error: {e}")

    def _preserve_entry(self, entry):
        """Keep an unloadable library entry and reserve its ID so no
        generated tile can take it and no later save can drop it."""
        tid = entry.get('id')
        if isinstance(tid, int) and tid in self.tiles:
            # collides with a built-in tile: keep the entry under a fresh ID
            tid = self._next_id()
            entry = dict(entry, id=tid)
        self._preserved_entries.append(entry)
        if isinstance(entry.get('id'), int):
            self._reserved_ids.add(entry['id'])

    def load_images(self, filepaths, category="tiles", process_ops=None):
        if not self.pil_available:
            return False, "Pillow not installed"
        try:
            loaded_count = 0
            new_id = None
            for filepath in filepaths:
                basename = os.path.basename(filepath)
                dest_path = self.unique_asset_path(basename)  # never reuse an old file
                shutil.copy2(filepath, dest_path)
                img = Image.open(dest_path).convert("RGBA")
                if process_ops:
                    img = self.apply_operations(img, process_ops)
                img = img.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                new_id = self._next_id()
                self.add_tile(new_id, 'image', {
                    'name': os.path.splitext(os.path.basename(dest_path))[0],
                    'category': category,
                    'image': img,
                    'frames': [img],
                    'filepaths': [dest_path]
                })
                loaded_count += 1
            if new_id is not None:
                self.selected_id = new_id
            self.save_sprite_library()
            return True, f"Loaded {loaded_count} tile(s)"
        except Exception as e:
            return False, str(e)

    def load_sprite_sheet(self, filepath, rows, cols, tile_size=None, category="tiles"):
        if not self.pil_available:
            return False, "Pillow not installed"
        try:
            img = Image.open(filepath).convert("RGBA")
            frames = ImageProcessor.slice_sprite_sheet(img, rows, cols, tile_size)
            basename = os.path.basename(filepath)
            dest_path = self.unique_asset_path(basename)
            shutil.copy2(filepath, dest_path)
            new_id = None
            for i, frame in enumerate(frames):
                new_id = self._next_id()
                frame_resized = frame.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                # persist each sliced frame as its own PNG so reloads keep the slices
                frame_path = self.unique_asset_path(f"{os.path.splitext(basename)[0]}_{i}.png")
                frame_resized.save(frame_path)
                self.add_tile(new_id, 'image', {
                    'name': f"{os.path.splitext(basename)[0]}_{i}",
                    'category': category,
                    'image': frame_resized,
                    'frames': [frame_resized],
                    'filepaths': [frame_path],
                    'sheet_index': i
                })
            if new_id is not None:
                self.selected_id = new_id
            self.save_sprite_library()
            return True, f"Sliced {len(frames)} frames"
        except Exception as e:
            return False, str(e)

    def create_animation(self, frame_ids, name=None, category="objects", frame_delay=150):
        try:
            frames = []
            filepaths = []
            frame_order = []  # filepath index per frame, in the exact playing order
            for fid in frame_ids:
                tile = self.tiles.get(fid)
                if tile and tile['type'] in ('image', 'animation'):
                    src_fps = tile.get('filepaths', [])
                    src_fp = src_fps[0] if src_fps else None
                    if src_fp not in filepaths:
                        filepaths.append(src_fp)
                    frames.append(tile['frames'][0])
                    frame_order.append(filepaths.index(src_fp))
            if not frames:
                return False, "No valid frames"
            new_id = self._next_id()
            self.add_tile(new_id, 'animation', {
                'name': name or f'Animation_{new_id}',
                'category': category,
                'frames': frames,
                'frame_order': frame_order,
                'filepaths': filepaths,
                'current_frame': 0,
                'frame_delay': frame_delay
            })
            self.selected_id = new_id
            self.save_sprite_library()
            return True, f"Created animation ({len(frames)} frames)"
        except Exception as e:
            return False, str(e)

    def apply_operations(self, img, ops):
        _require_pil()
        for op in ops:
            if op['type'] == 'crop':
                img = ImageProcessor.crop(img, op['box'])
            elif op['type'] == 'rotate':
                img = ImageProcessor.rotate(img, op['angle'])
            elif op['type'] == 'flip':
                img = ImageProcessor.flip(img, op.get('horizontal', False), op.get('vertical', False))
        return img

    def save_sprite_library(self):
        library = []
        seen_ids = set()
        for tid, tile in self.tiles.items():
            if tile['type'] in ('image', 'animation'):
                seen_ids.add(tid)
                library.append({
                    'id': tid,
                    'name': tile['name'],
                    'type': tile['type'],
                    'category': tile['category'],
                    'filepaths': tile.get('filepaths', []),
                    'frame_order': tile.get('frame_order', []),  # exact playing order
                    'frame_delay': tile.get('frame_delay', 150)
                })
        # re-emit entries whose files were missing at load time, so a save
        # can never silently erase them
        for entry in self._preserved_entries:
            if entry.get('id') not in seen_ids:
                library.append(entry)
                seen_ids.add(entry.get('id'))
        with open(self.sprite_library_path, 'w') as f:
            json.dump(library, f, indent=2)

    def get_category_tiles(self, category):
        return self.categories.get(category, [])

    def get_thumbnail(self, tid, size=40):
        """Headless version: returns a PIL Image (or None), never a Tk PhotoImage.
        v5.25: never throws — a tile with missing art yields None (the
        /api/thumb caller turns that into a 404, and the page paints a
        "?" placeholder), never a dead connection."""
        try:
            if not PIL_AVAILABLE:
                return None
            tile = self.tiles.get(tid)
            if not tile:
                return None
            if tile['type'] == 'color':
                return Image.new("RGBA", (size, size), tile['color'])
            frames = tile.get('frames') or []
            if not frames:
                return None
            frame = frames[tile.get('current_frame', 0) % len(frames)]
            return frame.resize((size, size), Image.Resampling.NEAREST)
        except Exception:
            return None


# ==========================================
# WORLD MAP
# ==========================================
def _build_color_map(assets_tiles, biome_name):
    """v5.0: resolve this biome's color names -> tile ids (shared by
    generate_biome and natural_tile_at)."""
    biome = BIOMES.get(biome_name, BIOMES["grassland"])
    # only tiles from THIS biome's own set are candidates, so shared
    # color names like "sand"/"water" can't resolve to another biome's tile.
    # Biome-owned tiles are named like "dungeon_wall"; nameless-prefix tiles
    # (the built-in defaults, user customs) stay shared.
    color_map = {}
    for tid, tile in assets_tiles.items():
        if tile['type'] != 'color':
            continue
        tname = tile.get('name', '')
        owner = next((b for b in BIOMES if tname.startswith(b + '_')), None)
        if owner is not None and owner != biome_name:
            continue  # belongs to a different biome
        for c_name, c_hex in biome["colors"].items():
            if tile.get('color') == c_hex:
                color_map[c_name] = tid
    # dungeon fallbacks resolve from the biome's own generated tiles,
    # not hardcoded IDs (7 and 8 are grassland water/sand)
    fallback = {'water': 1, 'sand': 2, 'grass': 4, 'stone': 5,
                'floor': color_map.get('floor', 0), 'wall': color_map.get('wall', 0)}
    return color_map, fallback


def _biome_cell(biome_name, color_map, fallback, settings, noise, x, y):
    """v5.0: the single tile the seed's noise places at (x, y)."""
    v = (noise.noise2d(x / 20.0, y / 20.0) + 1) / 2
    if biome_name == 'dungeon':
        if v > 0.6:
            return color_map.get('wall', fallback['wall'])
        return color_map.get('floor', fallback['floor'])
    if v < settings["water_level"]:
        return color_map.get('deep_water', color_map.get('water', fallback['water']))
    elif v < settings["sand_level"]:
        return color_map.get('sand', fallback['sand'])
    elif v < settings["grass_level"]:
        return color_map.get('grass', fallback['grass'])
    else:
        return color_map.get('stone', fallback['stone'])


def natural_tile_at(assets_tiles, biome_name, seed, x, y):
    """v5.0: the tile generate_biome(biome_name, seed) would have placed at
    (x, y) — the seed's own ground. The eraser restores this instead of a
    fixed tile 0. Returns None when the map has no known biome/seed."""
    if biome_name not in BIOMES or seed is None:
        return None
    biome = BIOMES[biome_name]
    color_map, fallback = _build_color_map(assets_tiles, biome_name)
    return _biome_cell(biome_name, color_map, fallback,
                       biome["noise_settings"], NoiseGenerator(seed), x, y)


def natural_grid(assets_tiles, biome_name, seed, w, h):
    """v5.0: the whole seed-ground grid at once (one noise/color-map build).
    None when the map has no known biome/seed."""
    if biome_name not in BIOMES or seed is None:
        return None
    biome = BIOMES[biome_name]
    color_map, fallback = _build_color_map(assets_tiles, biome_name)
    noise = NoiseGenerator(seed)
    settings = biome["noise_settings"]
    return [[_biome_cell(biome_name, color_map, fallback, settings,
                         noise, x, y) for x in range(w)] for y in range(h)]


class WorldMap:
    def __init__(self, width, height, assets):
        self.width, self.height = width, height
        self.assets = assets
        self.data = [[0 for _ in range(width)] for _ in range(height)]
        self.object_layer = [[None for _ in range(width)] for _ in range(height)]
        self.collision_layer = [[False for _ in range(width)] for _ in range(height)]

    def resize(self, w, h):
        # keep every tile/object/collision in the overlapping region —
        # resizing must never wipe the map
        old_w, old_h = self.width, self.height
        old_data, old_obj, old_col = self.data, self.object_layer, self.collision_layer
        self.width, self.height = w, h
        self.data = [[old_data[y][x] if y < old_h and x < old_w else 0
                      for x in range(w)] for y in range(h)]
        self.object_layer = [[old_obj[y][x] if y < old_h and x < old_w else None
                              for x in range(w)] for y in range(h)]
        self.collision_layer = [[old_col[y][x] if y < old_h and x < old_w else False
                                for x in range(w)] for y in range(h)]

    def generate_biome(self, biome_name, seed=None, noise_overrides=None):
        biome = BIOMES.get(biome_name, BIOMES["grassland"])
        noise = NoiseGenerator(seed)
        settings = dict(biome["noise_settings"])
        if noise_overrides:  # v5.16: preset recipes tweak the noise
            settings.update(noise_overrides)
        color_map, fallback = _build_color_map(self.assets.tiles, biome_name)
        for y in range(self.height):
            for x in range(self.width):
                # v5.0: per-cell logic shared with natural_tile_at so the
                # eraser can restore exactly what the seed placed here.
                self.data[y][x] = _biome_cell(
                    biome_name, color_map, fallback, settings, noise, x, y)

    def save(self, filepath, schema=None):
        try:
            if os.path.exists(filepath):
                shutil.copy2(filepath, filepath + ".backup")
            data = {
                'version': '3.0',
                'width': self.width,
                'height': self.height,
                'tiles': self.data,
                'objects': self.object_layer,
                'collision': self.collision_layer
            }
            if schema is not None:  # v5.16: data-schema stamp for migrations
                data['schema'] = schema
            # v5.29: atomic — a crash mid-save must never leave a torn map.
            # Write temp + fsync, then rename over the target; readers see
            # the old map or the new map, never half a JSON document.
            tmp = filepath + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, filepath)
            return True
        except Exception as e:
            print(f"ERROR saving map: {e}")
            return False

    def load(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self.width, self.height = data['width'], data['height']
            w, h = self.width, self.height

            def _grid(key, fill):
                # v5.16: a present-but-malformed layer (hand-edited JSON)
                # normalizes to a blank grid instead of crashing later.
                g = data.get(key)
                if (isinstance(g, list) and len(g) == h
                        and all(isinstance(r, list) and len(r) == w
                                for r in g)):
                    return [row[:] for row in g]
                return [[fill] * w for _ in range(h)]

            self.data = _grid('tiles', 0)
            self.object_layer = _grid('objects', None)
            self.collision_layer = _grid('collision', False)
            return True
        except Exception as e:
            print(f"ERROR loading map: {e}")
            return False

    def load_csv(self, filepath):
        """Legacy vault_map.txt-style comma-separated maps."""
        try:
            rows = []
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append([int(v) for v in line.split(',')])
            if not rows:
                print("WARNING: that file has no map data.")
                return False
            h = len(rows)
            w = max(len(r) for r in rows)
            self.width, self.height = w, h
            self.data = [[rows[y][x] if x < len(rows[y]) else 0 for x in range(w)] for y in range(h)]
            self.object_layer = [[None] * w for _ in range(h)]
            self.collision_layer = [[False] * w for _ in range(h)]
            return True
        except Exception as e:
            print(f"ERROR loading CSV map: {e}")
            return False


# ==========================================
# PLAYER
# ==========================================
class Player:
    def __init__(self, world, assets):
        self.world = world
        self.assets = assets
        self.x = (world.width * DEFAULT_TILE_SIZE) // 2
        self.y = (world.height * DEFAULT_TILE_SIZE) // 2
        self.speed = 4
        self.tile_id = None
        self.move_dx, self.move_dy = 0, 0

    def set_tile(self, tid):
        self.tile_id = tid

    def can_move_to(self, nx, ny):
        # no wrap-around: the player stops at the map edge
        tx = int(nx // DEFAULT_TILE_SIZE)
        ty = int(ny // DEFAULT_TILE_SIZE)
        if not (0 <= tx < self.world.width and 0 <= ty < self.world.height):
            return False
        # the collision layer actually blocks the player
        if self.world.collision_layer[ty][tx]:
            return False
        # v5.10: no climbing cliffs — one height level per step
        fx, fy = int(self.x // DEFAULT_TILE_SIZE), int(self.y // DEFAULT_TILE_SIZE)
        if climb_cost(self.world, fx, fy, tx, ty) is None:
            return False
        tile = self.assets.tiles.get(self.world.data[ty][tx])
        return not (tile and tile.get("properties", {}).get("solid"))

    def update(self):
        if self.move_dx == 0 and self.move_dy == 0:
            return
        nx, ny = self.x + self.move_dx * self.speed, self.y + self.move_dy * self.speed
        if self.can_move_to(nx, ny):
            self.x, self.y = nx, ny


# ==========================================
# HEIGHT / ELEVATION (v5.10)
# ==========================================
# One number per tile, derived from its preset (or an explicit override):
#   deep water -2 < water -1 < plains 0 < hills 1 < mountains 2.
# Walls sit one level above the terrain they stand on. Height drives
# shadows, tall faces, movement cost, climb blocking, line of sight,
# and the height overlay — all through the helpers below.
HEIGHT_MIN, HEIGHT_MAX = -2, 3
HEIGHT_DEFAULTS = {
    "deepwater": -2,
    "water": -1,
    "floor": 0,
    "decor": 0,
    "door": 0,
    "character": 0,
    "wall": 1,
    "hill": 1,
    "mountain": 2,
}
HEIGHT_NAMES = {
    -2: "deep water", -1: "water", 0: "plains",
    1: "hills", 2: "mountains", 3: "peaks",
}


def _builtin_height_from_name(name):
    """Height guess for built-in color tiles, which carry no preset —
    their names look like 'forest_deep_water' or 'dungeon_wall'."""
    n = (name or "").lower()
    if "deep_water" in n:
        return -2
    if "water" in n:
        return -1
    if "mountain" in n:
        return 2
    if "hill" in n:
        return 1
    if "wall" in n:
        return 1
    return 0


def tile_height(tile):
    """Numeric height of one tile asset. An explicit integer 'height' in
    properties wins; then a legacy top-level height; then the preset
    default; then a name guess for preset-less built-ins; else 0."""
    if not tile:
        return 0
    props = tile.get("properties", {}) or {}
    h = props.get("height", None)
    if isinstance(h, int):
        return max(HEIGHT_MIN, min(HEIGHT_MAX, h))
    th = tile.get("height", None)
    if th == "tall":
        return 1
    if isinstance(th, int):
        return max(HEIGHT_MIN, min(HEIGHT_MAX, th))
    preset = props.get("preset") or tile.get("preset")
    if preset in HEIGHT_DEFAULTS:
        return HEIGHT_DEFAULTS[preset]
    return _builtin_height_from_name(tile.get("name"))


def cell_height(world, x, y):
    """Effective height of a map cell: the tallest of its ground tile and
    any object sitting on it. Out of bounds -> 0."""
    if not (0 <= x < world.width and 0 <= y < world.height):
        return 0
    tiles = world.assets.tiles
    h = tile_height(tiles.get(world.data[y][x]))
    obj = world.object_layer[y][x]
    if obj:
        h = max(h, tile_height(tiles.get(obj)))
    return h


def height_grid(world):
    """Full per-cell height map (for the overlay / shadows / visibility)."""
    return [[cell_height(world, x, y) for x in range(world.width)]
            for y in range(world.height)]


def climb_cost(world, x0, y0, x1, y1):
    """Extra movement cost stepping from (x0,y0) to (x1,y1).
    Returns None when the step is unclimbable (more than one level up)."""
    dh = cell_height(world, x1, y1) - cell_height(world, x0, y0)
    if dh > 1:
        return None
    return max(0, dh)


def line_of_sight(world, x0, y0, x1, y1):
    """True when (x1,y1) is visible from (x0,y0). A cell blocks sight when
    its top (height + 1, eye level) pokes above the sight line between the
    two endpoints. Endpoints never block themselves."""
    h0 = cell_height(world, x0, y0)
    h1 = cell_height(world, x1, y1)
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx == 0 and dy == 0:
        return True
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err, x, y = dx - dy, x0, y0
    total = max(dx, dy)
    dist = 0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        dist += 1
        if (x, y) == (x1, y1):
            break
        if not (0 <= x < world.width and 0 <= y < world.height):
            return False
        line_h = (h0 + 1) + ((h1 + 1) - (h0 + 1)) * dist / total
        if cell_height(world, x, y) + 1 > line_h + 1e-6:
            return False
    return True


# ---- v5.11: sprite-sheet importer (GUI-free) ----------------------------------
# A sprite sheet is decoded to a flat row-major list of (r, g, b, a) pixel
# tuples. The browser decodes with Canvas (getImageData) for the live preview;
# the server and desktop decode with Pillow (list(img.convert("RGBA")
# .getdata())). Both feed the same slicer below, so preview and import agree
# cell-for-cell.
SPRITE_CELL_SIZES = (8, 16, 32)   # slice sizes we support; all upscale to 32
SPRITE_TARGET_PX = 32             # every imported cell lands at 32x32
PICO8_SHEET_PX = 128              # a PICO-8 sprite sheet is 128x128 px...
PICO8_CELL_PX = 8                 # ...of 8x8 cells -> a 16x16 grid, 256 sprites
SPRITE_MAX_PICKS = 64             # sanity cap per import request


def sheet_grid(sheet_w, sheet_h, cell, ox=0, oy=0):
    """(cols, rows) of whole `cell`-px cells that fit past the (ox, oy)
    offset. Partial edge cells are dropped, never stretched."""
    if cell not in SPRITE_CELL_SIZES:
        raise ValueError(f"cell must be one of {SPRITE_CELL_SIZES}")
    cols = max(0, (sheet_w - ox) // cell)
    rows = max(0, (sheet_h - oy) // cell)
    return cols, rows


def slice_sheet(pixels, sheet_w, sheet_h, cell, ox=0, oy=0):
    """Cut the sheet into cells. `pixels` is a flat row-major list of
    (r, g, b, a) tuples of length sheet_w * sheet_h. Returns a list of
    cell dicts in row-major order:
      {index, col, row, w, h, pixels}  (pixels flat, row-major)
    index == row * cols + col, so client and server address the same cell."""
    cols, rows = sheet_grid(sheet_w, sheet_h, cell, ox, oy)
    cells = []
    for row in range(rows):
        for col in range(cols):
            cp = []
            for dy in range(cell):
                sy = oy + row * cell + dy
                base = sy * sheet_w + ox + col * cell
                cp.extend(pixels[base:base + cell])
            cells.append({"index": row * cols + col, "col": col, "row": row,
                          "w": cell, "h": cell, "pixels": cp})
    return cells


def upscale_nearest(cell, target=SPRITE_TARGET_PX):
    """Integer nearest-neighbor upscale of a cell dict to `target` px.
    8px -> 4x, 16px -> 2x, 32px -> 1x. Crisp pixels, no blur."""
    w, h = cell["w"], cell["h"]
    if w == target and h == target:
        return dict(cell)
    sx, sy = target // w, target // h
    if sx < 1 or sy < 1 or w * sx != target or h * sy != target:
        raise ValueError(f"cannot upscale {w}x{h} to {target}x{target}")
    src = cell["pixels"]
    out = []
    for dy in range(target):
        srow = src[(dy // sy) * w:(dy // sy) * w + w]
        for dx in range(target):
            out.append(srow[dx // sx])
    return {"index": cell["index"], "col": cell["col"], "row": cell["row"],
            "w": target, "h": target, "pixels": out}


def cell_used(cell, alpha_min=8):
    """False for fully-transparent cells — the importer skips these unless
    the user explicitly shows and picks them."""
    return any(p[3] >= alpha_min for p in cell["pixels"])


def anim_cells(cells, start, count):
    """Consecutive cells -> animation frames. `start` is a cell index,
    `count` how many frames; clamps to the cells that exist."""
    if start < 0 or start >= len(cells):
        raise ValueError("animation start out of range")
    return cells[start:start + max(1, count)]


def sprite_import_plan(cells, picks):
    """Turn user picks into import jobs. `picks` is a list of:
        {kind: "tile", index, name, preset}
        {kind: "anim", start, count, name, preset, frame_ms?}
    Returns [{name, preset, frame_ms, frames: [cell, ...]}, ...] with frames
    still at sheet resolution — upscale with upscale_nearest() before saving.
    Raises ValueError on the first bad pick."""
    if len(picks) > SPRITE_MAX_PICKS:
        raise ValueError(f"too many picks (max {SPRITE_MAX_PICKS})")
    jobs = []
    for p in picks:
        kind = p.get("kind", "tile")
        name = str(p.get("name", "")).strip()[:24] or "sprite"
        preset = p.get("preset", "decor")
        if kind == "anim":
            try:
                frame_ms = max(80, min(2000, int(p.get("frame_ms", 400))))
            except (TypeError, ValueError):
                frame_ms = 400
            frames = anim_cells(cells, int(p["start"]), int(p.get("count", 2)))
            if len(frames) < 2:
                raise ValueError("animation needs at least 2 frames")
        elif kind == "tile":
            idx = int(p["index"])
            if not (0 <= idx < len(cells)):
                raise ValueError(f"cell {idx} out of range")
            frames, frame_ms = [cells[idx]], 400
        else:
            raise ValueError(f"unknown pick kind {kind!r}")
def sprite_import_plan(cells, picks):
    """Turn user picks into import jobs. `picks` is a list of:
        {kind: "tile", index, name, preset}
        {kind: "anim", start, count, name, preset, frame_ms?}
    Returns [{name, preset, frame_ms, frames: [cell, ...]}, ...] with frames
    still at sheet resolution — upscale with upscale_nearest() before saving.
    Raises ValueError on the first bad pick."""
    if len(picks) > SPRITE_MAX_PICKS:
        raise ValueError(f"too many picks (max {SPRITE_MAX_PICKS})")
    jobs = []
    for p in picks:
        kind = p.get("kind", "tile")
        name = str(p.get("name", "")).strip()[:24] or "sprite"
        preset = p.get("preset", "decor")
        if kind == "anim":
            try:
                frame_ms = max(80, min(2000, int(p.get("frame_ms", 400))))
            except (TypeError, ValueError):
                frame_ms = 400
            frames = anim_cells(cells, int(p["start"]), int(p.get("count", 2)))
            if len(frames) < 2:
                raise ValueError("animation needs at least 2 frames")
        elif kind == "tile":
            idx = int(p["index"])
            if not (0 <= idx < len(cells)):
                raise ValueError(f"cell {idx} out of range")
            frames, frame_ms = [cells[idx]], 400
        else:
            raise ValueError(f"unknown pick kind {kind!r}")
        jobs.append({"name": name, "preset": preset,
                     "frame_ms": frame_ms, "frames": frames})
    return jobs


# ---- v5.12: mission system (GUI-free) ---------------------------------------
# Melody's workshop: a preset library of mission templates, a short
# questionnaire (answers dict), difficulty tiers that scale the enemy flows,
# and a playtest that proves every objective is beatable before the player
# ever taps play. The server owns run state; this module owns the shape.
MISSION_PRESETS = [
    {"id": "reach", "label": "Reach the shrine",
     "hint": "Get your hero to one marked spot.",
     "fields": ["target", "difficulty", "reward"]},
    {"id": "visit", "label": "Waypoints",
     "hint": "Touch every marked waypoint, any order.",
     "fields": ["targets", "difficulty", "reward"]},
    {"id": "collect", "label": "Gatherer",
     "hint": "Gather wood or food from the land.",
     "fields": ["what", "count", "difficulty", "reward"]},
    {"id": "survive", "label": "Survivor",
     "hint": "Keep your meters alive for N ticks.",
     "fields": ["ticks", "difficulty", "reward"]},
    {"id": "timed", "label": "Beat the clock",
     "hint": "Reach the mark before time runs out.",
     "fields": ["target", "ticks", "difficulty", "reward"]},
]
MISSION_PRESET_IDS = [p["id"] for p in MISSION_PRESETS]

# Difficulty tiers: how hard Melody makes the enemy flows. hazards = number of
# hazard patrols she places near the objective; drain = extra meter pressure
# she expects the hero to handle (informational for now).
DIFFICULTY_TIERS = {
    1: {"label": "Gentle", "hazards": 0},
    2: {"label": "Bold", "hazards": 1},
    3: {"label": "Brave", "hazards": 2},
    4: {"label": "Fierce", "hazards": 3},
    5: {"label": "Legend", "hazards": 4},
}
MISSION_MAX_WAYPOINTS = 4


def _mission_xy(v, name):
    try:
        x, y = int(v[0]), int(v[1])
    except (TypeError, ValueError, IndexError):
        raise ValueError(f"bad {name}")
    return x, y


def build_mission(preset_id, answers):
    """Build a mission dict from a preset + questionnaire answers.
    answers: {name?, difficulty? (1-5), reward?, target? [x,y],
              targets? [[x,y]...], what? ("wood"/"food"), count?, ticks?}
    Returns a mission dict with objectives (all done=False). Raises
    ValueError on the first bad answer."""
    if preset_id not in MISSION_PRESET_IDS:
        raise ValueError(f"unknown mission preset {preset_id!r}")
    try:
        difficulty = int(answers.get("difficulty", 2))
    except (TypeError, ValueError):
        raise ValueError("difficulty must be 1-5")
    if difficulty not in DIFFICULTY_TIERS:
        raise ValueError("difficulty must be 1-5")
    name = str(answers.get("name", "")).strip()[:32] or \
        next(p["label"] for p in MISSION_PRESETS if p["id"] == preset_id)
    reward = str(answers.get("reward", "")).strip()[:48]

    objectives = []
    if preset_id in ("reach", "timed"):
        x, y = _mission_xy(answers.get("target"), "target")
        if preset_id == "reach":
            objectives.append({"kind": "reach", "x": x, "y": y, "done": False})
        else:
            try:
                ticks = max(20, min(600, int(answers.get("ticks", 120))))
            except (TypeError, ValueError):
                raise ValueError("ticks must be a number")
            objectives.append({"kind": "timed", "x": x, "y": y,
                               "ticks": ticks, "elapsed": 0, "done": False,
                               "failed": False})
    elif preset_id == "visit":
        tgts = answers.get("targets") or []
        if not (2 <= len(tgts) <= MISSION_MAX_WAYPOINTS):
            raise ValueError(f"visit needs 2-{MISSION_MAX_WAYPOINTS} waypoints")
        for t in tgts:
            x, y = _mission_xy(t, "waypoint")
            objectives.append({"kind": "reach", "x": x, "y": y, "done": False})
    elif preset_id == "collect":
        what = answers.get("what", "wood")
        if what not in ("wood", "food"):
            raise ValueError('collect "what" must be wood or food')
        try:
            count = max(1, min(20, int(answers.get("count", 5))))
        except (TypeError, ValueError):
            raise ValueError("count must be a number")
        objectives.append({"kind": "collect", "what": what, "count": count,
                           "have": 0, "done": False})
    elif preset_id == "survive":
        try:
            ticks = max(20, min(600, int(answers.get("ticks", 90))))
        except (TypeError, ValueError):
            raise ValueError("ticks must be a number")
        objectives.append({"kind": "survive", "ticks": ticks, "elapsed": 0,
                           "done": False})
    return {"name": name, "preset": preset_id, "difficulty": difficulty,
            "reward": reward, "objectives": objectives,
            "hazard_count": DIFFICULTY_TIERS[difficulty]["hazards"],
            "active": False, "won": False}


def mission_target_cells(mission):
    """Every (x, y) the hero must physically reach for this mission."""
    cells = []
    for o in mission["objectives"]:
        if o["kind"] in ("reach", "timed"):
            cells.append((o["x"], o["y"]))
    return cells


def mission_playtest(world, mission, spawn, walkable, path_exists):
    """Can every objective actually be completed? `spawn` is (x, y);
    `walkable(x, y)` and `path_exists(sx, sy, tx, ty)` are callables.
    Returns a list of human-readable issue strings (empty = beatable)."""
    issues = []
    sx, sy = spawn
    if not walkable(sx, sy):
        return ["no walkable spawn — Melody can't even start the run"]
    for o in mission["objectives"]:
        if o["kind"] in ("reach", "timed"):
            if not (0 <= o["x"] < world.width and 0 <= o["y"] < world.height):
                issues.append(f"target ({o['x']},{o['y']}) is off the map")
            elif not walkable(o["x"], o["y"]):
                issues.append(f"target ({o['x']},{o['y']}) can't be stood on")
            elif not path_exists(sx, sy, o["x"], o["y"]):
                issues.append(f"target ({o['x']},{o['y']}) can't be reached "
                              f"from spawn — a cliff or wall cuts it off")
        # collect/survive need no path check — the land and the clock decide
    return issues


def mission_progress_text(mission):
    """One-line HUD text + (done, total)."""
    obs = mission["objectives"]
    total = len(obs)
    done = sum(1 for o in obs if o.get("done"))
    bits = []
    for o in obs:
        if o["kind"] == "reach":
            bits.append("📍 reach (%d,%d)%s" % (o["x"], o["y"],
                                                " ✓" if o["done"] else ""))
        elif o["kind"] == "timed":
            bits.append("⏱ reach (%d,%d) %d/%d%s" % (
                o["x"], o["y"], o.get("elapsed", 0), o["ticks"],
                " ✓" if o["done"] else (" ✗" if o.get("failed") else "")))
        elif o["kind"] == "collect":
            bits.append("🌾 %s %d/%d%s" % (o["what"], o.get("have", 0),
                                           o["count"],
                                           " ✓" if o["done"] else ""))
        elif o["kind"] == "survive":
            bits.append("❤ survive %d/%d%s" % (o.get("elapsed", 0), o["ticks"],
                                               " ✓" if o["done"] else ""))
    return "; ".join(bits), done, total


# ---- v5.13: gear — weapons, tools, and things to carry -----------------------
# Items are objects: a tile for a face, a kind for behavior, a price for
# the market. Heroes stack them, equip them, eat them, sell them.
ITEM_KINDS = ("weapon", "tool", "food", "trinket")
ITEM_TOOL_EFFECTS = ("none", "ward")  # ward: -1 hazard damage while equipped
ITEM_MAX_STACK = 99


def build_item(name, tile_id, kind="trinket", power=0, effect="none",
               stack=ITEM_MAX_STACK, price=0):
    """Validate questionnaire answers into an item dict. Raises ValueError."""
    name = str(name or "").strip()[:32] or "Odd thing"
    try:
        tile_id = int(tile_id)
    except (TypeError, ValueError):
        raise ValueError("item needs a tile")
    if kind not in ITEM_KINDS:
        raise ValueError(f"kind must be one of {', '.join(ITEM_KINDS)}")
    try:
        power = int(power)
    except (TypeError, ValueError):
        raise ValueError("power must be a number")
    power = max(0, min(99, power))
    if effect not in ITEM_TOOL_EFFECTS:
        raise ValueError(f"effect must be one of "
                         f"{', '.join(ITEM_TOOL_EFFECTS)}")
    try:
        stack = int(stack)
    except (TypeError, ValueError):
        raise ValueError("stack must be a number")
    stack = max(1, min(ITEM_MAX_STACK, stack))
    if kind in ("weapon", "tool"):
        stack = 1  # gear doesn't pile up; food and trinkets do
    try:
        price = int(price)
    except (TypeError, ValueError):
        raise ValueError("price must be a number")
    price = max(0, min(9999, price))
    return {"name": name, "tile_id": tile_id, "kind": kind, "power": power,
            "effect": effect, "stack": stack, "price": price}
