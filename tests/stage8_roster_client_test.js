#!/usr/bin/env node
// stage8_roster_client_test.js — Stage 8 (Ball Room item 22, Lloyd's
// ruling): the starter roster. At world creation the player imports their
// own character or picks from ~10 starter creatures; the pick becomes the
// world's hero through the ordinary hero_tiles designation, so Stage 7's
// kind table sizes it (a spider hero is spider-sized). These tests pin
// the roster's integrity against the REAL shared-library data (every
// offered row resolves to an existing character tile — no placeholders),
// the starter/reserved split (reserved rows ship in the data but are
// never offered), the Stage 7 composition through the real heroDrawScale,
// the creation wiring (pick rides /api/maps/create; skip sends nothing),
// and the server stamp in both create paths.
// Run: node stage8_roster_client_test.js
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
const hud = fs.readFileSync(path.join(__dirname, "..", "crumbs_hud.py"), "utf8");
const shared = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "shared_library.json"), "utf8"));

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

// ---------------------------------------------------------------------------
console.log("== roster integrity: every row resolves to real art ==");
const R = eval([
  extractConst("STARTER_ROSTER"),
  extract("starterRosterOffered"), extract("starterRosterEntry"),
  "({ STARTER_ROSTER, starterRosterOffered, starterRosterEntry })",
].join("\n"));
const roster = R.STARTER_ROSTER;
const offered = R.starterRosterOffered();
const byId = {};
for (const t of shared.tiles) byId[t.id] = t;

check("roster is a data table of rows", Array.isArray(roster) && roster.length >= 11,
  "rows=" + (roster && roster.length));
check("every row carries name, species, tid, starter flag", roster.every(r =>
  typeof r.name === "string" && r.name && typeof r.species === "string" && r.species &&
  Number.isInteger(r.tid) && typeof r.starter === "boolean"));
check("tids are unique", new Set(roster.map(r => r.tid)).size === roster.length);
check("~10 offered starters", offered.length >= 9 && offered.length <= 11,
  "offered=" + offered.length);
check("every roster row resolves to an existing tile", roster.every(r => !!byId[r.tid]),
  roster.filter(r => !byId[r.tid]).map(r => r.tid).join(","));
check("every roster row maps to a CHARACTER tile (real creature art, no placeholders)",
  roster.every(r => byId[r.tid] && byId[r.tid].preset === "character"),
  roster.filter(r => !byId[r.tid] || byId[r.tid].preset !== "character").map(r => r.name).join(","));
check("species spread: at least 6 distinct species offered",
  new Set(offered.map(r => r.species)).size >= 6,
  [...new Set(offered.map(r => r.species))].join(","));

console.log("== the split: reserved ships in the data, never offered ==");
const reserved = roster.filter(r => !r.starter);
check("reserved rows exist in the schema", reserved.length >= 1, "reserved=" + reserved.length);
check("offered set is exactly the starter:true rows",
  offered.every(r => r.starter) && offered.length === roster.length - reserved.length);
check("no reserved tid is offered", reserved.every(r => !offered.some(o => o.tid === r.tid)));
check("entry lookup resolves a roster tid", !!R.starterRosterEntry(offered[0].tid));
check("entry lookup misses an unknown tid", R.starterRosterEntry(999999) === null);

console.log("== Stage 7 composition: the pick IS the size (real heroDrawScale) ==");
const S = eval([
  extractConst("KIND_RULES"), extractConst("KIND_SUB_FALLBACK"),
  extractConst("PRESENCE_SPREAD"),
  "const _kindCache = {};",
  "let spriteTiles = [], customTiles = [], palette = [];",
  "const customById = {};",
  "let playHeroSize = 1.0;",
  extract("tileDefById"), extract("kindDef"), extract("kindInfo"),
  extract("kindScale"), extract("heroDrawScale"),
  "function def(id, name, extra) { const d = Object.assign({ id, name }, extra || {});" +
  "  customTiles.push(d); customById[id] = d; return d; }",
  "({ heroDrawScale, kindScale, def, setHeroSize: v => { playHeroSize = v; } })",
].join("\n"));
for (const t of shared.tiles) if (t.preset === "character") S.def(t.id, t.name, { preset: t.preset });
const tidOf = name => offered.find(r => r.name === name).tid;
check("a spider hero draws spider-sized (0.3)", S.heroDrawScale(tidOf("Spider")) === 0.3,
  "got " + S.heroDrawScale(tidOf("Spider")));
