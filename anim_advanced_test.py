#!/usr/bin/env python3
"""anim_advanced_test.py — v5.44 Advanced animation filmstrip tests.
Run: python3 anim_advanced_test.py
Covers:
  - _clean_fx_layer: kind allow-list, amp clamp, magic hex, visible bool
  - _clean_frame_mods: per-frame ms/hue/sat/bri clamps, position ranges,
    string keys, empty-mods drop
  - _clean_anim_state/_clean_anim: fx_layers cap + order kept, tween_steps
    clamp, record stamps v2 only when v5.44 fields exist, n_frames hint
  - _anim_frame_op (temp dir): dup appends + inherits mods, del prunes the
    file + renumbers every state's lists + remaps mods, move swaps frames
    and their mods, retime writes ms; errors on bad op/pos/last-frame
  - _render_anim_sequence: tweening multiplies frames but preserves total
    loop time, per-frame ms honored, aura/HSB/act visibly render,
    invisible layers are no-ops
  - export round-trips: GIF bytes + frame count, PNG-sequence zip, sprite
    sheet grid, JSON share doc -> decode -> pixel-identical raw art +
    identical anim record (lossless)
  - beginner<->advanced same-data: v1 record stays v1 through cleaning;
    advanced edits stamp v2 and survive; beginner essentials (act/amp/
    frame_ms on idle+walk) are never dropped by the cleaner
Temp dir only — no server, no network, no user data.
"""
import base64
import io
import os
import sys
import tempfile
import zipfile

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
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return d.getbbox() is not None


def mk_tile_dir(n=4):
    """Temp dir with n numbered frame PNGs + a matching entry dict."""
    td = tempfile.mkdtemp(prefix="animadv")
    files = []
    for i in range(n):
        fn = f"900_f{i}.png"
        solid(color=(40 * i + 40, 90, 140, 255)).save(
            os.path.join(td, fn), "PNG")
        files.append(fn)
    entry = {"id": 900, "name": "Test Tile", "files": files,
             "anim": {"v": 1, "default": "idle",
                      "states": {
                          "idle": {"act": "none", "amp": 0, "frame_ms": 100,
                                   "frames": list(range(n))},
                          "walk": {"act": "bounce", "amp": 70,
                                   "frame_ms": 100,
                                   "frames": [n - 1, 0]}}}}
    return td, entry


print("== _clean_fx_layer ==")
l = h._clean_fx_layer({"kind": "aura", "amp": 120, "magic": "#ff9d5c",
                       "visible": True})
check("amp clamps to 100", l == {"kind": "aura", "amp": 100,
                                 "magic": "#ff9d5c", "visible": True}, str(l))
check("unknown kind drops", h._clean_fx_layer({"kind": "wobble"}) is None)
check("non-dict drops", h._clean_fx_layer("aura") is None)
check("junk amp -> 70",
      h._clean_fx_layer({"kind": "pulse", "amp": "x"})["amp"] == 70)
check("bad magic hex -> None",
      h._clean_fx_layer({"kind": "aura", "magic": "red"})["magic"] is None)
check("missing magic stays None",
      h._clean_fx_layer({"kind": "float"})["magic"] is None)
check("visible False survives",
      h._clean_fx_layer({"kind": "shake", "visible": False})["visible"] is False)
check("junk visible -> True",
      h._clean_fx_layer({"kind": "shake", "visible": "yes"})["visible"] is True)

print("== _clean_frame_mods ==")
fm = h._clean_frame_mods({"0": {"ms": 5000, "hue": 999, "sat": -5,
                                "bri": 250},
                          "2": {"ms": 200},
                          "9": {"ms": 100},
                          "x": {"ms": 100},
                          "3": {}}, 4)
check("ms clamps 80..2000", fm["0"]["ms"] == 2000, str(fm))
check("hue wraps -180..180", fm["0"]["hue"] == 180)
check("sat/bri clamp 0..200",
      fm["0"]["sat"] == 0 and fm["0"]["bri"] == 200)
