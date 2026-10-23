#!/usr/bin/env node
// melody_circuit_client_test.js — §14 Melody's daily circuit (pure planner + wiring).
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
const L = new Function(["melodyCircuitStops", "melodyCircuitPlan"].map(extract).join("\n") +
  "\nreturn {melodyCircuitStops,melodyCircuitPlan};")();

const st = L.melodyCircuitStops(50, 50, 100, 100, 6);
check("six stops", st.length === 6);
check("stops inside the map", st.every(s => s[0] >= 1 && s[0] <= 98 && s[1] >= 1 && s[1] <= 98));
check("stops spread out", new Set(st.map(s => s.join(","))).size === 6);
const edge = L.melodyCircuitStops(0, 0, 20, 20, 6);
check("clamped at corners", edge.every(s => s[0] >= 1 && s[1] >= 1));

const small = L.melodyCircuitPlan(200, 7, 3600);
check("small map: strolls at 1 tile/s and lingers to fill the day",
  small.speed === 1 && Math.abs(200 / small.speed + small.linger * 7 - 3600) < 1);
const big = L.melodyCircuitPlan(20000, 7, 3600);
check("big map: speeds up to finish the lap in a day", big.speed > 1 && big.speed <= 2.4);
check("never lingers under 4s", L.melodyCircuitPlan(100000, 7, 3600).linger >= 4);

check("circuit is started on spawn", /melodyStartCircuit\(melodyNpc\)/.test(html));
check("she holds still for company", /n\.melody && hero && \(MELODY\.open/.test(html));
check("swim ripple is drawn", /n\.melody && n\.swimming/.test(html));
check("server returns swims", /"swims": swims/.test(fs.readFileSync(path.join(__dirname, "..", "crumbs_hud.py"), "utf8")));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
