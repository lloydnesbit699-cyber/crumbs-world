#!/usr/bin/env node
// areas_client_test.js — §14 areas (100x100, Origin centre, 3x3 live window, feathered borders).
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
const L = new Function("const AREA_TILES = 100, WORLD_AREAS_EACH_WAY = 5;\n" +
  ["areaOf", "areaAwake", "areaLive", "areaLabel", "areaFeather"].map(extract).join("\n") +
  "\nreturn {areaOf,areaAwake,areaLive,areaLabel,areaFeather};")();

const W = 1100, H = 1100;
check("Origin area is the centre (index 0,0)", L.areaOf(550, 550, W, H).ax === 0 && L.areaOf(599, 501, W, H).ay === 0);
check("one area east", L.areaOf(650, 550, W, H).ax === 1);
check("far corner is area 5,5", L.areaOf(1099, 1099, W, H).ax === 5 && L.areaOf(1099, 1099, W, H).ay === 5);
check("far corner west is -5", L.areaOf(0, 0, W, H).ax === -5);
check("live window is 3x3 in the middle", L.areaLive(550, 550, W, H).length === 9);
check("live window clips at the world edge", L.areaLive(1099, 1099, W, H).length === 4);
check("neighbour awake, two away asleep", L.areaAwake(650, 550, 550, 550, W, H) && !L.areaAwake(800, 550, 550, 550, W, H));
check("small maps are entirely awake", L.areaAwake(1, 1, 24, 14, 25, 15));
check("label", L.areaLabel({ ax: 0, ay: 0 }) === "Origin" && L.areaLabel({ ax: 2, ay: -1 }) === "Area 2,-1");
check("feather is smooth 0..1", L.areaFeather(-20, 8) === 0 && L.areaFeather(20, 8) === 1 && Math.abs(L.areaFeather(0, 8) - 0.5) < 1e-9);
check("sleeping areas skip NPC ticks (Melody exempt)", /!n\.melody && hero && !areaAwake\(/.test(html));
check("HUD shows the area on big maps", /areaLabel\(areaOf\(hero\.x/.test(html));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
