#!/usr/bin/env node
// world_life_client_test.js — §13 day/night cycle, compass, waypoint ring.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
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
const L = new Function(["dayPhase", "dayLabel", "compassHeading", "waypointInfo"].map(extract).join("\n") +
  "\nreturn {dayPhase,dayLabel,compassHeading,waypointInfo};")();

console.log("== day/night ==");
check("noon is bright", L.dayPhase(0.5).dark === 0);
check("midnight is dark", Math.abs(L.dayPhase(0).dark - 0.6) < 1e-9);
check("dusk is warm and partial", L.dayPhase(0.75).dusk > 0.9 && L.dayPhase(0.75).rgb[0] > 3);
let mono = true, prev = L.dayPhase(0.5).dark;
for (let t = 0.5; t <= 1.0001; t += 0.01) { const d = L.dayPhase(t % 1).dark; if (d < prev - 0.03) mono = false; prev = d; }
check("evening darkens gradually", mono);
check("labels", L.dayLabel(0) === "night" && L.dayLabel(0.5) === "day");
check("day wraps", L.dayPhase(0).dark === L.dayPhase(1).dark);

console.log("== compass / waypoint ==");
check("facing up is N", L.compassHeading({ dx: 0, dy: -1 }).name === "N");
check("facing right is E", L.compassHeading({ dx: 1, dy: 0 }).name === "E");
check("facing down is S", L.compassHeading({ dx: 0, dy: 1 }).name === "S");
check("facing left is W", L.compassHeading({ dx: -1, dy: 0 }).name === "W");
check("waypoint distance", L.waypointInfo({ x: 0, y: 0 }, { x: 3, y: 4 }).dist === 5);

console.log("== wiring ==");
check("lighting uses the day phase", /dayPhase\(dayNow\(\)\)/.test(html));
check("ring + compass drawn in render", /drawWaypointRing\(\);\s*updateCompass\(\);/.test(html));
check("HUD hide button", /id="sky-hud"/.test(html));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
