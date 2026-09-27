#!/usr/bin/env node
// patrol_pause_test.js — v5.40 patrol stop pauses.
// Extracts legStopIdx + npcTick from editor.html and exercises the pause
// state machine against stubbed globals: timer countdown, stand vs sleep,
// resume after expiry, 0 = walk on, arrival mapping for anchored routes.
// Run: node patrol_pause_test.js
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

// ---- stubbed browser globals -------------------------------------------
let fakeNow = 1000000;
global.performance = { now: () => fakeNow };
let renders = 0;
global.queueRender = () => { renders++; };
let npcs = [];   // npcTick reads the global `npcs`

// v5.43: npcTick now calls setNpcState + npcAnimStateFor — extract them too
eval(extract("npcAnimStateFor"));
eval(extract("setNpcState"));
const _m = html.match(/const ANIM_STATES = (\[[^\]]*\])/);
if (!_m) throw new Error("ANIM_STATES const not found");
eval("global.ANIM_STATES = " + _m[1]);
eval(extract("legStopIdx"));
eval(extract("npcTick"));
eval(extract("pauseListFor"));

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log("  ok: " + name); }
  else { fail++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

function makeWalker(loop, stopAt, pauses) {
  return {
    tile_id: 1, loop, seg: 0, stopAt, pauses,
    x: loop[0][0], y: loop[0][1], flip: false, away: false,
    pauseUntil: 0, pauseMode: null, pauseStop: -1,
  };
}

console.log("== legStopIdx ==");
check("anchored leg0 (anchor->p0) ends at stop 0", legStopIdx(4, 0, true) === 0);
check("anchored leg1 ends at stop 1", legStopIdx(4, 1, true) === 1);
check("anchored leg2 ends at stop 2", legStopIdx(4, 2, true) === 2);
check("anchored last leg (p2->anchor) is home, no stop", legStopIdx(4, 3, true) === null);
check("unanchored leg0 ends at stop 1", legStopIdx(3, 0, false) === 1);
check("unanchored leg1 ends at stop 2", legStopIdx(3, 1, false) === 2);
check("unanchored last leg wraps to stop 0", legStopIdx(3, 2, false) === 0);

console.log("== arrival pauses the walker (stand) ==");
npcs = [makeWalker([[0, 0], [1, 0]], [undefined, 0],
                   [{ secs: 5, mode: "stand" }])];
npcTick(1);   // SPEED 2.4 tiles/s — plenty to cross one tile
const w = npcs[0];
check("walker reached the stop", w.x === 1 && w.y === 0, w.x + "," + w.y);
check("pause timer set ~5s out", w.pauseUntil === fakeNow + 5000, String(w.pauseUntil));
check("pause mode is stand", w.pauseMode === "stand");
check("pause stop recorded", w.pauseStop === 0);

console.log("== timer holds him still ==");
const heldX = w.x, heldY = w.y, heldUntil = w.pauseUntil;
fakeNow += 2000;
npcTick(1);
check("position frozen mid-pause", w.x === heldX && w.y === heldY);
check("timer untouched by ticks", w.pauseUntil === heldUntil);

console.log("== expiry resumes the walk ==");
fakeNow = heldUntil + 1;
npcTick(0.5);   // 1.2 tiles of movement budget
check("pause cleared", w.pauseUntil === 0 && w.pauseMode === null);
check("walker moving again", w.x !== heldX || w.y !== heldY, w.x + "," + w.y);

console.log("== secs 0 = walk on, no pause ==");
npcs = [makeWalker([[0, 0], [1, 0]], [undefined, 0],
                   [{ secs: 0, mode: "stand" }])];
npcTick(1);
check("no pause timer", npcs[0].pauseUntil === 0);
check("kept walking past the stop", npcs[0].seg !== 0 || npcs[0].x !== 1, "seg=" + npcs[0].seg);

console.log("== sleep mode ==");
fakeNow = 2000000;
npcs = [makeWalker([[0, 0], [1, 0]], [undefined, 1],
                   [{ secs: 0, mode: "stand" }, { secs: 60, mode: "sleep" }])];
npcTick(1);
const s = npcs[0];
check("sleep timer set ~60s out", s.pauseUntil === fakeNow + 60000);
check("pause mode is sleep", s.pauseMode === "sleep");
check("sleeping walker renders (bob frames)", renders > 0);

console.log("== no double-pause on duplicate path cells ==");
// pathfinder legs share their endpoint cell: [..., C, C, ...] — the pause
// must fire once, not re-fire when stepping over the duplicate.
fakeNow = 3000000;
npcs = [makeWalker([[0, 0], [2, 0], [2, 0]], [undefined, 0, undefined],
                   [{ secs: 9, mode: "stand" }])];
npcTick(1);
const d = npcs[0];
const firstUntil = d.pauseUntil;
check("paused once at the stop", firstUntil === fakeNow + 9000, String(firstUntil));
fakeNow = firstUntil + 1;   // let it expire — he steps past the duplicate cell
npcTick(0.01);   // tiny budget: clears the pause, skips the duplicate, no arrival
check("no re-pause on the duplicate cell", d.pauseUntil === 0, String(d.pauseUntil));
check("walker left the stop", d.seg === 0 && d.x < 2, "seg=" + d.seg + " x=" + d.x);

console.log("== v5.43: stops trigger animation states ==");
check("npcAnimStateFor: explicit state wins",
      npcAnimStateFor({ secs: 5, mode: "stand", state: "talk" }) === "talk");
check("npcAnimStateFor: sleep mode -> sleep",
      npcAnimStateFor({ secs: 5, mode: "sleep" }) === "sleep");
check("npcAnimStateFor: stand mode -> idle",
      npcAnimStateFor({ secs: 5, mode: "stand" }) === "idle");
check("npcAnimStateFor: bogus state falls back to mode",
      npcAnimStateFor({ secs: 5, mode: "sleep", state: "dance" }) === "sleep");
fakeNow = 4000000;
npcs = [makeWalker([[0, 0], [1, 0]], [undefined, 0],
                   [{ secs: 30, mode: "sleep", state: "sleep" }])];
npcTick(1);
const st = npcs[0];
check("sleep stop enters the Sleep state", st.animState === "sleep", st.animState);
check("state blend recorded", !!st.animBlend && st.animBlend.from === "walk");
fakeNow = st.pauseUntil + 1;
npcTick(0.5);
check("expiry returns to Walk state", npcs[0].animState === "walk", npcs[0].animState);
fakeNow = 5000000;
npcs = [makeWalker([[0, 0], [1, 0]], [undefined, 0],
                   [{ secs: 10, mode: "stand" }])];   // stand, no explicit state
npcTick(1);
check("standing pause maps to Idle", npcs[0].animState === "idle", npcs[0].animState);

console.log("== v5.43: pauseListFor preserves states ==");
const pl = pauseListFor({ points: [[0, 0], [1, 0]],
                          pauses: [{ secs: 5, mode: "sleep", state: "sleep" },
                                   { secs: 0, mode: "stand", state: "bogus" }] });
check("valid state kept", pl[0].state === "sleep", JSON.stringify(pl[0]));
check("bogus state dropped", !("state" in pl[1]), JSON.stringify(pl[1]));
check("secs/mode intact", pl[0].secs === 5 && pl[0].mode === "sleep");

console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);