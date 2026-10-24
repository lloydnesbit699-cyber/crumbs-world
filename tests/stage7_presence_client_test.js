#!/usr/bin/env node
// stage7_presence_client_test.js — Stage 7 (§16.3, Ball Room item 14):
// presence / believable scale. Lloyd: creatures sized to what they are
// vs the hero (a spider = spider-size; a giant spider = explicitly
// giant); tall things draw as a ground base + an above-hero canopy +
// a soft shadow, not floor paint. These tests pin the kind table's
// integrity, the explicit-size-wins rule, Melody's exemption, the tall
// geometry (registered parts, feet anchor), the three draw effects,
// and the canopy pass ordering inside render().
// Run: node stage7_presence_client_test.js
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
const core = fs.readFileSync(path.join(__dirname, "..", "crumbs_core.py"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}
function extract(name) {
  let start = html.indexOf("async function " + name + "(");
  if (start < 0) start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces in " + name);
}
function extractConst(name) {
  const start = html.indexOf("const " + name + " =");
  if (start < 0) throw new Error("const not found: " + name);
  const end = html.indexOf(";", start);
  return html.slice(start, end + 1);
}

// ---- build the sandbox: real presence code over stubbed tile registries --
const src = [
  extractConst("KIND_RULES"), extractConst("KIND_SUB_FALLBACK"),
  extractConst("PRESENCE_MIN_PX"), extractConst("PRESENCE_TRUNK"), extractConst("PRESENCE_SPREAD"),
  "const _kindCache = {};",
  "let spriteTiles = [], customTiles = [], palette = [];",
  "const customById = {};",
  "let playHeroSize = 1.0;",
  extract("tileDefById"), extract("tileHt"),
  extract("objTid"), extract("objA"), extract("objSize"),
  extract("kindDef"), extract("kindInfo"), extract("kindScale"), extract("kindTall"),
  extract("objDrawSize"), extract("walkerDrawScale"), extract("folkDrawScale"), extract("heroDrawScale"),
  extract("tallParts"), extract("drawTallSlice"), extract("drawSoftShadow"),
  "({ kindInfo, kindScale, kindTall, objDrawSize, walkerDrawScale, folkDrawScale, heroDrawScale,",
  "   tallParts, drawTallSlice, drawSoftShadow, KIND_RULES, PRESENCE_TRUNK,",
  "   spriteTiles, customTiles, palette, customById, _kindCache,",
  "   setHeroSize: v => { playHeroSize = v; } })",
].join("\n");
const S = eval(src);
function def(id, name, extra) {
  const d = Object.assign({ id, name }, extra || {});
  S.customTiles.push(d); S.customById[id] = d;
  Object.keys(S._kindCache).forEach(k => delete S._kindCache[k]);
  return d;
}

console.log("== the table: every known kind resolves a scale ==");
function hintTokens(listName) {
  const m = core.match(new RegExp(listName + " = \\[([^\\]]*)\\]"));
  return [...m[1].matchAll(/"([^"]+)"/g)].map(x => x[1]);
}
let _tid = 1000;
for (const [list, sub] of [["ANIMAL_HINTS", "animals"], ["CREATURE_HINTS", "creatures"]]) {
  for (const tok of hintTokens(list)) {
    def(_tid, tok[0].toUpperCase() + tok.slice(1), { subcategory: sub, preset: "character" });
    const s = S.kindScale(_tid);
    check(list + " '" + tok + "' resolves", typeof s === "number" && s >= 0.15 && s <= 3, "got " + s);
    _tid++;
  }
}

console.log("== marquee sizes (Lloyd's examples first) ==");
def(1, "Spider");            check("a spider is spider-size", S.kindScale(1) === 0.3, "got " + S.kindScale(1));
def(2, "Giant Spider");      check("a GIANT spider is explicitly giant (> hero)", S.kindScale(2) === 1.5, "got " + S.kindScale(2));
def(3, "Tiny Spider");       check("a tiny spider shrinks below spider-size", S.kindScale(3) < S.kindScale(1), "got " + S.kindScale(3));
def(4, "Hood Hero");         check("the hero reference is 1.0", S.kindScale(4) === 1.0, "got " + S.kindScale(4));
def(5, "Village Guard", { subcategory: "characters", preset: "character" });
check("a humanoid fellow is hero-size", S.kindScale(5) === 1.0, "got " + S.kindScale(5));
def(6, "Dragon");            check("a dragon towers", S.kindScale(6) === 2.0, "got " + S.kindScale(6));
def(7, "Horse");             check("a horse stands taller than the hero", S.kindScale(7) === 1.15, "got " + S.kindScale(7));
def(8, "Pixie");             check("a pixie is small", S.kindScale(8) === 0.4, "got " + S.kindScale(8));
def(9, "Nameless Blob");     check("an unknown kind defaults to hero-size (never invisible, never huge)", S.kindScale(9) === 1.0, "got " + S.kindScale(9));
def(10, "Mystery Wuzzle", { subcategory: "animals" });
check("an unlisted animal falls back by taxonomy, not to 1.0", S.kindScale(10) === 0.6, "got " + S.kindScale(10));

console.log("== explicit size wins; the table is only the default ==");
def(20, "Spider");
check("instance with no size takes the kind scale", S.objDrawSize({ tid: 20 }) === 0.3);
check("bare-int cell takes the kind scale", S.objDrawSize(20) === 0.3);
check("a hand-set build size beats the table", S.objDrawSize({ tid: 20, size: 2 }) === 2);
check("walker: unset patrol size takes the kind scale", S.walkerDrawScale({ tile_id: 20, size: 1 }) === 0.3);
check("walker: a set patrol size wins", S.walkerDrawScale({ tile_id: 20, size: 0.9 }) === 0.9);
check("hero: unset build size reads his kind", S.heroDrawScale(20) === 0.3);
S.setHeroSize(0.5);
check("hero: a set build size wins over his kind", S.heroDrawScale(20) === 0.5);
S.setHeroSize(1.0);
def(21, "Knight", { subcategory: "characters", preset: "character" });
check("hero: a humanoid PC is the 1.0 reference", S.heroDrawScale(21) === 1.0);

console.log("== Melody is exempt — her rendering is hers alone ==");
check("walker: Melody keeps her record's size path", S.walkerDrawScale({ tile_id: 20, melody: true, size: 1.3 }) === 1.3);
check("walker: Melody with no size is 1 (as before Stage 7)", S.walkerDrawScale({ tile_id: 20, melody: true }) === 1.0);
check("folk: her standing figure is untouched even on a spider tile", S.folkDrawScale({ tile_id: 20, id: "melody_prime" }) === 1);
check("folk: a normal fellow on a spider tile is spider-size", S.folkDrawScale({ tile_id: 20, id: "npc_7" }) === 0.3);
check("her true-form draw is byte-untouched", html.includes("const sw2 = tilePx * 1.15"));

console.log("== tall kinds: base + canopy + soft shadow ==");
def(30, "Oak Tree");
check("a tree is tall", S.kindTall(30) === true);
check("a tree stands taller than the hero", S.kindScale(30) === 1.8, "got " + S.kindScale(30));
def(31, "Cactus");
check("a cactus is tall but grows no crown (spread 1)", S.kindTall(31) === true && S.kindInfo(31).spread === 1);
def(32, "Stone Block", { height: 2 });
check("a tile whose own height data says tall is tall", S.kindTall(32) === true);
def(33, "Grass Patch", { subcategory: "natural" });
check("grass is not tall", S.kindTall(33) === false);

const P = S.tallParts(100, 200, 32, 1.8, undefined);
check("three parts: shadow, base, canopy", !!P.shadow && !!P.base && !!P.canopy);
check("feet anchor: the base bottom IS the tile's ground line", Math.abs(P.base.dy + P.base.dh - (200 + 32)) < 1e-9);
check("parts register: canopy bottom meets base top exactly", Math.abs(P.canopy.dy + P.canopy.dh - P.base.dy) < 1e-9);
check("the canopy is wider than the trunk", P.canopy.dw > P.base.dw, P.canopy.dw + " vs " + P.base.dw);
check("the canopy centers on the tile's axis", Math.abs((P.canopy.dx + P.canopy.dw / 2) - (100 + 16)) < 1e-9);
check("source slices partition the sprite (no gap, no overlap)",
  P.canopy.syFrac === 0 && Math.abs(P.canopy.shFrac - (1 - S.PRESENCE_TRUNK)) < 1e-9 &&
  Math.abs(P.base.syFrac - P.canopy.shFrac) < 1e-9 && Math.abs(P.base.shFrac - S.PRESENCE_TRUNK) < 1e-9);
check("the shadow falls south-east of the trunk (NW light, as the height shadows)", P.shadow.cx > 100 + 16 && P.shadow.ry < P.shadow.rx);
const Pc = S.tallParts(0, 0, 32, 1.25, S.kindInfo(31).spread);
check("cactus: canopy slice is exactly trunk width (spread 1)", Math.abs(Pc.canopy.dw - Pc.base.dw) < 1e-9);

// the three observable draw effects, on a recording stub ctx
const calls = [];
const gim = { naturalWidth: 100, naturalHeight: 200 };
const gstub = { drawImage: (...a) => calls.push(a) };
S.drawTallSlice(gstub, gim, P.base);
S.drawTallSlice(gstub, gim, P.canopy);
check("base slice draws the sprite's BOTTOM source rows", calls.length === 2 &&
  calls[0][2] === 200 * P.base.syFrac && calls[0][4] === 200 * P.base.shFrac && calls[0][5] === P.base.dx);
check("canopy slice draws the sprite's TOP source rows", calls[1][2] === 0 && calls[1][4] === 200 * P.canopy.shFrac);
let stops = [], scaled = null;
const sstub = {
  save() {}, restore() {}, translate() {}, beginPath() {}, arc() {}, fill() {},
  scale(x, y) { scaled = [x, y]; },
  createRadialGradient() { return { addColorStop: (o, c) => stops.push([o, c]) }; },
};
S.drawSoftShadow(sstub, 50, 60, 20, 8);
check("the shadow is a gradient that fades to nothing at the rim (soft, not a disc)",
  stops.length === 3 && stops[0][1] === "rgba(0,0,0,0.34)" && stops[2][1] === "rgba(0,0,0,0)", JSON.stringify(stops));
check("the gradient is squashed into an ellipse", scaled && scaled[0] === 1 && Math.abs(scaled[1] - 8 / 20) < 1e-9);

console.log("== wiring in render() ==");
check("the objects loop draws at the kind's presence size", /const sz = objDrawSize\(ocell\)/.test(html));
check("the small lens reads the same presence size", /size = objDrawSize\(cell\)/.test(html));
check("walkers size through walkerDrawScale", /const sz = walkerDrawScale\(n\)/.test(html));
check("standing folks size through folkDrawScale", /const _fsz = folkDrawScale\(n\)/.test(html));
check("the hero sizes through heroDrawScale", /const _hsz = heroDrawScale\(pcTid\)/.test(html));
check("tall instances split in the objects loop (soft shadow + base + deferred canopy)",
  /drawSoftShadow\(ctx, P\.shadow\.cx/.test(html) && /drawTallSlice\(ctx, oim, P\.base\)/.test(html) && /_canopies\.push/.test(html));
check("the split is gated on readable tile size (WORLD keeps kind scale, loses the split)",
  /tilePx >= PRESENCE_MIN_PX && kindTall\(oid\)/.test(html) && !/tilePx/.test(extract("objDrawSize")));
const iHero = html.indexOf("hero marker in play mode");
const iObj = html.indexOf("object markers — v5.29");
const iCan = html.indexOf("for (const c of _canopies) drawTallSlice");
const iLoc = html.indexOf("drawLocatorStage()");
check("the canopy pass lands after the hero AND the objects loop", iCan > iHero && iCan > iObj, iHero + "/" + iObj + "/" + iCan);
check("the canopy pass lands before the locator/shrine/waypoint family", iCan > 0 && iCan < iLoc);
check("world_life's adjacency survives: ring then compass, still paired", /drawWaypointRing\(\);\s*updateCompass\(\);/.test(html));

console.log("\nstage7_presence_client_test: " + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
