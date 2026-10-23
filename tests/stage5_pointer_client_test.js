#!/usr/bin/env node
// stage5_pointer_client_test.js — Stage 5 (§17, Ball Room items 15-18):
// keys are the camera's sole authority; the D-pad is universal; objects
// move by grab-to-palette, never by drag.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
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
let PASS = 0, FAIL = 0;
function check(name, cond) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name); }
}

console.log("== no pointer path moves any camera (item 16) ==");
const camPanelSlice = html.slice(html.indexOf('id="pill-panel-camera"'), html.indexOf('id="pill-panel-world"'));
check("the Move BUTTON is back in the camera panel — a D-pad mode toggle, not a drag tool (Lloyd's ruling 2026-10-23)",
  camPanelSlice.includes('id="btn-pan"') && html.includes('$("btn-pan").onclick = flipDpadMode'));
check("no panMode state remains", !/let panMode|panMode =|panMode;/.test(html));
check("no panStart drag state remains", !/panStart\s*=|panStart\./.test(html));
check("minimap tap-to-jump is gone", !html.includes("minimapJump"));
check("object drag machinery is gone",
  !html.includes("updateObjectDrag") && !html.includes("finishObjectDrag") &&
  !html.includes("objectDragAutoPan") && !/objectDrag\s*[=.]/.test(html));
check("the lens never reads a pointer position",
  !/worldLens\.pointer/.test(html) &&
  !/const worldLens = \{[^}]*pointer/.test(html));
const gestureBody = extract("onGestureMove");
check("two-finger gesture never pans the lens", !gestureBody.includes("lensPanBy("));
check("two-finger gesture never pans the Build map", !/pan[XY]\s*[+-]=/.test(gestureBody));
check("Build pinch zooms at the view center", gestureBody.includes("zoomAt(r.left + r.width / 2, r.top + r.height / 2, newPx)"));
check("lens pinch zooms unanchored (lensSetPx defaults to center)",
  /lensSetPx\(gesture\.startPx \* dist \/ gesture\.startDist\)/.test(gestureBody));
const focusBody = extract("updateWorldLensFocus");
check("lens focus has no pointer fallback", !focusBody.includes("worldLens.pointer"));
const wheelBody = extract("onCanvasWheel");
check("lens wheel zoom passes no cursor anchor", !wheelBody.includes("e.clientX - lr.left") &&
  /lensSetPx\(Math\.abs\(np - lensPx\) < 1 \? lensPx \+ Math\.sign\(np - lensPx\) : np\)/.test(wheelBody));
check("wheel zoom itself survives (item 16 passthrough)", wheelBody.includes("lensSetPx(") && wheelBody.includes("zoomAt("));

console.log("== pinch behavior: zoom only, pan untouched ==");
{
  const stage = { getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }) };
  const env = new Function("stage", `
    const calls = { zoomAt: [], lensSetPx: [], playSetN: [], lensPanBy: 0 };
    const ptrs = new Map();
    let gesture = null, tilePx = 20, lensPx = 20, playN = 6, panX = 5, panY = 7, manualZoom = false;
    let inLens = false, inPlay = false;
    const lensRegionOn = () => inLens, playRegionOn = () => inPlay;
    const maxTilePx = () => 160;
    const zoomAt = (x, y, px) => calls.zoomAt.push([x, y, px]);
    const lensSetPx = (...a) => calls.lensSetPx.push(a);
    const lensPanBy = () => { calls.lensPanBy++; };
    const playSetN = n => calls.playSetN.push(n);
    const render = () => {}, playModeBadge = () => {}, clampPan = () => {}, layout = () => {};
    ${extract("onGestureMove")}
    return { onGestureMove, calls, ptrs,
             setMode: (l, p) => { inLens = l; inPlay = p; gesture = null; },
             pan: () => [panX, panY] };`)(stage);
  const two = (x1, x2) => { env.ptrs.clear(); env.ptrs.set(1, { x: x1, y: 300 }); env.ptrs.set(2, { x: x2, y: 300 }); };
  // Build pinch: fingers spread 100 -> 200
  two(250, 350); env.onGestureMove(); env.ptrs.set(2, { x: 450, y: 300 }); env.onGestureMove();
  check("Build pinch zooms once, at center (400,300), 20 -> 40px", env.calls.zoomAt.length === 1 &&
    env.calls.zoomAt[0][0] === 400 && env.calls.zoomAt[0][1] === 300 && env.calls.zoomAt[0][2] === 40);
  check("Build pinch leaves panX/panY alone", env.pan()[0] === 5 && env.pan()[1] === 7);
  // Lens pinch
  env.setMode(true, false);
  two(250, 350); env.onGestureMove(); env.ptrs.set(2, { x: 450, y: 300 }); env.onGestureMove();
  check("lens pinch zooms with NO anchor arguments", env.calls.lensSetPx.length === 1 && env.calls.lensSetPx[0].length === 1);
  check("lens pinch never pans", env.calls.lensPanBy === 0);
  // Play pinch (hero-anchored N change — not a pointer camera)
  env.setMode(false, true);
  two(250, 350); env.onGestureMove(); env.ptrs.set(2, { x: 300, y: 300 }); env.onGestureMove();
  check("Play pinch still changes N (6 -> 12)", env.calls.playSetN.length === 1 && env.calls.playSetN[0] === 12);
}

