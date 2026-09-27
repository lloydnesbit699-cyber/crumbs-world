#!/usr/bin/env node
// anim_palette_test.js — v5.45.1 animated palette tile tests.
// Exercises the pure palette-animation helpers from editor.html with stubbed
// frame clocks: animSwatchIds (which tiles earn a live swatch) and
// palAnimSig (repaint signature — stable within a frame, changes when the
// frame does, FX-only motion rides the 150ms clock).
// Run: node anim_palette_test.js
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
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

// stubbed frame clock + motion map (the page wires the real ones)
const fxIds = { 7: true };   // tile 7 has FX-layer motion only
function tileHasMotion(id) { return !!fxIds[id]; }
function stateFrameIdx(t, state, now) {
  const n = t.frames || 1;
  return Math.floor(now / 200) % n;   // 200ms per frame, like a slow torch
}

eval(extract("animSwatchIds"));
eval(extract("palAnimSig"));

console.log("== animSwatchIds ==");
{
  const tiles = [
    { id: 1, frames: 1 },   // static
    { id: 2, frames: 4 },   // frame-animated torch
    { id: 7, frames: 1 },   // FX-motion only (bobbing)
    { id: 9 },              // no frames field at all
    null,
  ];
  const ids = animSwatchIds(tiles);
  check("frame-animated tile animates", ids.includes(2));
  check("FX-only tile animates", ids.includes(7));
  check("static tile skipped", !ids.includes(1));
  check("frameless tile skipped", !ids.includes(9));
  check("null entry tolerated", ids.length === 2, JSON.stringify(ids));
  check("empty input -> empty", animSwatchIds([]).length === 0);
  check("null input -> empty", animSwatchIds(null).length === 0);
}

console.log("== palAnimSig ==");
{
  const torch = { id: 2, frames: 4 };
  const a = palAnimSig(torch, 100), b = palAnimSig(torch, 150);
  check("stable within a frame", a === b, a + " vs " + b);
  check("changes across frames", palAnimSig(torch, 100) !== palAnimSig(torch, 350));
  check("loops back around", palAnimSig(torch, 100) === palAnimSig(torch, 900));
  const fx = { id: 7, frames: 1 };
  check("FX-only: stable within a 150ms quantum",
    palAnimSig(fx, 10) === palAnimSig(fx, 140));
  check("FX-only: changes across quanta",
    palAnimSig(fx, 10) !== palAnimSig(fx, 160));
  const rock = { id: 1, frames: 1 };
  check("static tile: signature never moves",
    palAnimSig(rock, 0) === palAnimSig(rock, 99999));
}

console.log("== RESULT: " + PASS + " passed, " + FAIL + " failed ==");
process.exit(FAIL ? 1 : 0);
