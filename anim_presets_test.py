#!/usr/bin/env python3
"""anim_presets_test.py — v5.43 animation preset + state-record tests.
Run: python3 anim_presets_test.py
Covers:
  - _tween_frames: 6 RGBA frames, same size, for every preset; amp=0 is a
    no-op; amp clamps; magic bakes a colored glow
  - _bring_to_life_frames: single picture -> tweened frames of the preset's
    motion; multi-pose sheet -> sliced poses (preset rides on as params)
  - _preset_anim_record: idle/walk/sleep states, default idle, transitions
  - _clean_anim: valid records pass, junk is sanitized, empty -> None
  - _clean_pauses: per-stop animation states (v5.43)
  - _store_custom_tile anim round-trip + _custom_public carries anim
Temp vault dir only — no server, no network, no user data.
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crumbs_hud as h
import crumbs_core as core
from PIL import Image, ImageChops

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def solid(w=64, hh=64, color=(200, 50, 50, 255)):
    return Image.new("RGBA", (w, hh), color)


def differs(a, b):
    # (Pillow's getbbox is unreliable on RGBA here — compare in RGB.)
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return d.getbbox() is not None


print("== _tween_frames ==")
base = solid()
for p in h.ANIM_PRESETS:
    fr = h._tween_frames(base, p, 70, "#6db7ff")
    check(f"{p}: 6 RGBA frames, base size",
          len(fr) == 6 and all(f.mode == "RGBA" and f.size == base.size
                               for f in fr))
# a sprite with transparent surroundings (magic's baked glow needs somewhere to show)
mg_base = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
mg_base.paste(solid(32, 32, (200, 50, 50, 255)), (16, 16))
for p in h.ANIM_PRESETS:
    # magic's glow hides behind a full-bleed sprite — test it on a sprite
    # with transparent surroundings
    src = mg_base if p == "magic" else base
    fr = h._tween_frames(src, p, 70, "#6db7ff")
    check(f"{p}: amp 70 visibly moves", any(differs(f, src) for f in fr))
for p in h.ANIM_PRESETS:
    fr = h._tween_frames(base, p, 0, "#6db7ff")
    check(f"{p}: amp 0 is a no-op",
          all(not differs(f, base) for f in fr))
fr = h._tween_frames(base, "bounce", 999)
fr70 = h._tween_frames(base, "bounce", 70)
check("amp clamps at 100 (999 == 100)",
      all(not differs(a, b) for a, b in
          zip(fr, h._tween_frames(base, "bounce", 100))))
check("amp 999 != amp 70", any(differs(a, b) for a, b in zip(fr, fr70)))
mg = h._tween_frames(mg_base, "magic", 100, "#6db7ff")[1]
px = mg.getpixel((8, 32))   # outside the sprite, inside the glow
check("magic bakes a blue-ish glow outside the sprite",
      px[3] > 20 and px[2] > px[0], str(px))
check("unknown preset falls back to alive",
      len(h._tween_frames(base, "dance", 70)) == 6)

print("== _bring_to_life_frames ==")
frames, method = h._bring_to_life_frames(base, "bounce", 70, "#ffd75f")
check("single picture -> tweened frames", method == "bounce" and len(frames) == 6)
check("tweened frames differ across the loop",
      differs(frames[0], frames[1]) or differs(frames[1], frames[2]))
# a two-pose sheet: two solid blocks with transparent gaps all around
sheet = Image.new("RGBA", (152, 76), (0, 0, 0, 0))
sheet.paste(solid(64, 64, (200, 50, 50, 255)), (6, 6))
sheet.paste(solid(64, 64, (50, 200, 50, 255)), (82, 6))
frames, method = h._bring_to_life_frames(sheet, "bounce", 70, "#ffd75f")
check("multi-pose sheet -> sliced poses", method == "sliced" and len(frames) == 2,
      f"{method} {len(frames)}")
check("sliced poses keep their art",
      frames[0].getpixel((32, 32))[:3] == (200, 50, 50) and
      frames[1].getpixel((32, 32))[:3] == (50, 200, 50))

print("== _preset_anim_record ==")
rec = h._preset_anim_record("bounce", 70, "#ffd75f", 400)
check("states idle/walk/sleep",
      sorted(rec["states"].keys()) == ["idle", "sleep", "walk"])
check("default is idle", rec["default"] == "idle")
check("walk carries the preset", rec["states"]["walk"]["act"] == "bounce" and
      rec["states"]["walk"]["amp"] == 70)
check("idle breathes slower", rec["states"]["idle"]["frame_ms"] >= 600)
check("sleep freezes frame 0", rec["states"]["sleep"]["frames"] == [0] and
      rec["states"]["sleep"]["act"] == "none")
check("transitions present",
      rec["transitions"]["idle->walk"]["blend_ms"] == 150)
rec_m = h._preset_anim_record("magic", 80, "#6db7ff", 400)
check("magic preset stores the aura color",
      rec_m["states"]["walk"]["magic"] == "#6db7ff" and
      rec_m["states"]["walk"]["act"] == "none")

print("== _clean_anim ==")
check("valid record survives", h._clean_anim(rec) is not None)
junk = {"states": {"idle": {"act": "dance", "amp": 500, "magic": "nope",
                            "frame_ms": 5, "frames": [0, -1, 99, "x"]},
                   "nope": {"act": "bounce"}},
        "default": "walk",
        "transitions": {"idle->walk": {"blend_ms": 5000}, "bogus": {}}}
c = h._clean_anim(junk)
check("unknown states dropped", c and set(c["states"]) == {"idle"})
check("bad act -> none", c["states"]["idle"]["act"] == "none")
check("amp clamps 0..100", c["states"]["idle"]["amp"] == 100)
check("bad magic -> null", c["states"]["idle"]["magic"] is None)
check("frame_ms clamps >= 80", c["states"]["idle"]["frame_ms"] == 80)
check("frames filtered to valid ints", c["states"]["idle"]["frames"] == [0],
      str(c["states"]["idle"].get("frames")))
check("default falls back to idle", c["default"] == "idle")
check("blend_ms clamps <= 1000",
      c["transitions"]["idle->walk"]["blend_ms"] == 1000)
check("bogus transition dropped", "bogus" not in c.get("transitions", {}))
check("empty states -> None", h._clean_anim({"states": {}}) is None)
check("non-dict -> None", h._clean_anim(None) is None)
check("missing states -> None", h._clean_anim({"default": "idle"}) is None)

print("== _clean_pauses with states (v5.43) ==")
pz = h._clean_pauses([{"secs": 5, "mode": "sleep", "state": "sleep"},
                      {"secs": 10, "mode": "stand", "state": "talk"},
                      {"secs": 0, "mode": "stand", "state": "dance"}], 3)
check("valid states kept", pz[0]["state"] == "sleep" and pz[1]["state"] == "talk",
      str(pz))
check("bogus state dropped", "state" not in pz[2], str(pz[2]))
check("mode still derived", pz[0]["mode"] == "sleep" and pz[1]["mode"] == "stand")
check("length mismatch -> None", h._clean_pauses([{"secs": 1}], 2) is None)

print("== _store_custom_tile anim round-trip ==")
tmp = tempfile.mkdtemp(prefix="crumbs-anim-")
_old_base = h._vault_base
h._vault_base = lambda: tmp
os.makedirs(os.path.join(tmp, "custom_tiles"), exist_ok=True)
try:
    old_tiles = list(h._custom_tiles)
    h._custom_tiles.clear()
    anim = h._preset_anim_record("float", 60, "#ffd75f", 400)
    entry, note = h._store_custom_tile("testbot", "character", 400,
                                       h._tween_frames(base, "float", 60),
                                       scope="local", anim=anim)
    check("store keeps the anim record", entry.get("anim") is not None and
          entry["anim"]["states"]["walk"]["act"] == "float")
    check("six frames written",
          entry.get("files") and len(entry["files"]) == 6,
          str(entry.get("files")))
    pub = h._custom_public(entry)
    check("_custom_public carries anim", pub.get("anim") is not None and
          pub["anim"]["default"] == "idle", str(pub.get("anim"))[:80])
    check("_custom_public carries frame count", pub["frames"] == 6)
    # /api/custom/update path: null anim erases
    entry2 = dict(entry)
    h._custom_tiles[:] = old_tiles
finally:
    h._vault_base = _old_base

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