check("out-of-range pos dropped", "9" not in fm and "x" not in fm)
check("empty mod dict dropped", "3" not in fm)
check("valid pos kept", fm["2"] == {"ms": 200})
check("non-dict -> None", h._clean_frame_mods([1, 2], 4) is None)
check("all junk -> None", h._clean_frame_mods({"7": {"ms": 1}}, 4) is None)

print("== _clean_anim_state / _clean_anim v5.44 fields ==")
sd = h._clean_anim_state(
    {"act": "bounce", "amp": 80, "frames": [0, 1, 2, 3],
     "fx_layers": [{"kind": "bounce", "amp": 60}] * 10 +
                  [{"kind": "nope", "amp": 5}],
     "tween_steps": 9,
     "frame_mods": {"0": {"ms": 200}, "5": {"ms": 100}}}, 4)
check("layers capped at 8", len(sd["fx_layers"]) == 8, str(len(sd)))
check("layer order kept",
      all(l["kind"] == "bounce" for l in sd["fx_layers"]))
check("tween clamps to 4", sd["tween_steps"] == 4)
check("frame_mods validated against n_frames",
      sd["frame_mods"] == {"0": {"ms": 200}}, str(sd.get("frame_mods")))
sd2 = h._clean_anim_state({"act": "none", "tween_steps": "x",
                           "fx_layers": "nope"})
check("junk tween -> absent", "tween_steps" not in sd2)
check("junk layers -> absent", "fx_layers" not in sd2)
check("plain state stays v1-shaped", "frame_mods" not in sd2)

plain = {"v": 1, "default": "idle",
         "states": {"idle": {"act": "float", "amp": 70, "frame_ms": 900}}}
fancy = {"v": 1, "default": "idle",
         "states": {"idle": {"act": "float", "amp": 70, "frame_ms": 900,
                             "fx_layers": [{"kind": "aura", "amp": 50}]}}}
check("v1 record stays v1", h._clean_anim(plain, 4)["v"] == 1)
check("fx layers stamp v2", h._clean_anim(fancy, 4)["v"] == 2)
tw = {"v": 1, "states": {"idle": {"tween_steps": 2}}}
check("tween stamps v2", h._clean_anim(tw, 4)["v"] == 2)
mo = {"v": 1, "states": {"idle": {"frame_mods": {"0": {"ms": 200}}}}}
check("frame mods stamp v2", h._clean_anim(mo, 4)["v"] == 2)
mo_bad = {"v": 1, "states": {"idle": {"frames": [0, 1, 2, 3],
                                            "frame_mods": {"9": {"ms": 200}}}}}
c = h._clean_anim(mo_bad, 4)
check("n_frames hint drops bad mod pos, back to v1",
      c["v"] == 1 and "frame_mods" not in c["states"]["idle"])

print("== _anim_frame_op: dup ==")
td, entry = mk_tile_dir(4)
entry["anim"]["states"]["idle"]["frame_mods"] = {"1": {"ms": 200},
                                                 "2": {"hue": 30}}
anim, n = h._anim_frame_op(entry, td, "idle", "dup", 1)
check("dup grows the file list", n == 5 and len(entry["files"]) == 5,
      f"n={n}")
check("dup writes the new file",
      os.path.exists(os.path.join(td, entry["files"][4])))
check("dup inserts after the source",
      anim["states"]["idle"]["frames"] == [0, 1, 4, 2, 3],
      str(anim["states"]["idle"]["frames"]))
check("dup leaves other states alone",
      anim["states"]["walk"]["frames"] == [3, 0])
check("dup copy inherits source mods",
      anim["states"]["idle"]["frame_mods"].get("2") == {"ms": 200} and
      anim["states"]["idle"]["frame_mods"].get("1") == {"ms": 200} and
      anim["states"]["idle"]["frame_mods"].get("3") == {"hue": 30},
      str(anim["states"]["idle"].get("frame_mods")))
check("op persists onto the entry", entry["anim"] is anim)

print("== _anim_frame_op: move / retime ==")
td, entry = mk_tile_dir(4)
entry["anim"]["states"]["idle"]["frame_mods"] = {"0": {"ms": 111},
                                                 "1": {"ms": 222}}
