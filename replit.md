# Crumbs HUD on Replit

Crumbs HUD is a dependency-free Python web app. The server must listen on all
interfaces and on Replit's preview port.

## Run

```sh
PORT=5000 python3 crumbs_hud.py --public
```

The `Start application` workflow runs this command and opens the web preview.

## Project files

- `crumbs_hud.py`: HTTP server and persistence endpoints
- `crumbs_core.py`: map engine
- `editor.html`: browser interface
- `sprite_library.json` and `asset_library/`: sprites and artwork
- `vault_map.txt`: starter map

Map edits autosave to `hud_map.json` when the editor is dirty.