#!/usr/bin/env node
// height_sculpt_test.js — v5.45.2 height/depth sculpt touch-parity tests.
// Drives the pure sculpt helpers from editor.html with stubbed page state:
// heightCellValue (raise/lower/clear/caps), heightStrokeAdd (buffers the
// target levels WITHOUT touching the grid — the ghost invariant that makes
// two-finger cancellation trivial), and endHeightStroke (commit-on-release:
// one /api/height-set call, one undo step, grid lands locally).
// Run: node height_sculpt_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

function extract(name) {
  let start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  if (html.slice(start - 6, start) === "async ") start -= 6;   // keep the async keyword
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

// stubbed page state (the eval'd functions resolve these at call time)
let hstroke, heightGrid, heightDir, heightSig = 0;
let renderCalls = 0, refreshed = false, apiCalls = [];
const dirtyRects = [];
function queueRender() { renderCalls++; }
function markBaseDirty(x0, y0, x1, y1) { dirtyRects.push([x0, y0, x1, y1]); }
function toast() {}
async function api(url, body) { apiCalls.push({ url, body }); return { ok: true }; }
async function refreshHeight() { refreshed = true; }

eval(extract("heightCellValue"));
eval(extract("heightStrokeAdd"));
eval(extract("endHeightStroke"));

console.log("== heightCellValue ==");
check("raise 0 -> 1", heightCellValue(0, 1) === 1);
check("raise 2 -> 3", heightCellValue(2, 1) === 3);
check("raise at cap 3 -> no-op", heightCellValue(3, 1) === false);
check("lower 0 -> -1", heightCellValue(0, -1) === -1);
check("lower -1 -> -2", heightCellValue(-1, -1) === -2);
check("lower at cap -2 -> no-op", heightCellValue(-2, -1) === false);
check("missing level reads as 0", heightCellValue(undefined, 1) === 1);
check("clear -> null (tile-driven)", heightCellValue(2, 0) === null);
check("clear of 0 still clears", heightCellValue(0, 0) === null);

console.log("== heightStrokeAdd (ghost buffering) ==");
{
  heightDir = 1; heightGrid = [[0, 0], [0, 0]];
  hstroke = { cells: new Map() }; renderCalls = 0;
  heightStrokeAdd({ x: 0, y: 0 });
  const c = hstroke.cells.get("0,0");
  check("buffers [x,y,level]", c && c[0] === 0 && c[1] === 0 && c[2] === 1,
    JSON.stringify(c));
  check("GHOST INVARIANT: grid untouched while sculpting", heightGrid[0][0] === 0);
  check("schedules a render for the ghost", renderCalls === 1);
  heightStrokeAdd({ x: 0, y: 0 });
  check("revisit dedups", hstroke.cells.size === 1);
  heightStrokeAdd({ x: 1, y: 0 });
  check("drag extends the buffer", hstroke.cells.size === 2);
  check("grid still untouched after the drag",
    heightGrid[0][0] === 0 && heightGrid[0][1] === 0);
}
{
  heightDir = 1; heightGrid = [[3]];
  hstroke = { cells: new Map() };
  heightStrokeAdd({ x: 0, y: 0 });
  check("at-cap cell skipped", hstroke.cells.size === 0);
}
{
  heightDir = 0; heightGrid = [[2]];
  hstroke = { cells: new Map() };
  heightStrokeAdd({ x: 0, y: 0 });
  check("clear buffers null", hstroke.cells.get("0,0")[2] === null);
  check("clear leaves the grid alone too", heightGrid[0][0] === 2);
}
{
  heightDir = 1; heightGrid = [[0]];
  hstroke = { cells: new Map() };
  heightStrokeAdd({ x: 5, y: 5 });   // off the grid rows
  check("missing row ignored", hstroke.cells.size === 0);
}

console.log("== endHeightStroke (commit on release) ==");
(async () => {
  heightDir = 1; heightGrid = [[0, 0], [0, 0]];
  hstroke = { cells: new Map() };
  apiCalls = []; dirtyRects.length = 0; refreshed = false; heightSig = 0;
  heightStrokeAdd({ x: 0, y: 0 });
  heightStrokeAdd({ x: 1, y: 1 });
  await endHeightStroke();
  check("stroke handle released", hstroke === null);
  check("levels land on the grid", heightGrid[0][0] === 1 && heightGrid[1][1] === 1);
  check("untouched cells stay put", heightGrid[0][1] === 0 && heightGrid[1][0] === 0);
  check("one server call", apiCalls.length === 1, "calls=" + apiCalls.length);
  check("call targets /api/height-set", apiCalls[0] && apiCalls[0].url === "/api/height-set");
  check("payload carries both cells",
    apiCalls[0] && apiCalls[0].body.cells.length === 2);
  check("dirty rects marked", dirtyRects.length === 2);
  check("server reconciles after", refreshed === true);
  check("heightSig bumped", heightSig === 1);
  // empty stroke: no call, no crash
  hstroke = { cells: new Map() }; apiCalls = [];
  await endHeightStroke();
  check("empty stroke sends nothing", apiCalls.length === 0);
  console.log("== RESULT: " + PASS + " passed, " + FAIL + " failed ==");
  process.exit(FAIL ? 1 : 0);
})();
