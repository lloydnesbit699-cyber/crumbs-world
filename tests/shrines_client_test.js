#!/usr/bin/env node
// shrines_client_test.js — §13.1 teleport shrines (pure rules + wiring).
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
const py = fs.readFileSync(path.join(__dirname, "..", "crumbs_hud.py"), "utf8");
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
function check(name, cond) { if (cond) { PASS++; console.log("  ok: " + name); } else { FAIL++; console.log("  FAIL: " + name); } }
const L = new Function("const SHRINE_UNLOCK_RANGE = 3, SHRINE_SEE_RANGE = 30;\n" +
  ["shrineState", "shrineTargets", "shrineScan"].map(extract).join("\n") +
  "\nreturn {shrineState,shrineTargets,shrineScan};")();

const list = [
  { id: "star_beacon", origin: true, x: 100, y: 100 },
  { id: "frost_reaper", x: 20, y: 20 },
  { id: "tide_mermaid", x: 110, y: 100 },
];
const un = new Set(["star_beacon"]), disc = new Set(["star_beacon"]);
check("undiscovered is hidden", L.shrineState(list[1], un, disc) === "hidden");
check("origin starts unlocked (full icon)", L.shrineState(list[0], un, disc) === "full");
check("origin alone is not a destination", L.shrineTargets(list, un).length === 0);
let r = L.shrineScan(list, { x: 100, y: 100 }, un, disc);
check("seeing a shrine from survey range discovers it (dimmed)", disc.has("tide_mermaid") && L.shrineState(list[2], un, disc) === "dim" && r.changed);
check("far shrine stays hidden", !disc.has("frost_reaper"));
r = L.shrineScan(list, { x: 108, y: 100 }, un, disc);
check("walking up unlocks it", un.has("tide_mermaid") && r.fresh && r.fresh.id === "tide_mermaid");
const t = L.shrineTargets(list, un).map(s => s.id);
check("origin joins the travel list once another shrine is unlocked", t.includes("star_beacon") && t.includes("tide_mermaid"));
check("rescanning changes nothing", !L.shrineScan(list, { x: 108, y: 100 }, un, disc).changed);

check("seven travel shrines + origin defined", (py.match(/\{"id": "[a-z_]+", "name":/g) || []).length >= 8);
check("every named shrine is present", ["Frost Reaper", "Ram-Horned Stone Warlord", "Void Obelisk", "Tide Mermaid",
  "Sun Falcon", "Forest Guardian", "Wind Pillar", "Star Beacon"].every(n => py.includes('"name": "' + n + '"')));
check("server endpoints exist", /"\/api\/play\/shrines"/.test(py) && /"\/api\/play\/teleport"/.test(py));
check("travel flies up, crosses, then dives (no hard cut)", /playGoMode\("world"\)[\s\S]{0,200}\/api\/play\/teleport[\s\S]{0,400}playGoMode\("ground"\)/.test(html));
check("markers drawn with the waypoint ring", /drawShrines\(\);\s*if \(rgActive\) drawWaypointRing\(\)/.test(html));
check("T key and View menu open the panel", /case "t": case "T"/.test(html) && /Teleport shrines/.test(html));
check("unlocks are stored per character", /crumbs_shrines_/.test(html) && /shrineKey\(\)/.test(html));
check("HUD hide is still manual (no auto-hide)", !/setTimeout\([^)]*uiClean\s*=\s*true/.test(html));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
