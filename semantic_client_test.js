#!/usr/bin/env node
// semantic_client_test.js — v5.46 semantic painting client tests.
// Extracts the pure engine from editor.html (semHash, semEdgeMask,
// semWallMask, semShadowSides, semShadowCorners, semBaseTile, semDecorPick,
// semCellPhysics, semValidTerrain, semGet) and asserts it against the SAME
// vectors the Python suite checks in crumbs_core.py — ghost previews must
// hash, mask, and pick exactly like the server commits. Parity runs through
// ONE python3 process fed JSON, so the suite stays fast.
// Run: node semantic_client_test.js
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

// the whole pure block: from the v5.46 engine banner to the ghost overlay
// banner. No DOM in here by construction.
const startMark = "// ---- v5.46: semantic painting — pure engine";
const endMark = "// -- the ghost overlay ---";
const a = html.indexOf(startMark), b = html.indexOf(endMark);
if (a < 0 || b < 0 || b < a) throw new Error("engine block not found");
const engineSrc = html.slice(a, b);

const engine = eval(engineSrc + "\n;({semHash, semValidTerrain, semGet, semEdgeMask," +
  " semWallMask, semShadowSides, semShadowCorners, semBaseTile," +
  " semDecorPick, semCellPhysics, SEM_TERRAINS, SEM_N, SEM_NE, SEM_E, SEM_SE," +
  " SEM_S, SEM_SW, SEM_W, SEM_NW})");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

const tags = (w, h, fill) =>
  Array.from({ length: h }, () => Array(w).fill(fill === undefined ? null : fill));

// ---- batched python parity --------------------------------------------
// jobs: [{k, fn, args}]; returns {k: result}. One process, one JSON round trip.
function pyBatch(jobs) {
  const script = `
import sys, json
sys.path.insert(0, ${JSON.stringify(__dirname)})
import crumbs_core as c
jobs = json.load(sys.stdin)
out = {}
for j in jobs:
    fn = getattr(c, j["fn"])
    out[j["k"]] = fn(*j["args"])
json.dump(out, sys.stdout)
`;
  const res = execFileSync("python3", ["-c", script],
    { input: JSON.stringify(jobs), encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  return JSON.parse(res);
}

console.log("== hash parity ==");
check("semHash(3,5,1234) == 3495858765", engine.semHash(3, 5, 1234) === 3495858765);
{
  const r = pyBatch([{ k: "h", fn: "sem_hash", args: [3, 5, 1234] }]);
  check("hash matches python", engine.semHash(3, 5, 1234) === r.h);
}
check("hash differs by seed", engine.semHash(3, 5, 1234) !== engine.semHash(3, 5, 999));

console.log("== mask parity (200 random grids x 25 cells) ==");
let seed = 42;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const grids = [];
for (let t = 0; t < 200; t++) {
  const g = tags(5, 5);
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) {
    const r = rnd();
    g[y][x] = r < 0.35 ? null : ["floor", "wall", "water"][Math.floor(rnd() * 3)];
  }
  grids.push(g);
}
const jobs = [];
grids.forEach((g, t) => {
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) {
    jobs.push({ k: t + ":e:" + x + "," + y, fn: "sem_edge_mask", args: [g, x, y, 5, 5] });
    jobs.push({ k: t + ":w:" + x + "," + y, fn: "sem_wall_mask", args: [g, x, y, 5, 5] });
  }
});
{
  const r = pyBatch(jobs);
  let ok = true, detail = "";
  grids.forEach((g, t) => {
    for (let y = 0; y < 5 && ok; y++) for (let x = 0; x < 5 && ok; x++) {
      const je = engine.semEdgeMask(g, x, y, 5, 5);
      const jw = engine.semWallMask(g, x, y, 5, 5);
      if (je !== r[t + ":e:" + x + "," + y] || jw !== r[t + ":w:" + x + "," + y]) {
        ok = false;
        detail = "grid " + t + " cell " + x + "," + y +
          " js=" + je + "/" + jw + " py=" + r[t + ":e:" + x + "," + y] + "/" + r[t + ":w:" + x + "," + y];
      }
    }
  });
  check("edge+wall masks == python", ok, detail);
}