anim, n = h._anim_frame_op(entry, td, "idle", "move", 0, direction=1)
check("move swaps the frames",
      anim["states"]["idle"]["frames"] == [1, 0, 2, 3])
check("move carries mods with the frames",
      anim["states"]["idle"]["frame_mods"] == {"1": {"ms": 111},
                                               "0": {"ms": 222}},
      str(anim["states"]["idle"].get("frame_mods")))
anim, n = h._anim_frame_op(entry, td, "idle", "move", 0, direction=-1)
check("move off the edge errors", anim is None and "can't move" in n,
      str(n))
anim, n = h._anim_frame_op(entry, td, "idle", "retime", 2, ms=500)
check("retime writes ms",
      anim["states"]["idle"]["frame_mods"]["2"] == {"ms": 500},
      str(anim["states"]["idle"].get("frame_mods")))
check("retime keeps the other mods",
      anim["states"]["idle"]["frame_mods"]["0"] == {"ms": 222})
anim, n = h._anim_frame_op(entry, td, "idle", "retime", 0, ms="junk")
check("bad ms errors", anim is None and n == "bad ms", str(n))

print("== _anim_frame_op: del ==")
td, entry = mk_tile_dir(4)
entry["anim"]["states"]["idle"]["frame_mods"] = {"1": {"ms": 200},
                                                 "2": {"hue": 30}}
# del renumbers compactly: the pruned file's NAME is reused by the file
# above it, so compare bytes, not names
victim_bytes = open(os.path.join(td, entry["files"][1]), "rb").read()
f2_bytes = open(os.path.join(td, entry["files"][2]), "rb").read()
anim, n = h._anim_frame_op(entry, td, "idle", "del", 1)
check("del shrinks the file list", n == 3, f"n={n}")
check("del drops the orphaned bytes",
      victim_bytes not in
      [open(os.path.join(td, f), "rb").read() for f in entry["files"]])
check("the file above slides into the hole",
      open(os.path.join(td, entry["files"][1]), "rb").read() == f2_bytes)
check("del renumbers this state's list",
      anim["states"]["idle"]["frames"] == [0, 1, 2],
      str(anim["states"]["idle"]["frames"]))
check("del remaps other states' indexes",
      anim["states"]["walk"]["frames"] == [2, 0],
      str(anim["states"]["walk"]["frames"]))
check("del drops the gone pos's mods, shifts later ones",
      anim["states"]["idle"]["frame_mods"] == {"1": {"hue": 30}},
      str(anim["states"]["idle"].get("frame_mods")))
check("files stay a clean sequence",
      entry["files"] == ["900_f0.png", "900_f1.png", "900_f2.png"],
      str(entry["files"]))
# deleting a frame another state still uses: the referenced file's BYTES
# survive (renumbered); the orphaned file's bytes are pruned
td, entry = mk_tile_dir(4)
entry["anim"]["states"]["idle"]["frames"] = [0, 2]   # file 1 unreferenced
entry["anim"]["states"]["walk"]["frames"] = [1, 3]   # file 1 referenced
f1_bytes = open(os.path.join(td, entry["files"][1]), "rb").read()
f0_bytes = open(os.path.join(td, entry["files"][0]), "rb").read()
anim, n = h._anim_frame_op(entry, td, "idle", "del", 0)
check("del still prunes the orphan (file 0)", n == 3, f"n={n}")
check("orphan bytes are gone",
      f0_bytes not in
      [open(os.path.join(td, f), "rb").read() for f in entry["files"]])
check("shared file's bytes survive, renumbered to index 0",
      open(os.path.join(td, entry["files"][0]), "rb").read() == f1_bytes)
check("walk's indexes follow the renumbering",
      anim["states"]["walk"]["frames"] == [0, 2],
      str(anim["states"]["walk"]["frames"]))
td, entry = mk_tile_dir(1)
anim, n = h._anim_frame_op(entry, td, "idle", "del", 0)
check("can't delete the last frame",
      anim is None and "last frame" in n, str(n))