console.log("== the D-pad is universal (item 18) ==");
check("pad visibility no longer requires Play", !extract("updateDpad").includes("playMode &&"));
check("pad press no longer refuses Build", !html.includes("if (!playMode || buildBreak) return;"));
check("pad dispatches Play -> hero step, Build -> pan",
  html.includes("if (playMode) { doStep(dx, dy, true); return; }") && html.includes("dpadPanStep(dx, dy);"));
check("pad dispatches Build + Nudge mode + hands free -> the WASD path",
  html.includes('if (!moveArmed && dpadMode === "nudge") { dpadNudgeStep(dx, dy); return; }'));
check("the nudge chain calls the very function WASD calls (no parallel save path)",
  extract("dpadNudgeStep").includes("kbMoveSelectedObject(dx, dy)") &&
  extract("dpadNudgeTick").includes("kbMoveSelectedObject(dx, dy)"));
check("Move mode persists per device, defaulting to Pan",
  html.includes('localStorage.getItem("crumbs_dpad_mode")') &&
  html.includes('localStorage.setItem("crumbs_dpad_mode", dpadMode)') &&
  html.includes('let dpadMode = "pan";'));
check("pad takes pointerdown (a plain mouse click fires it)", html.includes('b.addEventListener("pointerdown"'));
{
  const env = new Function(`
    let playMode = false, buildBreak = false, shown = null;
    let dpadMode = "pan";
    const RULES = { touch: true };
    const dpad = { classList: { toggle: (c, on) => { shown = on; } } };
    const panBtn = { textContent: "", title: "", disabled: false, _on: null,
      classList: { toggle: (c, on) => { panBtn._on = on; } } };
    const $ = id => id === "btn-pan" ? panBtn : null;
    const placeDpad = () => {};
    ${extract("syncDpadModeBtn")}
    ${extract("updateDpad")}
    return { updateDpad, set: (pm, bb, t) => { playMode = pm; buildBreak = bb; RULES.touch = t; },
             shown: () => shown, btn: () => panBtn,
             setMode: m => { dpadMode = m; } };`)();
  env.set(false, false, true); env.updateDpad();
  check("pad shows in Build (desktop included)", env.shown() === true);
  env.set(true, false, true); env.updateDpad();
  check("pad shows in Play", env.shown() === true);
  env.set(false, true, true); env.updateDpad();
  check("pad still rests during a build-break", env.shown() === false);
  env.set(true, false, false); env.updateDpad();
  check("pad still obeys the Controls rule (owner's switch)", env.shown() === false);
  env.set(false, false, true); env.setMode("pan"); env.updateDpad();
  check("Move toggle is live in Build, reading Pan",
    env.btn().disabled === false && env.btn().textContent === "Move: Pan" && env.btn()._on === false);
  env.set(true, false, true); env.updateDpad();
  check("Move toggle disables in a live Play run (the pad walks the hero)", env.btn().disabled === true);
  env.set(true, true, true); env.updateDpad();
  check("Move toggle is live again during a build-break (Build semantics)", env.btn().disabled === false);
  env.set(false, false, true); env.setMode("nudge"); env.updateDpad();
  check("Move toggle names Nudge, lights up, and says what tapping does",
    env.btn().textContent === "Move: Nudge" && env.btn()._on === true && env.btn().title.includes("switch back to Pan"));
}
{
  const timers = [];
  const fakeSet = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  const env = new Function("setTimeout", "clearTimeout", `
    const pans = [];
    let stepTimer = 0, runMode = false;
    let dpadHeld = null;
    const panMapByTiles = (dx, dy) => pans.push([dx, dy]);
    ${extract("dpadPanStep")}
    ${extract("dpadPanTick")}
    return { dpadPanStep, pans, hold: b => { dpadHeld = b; }, run: r => { runMode = r; } };`)(
    fakeSet, () => {});
  env.dpadPanStep(1, 0);
  check("one pad press pans one tile immediately", env.pans.length === 1 && env.pans[0][0] === 1 && env.pans[0][1] === 0);
  check("hold chain waits 280ms like a hero step", timers.length === 1 && timers[0].ms === 280);
  env.hold({});
  timers[0].fn();
  check("held pad keeps panning", env.pans.length === 2);
  check("walk cadence is 110ms", timers[1].ms === 110);
  env.run(true);
  timers[1].fn();
  check("double-tap-hold runs at 60ms", timers[2].ms === 60);
  env.hold(null);
  timers[2].fn();
  check("release stops the chain", env.pans.length === 3);
}

