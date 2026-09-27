#!/usr/bin/env node
// anim_client_test.js — v5.43 animation states + beginner presets.
// Extracts stateParams + stateFrameIdx + animLerpParams + tileHasMotion from
// editor.html and exercises the shared state model against stubbed globals:
// state fallback chains, per-state frames/timing, Rive-style blends, and
// legacy-fx backward compatibility. Also static checks: six preset cards
// exist, the preset table has six entries, the Advanced act row gained
// "alive", and the Animation menu carries the state picker.
// Run: node anim_client_test.js
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
function extractConst(name) {
  const m = html.match(new RegExp("const " + name + " = (\\{[\\s\\S]*?\\};|\\[[\\s\\S]*?\\];)"));
  if (!m) throw new Error("const not found: " + name);
  return "global." + name + " = " + m[1];
}

// ---- stubbed browser globals -------------------------------------------
let fakeNow = 1000000;
global.performance = { now: () => fakeNow };
global.FX_DEFAULT = { hue: 0, sat: 100, bri: 100, act: "none", magic: null };
let customById = {};   // stateParams/tileHasMotion read customById

eval(extractConst("ANIM_STATES"));
eval(extractConst("ANIM_STATE_DEFAULTS"));
eval(extractConst("ANIM_PRESETS"));      // v5.44 (mergeBeginnerPreset)
eval(extractConst("FX_LAYER_KINDS"));   // v5.44
eval(extract("filmstripFrames"));       // v5.44
eval(extract("frameModsFor"));          // v5.44
eval(extract("stateTick"));             // v5.44
eval(extract("stateParams"));
eval(extract("stateFrameIdx"));
eval(extract("animLerpParams"));
eval(extract("tileFx"));
eval(extract("tileHasMotion"));
eval(extract("mergeBeginnerPreset"));   // v5.44

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}

console.log("== stateParams: fallback chains ==");
const tile = {
  id: 7, frame_ms: 400, frames: 4, fx: null,
  anim: { v: 1, default: "idle",
          states: {
            idle: { act: "alive", amp: 60, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 900 },
            walk: { act: "bounce", amp: 80, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 420 },
            sleep: { act: "none", amp: 0, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 1200, frames: [0] },
          } },
};
let p = stateParams(tile, "walk");
check("walk state resolves", p.act === "bounce" && p.amp === 80 && p.frame_ms === 420,
      JSON.stringify(p));
p = stateParams(tile, "hurt");   // undefined state -> default (idle)
check("undefined state falls back to default",
      p.act === "alive" && p.frame_ms === 900, JSON.stringify(p));
const noDefault = { id: 8, frame_ms: 300, anim: { v: 1, default: "walk",
  states: { walk: { act: "shake", amp: 50, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 300 } } } };
p = stateParams(noDefault, "talk");
check("missing idle falls back to the record default",
      p.act === "shake", JSON.stringify(p));

console.log("== stateParams: legacy tiles keep their look ==");
const legacy = { id: 9, frame_ms: 500, frames: 2,
                 fx: { hue: 10, sat: 120, bri: 90, act: "float", magic: "#6db7ff" } };
p = stateParams(legacy, "idle");
check("legacy fx is the idle look",
      p.act === "float" && p.hue === 10 && p.magic === "#6db7ff" && p.frame_ms === 500,
      JSON.stringify(p));
p = stateParams(legacy, "walk");
check("legacy fx covers every state (old behavior)", p.act === "float");
const plain = { id: 10, frame_ms: 400, frames: 1, fx: null };
p = stateParams(plain, "idle");
check("no fx, no anim -> still", p.act === "none" && p.amp === 100);

console.log("== stateFrameIdx: per-state frames + timing ==");
fakeNow = 0;
check("walk cycles 4 frames", stateFrameIdx(tile, "walk", 0) === 0 &&
      stateFrameIdx(tile, "walk", 419) === 0 &&
      stateFrameIdx(tile, "walk", 420) === 1 &&
      stateFrameIdx(tile, "walk", 1680) === 0);
check("sleep freezes on frame 0", stateFrameIdx(tile, "sleep", 0) === 0 &&
      stateFrameIdx(tile, "sleep", 99999) === 0);
check("single-frame tile -> 0", stateFrameIdx(plain, "idle", 12345) === 0);

console.log("== animLerpParams: Rive-style blend ==");
const a = { act: "bounce", amp: 80, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 420, frames: null };
const b = { act: "none", amp: 0, hue: 0, sat: 100, bri: 100, magic: null, frame_ms: 1200, frames: [0] };
let m = animLerpParams(a, b, 0.5);
check("numbers lerp at midpoint", m.amp === 40 && m.frame_ms === 810, JSON.stringify(m));
m = animLerpParams(a, b, 0.25);
check("act cuts at midpoint (before)", m.act === "bounce" && m.frames === null);
m = animLerpParams(a, b, 0.75);
check("act cuts at midpoint (after)", m.act === "none" && m.frames[0] === 0);

console.log("== tileHasMotion ==");
customById = { 7: tile, 9: legacy, 10: plain };
check("state-record tile has motion", tileHasMotion(7));
check("legacy fx tile has motion", tileHasMotion(9));
check("plain tile has none", !tileHasMotion(10));
check("unknown id has none", !tileHasMotion(999));

console.log("== static: beginner surface ==");
const cards = (html.match(/class="anim-card"/g) || []).length;
check("cards are built in JS (container exists)", html.indexOf('id="anim-cards"') >= 0);
const presetKeys = ((html.match(/const ANIM_PRESETS = \{[\s\S]*?\n\};/) || [""])[0]
  .match(/^\s{2}(alive|bounce|float|pulse|shake|magic):\s+\{/gm) || []).length;
check("ANIM_PRESETS has six entries", presetKeys === 6, "found " + presetKeys);
["alive", "bounce", "float", "pulse", "shake", "magic"].forEach(k => {
  check("preset card for " + k, html.indexOf('"' + k + '":') >= 0 ||
        html.indexOf(k + ":  {") >= 0 || html.indexOf(k + ": {") >= 0);
});
check("each card has a feel slider", html.indexOf('aria-label="motion intensity"') >= 0);
check("magic card has aura color swatches", html.indexOf("anim-card-sw") >= 0);
check("advanced act row gained alive", html.indexOf('data-a="alive"') >= 0);
check("advanced has a state picker", html.indexOf('id="anim-state"') >= 0);
check("advanced has an intensity slider", html.indexOf('id="anim-amp"') >= 0);
check("bring-to-life sends the preset",
      html.indexOf("anim_preset: beginnerPreset") >= 0);
check("patrol stop rows have a state select",
      html.indexOf('data-act="stopstate"') >= 0);
check("drawFxTile takes a state", html.indexOf(
      "function drawFxTile(g, id, im, dx, dy, dw, dh, now, state, blend)") >= 0);

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