anim, n = h._anim_frame_op(entry, td, "idle", "bogus", 0)
check("bad op errors", anim is None and n == "bad op")
anim, n = h._anim_frame_op(entry, td, "idle", "dup", 7)
check("bad pos errors", anim is None and n == "bad pos")
anim, n = h._anim_frame_op(entry, td, "nap", "dup", 0)
check("bad state errors", anim is None and n == "bad state")

print("== _render_anim_sequence ==")
td, entry = mk_tile_dir(3)
sd = {"frames": [0, 1, 2], "frame_ms": 100, "tween_steps": 2,
      "act": "none", "amp": 0}
seq = h._render_anim_sequence(td, entry["files"], sd)
check("tween multiplies frames", len(seq) == 9, f"len={len(seq)}")
total = sum(m for _, m in seq)
check("tween preserves total loop time", total == 300, f"total={total}")
sd = {"frames": [0, 1, 2], "frame_ms": 100,
      "frame_mods": {"1": {"ms": 300}}, "act": "none", "amp": 0}
seq = h._render_anim_sequence(td, entry["files"], sd)
check("per-frame ms honored",
      [m for _, m in seq] == [100, 300, 100],
      str([m for _, m in seq]))
check("durations clamp 80..2000",
      h._render_anim_sequence(
          td, entry["files"],
          {"frame_ms": 5, "act": "none"})[0][1] == 80)
sd = {"frames": [0, 1, 2], "frame_ms": 100, "act": "none",
      "fx_layers": [{"kind": "aura", "amp": 100, "magic": "#ff0000",
                     "visible": True}]}
glow = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
glow.paste(solid(32, 32), (16, 16))
glow.save(os.path.join(td, "glow.png"), "PNG")
seq = h._render_anim_sequence(td, ["glow.png"], sd)
check("aura layer visibly renders", differs(seq[0][0], glow))
sd_off = {"frames": [0, 1, 2], "frame_ms": 100, "act": "none",
          "fx_layers": [{"kind": "aura", "amp": 100, "magic": "#ff0000",
                         "visible": False}]}
seq_off = h._render_anim_sequence(td, ["glow.png"], sd_off)
check("invisible layer is a no-op", not differs(seq_off[0][0], glow))
seq_h = h._render_anim_sequence(
    td, ["glow.png"], {"frame_ms": 100, "hue": 90, "act": "none"})
check("state HSB renders", differs(seq_h[0][0], glow))
seq_b = h._render_anim_sequence(
    td, ["glow.png"], {"frame_ms": 100, "act": "bounce", "amp": 100})
check("act motion renders", differs(seq_b[0][0], glow))
sd = {"frames": [2, 0], "frame_ms": 100, "act": "none", "amp": 0}
seq = h._render_anim_sequence(td, entry["files"], sd)
f2 = Image.open(os.path.join(td, entry["files"][2])).convert("RGBA")
check("sequence follows the frames list", not differs(seq[0][0], f2))

print("== export round-trips ==")
td, entry = mk_tile_dir(3)
sd = {"frames": [0, 1, 2], "frame_ms": 100, "tween_steps": 1,
      "act": "none", "amp": 0}
seq = h._render_anim_sequence(td, entry["files"], sd)
# GIF — same save params as /api/anim/export
buf = io.BytesIO()
imgs = [im for im, _ in seq]
durs = [max(20, int(m)) for _, m in seq]
imgs[0].save(buf, "GIF", save_all=True, append_images=imgs[1:],
             duration=durs, loop=0, disposal=2)
check("GIF magic bytes", buf.getvalue()[:6] == b"GIF89a")
g = Image.open(io.BytesIO(buf.getvalue()))
check("GIF carries every rendered frame", g.n_frames == len(seq),
      f"{g.n_frames} vs {len(seq)}")
# PNG sequence zip
zbuf = io.BytesIO()
with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
    for i, (im, _) in enumerate(seq):
        pbuf = io.BytesIO()
        im.save(pbuf, "PNG")
        zf.writestr(f"tile-idle-{i:03d}.png", pbuf.getvalue())
znames = zipfile.ZipFile(io.BytesIO(zbuf.getvalue())).namelist()
check("zip holds one PNG per frame",
      len(znames) == len(seq) and all(z.endswith(".png") for z in znames))