console.log("== shadow parity (all 256 masks) ==");
{
  const sj = [];
  for (let m = 0; m < 256; m++) sj.push({ k: String(m), fn: "sem_shadow_sides", args: [m] });
  for (let m = 0; m < 256; m++) sj.push({ k: "c" + m, fn: "sem_shadow_corners", args: [m] });
  const r = pyBatch(sj);
  let ok = true;
  for (let m = 0; m < 256 && ok; m++) {
    if (JSON.stringify(engine.semShadowSides(m)) !== JSON.stringify(r[String(m)]) ||
        JSON.stringify(engine.semShadowCorners(m)) !== JSON.stringify(r["c" + m])) ok = false;
  }
  check("shadow sides+corners == python", ok);
}

console.log("== tile/decor parity ==");
const pools = { floor: [11, 12, 13], wall: [21, 22], water: [31], decor: [41, 42] };
{
  seed = 7;
  const tj = [];
  const cases = [];
  for (let t = 0; t < 120; t++) {
    const x = Math.floor(rnd() * 9), y = Math.floor(rnd() * 9);
    const terr = ["floor", "wall", "water"][t % 3];
    cases.push([terr, x, y]);
    tj.push({ k: "t" + t, fn: "sem_base_tile", args: [terr, x, y, pools, "mixed", 1234] });
  }
  const big = tags(9, 9, "floor");
  for (let t = 0; t < 60; t++) {
    const x = 1 + Math.floor(rnd() * 7), y = 1 + Math.floor(rnd() * 7);
    cases.push(["decor", x, y]);
    tj.push({ k: "d" + t, fn: "sem_decor_pick",
              args: [big, x, y, 9, 9, 100, pools.decor, 1234] });
  }
  const r = pyBatch(tj);
  let ok = true, detail = "";
  cases.forEach((c, i) => {
    if (!ok) return;
    const js = c[0] === "decor"
      ? engine.semDecorPick(big, c[1], c[2], 9, 9, 100, pools.decor, 1234)
      : engine.semBaseTile(c[0], c[1], c[2], pools, "mixed", 1234);
    const key = c[0] === "decor" ? "d" + (i - 120) : "t" + i;
    if (js !== r[key]) { ok = false; detail = c.join(",") + " js=" + js + " py=" + r[key]; }
  });
  check("180 picks: base tiles + decor == python", ok, detail);
}
check("explicit style wins", engine.semBaseTile("floor", 2, 3, pools, 12, 1234) === 12);
check("empty pool -> null", engine.semBaseTile("floor", 2, 3, { floor: [] }, "mixed", 1) === null);

console.log("== physics + validation ==");
check("floor walkable",
  JSON.stringify(engine.semCellPhysics("floor")) === JSON.stringify([false, false]));
check("wall blocked",
  JSON.stringify(engine.semCellPhysics("wall")) === JSON.stringify([true, false]));
check("water hazard",
  JSON.stringify(engine.semCellPhysics("water")) === JSON.stringify([true, true]));
check("lava rejected", engine.semValidTerrain("lava") === null);
check("terrains list", JSON.stringify(engine.SEM_TERRAINS) === '["floor","wall","water"]');
check("direction bits",
  engine.SEM_N === 1 && engine.SEM_NW === 128 && engine.SEM_S === 16);

console.log("== ghost-semantics smoke ==");
// the ghost overlay painter reads stroke tags through a proxy view —
// emulate one cell: buffered "wall" over a live "floor" grid must mask 255.
const live = tags(3, 3, "floor");
const view = { 1: { 1: "wall" } };
const proxy = new Proxy({}, {
  get(t, py2) {
    const y = +py2, row = view[y] || {};
    return new Proxy({}, { get(tt, px) { const x = +px; return (x in row) ? row[x] : live[y][x]; } });
  }
});
check("ghost view masks like the server",
  engine.semEdgeMask(proxy, 1, 1, 3, 3) === 255);

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
