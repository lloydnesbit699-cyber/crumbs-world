#===========================================================================================
# Vaults World Editor v3.0 (Complete Edition)
#===========================================================================================

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, Menu
import os
import json
import random
import math
import shutil
import time
from datetime import datetime
from collections import deque

try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ WARNING: Pillow not found. Install with: pip install Pillow")


# ==========================================
# TOOLTIP CLASS
# ==========================================
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event):
        if self.tooltip:
            return
        # (#8) position from the widget's own screen coordinates; buttons have
        # no text cursor, so bbox("insert") threw on every hover
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, bg="#ffffe0", relief="solid", borderwidth=1, font=("Segoe UI", 8))
        label.pack()
    
    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


# ==========================================
# CONFIGURATION
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_LIBRARY_PATH = os.path.join(SCRIPT_DIR, "asset_library")
DEFAULT_TILE_SIZE = 64
DEFAULT_GRID_WIDTH = 40
DEFAULT_GRID_HEIGHT = 40

# Colors
COLOR_BG = '#0f1115'
COLOR_PANEL = '#1e222d'
COLOR_PANEL_LIGHT = '#2a2f3a'
COLOR_TEXT = '#e2e8f0'
COLOR_ACCENT = '#00d4ff'
COLOR_SUCCESS = '#48bb78'
COLOR_DANGER = '#ff6b6b'


# ==========================================
# BIOME DATA
# ==========================================
BIOMES = {
    "grassland": {
        "name": "Grassland",
        "colors": {
            "deep_water": "#1a4d6b", "water": "#2d6b9e", "sand": "#c2b280",
            "grass_dark": "#3d6b2e", "grass": "#4a7c23", "grass_light": "#5a9c33",
            "dirt": "#6b4423", "stone": "#5a5a5a", "snow": "#f0f8ff"
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
            "floor": "#2a2a2a", "floor_dark": "#1a1a1a", "wall": "#3a3a3a",
            "wall_dark": "#252525", "door": "#6b4423", "chest": "#8b6914"
        },
        "noise_settings": {"water_level": 0.0, "sand_level": 0.0, "grass_level": 0.0, "stone_level": 0.0}
    }
}


# ==========================================
# IMAGE PROCESSOR
# ==========================================
class ImageProcessor:
    @staticmethod
    def crop(img, box):
        return img.crop((box[0], box[1], box[0]+box[2], box[1]+box[3]))
    
    @staticmethod
    def rotate(img, angle):
        return img.rotate(angle, expand=True, resample=Image.Resampling.NEAREST)
    
    @staticmethod
    def flip(img, horizontal=True, vertical=False):
        if horizontal and vertical:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif horizontal:
            return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif vertical:
            return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return img
    
    @staticmethod
    def resize(img, width, height):
        return img.resize((width, height), Image.Resampling.NEAREST)
    
    @staticmethod
    def slice_sprite_sheet(img, rows, cols, tile_size=None):
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
        # (#11) rewritten: prefer grids that divide the image evenly into
        # square tiles of a sensible size, instead of an error term that is
        # always zero and made 1x1 win every time
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
        # (#13) collision painting edits the collision layer
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
    """(#15) One undo step for a multi-cell brush stroke."""
    def __init__(self, commands):
        self.commands = commands

    def execute(self):
        for c in self.commands:
            c.execute()

    def undo(self):
        for c in reversed(self.commands):
            c.undo()