# sprite sheet grid
import math
n = len(seq)
cw, ch = seq[0][0].size
cols = max(1, int(math.ceil(math.sqrt(n))))
rows = max(1, int(math.ceil(n / cols)))
sheet = core.Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
for i, (im, _) in enumerate(seq):
    sheet.paste(im, ((i % cols) * cw, (i // cols) * ch), im)
check("sheet grid fits every frame",
      sheet.size == (cols * cw, rows * ch) and cols * rows >= n,
      str(sheet.size))
# JSON share doc: raw frames + full record, lossless round-trip
entry["anim"]["states"]["idle"] = {
    "act": "float", "amp": 70, "frame_ms": 200, "frames": [0, 1, 2],
    "fx_layers": [{"kind": "aura", "amp": 60, "magic": "#7fe7ff",
                   "visible": True}],
    "tween_steps": 2, "frame_mods": {"1": {"ms": 300}}}
b64 = []
for fn in entry["files"]:
    with core.Image.open(os.path.join(td, fn)) as im:
        pbuf = io.BytesIO()
        im.convert("RGBA").save(pbuf, "PNG")
        b64.append(base64.b64encode(pbuf.getvalue()).decode("ascii"))
doc = h._anim_share_doc(entry, td, "idle",
                        entry["anim"]["states"]["idle"], b64)
check("share doc format tag", doc["format"] == "crumbs-anim/1")
check("share doc carries every raw frame", len(doc["frames"]) == 3)
rt_frames = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGBA")
             for b in doc["frames"]]
raw_frames = [Image.open(os.path.join(td, fn)).convert("RGBA")
              for fn in entry["files"]]
check("share doc art is pixel-identical (lossless)",
      all(not differs(a, b) for a, b in zip(rt_frames, raw_frames)))
check("share doc keeps the full record",
      doc["anim"]["states"]["idle"]["fx_layers"][0]["kind"] == "aura" and
      doc["anim"]["states"]["idle"]["tween_steps"] == 2 and
      doc["anim"]["states"]["idle"]["frame_mods"] == {"1": {"ms": 300}})
rt_anim = h._clean_anim(doc["anim"], len(rt_frames))
orig_anim = h._clean_anim(entry["anim"], len(entry["files"]))
check("record survives the round-trip", rt_anim == orig_anim)
check("round-trip re-stamps v2", rt_anim["v"] == 2)

print("== beginner <-> advanced: same data ==")
# a v1 record the way a beginner card tap writes it
v1 = {"v": 1, "default": "idle",
      "states": {
          "idle": {"act": "float", "amp": 70, "frame_ms": 900},
          "walk": {"act": "float", "amp": 70, "frame_ms": 420},
          "sleep": {"act": "none", "amp": 0, "frame_ms": 1200,
                    "frames": [0]}},
      "transitions": {"idle->walk": {"blend_ms": 150}}}
c1 = h._clean_anim(v1, 4)
check("beginner v1 record stays v1", c1["v"] == 1)
# the same record after Advanced edits (strip ops, layers, tween, mods)
v1["states"]["idle"].update(
    {"frames": [0, 2], "tween_steps": 2,
     "fx_layers": [{"kind": "bounce", "amp": 60, "visible": True}],
     "frame_mods": {"0": {"ms": 200}}})
v1["states"]["talk"] = {"act": "pulse", "amp": 40, "frame_ms": 600}
c2 = h._clean_anim(v1, 4)
check("advanced edits stamp v2", c2["v"] == 2)
st = c2["states"]["idle"]
check("advanced fields survive cleaning",
      st["frames"] == [0, 2] and st["tween_steps"] == 2 and
      len(st["fx_layers"]) == 1 and st["frame_mods"] == {"0": {"ms": 200}})
check("beginner essentials never dropped",
      st["act"] == "float" and st["amp"] == 70 and
      st["frame_ms"] == 900 and
      c2["states"]["walk"]["frame_ms"] == 420 and
      c2["states"]["sleep"]["frames"] == [0])
check("untouched states ride along", c2["states"]["talk"]["act"] == "pulse")
check("transitions ride along",
      c2["transitions"]["idle->walk"]["blend_ms"] == 150)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
