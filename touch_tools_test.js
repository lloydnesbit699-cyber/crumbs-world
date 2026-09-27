#!/usr/bin/env node
// touch_tools_test.js — v5.45 touch painting toolkit tests.
// Extracts the pure brush helpers from editor.html (stampCells, bresenham,
// rectCells, floodFillCells, fillNorm, scatterPick) and exercises them
// against stubbed inputs: stamp placement incl. multi-tile + edge clipping,
// line/rect geometry, flood fill regions + caps, scatter distribution sanity.
// Run: node touch_tools_test.js
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
function extractConstObj(name) {
  // const NAME = { ... }; — returns the object literal source for eval()
  const start = html.indexOf("const " + name + " =");
  if (start < 0) throw new Error("not found: const " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(i, j + 1); }
  }
  throw new Error("unbalanced braces in const " + name);
}

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

const STAMP_SHAPES = eval("(" + extractConstObj("STAMP_SHAPES") + ")");
eval(extract("stampCells"));
eval(extract("bresenham"));
eval(extract("rectCells"));
eval(extract("fillNorm"));
eval(extract("floodFillCells"));
eval(extract("scatterPick"));

const key = cells => cells.map(c => c[0] + "," + c[1]).sort().join("|");

console.log("== stampCells ==");
check("single = 1 cell", key(stampCells("single", 5, 5, 10, 10)) === "5,5");
check("2x2 = 4 cells",
  key(stampCells("b2", 5, 5, 10, 10)) === "5,5|5,6|6,5|6,6");
check("3x3 = 9 cells", stampCells("b3", 0, 0, 10, 10).length === 9);
check("corner = 5 cells (3x3 L)",
  key(stampCells("corner", 0, 0, 10, 10)) === "0,0|0,1|0,2|1,0|2,0");
check("ring = 8 cells (hollow center)",
  stampCells("ring", 0, 0, 10, 10).length === 8 &&
  !stampCells("ring", 0, 0, 10, 10).some(c => c[0] === 1 && c[1] === 1));
check("plus = 5 cells",
  key(stampCells("plus", 0, 0, 10, 10)) === "0,1|1,0|1,1|1,2|2,1");
check("2x2 clips at the east/south edges",
  key(stampCells("b2", 9, 9, 10, 10)) === "9,9");
check("3x3 clips at the corner",
  key(stampCells("b3", 8, 8, 10, 10)) === "8,8|8,9|9,8|9,9");
check("negative anchor drops out-of-map cells",
  stampCells("single", -1, -1, 10, 10).length === 0);
check("unknown shape falls back to single",
  key(stampCells("nope", 3, 3, 10, 10)) === "3,3");

console.log("== bresenham ==");
check("horizontal line", key(bresenham(0, 0, 4, 0)) === "0,0|1,0|2,0|3,0|4,0");
check("vertical line", key(bresenham(2, 1, 2, 4)) === "2,1|2,2|2,3|2,4");
check("diagonal hits every step", key(bresenham(0, 0, 3, 3)) === "0,0|1,1|2,2|3,3");
check("single point", key(bresenham(7, 7, 7, 7)) === "7,7");
check("reversed endpoints cover the same cells",
  key(bresenham(4, 0, 0, 0)) === key(bresenham(0, 0, 4, 0)));
{
  const l = bresenham(0, 0, 5, 2);
  check("shallow slope stays connected",
    l.every((c, i) => i === 0 || Math.abs(c[0] - l[i-1][0]) + Math.abs(c[1] - l[i-1][1]) <= 2));
}

console.log("== rectCells ==");
check("outline 3x3 = 8 cells", rectCells(0, 0, 2, 2, false).length === 8);
check("outline keeps the interior empty",
  !rectCells(0, 0, 2, 2, false).some(c => c[0] === 1 && c[1] === 1));
check("filled 3x3 = 9 cells", rectCells(0, 0, 2, 2, true).length === 9);
check("reversed corners normalize",
  key(rectCells(2, 2, 0, 0, true)) === key(rectCells(0, 0, 2, 2, true)));
check("1x1 rect = 1 cell", rectCells(4, 4, 4, 4, false).length === 1);
check("outline 4x2 = 8 cells", rectCells(0, 0, 3, 1, false).length === 8);

console.log("== floodFillCells ==");
{
  // 5x5: a 3x3 block of 1s ringed by 2s
  const g = [
    [2,2,2,2,2],
    [2,1,1,1,2],
    [2,1,1,1,2],
    [2,1,1,1,2],
    [2,2,2,2,2],
  ];
  const r = floodFillCells(g, 5, 5, 2, 2, 1000);
  check("fills exactly the matching region", r.cells.length === 9 && !r.truncated);
  check("region is the 3x3 block",
    key(r.cells) === "1,1|1,2|1,3|2,1|2,2|2,3|3,1|3,2|3,3");
  const r2 = floodFillCells(g, 5, 5, 0, 0, 1000);
  check("ring fill = 16 cells", r2.cells.length === 16);
  const r3 = floodFillCells(g, 5, 5, 2, 2, 4);
  check("cap truncates", r3.truncated && r3.cells.length === 4);
  const r4 = floodFillCells(g, 5, 5, 9, 9, 1000);
  check("out-of-bounds start = empty", r4.cells.length === 0 && !r4.truncated);
  // diagonal 1s must NOT connect (4-way)
  const d = [[1,0],[0,1]];
  const r5 = floodFillCells(d, 2, 2, 0, 0, 100);
  check("4-way: diagonals don't connect", r5.cells.length === 1);
  // object-shaped values compare by tid+flavor
  const o = [[{tid: 5, flavor: "a"}, {tid: 5, flavor: "b"}], [{tid: 5, flavor: "a"}, null]];
  const r6 = floodFillCells(o, 2, 2, 0, 0, 100);
  check("object cells compare by tid+flavor", r6.cells.length === 2);
}

console.log("== scatterPick ==");
check("empty mix = null", scatterPick([], 100, () => 0.1) === null);
check("density 0 = null", scatterPick([1, 2], 0, () => 0.01) === null);
check("density 100 always picks", scatterPick([7], 100, () => 0.99) === 7);
check("gate rejects above density", scatterPick([7], 50, () => 0.6) === null);
check("gate passes below density", scatterPick([7], 50, () => 0.4) === 7);
{
  // distribution sanity: over many picks every mix tile appears, roughly even
  // (rand is drawn twice per pick — gate then index — so the stub feeds
  // gate-pass values interleaved with index values cycling 0..3)
  let i = 0;
  const idx = [0.1, 0.3, 0.6, 0.9];   // -> mix indices 0,1,2,3
  const rand = () => { const v = (i % 2 === 0) ? 0.05 : idx[(i >> 1) % 4]; i++; return v; };
  const counts = { 10: 0, 20: 0, 30: 0, 40: 0 };
  for (let n = 0; n < 400; n++) counts[scatterPick([10, 20, 30, 40], 100, rand)]++;
  const vals = Object.values(counts);
  check("every mix tile gets picked", vals.every(v => v > 0), JSON.stringify(counts));
  check("picks spread across the mix (no single tile > 60%)",
    vals.every(v => v < 240), JSON.stringify(counts));
}
{
  // density ~50% lands about half the cells over a big sample
  let s = 12345;
  const lcg = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  let hits = 0;
  for (let n = 0; n < 2000; n++) if (scatterPick([1], 50, lcg) !== null) hits++;
  check("density 50 ≈ half the cells", hits > 700 && hits < 1300, "hits=" + hits);
}

console.log("== RESULT: " + PASS + " passed, " + FAIL + " failed ==");
process.exit(FAIL ? 1 : 0);
