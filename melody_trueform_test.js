#!/usr/bin/env node
// melody_trueform_test.js — v5.61 static checks.
// Melody's confirmed true form in the game: her portrait in the talk dialog,
// an animated sprite of her on the map, and the exclusivity lock keeping her
// design out of the tile palette and out of player hands.
// Run: node melody_trueform_test.js
const fs = require("fs");
const path = require("path");

const dir = __dirname;
const html = fs.readFileSync(path.join(dir, "editor.html"), "utf8");
const py = fs.readFileSync(path.join(dir, "crumbs_hud.py"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

const FRAMES = [0, 1, 2, 3].map(i => "asset_library/melody_trueform_f" + i + ".png");
const PORTRAIT = "asset_library/melody_trueform_portrait.png";
const ALL = [PORTRAIT].concat(FRAMES);

console.log("== her art ships with the game ==");
for (const f of ALL) {
  check(f + " exists on disk", fs.existsSync(path.join(dir, f)));
  check(f + " is in the server update manifest",
    py.includes('"' + f + '"'), "UPDATE_ART_FILES");
  check(f + " is in the client update list",
    html.includes('"' + f + '"'), "artNames");
}
console.log("== her art is served, never a static tile ==");
check("the server has a whitelisted true-form art endpoint",
  /\/api\/melody-trueform\//.test(py) && /melody_trueform_f3\.png/.test(py));
check("the endpoint rejects non-whitelisted names",
  /if name not in \("melody_trueform_portrait\.png"/.test(py));

console.log("== her portrait in the talk dialog ==");
check("the dock header carries her portrait img",
  /<img id="melody-portrait"[^>]*src="\/api\/melody-trueform\/melody_trueform_portrait\.png"/.test(html));
check("the portrait is styled (round, framed)", /#melody-portrait \{/.test(html));

console.log("== her animated sprite on the map ==");
check("the client preloads her 4 sprite frames",
  /melodySpriteFrames/.test(html) && /MELODY_TRUEFORM_FILES\.slice\(1\)/.test(html));
check("drawNpc draws her true-form sprite when her art is ready",
  /n\.melody && melodySpriteReady\(\)/.test(html));
check("the sprite animates — frames cycle on a timer",
  /melodySpriteFrames\[Math\.floor\(Date\.now\(\) \/ 280\) % 4\]/.test(html));
check("the sprite hovers — gentle bob at draw time",
  /Math\.sin\(Date\.now\(\) \/ 650\)/.test(html));
check("her marker survives — purple ring, heart, nameplate still drawn for her",
  /if \(n\.melody\) \{/.test(html) && /fillText\("Melody"/.test(html));
check("borrowed-tile fallback remains while her art loads",
  /Falls back to the old body tile/.test(html) && /function melodyBodyTile/.test(html));
check("her animation drives frames — npcTick re-renders while she is live",
  /melodyLive/.test(html) && /her glow \+ hover/.test(html));

console.log("== the exclusivity lock ==");
check("the lock helper exists", /function melodyLockTiles\(tiles\)/.test(html));
check("the lock covers the palette load",
  /palette = melodyLockTiles\(p\.tiles\)/.test(html));
check("the lock covers the sprite list load",
  /spriteTiles = melodyLockTiles\(s\.tiles\)/.test(html));
check("the lock covers the custom tile load",
  /customTiles = melodyLockTiles\(r\.tiles\)/.test(html));
for (const reg of ["sprite_library.json", "shared_library.json", "asset_library/palette.json"]) {
  const body = fs.readFileSync(path.join(dir, reg), "utf8");
  check(reg + " has no true-form entry", !/melody_trueform/i.test(body), reg);
}
const spawns = (html.match(/melody: true/g) || []).length;
check("she spawns from exactly one place (spawnMelodyNpc)",
  spawns === 1, "found " + spawns);

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
