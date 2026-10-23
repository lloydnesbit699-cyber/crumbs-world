#!/usr/bin/env node
// keyboard_move_client_test.js — keyboard movement (Lloyd's split).
// Build arrows pan the MAP; Play arrows + WASD move the CHARACTER.
// Also guards the restored Move toggle: #btn-pan must NOT be in the
// v5.67 stage-3 hide list, and its zoom-cluster button + handler must exist.
// Run: node tests/keyboard_move_client_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}

// ---- static wiring: Move toggle restored --------------------------------
console.log("== Move toggle ==");
const hideBlock = html.match(/#paint-strip,#strip-search-row[^{]*\{display:none!important;\}/);
check("stage-3 hide list still exists", !!hideBlock);
check("btn-pan NOT hidden by stage-3 list", !!hideBlock && !hideBlock[0].includes("#btn-pan"),
  hideBlock ? hideBlock[0].slice(0, 120) : "no block");
check("Move button present (camera pill since Stage 4)",
  html.includes('<button id="btn-pan"') && html.includes(">Move</button>"));
check("btn-pan toggles the D-pad mode, and drag-pan stays dead (§17 + Lloyd's Move ruling 2026-10-23)",
  html.includes('$("btn-pan").onclick = flipDpadMode') && !html.includes("panMode = !panMode") && !html.includes("let panMode") && !html.includes("let panStart"));

// ---- behaviour: extract the v5.67.0 keyboard block -----------------------
console.log("== keyboard movement ==");
const start = html.indexOf("function kbTypingTarget");
const endMarker = 'document.addEventListener("keydown", onKbMove);';
const end = html.indexOf(endMarker, start);
check("keyboard block found", start >= 0 && end > start);
const src = html.slice(start, end + endMarker.length);

// stubbed globals the block rides on
let W = 20, tilePx = 32;
let RULES = { walk_ms: 140 };
let layoutCalls = 0, clampCalls = 0;
function clampPan() { clampCalls++; state.panX = Math.max(-500, Math.min(500, state.panX)); state.panY = Math.max(-500, Math.min(500, state.panY)); }
function layout() { layoutCalls++; }
let steps = [];
function doStep(dx, dy, repeat) { steps.push([dx, dy, repeat]); }
const state = { panX: 0, panY: 0, playMode: false, buildBreak: false };
let selectedInstance = null, objects = [];
function moveTap() {}
function zoomCenter() {}
function playInteract() {}
let testNow = 1000;
function playCancelFlight() {}
const playFacing = null;
const testPerformance = { now: () => testNow };
let kbHandler = null;
const documentStub = { addEventListener: (ev, fn) => { if (ev === "keydown") kbHandler = fn; } };

// Rebind page state through a shared object so presses can be observed.
const src2 = src
  .replace(/\bpanX\b/g, "state.panX")
  .replace(/\bpanY\b/g, "state.panY")
  .replace(/\bplayMode\b/g, "state.playMode")
  .replace(/\bbuildBreak\b/g, "state.buildBreak");
const api = new Function("W", "tilePx", "state", "RULES", "clampPan", "layout", "doStep", "document", "performance",
  "selectedInstance", "objects", "moveTap", "zoomCenter", "playInteract", "playCancelFlight", "playFacing", "playGoMode",
  "lensRegionOn", "lensToggle", "lensPanBy", "flightToggle", "shrineToggle", "applyUiClean", "playCycleQuality", "toast",
  src2 + "\nreturn { onKbMove, kbTypingTarget };")(W, tilePx, state, RULES, clampPan, layout, doStep, documentStub, testPerformance,
  selectedInstance, objects, moveTap, zoomCenter, playInteract, playCancelFlight, playFacing, () => {},
  () => false, () => {}, () => {}, () => {}, () => {}, () => {}, () => {}, () => {});
check("keydown listener registered", typeof kbHandler === "function" || typeof api.onKbMove === "function");
const onKbMove = api.onKbMove;

function key(k, target, mods) {
  let prevented = false;
  onKbMove(Object.assign({ key: k, target: target || { tagName: "BODY" },
    preventDefault: () => { prevented = true; } }, mods || {}));
  return prevented;
}

// In Build mode arrows pan the camera one tile, in the arrow's direction
state.panX = 0; state.panY = 0;
check("ArrowRight handled + prevented", key("ArrowRight") === true);
check("ArrowRight moves view right (panX -= tile)", state.panX === -32 && state.panY === 0,
  JSON.stringify(state));
key("ArrowLeft"); check("ArrowLeft moves view back", state.panX === 0);
key("ArrowDown"); check("ArrowDown moves view down", state.panY === -32);
key("ArrowUp"); check("ArrowUp moves view back", state.panY === 0);

// WASD does nothing outside Play mode when no object is selected
steps = [];
check("W ignored in edit mode", key("w") === false && steps.length === 0);

// Both arrow keys and WASD move the character in Play mode
state.playMode = true;
key("ArrowRight"); check("Right arrow steps hero right", steps.length === 1 && steps[0][0] === 1 && steps[0][1] === 0, JSON.stringify(steps));
steps = []; state.playMode = false; key("w"); state.playMode = true; testNow += 200;
key("w"); check("W steps hero up", steps.length === 1 && steps[0][0] === 0 && steps[0][1] === -1, JSON.stringify(steps));
// cooldown: an immediate second press is swallowed (gamepad-style throttle)
// (walk_ms 140 -> cool 150ms; real time has not advanced)
key("s"); check("cooldown swallows instant repeat", steps.length === 1, JSON.stringify(steps));

// typing is never stolen
state.playMode = true;
const before = steps.length, panBefore = [state.panX, state.panY];
check("arrows ignored in an input", key("ArrowRight", { tagName: "INPUT" }) === false && state.panX === panBefore[0]);
check("WASD ignored in a textarea", key("a", { tagName: "TEXTAREA" }) === false && steps.length === before);
check("WASD ignored in contentEditable", key("d", { tagName: "DIV", isContentEditable: true }) === false);

// browser combos stay the browser's
check("Ctrl+Arrow not stolen", key("ArrowRight", { tagName: "BODY" }, { ctrlKey: true }) === false && state.panX === panBefore[0]);

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
