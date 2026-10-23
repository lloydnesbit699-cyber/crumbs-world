#!/usr/bin/env node
// stage1_camera_client_test.js — v6.4 Stage 1 camera pass:
// hero glide (jitter cure), FIRST = over-the-shoulder (§15), close-range
// origin snap, quality-scaler pin, and the item-20 lens/snapshot fix.
// Run: node stage1_camera_client_test.js
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
const body = consts + "\n" + ["playCameraStep", "playHeroGlideStep", "playFirstFocus",
  "playSnapOrigin", "playQualityStep"].map(extract).join("\n") +
  "\nreturn {playCameraStep,playHeroGlideStep,playFirstFocus,playSnapOrigin,playQualityStep,PLAY_FIRST_AHEAD,PLAY_GLIDE_SNAP_TILES};";
const P = new Function(body)();

console.log("== hero glide ==");
let g = P.playHeroGlideStep(null, { x: 10, y: 7 }, 16);
check("first sight lands on the tile, settled", g.x === 10 && g.y === 7 && g.settled);
g = P.playHeroGlideStep({ x: 10, y: 7 }, { x: 11, y: 7 }, 16);
check("one step in, the drawn hero is between tiles", g.x > 10 && g.x < 11 && !g.settled, "x " + g.x);
check("one step in, the drawn hero is most of the way there next step", (() => {
  const g2 = P.playHeroGlideStep(g, { x: 11, y: 7 }, 140);
  return g2.x > g.x && g2.x < 11;
})());
let d = { x: 10, y: 7 };
for (let i = 0; i < 60; i++) d = P.playHeroGlideStep(d, { x: 11, y: 7 }, 16);
check("the glide converges and settles", Math.abs(d.x - 11) < 0.01 && d.settled, "x " + d.x);
g = P.playHeroGlideStep({ x: 10, y: 7 }, { x: 11, y: 7 }, 0);
check("zero dt does not move the drawn hero", g.x === 10 && !g.settled);
g = P.playHeroGlideStep({ x: 0, y: 0 }, { x: P.PLAY_GLIDE_SNAP_TILES + 5, y: 0 }, 16);
check("a warp-sized jump snaps (no swoop)", g.x === P.PLAY_GLIDE_SNAP_TILES + 5 && g.settled);
g = P.playHeroGlideStep({ x: 0, y: 0 }, { x: 1, y: 1 }, 16);
check("diagonal steps glide on both axes", g.x > 0 && g.x < 1 && g.y > 0 && g.y < 1);

console.log("== FIRST focus (over-the-shoulder) ==");
const draw = { x: 50, y: 50 }, VW = 20, VH = 12;
let f = P.playFirstFocus(draw, { dx: 0, dy: 1 }, VW, VH);
check("facing down: focus leads below the hero", f.x === 50 && Math.abs(f.y - (50 + VH * P.PLAY_FIRST_AHEAD)) < 1e-9);
check("hero anchors at 20% from the edge behind him", Math.abs((0.5 - (f.y - draw.y) / VH) - 0.2) < 1e-9);
f = P.playFirstFocus(draw, { dx: 0, dy: -1 }, VW, VH);
check("facing up: hero anchors at the bottom edge (80% down)",
  f.y < 50 && Math.abs((0.5 - (f.y - draw.y) / VH) - 0.8) < 1e-9);
f = P.playFirstFocus(draw, { dx: -1, dy: 0 }, VW, VH);
check("facing left: focus leads left on the view width", Math.abs(f.x - (50 - VW * P.PLAY_FIRST_AHEAD)) < 1e-9 && f.y === 50);
f = P.playFirstFocus(draw, { dx: 1, dy: 1 }, VW, VH);
check("diagonal facing is normalized (no double lead)",
  Math.abs(Math.hypot((f.x - 50) / VW, (f.y - 50) / VH) - P.PLAY_FIRST_AHEAD) < 1e-9 &&
  Math.abs((f.x - 50) / VW - (f.y - 50) / VH) < 1e-9);
f = P.playFirstFocus(draw, null, VW, VH);
check("no facing falls back to facing down", f.x === 50 && f.y > 50);

