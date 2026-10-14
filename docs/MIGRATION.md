# Crumbs Vault Dungeon — Migration Notes

Sorted 2026-09-15 after the files were recovered. Originals untouched in upload folder.

## Project layout

```
crumbs-vault-dungeon/
├── vaults_editor.py      # THE EDITOR — v3.0, 1433 lines, tkinter, compiles clean
├── sprite_library.json   # FIXED: absolute C:\ paths -> relative asset_library/...
├── vault_map.txt         # blank 15x25 starter map (all zeros)
├── asset_library/        # EMPTY — copy your PNGs here (see PUT_PNGS_HERE.txt)
├── docs/
│   ├── qwen_build_history.md  # full Qwen chat log (v0.1 -> v0.8/v0.95 -> v3.0)
│   ├── dev_notes.txt          # your raw fix/upgrade notes
│   └── improvements_list.txt  # claimed v3.0 feature list + future roadmap
└── archive/
    └── vaults_editor_assets.py  # DEAD STUB — placeholder template, nothing imports it
```

## What I verified

- `vaults_editor.py` compiles, uses `SCRIPT_DIR`-relative paths everywhere — no hardcoded
  Windows paths in code. Drop the folder anywhere and it runs.
- `sprite_library.json` was the migration hazard: filepaths pointed at
  `C:\Users\lloyd\OneDrive\Desktop\VaultsWorldEditor\asset_library\`. Rewritten relative.
- `vaults_editor_assets.py` is not imported by anything. It contains placeholder comments
  ("replace with actual implementation code") and a junk line (`self0y = y`). Archived,
  not deleted — your call whether to trash it.
- `vault_map.txt` is just an empty map. Keep as starter/default.

## Gaps: claimed vs. actual (checked in code)

The improvements list claims these, but I can't find them in `vaults_editor.py`:

- **Brush shapes** (square/circle) — only `brush_size` exists, no shape logic.
- **Auto-categorize uploads** — categories exist (tiles/objects/animations), but uploads
  aren't auto-sorted; likely manual.
- Your dev notes also ask for: >2 animation frames, directional sprites, sprite at
  1/2–1/3 tile size, biome character differences, shape-drawing tools. Some may be
  partially done — needs a live run to confirm.

## Still needed from the old PC

1. The PNGs: `asset_library/hero4.png`, `asset_library/3.png` (and any others) from
   `C:\Users\lloyd\OneDrive\Desktop\VaultsWorldEditor\asset_library\`
   (original sprite source was `D:\VaultSdc120\sprites`).
2. Any other maps you saved (.txt levels) besides the blank starter.

## Running it (needs a real computer — tkinter has no iPhone GUI)

- Python 3.12 or 3.14 both fine for the tkinter version (no pygame needed).
- `pip install Pillow` for PNG sprite uploads.
- `python vaults_editor.py`
