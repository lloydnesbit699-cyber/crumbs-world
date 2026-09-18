# Shared tile library

Tiles published here ship with the repo — everyone who pulls gets them on
every deployment. This is the **"Shared with everyone"** shelf in the HUD's
import form.

- `shared_library.json` is the registry (id, name, preset, flags, frame files).
- `NNNN_fM.png` files are the tile frames.
- Tiles imported as **"This device"** live in `custom_tiles/` instead and are
  never committed — they're private to that server.

To publish a device-local tile, use the tile manager's **Share** button in the
HUD (or move its entry + PNGs here by hand and restart).