console.log("== FIRST camera chase (swings, never snaps) ==");
const focus = P.playFirstFocus(draw, { dx: 1, dy: 0 }, VW, VH);
let cam = { x: 50, y: 50 };
const one = P.playCameraStep(cam, draw, { dx: 1, dy: 0 }, 1, 16, { focus, dzW: 0, dzH: 0 });
check("one frame moves only partway to the focus", one.x > 50 && one.x < focus.x, "x " + one.x);
for (let i = 0; i < 300; i++) cam = P.playCameraStep(cam, draw, { dx: 1, dy: 0 }, 1, 16, { focus, dzW: 0, dzH: 0 });
check("the camera settles ON the focus", Math.abs(cam.x - focus.x) < 0.05 && Math.abs(cam.y - focus.y) < 0.05, JSON.stringify(cam));
const focus2 = P.playFirstFocus(draw, { dx: -1, dy: 0 }, VW, VH);
const turned = P.playCameraStep(cam, draw, { dx: -1, dy: 0 }, 1, 16, { focus: focus2, dzW: 0, dzH: 0 });
check("a 180° turn starts swinging, does not snap", turned.x < cam.x && turned.x > focus2.x, "x " + turned.x);

console.log("== close-range origin snap ==");
for (const [o, px, s] of [[3.217, 34.8, 1], [3.217, 34.8, 0.85], [-1.93, 40.9, 1.2], [0.001, 100, 2]]) {
  const r = P.playSnapOrigin(o, px, s);
  check("origin " + o + " @ tilePx " + px + " x" + s + " lands on a whole backing pixel",
    Math.abs(r * px * s - Math.round(r * px * s)) < 1e-6, "-> " + r * px * s);
}
check("an already-whole origin is untouched", P.playSnapOrigin(2, 40, 1) === 2);
check("degenerate scale is a no-op", P.playSnapOrigin(1.5, 0, 1) === 1.5);

console.log("== quality scaler pin ==");
let q = { scale: 0, ema: 8, adjusted: 0 };
let s = P.playQualityStep(q, 40, 0, 2, true);
check("pinned: still initializes at the cap", s === 2);
for (let i = 1; i < 40; i++) s = P.playQualityStep(q, 40, i * 1100, 2, true);
check("pinned: slow frames never back the scale off", s === 2, "s " + s);
q = { scale: 0, ema: 8, adjusted: 0 };
P.playQualityStep(q, 8, 0, 2);
for (let i = 1; i < 40; i++) s = P.playQualityStep(q, 40, i * 1100, 2);
check("unpinned control: the same frames DO back off", s < 2, "s " + s);
q = { scale: 3, ema: 8, adjusted: 0 };
check("pinned: an over-cap scale still clamps to the cap", P.playQualityStep(q, 40, 0, 2, true) === 2);

console.log("== wiring ==");
check("region camera follows the drawn hero", /const hd = heroDrawPos\(now\)/.test(html) &&
  /playCameraStep\(cam, hd,/.test(html));
check("FIRST passes a focus chase (no deadzone)", /playFirstFocus\(hd, playFacing, viewW, viewH\), dzW: 0, dzH: 0/.test(html));
check("hero sprite + light pool draw at the gliding position",
  (html.match(/heroDrawPos\(performance\.now\(\)\)/g) || []).length >= 2);
check("glide keeps frames flowing while unsettled", /!st\.settled \|\| !playHeroDrawSettled\) playKick\(\)/.test(html));
check("origin snaps only at close range", /!lens && playN <= PLAY_CLOSE_MAX_N\) \{\s*\/\/ v6\.4/.test(html) &&
  /playSnapOrigin\(ox, tilePx, rgScale\)/.test(html));
check("scaler is pinned only at close range", /playQualityStep\(playQ, playLastMs, now, cap, !lens && playN <= PLAY_CLOSE_MAX_N\)/.test(html));
const tp = extract("togglePlay");
check("item 20: togglePlay leaves the lens before the camera snapshot",
  tp.indexOf("lensLeave()") >= 0 && tp.indexOf("lensLeave()") < tp.indexOf("snapCameraSel()"),
  "lensLeave@" + tp.indexOf("lensLeave()") + " snap@" + tp.indexOf("snapCameraSel()"));
check("item 20: render() keeps its lens-leave backstop", /if \(lensFull && playMode\) lensLeave\(\);/.test(html));
check("ladder labels: Ground (top-down) in both panels, no Close stop",
  /data-mode="ground"[^>]*>🧍 Ground/.test(html) && /data-fl="ground">🧍 Ground/.test(html) && !/🧍 Close/.test(html));
check("mode badge reads FIRST for the over-the-shoulder stop", /if \(playFirst\) return "FIRST";/.test(html));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