console.log("== grab-to-palette (item 17) ==");
check("the held slot exists in the palette bar, hidden at rest",
  /<button id="bb-held" hidden/.test(html));
check("tapping the slot puts the object back", html.includes('$("bb-held").onclick = () => cancelGrab();'));
check("a canvas tap places a carried object in any Build context",
  html.includes("if (moveArmed && (!playMode || buildBreak)) { moveTap(cell); return; }"));
check("Esc puts a carried object back before it exits the lens",
  extract("onKbMove").includes("if (moveArmed) cancelGrab()"));
check("right-click cancels only while carrying",
  html.includes('addEventListener("contextmenu"') && html.includes("if (!moveArmed) return;"));
check("moveTap still makes exactly ONE /api/move call",
  (extract("moveTap").match(/api\("\/api\/move"/g) || []).length === 1);
{
  const els = {
    "bb-held": { hidden: true, title: "" },
    "bb-held-cv": { getContext: () => ({ imageSmoothingEnabled: true, clearRect() {}, drawImage() {} }) },
  };
  const counter = { n: 0 };
  const env = new Function("els", "counter", `
    const $ = id => els[id];
    let moveArmed = null, selectedInstance = null, inspectPos = null, grabTap = null, heldSlotKey = "";
    const objects = [[null, 7]];
    const objTid = v => v, tileFrameImage = () => ({}), instanceName = () => "oak tree", tileLabel = () => "tree";
    const renderSelCard = () => {}, render = () => {}, toast = () => {};
    const moveTap = () => { counter.n++; };
    ${extract("grabObjectAt")}
    ${extract("cancelGrab")}
    ${extract("syncHeldSlot")}
    ${extract("finishGrabTap")}
    return { cancelGrab, finishGrabTap,
             grab: g => { grabTap = g; }, state: () => ({ moveArmed }) };`)(els, counter);
  env.grab({ pointerId: 1, from: { x: 1, y: 0 }, startX: 100, startY: 100 });
  env.finishGrabTap({ pointerId: 1, clientX: 103, clientY: 102 }, false);
  check("a tap grabs: moveArmed carries the object", !!env.state().moveArmed &&
    env.state().moveArmed.x === 1 && env.state().moveArmed.tile === 7);
  check("the held slot shows the grabbed object", els["bb-held"].hidden === false &&
    els["bb-held"].title.includes("oak tree"));
  env.cancelGrab();
  check("cancel disarms and hides the slot", env.state().moveArmed === null && els["bb-held"].hidden === true);
  check("grab + cancel made NO server move (he never left)", counter.n === 0);
  env.grab({ pointerId: 2, from: { x: 1, y: 0 }, startX: 100, startY: 100 });
  env.finishGrabTap({ pointerId: 2, clientX: 220, clientY: 100 }, false);
  check("a drag is NOT a grab (nothing held, nothing moves)", env.state().moveArmed === null);
  env.grab({ pointerId: 3, from: { x: 1, y: 0 }, startX: 100, startY: 100 });
  env.finishGrabTap({ pointerId: 3, clientX: 100, clientY: 100 }, true);
  check("a cancelled press grabs nothing", env.state().moveArmed === null);
}

console.log("== the Move toggle flips and persists (Lloyd's ruling) ==");
{
  const store = {};
  const btn = { textContent: "", title: "", disabled: false, _on: null,
    classList: { toggle: (c, on) => { btn._on = on; } } };
  const toasts = [];
  const env = new Function("store", "btn", "toasts", `
    let playMode = false, buildBreak = false;
    const localStorage = { getItem: k => (k in store ? store[k] : null),
                           setItem: (k, v) => { store[k] = String(v); } };
    const $ = id => id === "btn-pan" ? btn : null;
    const toast = m => toasts.push(m);
    let dpadMode = "pan";
    try { if (localStorage.getItem("crumbs_dpad_mode") === "nudge") dpadMode = "nudge"; } catch (e) {}
    ${extract("syncDpadModeBtn")}
    ${extract("flipDpadMode")}
    syncDpadModeBtn();
    return { flipDpadMode, mode: () => dpadMode };`)(store, btn, toasts);
  check("boots in Pan when nothing is saved",
    env.mode() === "pan" && btn.textContent === "Move: Pan" && btn._on === false);
  env.flipDpadMode();
  check("one tap flips to Nudge: mode, face, save, toast",
    env.mode() === "nudge" && btn.textContent === "Move: Nudge" && btn._on === true &&
    store.crumbs_dpad_mode === "nudge" && toasts.some(t => t.includes("Nudge")));
  env.flipDpadMode();
  check("a second tap flips back to Pan",
    env.mode() === "pan" && btn.textContent === "Move: Pan" && store.crumbs_dpad_mode === "pan");
  const store2 = { crumbs_dpad_mode: "nudge" };
  const env2 = new Function("store2", `
    const localStorage = { getItem: k => (k in store2 ? store2[k] : null), setItem: () => {} };
    let dpadMode = "pan";
    try { if (localStorage.getItem("crumbs_dpad_mode") === "nudge") dpadMode = "nudge"; } catch (e) {}
    return { mode: () => dpadMode };`)(store2);
  check("a saved Nudge is where the next boot starts", env2.mode() === "nudge");
}

async function moveToggleProof() {
  console.log("== pad routing under the Move toggle (behavioral) ==");
  const timers = [];
  const fakeSet = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  const fakeClear = id => { if (id >= 1 && id <= timers.length) timers[id - 1].fn = () => {}; };
  const apiCalls = [], toasts = [], pans = [];
  const btnR = { dataset: { dx: "1", dy: "0" }, _h: {},
    addEventListener(ev, fn) { this._h[ev] = fn; } };
  const handlerStart = html.indexOf('dpad.querySelectorAll("button")');
  const handlerEnd = html.indexOf("async function doStep", handlerStart);
  check("pad press handler block found", handlerStart >= 0 && handlerEnd > handlerStart);
  const handlerSrc = html.slice(handlerStart, handlerEnd);
  const env = new Function("setTimeout", "clearTimeout", "apiCalls", "toasts", "pans", "btnR", "handlerSrc", `
    let playMode = false, buildBreak = false;
    let runMode = false, lastTap = { t: 0, btn: null }, runHintShown = true;
    let dpadHeld = null, stepTimer = 0, kbStepCool = 0;
    let dpadMode = "pan", moveArmed = null;
    let selectedInstance = null, inspectPos = null, hero = null;
    let W = 20, H = 20;
    const RULES = { walk_ms: 140 };
    const objects = [[7, null]];
    const stepsRef = { n: 0 };
    const dpad = { querySelectorAll: () => [btnR] };
    const panMapByTiles = (dx, dy) => pans.push([dx, dy]);
    const doStep = () => { stepsRef.n++; };
    const playCancelFlight = () => {};
    const api = async (p, body) => { apiCalls.push([p, body]); return { ok: true }; };
    const refresh = async () => {}, loadPatrols = async () => {};
    const renderSelCard = () => {}, renderInspect = () => {}, render = () => {};
    const toast = m => toasts.push(m);
    ${extract("kbMoveSelectedObject")}
    ${extract("moveTap")}
    ${extract("dpadPanStep")}
    ${extract("dpadPanTick")}
    ${extract("dpadNudgeStep")}
    ${extract("dpadNudgeTick")}
    ` + handlerSrc + `
    return { press: () => btnR._h.pointerdown({ preventDefault() {} }),
             release: () => btnR._h.pointerup(),
             setMode: m => { dpadMode = m; },
             setPlay: p => { playMode = p; },
             select: s => { selectedInstance = s; },
             sel: () => selectedInstance,
             carry: m => { moveArmed = m; },
             cool: () => { kbStepCool = 0; },
             steps: () => stepsRef.n };`)(fakeSet, fakeClear, apiCalls, toasts, pans, btnR, handlerSrc);
  const flush = () => new Promise(r => setTimeout(r, 0));
  env.press();
  check("Pan mode: a press pans one tile, no object move", pans.length === 1 && apiCalls.length === 0);
  env.release();
  env.setMode("nudge"); env.cool(); env.select({ x: 0, y: 0 });
  env.press();
  check("Nudge mode: one press-step = exactly one /api/move (0,0) -> (1,0)",
    apiCalls.length === 1 && apiCalls[0][0] === "/api/move" &&
    apiCalls[0][1].fx === 0 && apiCalls[0][1].fy === 0 &&
    apiCalls[0][1].tx === 1 && apiCalls[0][1].ty === 0);
  await flush();
  check("the selection follows the nudged object",
    !!env.sel() && env.sel().x === 1 && env.sel().y === 0);
  env.release();
  env.select(null); env.cool();
  const toastBefore = toasts.length;
  env.press();
  check("Nudge with no selection: no move, no crash, a hint toast",
    apiCalls.length === 1 && toasts.length > toastBefore &&
    /nothing selected/.test(toasts[toasts.length - 1]));
  env.release();
  env.carry({ x: 0, y: 0, tile: 7 });
  const pansBefore = pans.length;
  env.press();
  check("while carrying, the pad pans even in Nudge mode (navigate, then place)",
    pans.length === pansBefore + 1 && apiCalls.length === 1);
  env.release(); env.carry(null);
  env.setPlay(true);
  env.press();
  check("Play: a press steps the hero (doStep) — no pan, no nudge",
    env.steps() === 1 && apiCalls.length === 1 && pans.length === pansBefore + 1);
  env.release();
}

async function placeProof() {
  console.log("== grab -> place lands the object exactly once ==");
  const apiCalls = [];
  const env = new Function("apiCalls", `
    let moveArmed = { x: 0, y: 0, tile: 7 }, selectedInstance = null, inspectPos = null, refreshed = 0;
    const objects = [[7, null, 9]];
    const api = async (p, body) => { apiCalls.push([p, body]); return { ok: true }; };
    const refresh = async () => { refreshed++; };
    const loadPatrols = async () => {};
    const render = () => {}, toast = () => {};
    const renderSelCard = () => {}, renderInspect = () => {};
    ${extract("moveTap")}
    return { moveTap, armed: () => moveArmed, refreshed: () => refreshed,
             rearm: () => { moveArmed = { x: 0, y: 0, tile: 7 }; } };`)(apiCalls);
  await env.moveTap({ x: 1, y: 0 });
  check("place = one /api/move with from -> to", apiCalls.length === 1 &&
    apiCalls[0][1].fx === 0 && apiCalls[0][1].fy === 0 &&
    apiCalls[0][1].tx === 1 && apiCalls[0][1].ty === 0);
  check("slot cleared and the world reloaded after the move",
    env.armed() === null && env.refreshed() >= 1);
  env.rearm();
  await env.moveTap({ x: 0, y: 0 });
  check("tapping his own cell sets him back down — no server call",
    apiCalls.length === 1 && env.armed() === null);
  env.rearm();
  await env.moveTap({ x: 2, y: 0 });
  check("an occupied cell refuses — no server call",
    apiCalls.length === 1 && env.armed() === null);
}

placeProof().then(moveToggleProof).then(() => {
  console.log(`\nstage5_pointer_client_test: ${PASS} passed, ${FAIL} failed`);
  if (FAIL) process.exitCode = 1;
});
