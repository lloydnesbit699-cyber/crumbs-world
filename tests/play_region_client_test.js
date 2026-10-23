#!/usr/bin/env node
// play_region_client_test.js — v6.2 region-rendered Play view + altitude modes.
// Extracts the pure play* helpers from editor.html and checks the handoff
// acceptance cases. Run: node play_region_client_test.js
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
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}
const consts = html.match(/^const PLAY_[^\n]*$/gm).join("\n");
const body = consts + "\n" + ["playTilePx", "playSurveyN", "playWorldN", "playModeTargets", "playClampN",
  "playFlightDur", "playFlightStart", "playFlightAt", "playCameraStep", "playScaleCap", "playQualityStep"]
  .map(extract).join("\n") + "\nreturn {playTilePx,playModeTargets,playClampN,playFlightDur,playFlightStart,playFlightAt,playCameraStep,playScaleCap,playQualityStep,PLAY_DEADZONE_W,PLAY_FLIGHT_MIN_MS};";
const P = new Function(body)();

console.log("== character-relative scale ==");
check("N characters fill the stage height", Math.abs(P.playTilePx(6, 600, 2) * 2 * 6 - 600) < 1e-9);
check("same N, taller hero: tiles shrink", P.playTilePx(6, 600, 2) < P.playTilePx(6, 600, 1));

console.log("== mode targets ==");
let t = P.playModeTargets(500, 500, 2, 16 / 9);
check("500 map, 2-tile hero: ground 6, survey 64", t.ground === 6 && t.survey === 64, JSON.stringify(t));
check("500 map world spans the map", t.world >= 250, "world " + t.world);
t = P.playModeTargets(64, 64, 1, 16 / 9);
check("64 map, 1-tile hero: survey 32, world 64", t.survey === 32 && t.world === 64, JSON.stringify(t));
check("first person is the floor", t.first === 4);
t = P.playModeTargets(10, 10, 1, 1);
check("tiny map clamps modes to world", t.survey <= t.world && t.ground <= t.world);

console.log("== flights ==");
const w = 250;
const dFar = P.playFlightDur(250, 6, w), dNear = P.playFlightDur(12, 6, w);
check("duration scales with log distance", dFar > dNear, dFar + " vs " + dNear);
check("floor of 1100ms", P.playFlightDur(6.1, 6, w) >= 1100);
check("rise is slower than dive", P.playFlightDur(6, 250, w) > P.playFlightDur(250, 6, w));
check("no flight when already there", P.playFlightStart(6, 6, 0, w) === null);
const fl = P.playFlightStart(250, 6, 0, w);
check("flight starts at from, ends at to", Math.abs(P.playFlightAt(fl, 0).n - 250) < 1e-6 && P.playFlightAt(fl, fl.dur).n === 6);
let prev = 1e9, mono = true;
for (let i = 0; i <= 20; i++) { const n = P.playFlightAt(fl, fl.dur * i / 20).n; if (n > prev + 1e-9) mono = false; prev = n; }
check("dive is monotonic (no hard cuts)", mono);
const mid = P.playFlightAt(fl, fl.dur / 2).n;
check("cancel mid-flight keeps interrupted N", mid > 6 && mid < 250);
check("clamp holds N inside [floor, world]", P.playClampN(1, 64) === 4 && P.playClampN(999, 64) === 64);

console.log("== deadzone camera ==");
let cam = { x: 50, y: 50 };
let r = P.playCameraStep(cam, { x: 51, y: 50.5 }, null, 2, 16, null);
check("inside the deadzone the camera holds", r.x === 50 && r.y === 50 && r.settled);
r = P.playCameraStep(cam, { x: 60, y: 50 }, null, 2, 100, null);
check("outside the deadzone it follows", r.x > 50 && !r.settled);
let c = { x: 50, y: 50 };
for (let i = 0; i < 200; i++) c = P.playCameraStep(c, { x: 60, y: 50 }, null, 2, 16, null);
check("converges to the deadzone edge", Math.abs(c.x - (60 - 3 * 2 / 2)) < 0.05, "x " + c.x);
r = P.playCameraStep(cam, { x: 51, y: 50 }, { dx: 1, dy: 0 }, 2, 16, null);
check("lookahead pulls the camera ahead of the facing", r.x > 50);

console.log("== pixel budget ==");
check("cap respects the pixel budget", Math.pow(P.playScaleCap(3840, 2160, 3, 8294400), 2) * 3840 * 2160 <= 8294400 * 1.0001);
check("cap limited by DPR", P.playScaleCap(800, 600, 2, 8294400) === 2);
check("cap never below 0.6", P.playScaleCap(20000, 20000, 1, 1e6) >= 0.6);
const q = { scale: 0, ema: 8, adjusted: 0 };
let s = P.playQualityStep(q, 8, 0, 2);
check("starts at the cap", s === 2);
for (let i = 1; i < 40; i++) s = P.playQualityStep(q, 40, i * 1100, 2);
check("slow frames back the scale off", s < 2 && s >= 0.6, "s " + s);
for (let i = 1; i < 80; i++) s = P.playQualityStep(q, 2, 50000 + i * 3000, 2);
check("fast frames recover to the cap", Math.abs(s - 2) < 1e-9, "s " + s);

console.log("== wiring ==");
check("render() has a region path", /if \(playRegionOn\(\) \|\| lensRegionOn\(\)\) \{\s*if \(!playRegionBegin\(\)\) return;/.test(html));
check("build mode keeps the full-map path", /function playRegionOn\(\) \{ return playMode && !buildBreak/.test(html));
check("mode buttons present", ["first", "ground", "survey", "world"].every(m => html.includes('data-mode="' + m + '"')));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