class MapSnapshotCommand(Command):
    """(#5) One undo step that restores whole map layers (used for generation)."""
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
        self.rng = random.Random(self.seed)  # (#9) private generator; never touches global random
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
# ASSET MANAGER
# ==========================================
class AssetManager:
    def __init__(self):
        self.tiles = {}
        self.selected_id = 0
        self.pil_available = PIL_AVAILABLE
        self.sprite_library_path = os.path.join(SCRIPT_DIR, "sprite_library.json")
        self.categories = {'tiles': [], 'objects': [], 'animations': []}
        self.tk_cache = {}  # id → PhotoImage
        self.next_tile_id = 0  # (#1) single shared tile-ID counter; never reuses a number
        # (#1) library entries whose files are missing (e.g. PNGs still on the old
        # PC) can't become tiles, but they must survive every later save
        self._preserved_entries = []
        self._reserved_ids = set()  # (#1) IDs owned by preserved entries; never handed out

        if not os.path.exists(ASSET_LIBRARY_PATH):
            os.makedirs(ASSET_LIBRARY_PATH, exist_ok=True)

        self.create_default_tiles()
        self.load_sprite_library()
        self.create_biome_tiles()

    def _next_id(self):
        """(#1) Hand out a tile ID that is not already in use."""
        while self.next_tile_id in self.tiles or self.next_tile_id in self._reserved_ids:
            self.next_tile_id += 1
        tid = self.next_tile_id
        self.next_tile_id += 1
        return tid

    def unique_asset_path(self, basename):
        """(#20) Pick a filename in asset_library/ that does not exist yet,
        appending _2, _3... on collision instead of silently reusing the old file."""
        name, ext = os.path.splitext(basename)
        dest = os.path.join(ASSET_LIBRARY_PATH, basename)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(ASSET_LIBRARY_PATH, f"{name}_{n}{ext}")
            n += 1
        return dest
    
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
        cat = self.tiles[tid]['category']
        if cat not in self.categories:
            self.categories[cat] = []
        if tid not in self.categories[cat]:
            self.categories[cat].append(tid)
        if tid >= self.next_tile_id:  # (#1) keep the counter ahead of every used ID
            self.next_tile_id = tid + 1
    
    def load_sprite_library(self):
        if not os.path.exists(self.sprite_library_path):
            return
        try:
            with open(self.sprite_library_path, 'r') as f:
                library = json.load(f)
            for entry in library:
                if not self.pil_available:
                    # (#1) keep entries we can't load so a save doesn't erase them
                    self._preserve_entry(entry)
                    continue
                tid = entry.get('id')
                if tid is None or tid in self.tiles:
                    tid = self._next_id()  # (#1) saved ID collides: remap, never clobber
                frames = []
                for fp in entry.get('filepaths', []):
                    if fp and os.path.exists(fp):
                        img = Image.open(fp).convert("RGBA")
                        img = img.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                        frames.append(img)
                if frames:
                    # (#3) frames load in filepath order; frame_order rebuilds
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
                    # (#1) the entry's files are missing (PNGs still on the old PC):
                    # it can't become a tile, but it must survive later saves
                    self._preserve_entry(entry)
        except Exception as e:
            print(f"⚠️ Library Load Error: {e}")

    def _preserve_entry(self, entry):
        """(#1) Keep an unloadable library entry and reserve its ID so no
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
                dest_path = self.unique_asset_path(basename)  # (#20) never reuse an old file
                shutil.copy2(filepath, dest_path)
                img = Image.open(dest_path).convert("RGBA")
                if process_ops:
                    img = self.apply_operations(img, process_ops)
                img = img.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                new_id = self._next_id()  # (#1)
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
            dest_path = self.unique_asset_path(basename)  # (#20)
            shutil.copy2(filepath, dest_path)
            new_id = None
            for i, frame in enumerate(frames):
                new_id = self._next_id()  # (#1)
                frame_resized = frame.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
                # (#2) persist each sliced frame as its own PNG so reloads keep the slices
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
            frame_order = []  # (#3) filepath index per frame, in the exact playing order
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
            new_id = self._next_id()  # (#1)
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
                    'frame_order': tile.get('frame_order', []),  # (#3) exact playing order
                    'frame_delay': tile.get('frame_delay', 150)
                })
        # (#1) re-emit entries whose files were missing at load time, so a save
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
        if not PIL_AVAILABLE:
            return None
        tile = self.tiles.get(tid)
        if not tile:
            return None
        key = (tid, size)
        if key in self.tk_cache:
            return self.tk_cache[key]
        if tile['type'] == 'color':
            img = Image.new("RGBA", (size, size), tile['color'])
        else:
            frame = tile['frames'][tile.get('current_frame', 0)]
            img = frame.resize((size, size), Image.Resampling.NEAREST)
        tkimg = ImageTk.PhotoImage(img)
        self.tk_cache[key] = tkimg
        return tkimg


# ==========================================
# WORLD MAP
# ==========================================
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
    
    def generate_biome(self, biome_name, seed=None):
        biome = BIOMES.get(biome_name, BIOMES["grassland"])
        noise = NoiseGenerator(seed)
        settings = biome["noise_settings"]
        
        # (#10) only tiles from THIS biome's own set are candidates, so shared
        # color names like "sand"/"water" can't resolve to another biome's tile.
        # Biome-owned tiles are named like "dungeon_wall"; nameless-prefix tiles
        # (the built-in defaults, user customs) stay shared.
        color_map = {}
        for tid, tile in self.assets.tiles.items():
            if tile['type'] != 'color':
                continue
            tname = tile.get('name', '')
            owner = next((b for b in BIOMES if tname.startswith(b + '_')), None)
            if owner is not None and owner != biome_name:
                continue  # belongs to a different biome
            for c_name, c_hex in biome["colors"].items():
                if tile.get('color') == c_hex:
                    color_map[c_name] = tid

        # (#21) dungeon fallbacks resolve from the biome's own generated tiles,
        # not hardcoded IDs (7 and 8 are grassland water/sand)
        fallback = {'water': 1, 'sand': 2, 'grass': 4, 'stone': 5,
                    'floor': color_map.get('floor', 0), 'wall': color_map.get('wall', 0)}
        
        for y in range(self.height):
            for x in range(self.width):
                v = (noise.noise2d(x/20.0, y/20.0) + 1) / 2
                if biome_name == 'dungeon':
                    if v > 0.6:
                        self.data[y][x] = color_map.get('wall', fallback['wall'])
                    else:
                        self.data[y][x] = color_map.get('floor', fallback['floor'])
                else:
                    if v < settings["water_level"]:
                        self.data[y][x] = color_map.get('deep_water', color_map.get('water', fallback['water']))
                    elif v < settings["sand_level"]:
                        self.data[y][x] = color_map.get('sand', fallback['sand'])
                    elif v < settings["grass_level"]:
                        self.data[y][x] = color_map.get('grass', fallback['grass'])
                    else:
                        self.data[y][x] = color_map.get('stone', fallback['stone'])
    
    def save(self, filepath):
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
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return False
    
    def load(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self.width, self.height = data['width'], data['height']
            self.data = data['tiles']
            self.object_layer = data.get('objects', [[None]*self.width for _ in range(self.height)])
            self.collision_layer = data.get('collision', [[False]*self.width for _ in range(self.height)])
            return True
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return False

    def load_csv(self, filepath):
        """(#19) Legacy vault_map.txt-style comma-separated maps."""
        try:
            rows = []
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append([int(v) for v in line.split(',')])
            if not rows:
                messagebox.showwarning("Load", "That file has no map data.")
                return False
            h = len(rows)
            w = max(len(r) for r in rows)
            self.width, self.height = w, h
            self.data = [[rows[y][x] if x < len(rows[y]) else 0 for x in range(w)] for y in range(h)]
            self.object_layer = [[None] * w for _ in range(h)]
            self.collision_layer = [[False] * w for _ in range(h)]
            return True
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
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
        # (#14) no wrap-around: the player stops at the map edge
        tx = int(nx // DEFAULT_TILE_SIZE)
        ty = int(ny // DEFAULT_TILE_SIZE)
        if not (0 <= tx < self.world.width and 0 <= ty < self.world.height):
            return False
        # (#13) the collision layer now actually blocks the player
        if self.world.collision_layer[ty][tx]:
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
# ANIMATION STUDIO PANEL
# ==========================================
class AnimationStudioPanel:
    def __init__(self, parent, assets, editor):
        self.parent = parent
        self.assets = assets
        self.editor = editor
        self.setup_ui()
    
    def setup_ui(self):
        for w in self.parent.winfo_children():
            w.destroy()
        
        self.canvas = tk.Canvas(self.parent, bg=COLOR_PANEL, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas, bg=COLOR_PANEL)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        self.build_sections()
    
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def build_sections(self):
        self.create_section("📥 1. Import Images")
        
        tk.Button(self.frame, text="🖼️ Import Single/Multi Frames", 
                  command=self.editor.import_tiles,
                  bg=COLOR_ACCENT, fg='#000', relief=tk.FLAT, pady=8).pack(fill=tk.X, padx=8, pady=5)
        
        tk.Button(self.frame, text="📊 Import Sprite Sheet (Grid)", 
                  command=self.open_sprite_sheet_dialog,
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, pady=8).pack(fill=tk.X, padx=8, pady=5)
        
        self.create_section("👁️ 2. Preview Selected")
        
        self.preview_canvas = tk.Canvas(self.frame, width=96, height=96, bg='#000', 
                                         highlightthickness=2, highlightbackground=COLOR_ACCENT)
        self.preview_canvas.pack(pady=10)
        
        self.preview_label = tk.Label(self.frame, text="No tile selected", 
                                       bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 8))
        self.preview_label.pack()
        
        self.create_section("✂️ 3. Quick Edit (Optional)")
        
        edit_frame = tk.Frame(self.frame, bg=COLOR_PANEL)
        edit_frame.pack(fill=tk.X, padx=8, pady=5)
        
        tk.Button(edit_frame, text="↺", command=lambda: self.apply_transform('rotate', -90),
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_frame, text="↻", command=lambda: self.apply_transform('rotate', 90),
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_frame, text="↔", command=lambda: self.apply_transform('flip', 'h'),
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        
        self.create_section("🎬 4. Create Animation")
        
        info_frame = tk.Frame(self.frame, bg=COLOR_PANEL)
        info_frame.pack(fill=tk.X, padx=8, pady=5)
        tk.Label(info_frame, text="Pick frames in order in the dialog,",
                 bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 7)).pack(anchor="w")
        tk.Label(info_frame, text="then click Create Animation",
                 bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 7)).pack(anchor="w")
        
        tk.Label(self.frame, text="Speed: 150ms/frame", 
                 bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 8)).pack(pady=(10,5))
        
        self.anim_speed_var = tk.IntVar(value=150)
        self.anim_slider = ttk.Scale(self.frame, from_=50, to=500, variable=self.anim_speed_var, 
                                      orient=tk.HORIZONTAL, command=self.update_speed_label)
        self.anim_slider.pack(fill=tk.X, padx=8, pady=5)
        
        tk.Button(self.frame, text="✨ Create Animation from Selected Frames",
                  command=self.create_animation_from_selection,
                  bg=COLOR_SUCCESS, fg='#000', relief=tk.FLAT, pady=10,
                  font=("Segoe UI", 9, "bold")).pack(fill=tk.X, padx=8, pady=10)

        # (#16) animation queue builder: reorder frames and tweak speed of existing animations
        tk.Button(self.frame, text="📋 Animation Queue Builder",
                  command=self.editor.open_animation_queue,
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, pady=8).pack(fill=tk.X, padx=8, pady=5)

        self.create_section("🔍 Auto-Detect Grid")
        
        tk.Button(self.frame, text="📐 Detect from Selected Image", 
                  command=self.auto_detect_grid,
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT).pack(fill=tk.X, padx=8, pady=5)
        
        self.grid_info_label = tk.Label(self.frame, text="Select an image first", 
                                         bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 7))
        self.grid_info_label.pack(pady=5)
    
    def create_section(self, title):
        tk.Label(self.frame, text=title, bg=COLOR_PANEL, fg=COLOR_ACCENT, 
                 anchor="w", font=("Segoe UI", 9, "bold")).pack(fill=tk.X, padx=8, pady=(15,5))
    
    def update_speed_label(self, val):
        for widget in self.frame.winfo_children():
            if isinstance(widget, tk.Label) and "Speed:" in widget.cget("text"):
                widget.config(text=f"Speed: {int(float(val))}ms/frame")
                break
    
    def open_sprite_sheet_dialog(self):
        filepath = filedialog.askopenfilename(title="Select Sprite Sheet", 
                                               filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if not filepath:
            return
        
        rows = simpledialog.askinteger("Rows", "How many ROWS (horizontal lines)?", 
                                        initialvalue=1, minvalue=1, maxvalue=32)
        cols = simpledialog.askinteger("Columns", "How many COLUMNS (vertical lines)?", 
                                        initialvalue=4, minvalue=1, maxvalue=32)
        
        if rows and cols:
            success, msg = self.assets.load_sprite_sheet(filepath, rows, cols, category="tiles")
            self.editor.status_lbl.config(text=msg)
            self.editor.update_sidebar()
            self.editor.draw_world()
    
    def apply_transform(self, op_type, value=None):
        tid = self.assets.selected_id
        tile = self.assets.tiles.get(tid)
        if not tile or tile['type'] not in ('image', 'animation'):
            messagebox.showwarning("Warning", "Select an image tile in Assets panel first")
            return
        
        if 'filepaths' in tile and tile['filepaths']:
            try:
                img = Image.open(tile['filepaths'][0]).convert("RGBA")
            except:
                return
        else:
            img = tile['frames'][0].copy()
        
        if op_type == 'rotate':
            img = ImageProcessor.rotate(img, value)
        elif op_type == 'flip':
            img = ImageProcessor.flip(img, value=='h', value=='v')
        
        self.update_preview(img)
        
        new_id = self.assets._next_id()  # (#1)
        img_resized = img.resize((DEFAULT_TILE_SIZE, DEFAULT_TILE_SIZE), Image.Resampling.NEAREST)
        # (#4) write the edited image out as its own PNG so the edit survives a reload
        edited_path = self.assets.unique_asset_path(f"{tile['name']}_edited_{new_id}.png")
        img_resized.save(edited_path)
        self.assets.add_tile(new_id, 'image', {
            'name': f"{tile['name']}_edited",
            'category': tile['category'],
            'image': img_resized,
            'frames': [img_resized],
            'filepaths': [edited_path]
        })

        self.assets.save_sprite_library()
        self.assets.selected_id = new_id
        self.editor.update_sidebar()
        self.editor.draw_world()
        self.editor.status_lbl.config(text=f"Created edited copy (ID: {new_id})")
    
    def update_preview(self, img):
        self.preview_canvas.delete("all")
        try:
            pimg = ImageTk.PhotoImage(img.resize((96, 96), Image.Resampling.NEAREST))
            self.preview_canvas.create_image(48, 48, image=pimg)
            self.preview_canvas.image = pimg
        except:
            pass
    
    def update_preview_for_selected(self):
        tid = self.assets.selected_id
        tile = self.assets.tiles.get(tid)
        if tile and tile['type'] in ('image', 'animation'):
            frame_idx = tile.get('current_frame', 0) % len(tile['frames'])
            self.update_preview(tile['frames'][frame_idx])
            self.preview_label.config(
                text=f"{tile['name']} ({tile['type']}) - Frame {frame_idx + 1}/{len(tile['frames'])}"
            )
        else:
            self.preview_canvas.delete("all")
            self.preview_label.config(text="No tile selected")
    
    def create_animation_from_selection(self):
        """(#12) Explicit frame picker: choose frames in order instead of
        sweeping up the whole category."""
        category = self.assets.tiles.get(self.assets.selected_id, {}).get('category', 'objects')
        candidates = [tid for tid in self.assets.get_category_tiles(category)
                      if self.assets.tiles.get(tid, {}).get('type') in ('image', 'animation')]
        if not candidates:
            messagebox.showwarning("Warning", "Import at least 2 image frames first!")
            return

        picker = tk.Toplevel(self.editor.root)
        picker.title("Build Animation — pick frames in order")
        picker.geometry("540x430")
        picker.configure(bg=COLOR_PANEL)
        picker.grid_columnconfigure(0, weight=1)
        picker.grid_columnconfigure(2, weight=1)
        picker.grid_rowconfigure(1, weight=1)

        tk.Label(picker, text="Available frames", bg=COLOR_PANEL, fg=COLOR_ACCENT,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")
        tk.Label(picker, text="Frame order (top = first)", bg=COLOR_PANEL, fg=COLOR_ACCENT,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=8, pady=(8, 2), sticky="w")

        avail = tk.Listbox(picker, selectmode=tk.EXTENDED, bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT,
                           font=("Segoe UI", 8))
        avail.grid(row=1, column=0, padx=8, pady=5, sticky="nsew")
        for tid in candidates:
            avail.insert(tk.END, f"{tid}: {self.assets.tiles[tid]['name']}")

        order = []
        order_box = tk.Listbox(picker, bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, font=("Segoe UI", 8))
        order_box.grid(row=1, column=2, padx=8, pady=5, sticky="nsew")

        def refresh_order():
            order_box.delete(0, tk.END)
            for tid in order:
                order_box.insert(tk.END, f"{tid}: {self.assets.tiles[tid]['name']}")

        def add_selected():
            for idx in avail.curselection():
                tid = candidates[idx]
                if tid not in order:
                    order.append(tid)
            refresh_order()

        def remove_selected():
            for idx in reversed(order_box.curselection()):
                del order[idx]
            refresh_order()

        def move_selected(delta):
            sel = order_box.curselection()
            if len(sel) != 1:
                return
            i = sel[0]
            j = i + delta
            if 0 <= j < len(order):
                order[i], order[j] = order[j], order[i]
                refresh_order()
                order_box.select_set(j)

        btns = tk.Frame(picker, bg=COLOR_PANEL)
        btns.grid(row=1, column=1, padx=4)
        tk.Button(btns, text="Add →", command=add_selected, bg=COLOR_SUCCESS, fg='#000',
                  relief=tk.FLAT, width=8).pack(pady=2)
        tk.Button(btns, text="← Remove", command=remove_selected, bg=COLOR_PANEL_LIGHT,
                  fg=COLOR_TEXT, relief=tk.FLAT, width=8).pack(pady=2)
        tk.Button(btns, text="↑ Up", command=lambda: move_selected(-1), bg=COLOR_PANEL_LIGHT,
                  fg=COLOR_TEXT, relief=tk.FLAT, width=8).pack(pady=2)
        tk.Button(btns, text="↓ Down", command=lambda: move_selected(1), bg=COLOR_PANEL_LIGHT,
                  fg=COLOR_TEXT, relief=tk.FLAT, width=8).pack(pady=2)

        def create():
            if len(order) < 2:
                messagebox.showwarning("Warning", "Add at least 2 frames first.")
                return
            name = simpledialog.askstring("Animation Name", "Name your animation:",
                                          initialvalue=f"Animation_{self.assets.next_tile_id}")
            if not name:
                return
            success, msg = self.assets.create_animation(order, name=name,
                                                        frame_delay=self.anim_speed_var.get())
            picker.destroy()
            if success:
                self.editor.update_sidebar()
                self.editor.draw_world()
                self.editor.status_lbl.config(text=msg)
            else:
                messagebox.showerror("Error", msg)

        tk.Button(picker, text="✨ Create Animation", command=create,
                  bg=COLOR_SUCCESS, fg='#000', relief=tk.FLAT, pady=8,
                  font=("Segoe UI", 9, "bold")).grid(row=2, column=0, columnspan=3,
                                                     padx=8, pady=10, sticky="ew")
    
    def auto_detect_grid(self):
        tid = self.assets.selected_id
        tile = self.assets.tiles.get(tid)
        if not tile or 'filepaths' not in tile or not tile['filepaths']:
            messagebox.showwarning("Warning", "Select an image tile first")
            return
        
        try:
            img = Image.open(tile['filepaths'][0])
            result = ImageProcessor.auto_detect_grid(img)
            rows, cols, tile_size = result
            self.grid_info_label.config(
                text=f"✅ Detected: {rows} rows × {cols} cols | Tile: {tile_size[0]}×{tile_size[1]}px"
            )
        except Exception as e:
            self.grid_info_label.config(text=f"❌ Error: {str(e)}")


# ==========================================
# MAP GENERATION PANEL
# ==========================================
class MapGenPanel:
    def __init__(self, parent, assets, editor):
        self.parent = parent
        self.assets = assets
        self.editor = editor
        self.setup_ui()
    
    def setup_ui(self):
        for w in self.parent.winfo_children():
            w.destroy()
        
        self.canvas = tk.Canvas(self.parent, bg=COLOR_PANEL, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas, bg=COLOR_PANEL)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.create_section("🌍 Biome Generator")
        
        sel_frame = tk.Frame(self.frame, bg=COLOR_PANEL)
        sel_frame.pack(fill=tk.X, padx=8, pady=5)
        
        tk.Label(sel_frame, text="Biome Type", bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 8)).pack(anchor="w")
        self.biome_var = tk.StringVar(value="grassland")
        biome_combo = ttk.Combobox(sel_frame, textvariable=self.biome_var, values=list(BIOMES.keys()), state="readonly", font=("Segoe UI", 8))
        biome_combo.pack(fill=tk.X, pady=5)
        
        seed_frame = tk.Frame(self.frame, bg=COLOR_PANEL)
        seed_frame.pack(fill=tk.X, padx=8, pady=5)
        
        tk.Label(seed_frame, text="Seed (Optional)", bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 8)).pack(anchor="w")
        self.seed_var = tk.IntVar()
        tk.Entry(seed_frame, textvariable=self.seed_var, font=("Segoe UI", 8)).pack(fill=tk.X, pady=5)
        tk.Button(seed_frame, text="🎲 Randomize", command=self.randomize_seed,
                  bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT).pack(fill=tk.X, pady=2)
        
        tk.Button(self.frame, text="⚡ Generate Map", command=self.generate_map,
                  bg=COLOR_SUCCESS, fg='#000', relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(fill=tk.X, padx=8, pady=10)
        
        info_frame = tk.Frame(self.frame, bg=COLOR_PANEL)
        info_frame.pack(fill=tk.X, padx=8, pady=5)
        tk.Label(info_frame, text="⚠️ Generation overwrites\ncurrent map data.",
                 bg=COLOR_PANEL, fg=COLOR_DANGER, font=("Segoe UI", 7), justify=tk.LEFT).pack(anchor="w")
    
    def create_section(self, title):
        tk.Label(self.frame, text=title, bg=COLOR_PANEL, fg=COLOR_ACCENT, 
                 anchor="w", font=("Segoe UI", 9, "bold")).pack(fill=tk.X, padx=8, pady=(10,5))
    
    def randomize_seed(self):
        self.seed_var.set(random.randint(0, 999999))
    
    def generate_map(self):
        biome = self.biome_var.get()
        try:
            seed = self.seed_var.get() or None
        except (tk.TclError, ValueError):
            # (#18) letters in the seed box fall back to a random seed
            seed = random.randint(0, 999999)
            self.seed_var.set(seed)
        if messagebox.askyesno("Generate", f"Overwrite map with {biome} biome?"):
            # (#5) generation becomes one undo step; (#6) history restarts with it
            self.editor.snapshot_generate(lambda: self.editor.world.generate_biome(biome, seed))
            self.editor.status_lbl.config(text=f"Generated {biome} (Seed: {seed or 'Random'})")


# ==========================================
# WORLD EDITOR
# ==========================================
class VaultsEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Vaults Editor v3.0 Complete")
        self.root.configure(bg=COLOR_BG)
        
        screen_width = self.root.winfo_screenwidth()
        self.sidebar_width = int(screen_width * 0.15)
        self.sidebar_width = max(220, min(350, self.sidebar_width))
        
        self.is_playing = False
        self.dragging = False
        self.tool = 'paint'
        self.brush_size = 1
        self.brush_shape = 'square'  # (#15) 'square' or 'circle'
        self.sidebar_visible = True  # (#16) sidebar toggle state
        self._dirty = True  # (#17) redraw flag for the animate loop
        self.zoom_level = 1.0
        self.show_grid = True
        self.show_collision = False
        self.camera_x, self.camera_y = 0, 0
        self.camera_dx, self.camera_dy = 0, 0
        self.player_size_factor = 0.75
        
        self.assets = AssetManager()
        self.world = WorldMap(DEFAULT_GRID_WIDTH, DEFAULT_GRID_HEIGHT, self.assets)
        self.player = Player(self.world, self.assets)
        self.history = HistoryManager()
        
        self.create_menu()
        self.create_layout()
        self.bind_events()
        
        self.last_frame_time = time.time()
        self.animate()
        self.game_loop()
        self.smooth_scroll()
        
        self.draw_world()
        self.update_sidebar()
    
    def create_layout(self):
        self.toolbar = tk.Frame(self.root, bg=COLOR_PANEL, height=35)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        btn_style = {'bg': COLOR_PANEL_LIGHT, 'fg': COLOR_TEXT, 'relief': tk.FLAT, 'padx': 8, 'pady': 4, 'font': ('Segoe UI', 8)}
        
        save_btn = tk.Button(self.toolbar, text="Save Map", command=self.save_map, **btn_style)
        save_btn.pack(side=tk.LEFT, padx=2)
        Tooltip(save_btn, "Save the current map to a JSON file")
        
        load_btn = tk.Button(self.toolbar, text="Load Map", command=self.load_map, **btn_style)
        load_btn.pack(side=tk.LEFT, padx=2)
        Tooltip(load_btn, "Load a map from a JSON file")
        
        undo_btn = tk.Button(self.toolbar, text="Undo", command=self.undo, **btn_style)
        undo_btn.pack(side=tk.LEFT, padx=2)
        Tooltip(undo_btn, "Undo the last action")
        
        redo_btn = tk.Button(self.toolbar, text="Redo", command=self.redo, **btn_style)
        redo_btn.pack(side=tk.LEFT, padx=2)
        Tooltip(redo_btn, "Redo the last undone action")

        # (#13/#15) tool buttons
        self.tool_btns = {}
        for tool_name, label, tip in [
                ('paint', 'Paint', 'Paint the selected tile'),
                ('erase', 'Erase', 'Erase ground tiles'),
                ('erase_obj', 'Erase Obj', 'Erase object tiles'),
                ('paint_collision', 'Collide+', 'Paint collision (blocks player)'),
                ('erase_collision', 'Collide−', 'Erase collision')]:
            b = tk.Button(self.toolbar, text=label, command=lambda t=tool_name: self.set_tool(t), **btn_style)
            b.pack(side=tk.LEFT, padx=2)
            self.tool_btns[tool_name] = b
            Tooltip(b, tip)
        self.refresh_tool_buttons()

        # (#15) brush size + shape controls
        tk.Label(self.toolbar, text="Brush:", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(8, 2))
        self.brush_var = tk.IntVar(value=self.brush_size)
        brush_spin = tk.Spinbox(self.toolbar, from_=1, to=8, width=3, textvariable=self.brush_var,
                                command=self.update_brush, font=("Segoe UI", 8))
        brush_spin.pack(side=tk.LEFT, padx=2)
        brush_spin.bind("<FocusOut>", lambda e: self.update_brush())
        self.brush_shape_var = tk.StringVar(value=self.brush_shape)
        shape_menu = tk.OptionMenu(self.toolbar, self.brush_shape_var, 'square', 'circle',
                                   command=self.set_brush_shape)
        shape_menu.config(bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT,
                          font=("Segoe UI", 8), width=6)
        shape_menu.pack(side=tk.LEFT, padx=2)

        # (#13) collision overlay toggle
        self.collision_btn = tk.Button(self.toolbar, text="Collision", command=self.toggle_collision_overlay,
                                       **btn_style)
        self.collision_btn.pack(side=tk.LEFT, padx=(8, 2))
        Tooltip(self.collision_btn, "Show/hide the collision layer overlay")

        # (#16) sidebar toggle
        sidebar_btn = tk.Button(self.toolbar, text="Sidebar", command=self.toggle_sidebar, **btn_style)
        sidebar_btn.pack(side=tk.LEFT, padx=2)
        Tooltip(sidebar_btn, "Show/hide the sidebar")

        self.mode_label = tk.Label(self.toolbar, text="EDIT MODE", bg=COLOR_PANEL, fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold"))
        self.mode_label.pack(side=tk.RIGHT, padx=10)
        
        self.main_pane = tk.PanedWindow(self.root, bg=COLOR_BG, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)
        
        self.canvas_frame = tk.Frame(self.main_pane, bg=COLOR_BG)
        self.main_pane.add(self.canvas_frame, minsize=400)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg='#1a1d24', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.sidebar = tk.Frame(self.main_pane, bg=COLOR_PANEL, width=self.sidebar_width)
        self.main_pane.add(self.sidebar, minsize=150)
        
        self.root.after(100, self.lock_sidebar_width)
        
        self.notebook = ttk.Notebook(self.sidebar)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.tab_studio = tk.Frame(self.notebook, bg=COLOR_PANEL)
        self.notebook.add(self.tab_studio, text="🎬 Studio")
        self.studio_panel = AnimationStudioPanel(self.tab_studio, self.assets, self)
        
        self.tab_assets = tk.Frame(self.notebook, bg=COLOR_PANEL)
        self.notebook.add(self.tab_assets, text="📦 Assets")
        # (#16) asset palette popup with search
        pal_btn = tk.Button(self.tab_assets, text="🔎 Palette (Search All)", command=self.open_asset_palette,
                            bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, relief=tk.FLAT, font=("Segoe UI", 8))
        pal_btn.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        Tooltip(pal_btn, "Search every tile and double-click to select it")
        self.asset_scroll = tk.Canvas(self.tab_assets, bg=COLOR_PANEL, highlightthickness=0)
        self.asset_frame = tk.Frame(self.asset_scroll, bg=COLOR_PANEL)
        self.asset_scroll.create_window((0,0), window=self.asset_frame, anchor="nw")
        self.asset_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Scrollbar(self.tab_assets, orient="vertical", command=self.asset_scroll.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.asset_scroll.configure(yscrollcommand=lambda f, l: self.asset_scroll.yview_moveto(f))
        self.asset_frame.bind("<Configure>", lambda e: self.asset_scroll.configure(scrollregion=self.asset_scroll.bbox("all")))
        
        self.tab_map = tk.Frame(self.notebook, bg=COLOR_PANEL)
        self.notebook.add(self.tab_map, text="🗺️ Map")
        self.map_gen_panel = MapGenPanel(self.tab_map, self.assets, self)
        
        self.status_bar = tk.Frame(self.root, bg=COLOR_PANEL, height=22)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_lbl = tk.Label(self.status_bar, text="Ready", bg=COLOR_PANEL, fg=COLOR_TEXT, anchor=tk.W, padx=8, font=("Segoe UI", 8))
        self.status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.info_lbl = tk.Label(self.status_bar, text="Zoom: 100%", bg=COLOR_PANEL, fg=COLOR_ACCENT, padx=8, font=("Segoe UI", 8))
        self.info_lbl.pack(side=tk.RIGHT)
    
    def lock_sidebar_width(self):
        self.main_pane.sash_place(0, self.root.winfo_width() - self.sidebar_width, 0)
    
    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Map", command=self.new_map)
        file_menu.add_command(label="Save", command=self.save_map)
        file_menu.add_command(label="Load", command=self.load_map)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        gen_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Generate", menu=gen_menu)
        for biome in BIOMES.keys():
            gen_menu.add_command(label=biome.capitalize(), command=lambda b=biome: self.generate_biome(b))
        
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Grid", command=self.toggle_grid)
        view_menu.add_command(label="Toggle Collision Overlay", command=self.toggle_collision_overlay)
        view_menu.add_command(label="Toggle Sidebar", command=self.toggle_sidebar)
        view_menu.add_command(label="Reset Zoom", command=self.reset_zoom)
    
    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-2>", self.on_middle_click)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))   # (#22) Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1))   # (#22) Linux scroll down
        
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<space>", self.toggle_play)
        self.root.bind("<Control-s>", lambda e: self.save_map())
        self.root.bind("<Control-l>", lambda e: self.load_map())
        self.root.bind("<Control-g>", lambda e: self.toggle_grid())
        self.root.bind("<Control-p>", lambda e: self.set_player_from_selected())
        
        for key in ["Up", "Down", "Left", "Right", "w", "a", "s", "d"]:
            self.root.bind(f"<KeyPress-{key}>", self.on_key_press)
            self.root.bind(f"<KeyRelease-{key}>", self.on_key_release)
        
        self.root.bind("<Configure>", self.on_window_resize)
    
    def on_window_resize(self, event):
        if event.widget == self.root:
            self.root.after(100, self.lock_sidebar_width)
    
    def get_tile_coords(self, event):
        ts = int(DEFAULT_TILE_SIZE * self.zoom_level)
        cx = int(self.canvas.canvasx(event.x) // ts)
        cy = int(self.canvas.canvasy(event.y) // ts)
        return cx, cy
    
    def _brush_cells(self, x, y):
        """(#15) Cells covered by the current brush (size + square/circle shape)."""
        size = max(1, self.brush_size)
        half = size // 2
        cells = []
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                if self.brush_shape == 'circle' and dx * dx + dy * dy > half * half + half:
                    continue
                cx, cy = x + dx, y + dy
                if 0 <= cx < self.world.width and 0 <= cy < self.world.height:
                    cells.append((cx, cy))
        return cells

    def _paint_cell_command(self, x, y, tool):
        """Build (but don't run) the undoable command for one cell. None if no change."""
        tid = self.assets.selected_id
        if tool == 'paint':
            tile = self.assets.tiles.get(tid)
            if tile and tile['type'] in ('image', 'animation'):
                old_val = self.world.object_layer[y][x]
                if old_val == tid:
                    return None
                return SetTileCommand(self.world, x, y, old_val, tid, 'objects')
            old_val = self.world.data[y][x]
            if old_val == tid:
                return None
            return SetTileCommand(self.world, x, y, old_val, tid, 'tiles')
        elif tool == 'erase':
            old_val = self.world.data[y][x]
            if old_val == 0:
                return None
            return SetTileCommand(self.world, x, y, old_val, 0, 'tiles')
        elif tool == 'erase_obj':
            old_val = self.world.object_layer[y][x]
            if old_val is None:
                return None
            return SetTileCommand(self.world, x, y, old_val, None, 'objects')
        elif tool == 'paint_collision':
            # (#13) collision paint tool
            if self.world.collision_layer[y][x]:
                return None
            return SetTileCommand(self.world, x, y, False, True, 'collision')
        elif tool == 'erase_collision':
            # (#13) collision erase tool
            if not self.world.collision_layer[y][x]:
                return None
            return SetTileCommand(self.world, x, y, True, False, 'collision')
        return None

    def execute_paint(self, x, y, override_tool=None):
        tool = override_tool or self.tool
        if tool == 'eyedropper':
            if not (0 <= x < self.world.width and 0 <= y < self.world.height):
                return
            t_id = self.world.data[y][x]
            o_id = self.world.object_layer[y][x]
            pick_id = o_id if o_id is not None else t_id
            self.assets.selected_id = pick_id
            self.update_sidebar()
            self.status_lbl.config(text=f"Picked ID: {pick_id}")
            return
        cells = self._brush_cells(x, y)
        if not cells:
            return
        cmds = []
        for cx, cy in cells:
            cmd = self._paint_cell_command(cx, cy, tool)
            if cmd:
                cmd.execute()
                cmds.append(cmd)
        if cmds:
            # (#15) a whole brush stroke is one undo step
            self.history.push(cmds[0] if len(cmds) == 1 else MultiCommand(cmds))
            self.draw_world()
    
    def undo(self):
        if self.history.undo():
            self.draw_world()
            self.status_lbl.config(text="Undo")
    
    def redo(self):
        if self.history.redo():
            self.draw_world()
            self.status_lbl.config(text="Redo")
    
    def on_press(self, event):
        if self.is_playing:
            return
        self.dragging = True
        self.execute_paint(*self.get_tile_coords(event))
    
    def on_drag(self, event):
        if self.is_playing or not self.dragging:
            return
        self.execute_paint(*self.get_tile_coords(event))
    
    def on_right_click(self, event):
        if self.is_playing:
            return
        self.execute_paint(*self.get_tile_coords(event), override_tool='eyedropper')
    
    def on_middle_click(self, event):
        if self.is_playing:
            return
        x, y = self.get_tile_coords(event)
        # (#7) check bounds BEFORE reading the grid, same as the paint tool
        if not (0 <= x < self.world.width and 0 <= y < self.world.height):
            return
        if self.world.object_layer[y][x] is not None:
            self.execute_paint(x, y, override_tool='erase_obj')
        else:
            self.execute_paint(x, y, override_tool='erase')
    
    def on_zoom(self, event, direction=None):
        # Anchor zoom to screen center
        ts_before = DEFAULT_TILE_SIZE * self.zoom_level
        cx_screen = self.canvas.winfo_width() // 2
        cy_screen = self.canvas.winfo_height() // 2
        world_x = (self.camera_x + cx_screen) / ts_before
        world_y = (self.camera_y + cy_screen) / ts_before

        if direction is None:
            # (#22) MouseWheel carries event.delta (Windows/macOS);
            # Linux sends Button-4/Button-5 instead
            if getattr(event, 'delta', 0):
                direction = 1 if event.delta > 0 else -1
            else:
                direction = 1 if getattr(event, 'num', 0) == 4 else -1

        if direction > 0:
            self.zoom_level = min(5.0, self.zoom_level * 1.1)
        else:
            self.zoom_level = max(0.2, self.zoom_level / 1.1)
        
        ts_after = DEFAULT_TILE_SIZE * self.zoom_level
        self.camera_x = world_x * ts_after - cx_screen
        self.camera_y = world_y * ts_after - cy_screen
        
        self.draw_world()
        self.info_lbl.config(text=f"Zoom: {int(self.zoom_level*100)}%")
    
    def on_key_press(self, event):
        k = event.keysym.lower()
        if self.is_playing:
            if k == 'w':
                self.player.move_dy = -1
            if k == 's':
                self.player.move_dy = 1
            if k == 'a':
                self.player.move_dx = -1
            if k == 'd':
                self.player.move_dx = 1
        else:
            speed = 20
            if k in ('left', 'a'):
                self.camera_dx = -speed
            if k in ('right', 'd'):
                self.camera_dx = speed
            if k in ('up', 'w'):
                self.camera_dy = -speed
            if k in ('down', 's'):
                self.camera_dy = speed
    
    def on_key_release(self, event):
        k = event.keysym.lower()
        if self.is_playing:
            if k in ('w','s'):
                self.player.move_dy = 0
            if k in ('a','d'):
                self.player.move_dx = 0
        else:
            if k in ('left','right','a','d'):
                self.camera_dx = 0
            if k in ('up','down','w','s'):
                self.camera_dy = 0
    
    def toggle_play(self, event=None):
        self.is_playing = not self.is_playing
        self.mode_label.config(text="PLAY MODE" if self.is_playing else "EDIT MODE")
        self.player.move_dx, self.player.move_dy = 0, 0
        if self.is_playing:
            self.camera_x = self.player.x * self.zoom_level - (self.canvas.winfo_width()//2)
            self.camera_y = self.player.y * self.zoom_level - (self.canvas.winfo_height()//2)
    
    def set_player_from_selected(self):
        tid = self.assets.selected_id
        tile = self.assets.tiles.get(tid)
        if tile and tile['type'] in ('image', 'animation'):
            self.player.tile_id = tid
            self.status_lbl.config(text=f"Player sprite set to: {tile['name']}")
    
    def draw_world(self):
        self._dirty = False  # (#17) a fresh draw clears the redraw flag
        self.canvas.delete("all")
        ts = int(DEFAULT_TILE_SIZE * self.zoom_level)
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        start_x = int(self.camera_x // ts)
        start_y = int(self.camera_y // ts)
        end_x = start_x + int(canvas_width // ts) + 2
        end_y = start_y + int(canvas_height // ts) + 2
        
        self._img_refs = []
        
        for y in range(start_y, end_y):
            world_y = y % self.world.height
            sy = (y - start_y) * ts
            for x in range(start_x, end_x):
                world_x = x % self.world.width
                sx = (x - start_x) * ts
                
                tid = self.world.data[world_y][world_x]
                tile = self.assets.tiles.get(tid)
                
                if tile:
                    if tile['type'] == 'color':
                        self.canvas.create_rectangle(
                            sx, sy, sx+ts, sy+ts,
                            fill=tile['color'],
                            outline="#222" if self.show_grid else ""
                        )
                    elif tile['type'] in ('image', 'animation'):
                        frame = tile['frames'][tile.get('current_frame', 0) % len(tile['frames'])]
                        img = ImageTk.PhotoImage(frame.resize((ts, ts)))
                        self.canvas.create_image(sx, sy, anchor="nw", image=img)
                        self._img_refs.append(img)
                
                oid = self.world.object_layer[world_y][world_x]
                if oid:
                    otile = self.assets.tiles.get(oid)
                    if otile and otile['type'] in ('image', 'animation'):
                        frame = otile['frames'][otile.get('current_frame', 0) % len(otile['frames'])]
                        img = ImageTk.PhotoImage(frame.resize((ts, ts)))
                        self.canvas.create_image(sx, sy, anchor="nw", image=img)
                        self._img_refs.append(img)
                
                if self.show_collision and self.world.collision_layer[world_y][world_x]:
                    self.canvas.create_rectangle(sx, sy, sx+ts, sy+ts, outline="red", width=2)
        
        if self.is_playing and self.player.tile_id:
            ptile = self.assets.tiles.get(self.player.tile_id)
            if ptile:
                player_ts = int(ts * self.player_size_factor)
                frame_idx = ptile.get('current_frame', 0) % len(ptile['frames']) if ptile['type'] == 'animation' else 0
                img = ptile['frames'][frame_idx]
                if img:
                    pimg = ImageTk.PhotoImage(img.resize((player_ts, player_ts)))
                    px = self.player.x * self.zoom_level - self.camera_x - player_ts // 2
                    py = self.player.y * self.zoom_level - self.camera_y - player_ts // 2
                    self.canvas.create_image(px, py, anchor="nw", image=pimg)
                    self._img_refs.append(pimg)
    
    def animate(self):
        now = time.time()
        dt = (now - self.last_frame_time) * 1000  # ms
        self.last_frame_time = now

        animation_advanced = False
        for tile in self.assets.tiles.values():
            if tile['type'] == 'animation':
                tile.setdefault('_accum', 0)
                tile['_accum'] += dt
                delay = tile.get('frame_delay', 150)
                while tile['_accum'] >= delay:
                    tile['_accum'] -= delay
                    tile['current_frame'] = (tile.get('current_frame', 0) + 1) % len(tile['frames'])
                    animation_advanced = True

        if hasattr(self, 'studio_panel'):
            self.studio_panel.update_preview_for_selected()

        # (#17) only redraw when something changed: the dirty flag, an animation
        # frame actually advancing, or play mode (the camera keeps moving)
        if self._dirty or animation_advanced or self.is_playing:
            self.draw_world()
        self.root.after(16, self.animate)
    
    def game_loop(self):
        if self.is_playing:
            self.player.update()
            target_x = self.player.x * self.zoom_level - (self.canvas.winfo_width() // 2)
            target_y = self.player.y * self.zoom_level - (self.canvas.winfo_height() // 2)
            self.camera_x += (target_x - self.camera_x) * 0.1
            self.camera_y += (target_y - self.camera_y) * 0.1
        
        self.root.after(16, self.game_loop)
    
    def smooth_scroll(self):
        if not self.is_playing:
            if self.camera_dx or self.camera_dy:
                self.camera_x += self.camera_dx
                self.camera_y += self.camera_dy
                self.camera_dx *= 0.8
                self.camera_dy *= 0.8
                self._dirty = True  # (#17) camera moved: needs a redraw
        self.root.after(16, self.smooth_scroll)
    
    def update_sidebar(self):
        for w in self.asset_frame.winfo_children():
            w.destroy()
        
        cols = max(3, self.sidebar_width // 50)
        row, col = 0, 0
        
        for cat in ['tiles', 'objects', 'animations']:
            tile_ids = self.assets.get_category_tiles(cat)
            if not tile_ids:
                continue
            
            tk.Label(
                self.asset_frame,
                text=cat.upper(),
                bg=COLOR_PANEL,
                fg=COLOR_ACCENT,
                anchor="w",
                font=("Segoe UI", 8, "bold")
            ).grid(row=row, column=0, columnspan=cols, sticky="w", padx=5, pady=(8,4))
            row += 1
            
            for tid in tile_ids:
                t = self.assets.tiles.get(tid)
                if not t:
                    continue
                
                swatch = tk.Canvas(self.asset_frame, width=40, height=40, bg=COLOR_PANEL_LIGHT, highlightthickness=0)
                swatch.grid(row=row, column=col, padx=2, pady=2)
                
                if t['type'] == 'color':
                    swatch.create_rectangle(0,0,40,40, fill=t['color'])
                elif PIL_AVAILABLE and t['type'] in ('image', 'animation'):
                    thumb = self.assets.get_thumbnail(tid, size=40)
                    if thumb:
                        swatch.create_image(20,20, image=thumb)
                        swatch.image = thumb
                
                if tid == self.assets.selected_id:
                    swatch.config(highlightthickness=2, highlightbackground=COLOR_ACCENT)
                
                def make_select(id=tid):
                    return lambda e: self.select_tile(id)
                swatch.bind("<Button-1>", make_select())
                
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
            row += 1
        self.asset_frame.bind("<Configure>", lambda e: self.asset_scroll.configure(scrollregion=self.asset_scroll.bbox("all")))
    
    def select_tile(self, tid):
        self.assets.selected_id = tid
        self.update_sidebar()
        t = self.assets.tiles.get(tid)
        self.status_lbl.config(text=f"Selected: {t['name'] if t else 'Unknown'}")
        if hasattr(self, 'studio_panel'):
            self.studio_panel.update_preview_for_selected()
    
    def import_tiles(self):
        filepaths = filedialog.askopenfilenames(
            title="Import Tile(s) from Any Location", 
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif"), ("All Files", "*.*")]
        )
        if not filepaths:
            return
        
        success, msg = self.assets.load_images(filepaths, category="tiles")
        if success:
            self.update_sidebar()
            self.draw_world()
            self.status_lbl.config(text=msg)
        else:
            messagebox.showerror("Import Error", msg)
    
    def save_map(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path and self.world.save(path):
            self.status_lbl.config(text=f"Saved: {os.path.basename(path)}")
    
    def load_map(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("Text/CSV", "*.txt")])
        if not path:
            return
        # (#19) legacy vault_map.txt-style maps load as CSV; JSON as before
        ok = self.world.load_csv(path) if path.lower().endswith(".txt") else self.world.load(path)
        if ok:
            self.history = HistoryManager()  # (#6) never undo into a discarded map
            self.draw_world()
            self.status_lbl.config(text=f"Loaded: {os.path.basename(path)}")
    
    def new_map(self):
        if messagebox.askyesno("New Map", "Clear current map?"):
            self.world = WorldMap(DEFAULT_GRID_WIDTH, DEFAULT_GRID_HEIGHT, self.assets)
            self.player.world = self.world  # (extra) keep the player on the new map
            self.history = HistoryManager()  # (#6) never undo into a discarded map
            self.draw_world()
    
    def generate_biome(self, name):
        # (#5) the menu path gets the same confirmation the sidebar panel has,
        # and the whole generation becomes one undo step
        if messagebox.askyesno("Generate", f"Overwrite map with {name} biome?"):
            self.snapshot_generate(lambda: self.world.generate_biome(name))
            self.status_lbl.config(text=f"Generated {name}")

    def _map_layers(self):
        """Deep copies of all map layers (for undo snapshots)."""
        return ([row[:] for row in self.world.data],
                [row[:] for row in self.world.object_layer],
                [row[:] for row in self.world.collision_layer])

    def snapshot_generate(self, generate_fn):
        """(#5) Run a map-wiping generation as a single undoable step."""
        old = self._map_layers()
        generate_fn()
        new = self._map_layers()
        self.history = HistoryManager()  # (#6) generation starts a fresh undo history
        self.history.push(MapSnapshotCommand(self.world, old, new))
        self.draw_world()
    
    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.draw_world()

    def set_tool(self, tool):
        self.tool = tool
        self.refresh_tool_buttons()
        self.status_lbl.config(text=f"Tool: {tool.replace('_', ' ').title()}")

    def refresh_tool_buttons(self):
        for name, btn in self.tool_btns.items():
            active = (name == self.tool)
            btn.config(relief=tk.SUNKEN if active else tk.FLAT,
                       bg=COLOR_ACCENT if active else COLOR_PANEL_LIGHT,
                       fg='#000' if active else COLOR_TEXT)

    def update_brush(self):
        # (#15) clamp the brush size to 1..8
        try:
            self.brush_size = max(1, min(8, int(self.brush_var.get())))
        except (tk.TclError, ValueError):
            self.brush_size = 1
        self.brush_var.set(self.brush_size)

    def set_brush_shape(self, shape):
        self.brush_shape = shape
        self.brush_shape_var.set(shape)

    def toggle_collision_overlay(self):
        # (#13) the overlay finally has a button; red outline shows blocked cells
        self.show_collision = not self.show_collision
        self.draw_world()
        self.status_lbl.config(text=f"Collision overlay: {'ON' if self.show_collision else 'OFF'}")

    def toggle_sidebar(self):
        # (#16) sidebar toggle button
        if self.sidebar_visible:
            self.main_pane.forget(self.sidebar)
        else:
            self.main_pane.add(self.sidebar, minsize=150)
            self.root.after(100, self.lock_sidebar_width)
        self.sidebar_visible = not self.sidebar_visible

    def open_asset_palette(self):
        """(#16) Asset palette popup with search: double-click a tile to select it."""
        pal = tk.Toplevel(self.root)
        pal.title("Asset Palette")
        pal.geometry("360x480")
        pal.configure(bg=COLOR_PANEL)

        tk.Label(pal, text="Search", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(8, 2))
        search_var = tk.StringVar()
        tk.Entry(pal, textvariable=search_var, bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(fill=tk.X, padx=8, pady=2)

        lst = tk.Listbox(pal, bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, font=("Segoe UI", 8))
        lst.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        shown = []

        def refresh(*_):
            q = search_var.get().lower()
            lst.delete(0, tk.END)
            shown.clear()
            for tid, t in sorted(self.assets.tiles.items()):
                label = f"{tid}: {t['name']} ({t['type']})"
                if q in label.lower():
                    lst.insert(tk.END, label)
                    shown.append(tid)

        def pick(event=None):
            sel = lst.curselection()
            if sel:
                self.select_tile(shown[sel[0]])
                pal.destroy()

        search_var.trace_add("write", refresh)
        refresh()
        lst.bind("<Double-Button-1>", pick)
        tk.Button(pal, text="Select", command=pick, bg=COLOR_ACCENT, fg='#000',
                  relief=tk.FLAT).pack(fill=tk.X, padx=8, pady=8)

    def open_animation_queue(self):
        """(#16) Animation queue builder: reorder frames and tweak the speed
        of existing animations."""
        anims = {tid: t for tid, t in self.assets.tiles.items() if t.get('type') == 'animation'}
        if not anims:
            messagebox.showwarning("Warning", "No animations yet — build one in the Studio tab first.")
            return

        q = tk.Toplevel(self.root)
        q.title("Animation Queue Builder")
        q.geometry("420x470")
        q.configure(bg=COLOR_PANEL)

        tk.Label(q, text="Animation", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(8, 2))
        anim_var = tk.StringVar()
        names = {f"{tid}: {t['name']}": tid for tid, t in sorted(anims.items())}
        combo = ttk.Combobox(q, textvariable=anim_var, values=list(names.keys()),
                             state="readonly", font=("Segoe UI", 8))
        combo.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(q, text="Frame order (top = first)", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(5, 2))
        frame_box = tk.Listbox(q, bg=COLOR_PANEL_LIGHT, fg=COLOR_TEXT, font=("Segoe UI", 8))
        frame_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        current = {'tid': None}
        seq = {'items': []}  # list of (filepath_index, PIL frame) in playing order

        def refresh_frames():
            frame_box.delete(0, tk.END)
            t = self.assets.tiles.get(current['tid'])
            fps = t.get('filepaths', []) if t else []
            for i, (fp_idx, _) in enumerate(seq['items']):
                fp = fps[fp_idx] if 0 <= fp_idx < len(fps) else None
                frame_box.insert(tk.END, f"{i}: {os.path.basename(fp) if fp else '?'}")

        def commit():
            t = self.assets.tiles.get(current['tid'])
            if not t:
                return
            t['frames'] = [fr for _, fr in seq['items']]
            t['frame_order'] = [fp for fp, _ in seq['items']]
            t['current_frame'] = 0
            self.assets.save_sprite_library()
            self.update_sidebar()
            self.draw_world()

        def load_anim(event=None):
            tid = names.get(anim_var.get())
            if tid is None:
                return
            current['tid'] = tid
            t = self.assets.tiles.get(tid)
            frames = t.get('frames', [])
            order = t.get('frame_order') or list(range(len(frames)))
            n = min(len(frames), len(order))
            seq['items'] = [(order[i], frames[i]) for i in range(n)]
            speed_var.set(t.get('frame_delay', 150))
            speed_lbl.config(text=f"{t.get('frame_delay', 150)}ms")
            refresh_frames()

        def move(delta):
            sel = frame_box.curselection()
            if current['tid'] is None or len(sel) != 1:
                return
            i, j = sel[0], sel[0] + delta
            items = seq['items']
            if not (0 <= j < len(items)):
                return
            items[i], items[j] = items[j], items[i]
            commit()
            refresh_frames()
            frame_box.select_set(j)

        combo.bind("<<ComboboxSelected>>", load_anim)

        nav = tk.Frame(q, bg=COLOR_PANEL)
        nav.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(nav, text="↑ Up", command=lambda: move(-1), bg=COLOR_PANEL_LIGHT,
                  fg=COLOR_TEXT, relief=tk.FLAT, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(nav, text="↓ Down", command=lambda: move(1), bg=COLOR_PANEL_LIGHT,
                  fg=COLOR_TEXT, relief=tk.FLAT, width=8).pack(side=tk.LEFT, padx=2)

        speed_var = tk.IntVar(value=150)
        tk.Label(q, text="Frame delay (ms)", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        speed_lbl = tk.Label(q, text="150ms", bg=COLOR_PANEL, fg=COLOR_ACCENT, font=("Segoe UI", 8))
        speed_lbl.pack(anchor="w", padx=8)

        def apply_speed(val):
            ms = int(float(val))
            speed_lbl.config(text=f"{ms}ms")
            t = self.assets.tiles.get(current['tid'])
            if t:
                t['frame_delay'] = ms
                self.assets.save_sprite_library()

        ttk.Scale(q, from_=50, to=500, variable=speed_var, orient=tk.HORIZONTAL,
                  command=apply_speed).pack(fill=tk.X, padx=8, pady=5)

        combo.current(0)
        load_anim()
    
    def reset_zoom(self):
        self.zoom_level = 1.0
        self.draw_world()
        self.info_lbl.config(text="Zoom: 100%")


# ==========================================
# ENTRY POINT
# ==========================================
def run_editor():
    try:
        root = tk.Tk()
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        root.geometry("1400x900")
        root.configure(bg=COLOR_BG)
        
        app = VaultsEditor(root)
        root.mainloop()
    except Exception as e:
        import traceback
        # (#23) write the traceback to a log file; only wait for Enter when a
        # console is actually attached, so a headless crash can't hang forever
        log_path = os.path.join(SCRIPT_DIR, "crash.log")
        try:
            with open(log_path, "a") as f:
                f.write(f"\n===== {datetime.now()} =====\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        traceback.print_exc()
        try:
            input("Press Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    run_editor()
