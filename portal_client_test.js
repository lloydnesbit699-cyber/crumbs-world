#!/usr/bin/env node
// portal_client_test.js — v5.42 client portal/neighbor tests.
// Extracts groupMaps from editor.html and exercises it against stubbed
// globals; plus static assertions that the portal sheet, neighbor editor,
// and play-flow edge handling are wired up.
// Run: node portal_client_test.js
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
let currentFile = "home.json";
eval(extract("groupMaps"));

console.log("== groupMaps ==");
let groups = groupMaps([
  { file: "home.json", kind: "overworld", modified: 10 },
  { file: "cave.json", kind: "pocket", modified: 20 },
  { file: "shop.json", kind: "interior", modified: 5 },
  { file: "field.json", kind: "overworld", modified: 30 },
  { file: "legacy.json", modified: 1 },
]);
check("two groups", groups.length === 2);
check("worlds first", groups[0].title === "Worlds");
check("pockets group titled", groups[1].title === "Pockets & interiors");
check("worlds hold overworld + kindless",
  groups[0].maps.map(m => m.file).join(",") === "home.json,field.json,legacy.json",
  JSON.stringify(groups[0].maps.map(m => m.file)));
check("pockets hold pocket + interior",
  groups[1].maps.map(m => m.file).join(",") === "cave.json,shop.json",
  JSON.stringify(groups[1].maps.map(m => m.file)));
check("current map tops its group", groups[0].maps[0].file === "home.json");
// newest-modified first after the current map
groups = groupMaps([
  { file: "a.json", kind: "overworld", modified: 5 },
  { file: "b.json", kind: "overworld", modified: 50 },
]);
currentFile = "zzz.json";
groups = groupMaps([
  { file: "a.json", kind: "overworld", modified: 5 },
  { file: "b.json", kind: "overworld", modified: 50 },
]);
check("newest modified first", groups[0].maps[0].file === "b.json");
check("empty list -> two empty groups",
  groupMaps([]).every(g => g.maps.length === 0));
check("null-safe", groupMaps(null).every(g => g.maps.length === 0));

console.log("== portal sheet wiring (static) ==");
check("spawn X input present", html.includes('id="portal-sx"'));
check("spawn Y input present", html.includes('id="portal-sy"'));
check("target map picker present", html.includes('id="portal-target-pick"'));
check("portal-save sends spawn_x", html.includes("spawn_x:"));
check("portal-save sends spawn_y", html.includes("spawn_y:"));
check("portal picker fills target input",
  html.includes('pick.onchange'));

console.log("== neighbor editor (static) ==");
check("renderNeighborEditor defined", html.includes("function renderNeighborEditor("));
check("neighbor editor container in load sheet", html.includes('id="neighbor-editor"'));
check("posts to /api/neighbors/set", html.includes('"/api/neighbors/set"'));
check("gets /api/neighbors", html.includes('"/api/neighbors"'));
check("four edges offered",
  ["North", "South", "East", "West"].every(w => html.includes('"' + w + ' \\u2191"') || html.includes(w)));
check("broken neighbor shown, not hidden", html.includes("(gone)"));

console.log("== play flow edge handling (static) ==");
const edgeRefs = (html.match(/r\.edge_warp/g) || []).length;
check("edge_warp remapped in playTap + doStep", edgeRefs >= 2,
  "found " + edgeRefs);
check("notice toasted in playTap", html.includes("if (r.notice) toast(r.notice);"));
check("new-map button posts /api/maps/create",
  html.includes('"/api/maps/create"'));
check("kind cycles via /api/maps/meta",
  html.includes('kind: next'));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
