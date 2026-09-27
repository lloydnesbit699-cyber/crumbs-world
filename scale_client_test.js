#!/usr/bin/env node
// scale_client_test.js — v5.41 client scale tests.
// Extracts maxTilePx + visibleTiles + markBaseDirty from editor.html and
// exercises them against stubbed globals; plus static assertions that the
// old 64-cap inputs and the per-render full-grid checksum are gone.
// Run: node scale_client_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

function extract(name) {
  const start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces in " + name);
}

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}

// ---- stubbed globals ----------------------------------------------------
let W = 0, H = 0, tilePx = 32, panX = 0, panY = 0;
let stage = { clientWidth: 800, clientHeight: 600 };
const MAX_CANVAS_DIM = 4096;   // mirrors the page const
let baseDirty = { full: true };

eval(extract("maxTilePx"));
eval(extract("visibleTiles"));
eval(extract("markBaseDirty"));

console.log("== maxTilePx ==");
W = 500; H = 500;
check("500x500 -> 8px tiles", maxTilePx() === 8, "got " + maxTilePx());
W = 64; H = 64;
check("64x64 unaffected (64)", maxTilePx() === 64, "got " + maxTilePx());
W = 256; H = 256;
check("256x256 -> 16px tiles", maxTilePx() === 16, "got " + maxTilePx());
W = 100; H = 500;
check("uses the larger dimension", maxTilePx() === 8, "got " + maxTilePx());
W = 4096; H = 4096;   // beyond the cap — never less than 8
check("never below 8", maxTilePx() === 8, "got " + maxTilePx());

console.log("== visibleTiles ==");
W = 500; H = 500; tilePx = 8; panX = 0; panY = 0;
stage = { clientWidth: 800, clientHeight: 600 };
let vr = visibleTiles();
check("range ordered", vr.x0 <= vr.x1 && vr.y0 <= vr.y1, JSON.stringify(vr));
check("range in bounds", vr.x0 >= 0 && vr.y0 >= 0 && vr.x1 < 500 && vr.y1 < 500,
  JSON.stringify(vr));
check("culls to a fraction of 500x500",
  (vr.x1 - vr.x0 + 1) * (vr.y1 - vr.y0 + 1) < 500 * 500 / 4,
  JSON.stringify(vr));
// scrolled to top-left corner: range starts at 0
panX = 1600; panY = 1700;   // undo the centering offset
vr = visibleTiles();
check("corner pan starts at 0", vr.x0 === 0 && vr.y0 === 0, JSON.stringify(vr));
// tiny map fully visible
W = 25; H = 15; tilePx = 32; panX = 0; panY = 0;
vr = visibleTiles();
check("small map fully covered", vr.x0 === 0 && vr.y0 === 0 && vr.x1 === 24 && vr.y1 === 14,
  JSON.stringify(vr));

console.log("== markBaseDirty ==");
W = 500; H = 500;
baseDirty = null;
markBaseDirty();
check("no-arg invalidates all", baseDirty && baseDirty.full === true);
baseDirty = null;
markBaseDirty(10, 10, 12, 12);
check("rect stored", baseDirty && baseDirty.x0 === 10 && baseDirty.y1 === 12,
  JSON.stringify(baseDirty));
markBaseDirty(20, 20, 22, 22);
check("rects merge", baseDirty.x0 === 10 && baseDirty.x1 === 22 &&
  baseDirty.y0 === 10 && baseDirty.y1 === 22, JSON.stringify(baseDirty));
markBaseDirty(490, 490, 600, 600);
check("clamped to map bounds", baseDirty.x1 === 499 && baseDirty.y1 === 499,
  JSON.stringify(baseDirty));
markBaseDirty();
check("rect + full -> full", baseDirty.full === true);

console.log("== static assertions ==");
check("no max=\"64\" inputs remain", !html.includes('max="64"'));
check("tilesChecksum gone", !html.includes("tilesChecksum"));
check("baseSig gone", !html.includes("baseSig"));
check("stroke echo applied", html.includes("applyStrokeEcho"));
check("export toast mentions reduced size", html.includes("reduced size"));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