check("a hydra hero draws hydra-sized (1.9)", S.heroDrawScale(tidOf("Hydra")) === 1.9,
  "got " + S.heroDrawScale(tidOf("Hydra")));
check("a hound hero draws hound-sized (0.8)", S.heroDrawScale(tidOf("Hound")) === 0.8,
  "got " + S.heroDrawScale(tidOf("Hound")));
check("a knight hero stays the 1.0 reference", S.heroDrawScale(tidOf("Knight")) === 1.0,
  "got " + S.heroDrawScale(tidOf("Knight")));
check("every offered hero resolves a sane kind scale",
  offered.every(r => { const s = S.heroDrawScale(r.tid); return s >= 0.15 && s <= 3; }));
S.setHeroSize(2);
check("an explicit build size still wins over the pick (no special-casing)",
  S.heroDrawScale(tidOf("Spider")) === 2);
S.setHeroSize(1.0);

console.log("== creation wiring: the pick rides the create call ==");
check("step 2 renders the hero grid + hidden file input",
  /id="sh-cr-heroes"/.test(html) && /id="sh-cr-file" accept="image\/\*"/.test(html));
check("cards paint from the offered rows only",
  /starterRosterOffered\(\)\.forEach/.test(extract("shellCreatePaintHeroes")));
check("the Classic default card clears the pick",
  /_createHero = null; _createHeroName = ""; shellCreatePaintHeroes\(\)/.test(extract("shellCreatePaintHeroes")));
check("a fresh create flow starts with no pick",
  /_createHero = null; _createHeroName = "";/.test(extract("shellShowCreate")));
check("the create body carries hero_tile only when a pick exists",
  /if \(_createHero != null\) body\.hero_tile = _createHero;/.test(extract("shellCreateDo")) &&
  /shellApi\("\/api\/maps\/create", body\)/.test(extract("shellCreateDo")));
check("step 3 names the hero only when one was picked",
  /_createHero != null \? '<p class="sh-world-line">Your hero: '/.test(html));

console.log("== import: the existing custom-tile import is the route ==");
const imp = extract("shellCreateImportHero");
check("import posts to /api/custom-tiles as a character tile",
  imp.includes('"/api/custom-tiles"') && /preset: "character"/.test(imp));
check("the imported tile's id becomes the pick",
  /_createHero = r\.tile\.id;/.test(imp));
check("a failed import leaves the pick alone (no _createHero write in the error paths)",
  (imp.match(/_createHero = /g) || []).length === 1);

console.log("== server: the create handler stamps the designation ==");
const c0 = hud.indexOf('if path == "/api/maps/create":');
const c1 = hud.indexOf('if path == "/api/maps/meta":', c0);
const createSrc = hud.slice(c0, c1);
check("create slice found", c0 >= 0 && c1 > c0);
check("pick sanitized by the rules endpoint's own _valid_hero_list",
  createSrc.includes('_valid_hero_list([body.get("hero_tile")])'));
check("both create paths stamp hero_tiles + the legacy mirror",
  (createSrc.match(/\["hero_tiles"\] = \[hero_tile\]/g) || []).length === 2 &&
  (createSrc.match(/\["hero_tile"\] = hero_tile/g) || []).length === 2,
  "stamps=" + (createSrc.match(/\["hero_tiles"\] = \[hero_tile\]/g) || []).length);
check("both create responses report the stamped hero_tile",
  (createSrc.match(/"hero_tile": hero_tile/g) || []).length === 2);
check("no hero_tile in the body still creates (pick is optional, never a 400)",
  !/hero_tile[^)]*400/.test(createSrc));

console.log("\nstage8_roster_client_test: " + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
