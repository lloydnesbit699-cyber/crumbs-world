#!/usr/bin/env node
// melody_fabtap_test.js — Ball Room item 23: "Mel's ball is dead to clicks."
// Behavioral tests over the REAL extracted code (placeMelDock / clampMelDock
// / openMelDock and the FAB pointer wiring sliced out of melodyInitInner).
// Two mechanisms made the ball feel dead, both reproduced here:
//   M2 — the dock's parked spot (localStorage "crumbs_meldock") is applied
//        raw at load and clampMelDock no-ops while the dock is hidden, so a
//        spot parked on a wider screen (or before a rotation) opened the
//        dock off-view; every tap just toggled an invisible dock.
//        Fix: openMelDock clamps now that the dock is visible.
//   M1 — melFabMoved is set when a drag ends and is only cleared by the
//        click that follows the drag. Browsers may suppress that click
//        after real movement, leaking the flag into the NEXT tap, which
//        then gets swallowed too. Fix: pointerdown starts a new gesture
//        with a clean flag; the drag's own click is still eaten.
// Run: node melody_fabtap_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}
function fnBody(name) {
  const start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces in " + name);
}

console.log("== M2: a parked-off-view dock spot can never strand the dock ==");
function dockWorld(store) {
  const dock = { hidden: true, style: {}, offsetWidth: 340, offsetHeight: 420 };
  const els = { "melody-dock": dock, "melody-input": { focus() {} } };
  const body =
    "const window = { innerWidth: 390, innerHeight: 844 };\n" +
    "const localStorage = { getItem: k => (k in STORE ? STORE[k] : null), setItem() {} };\n" +
    "const MELODY = { open: false };\n" +
    "function melTtsUnlock() {}\n" +
    "function matchMedia() { return { matches: true }; }\n" +
    "const $ = id => ELS[id];\n" +
    fnBody("placeMelDock") + "\n" + fnBody("clampMelDock") + "\n" + fnBody("openMelDock") +
    "\nreturn { placeMelDock, openMelDock, dock: ELS['melody-dock'] };";
  return new Function("STORE", "ELS", body)(store, els);
}
{
  // parked at x=700 in an 844-wide landscape, reopened on a 390-wide portrait
  const M = dockWorld({ crumbs_meldock: JSON.stringify({ x: 700, y: 500 }) });
  M.placeMelDock();
  M.openMelDock();
  const left = parseFloat(M.dock.style.left), top = parseFloat(M.dock.style.top);
  check("landscape-parked spot is pulled back on-screen horizontally",
    isFinite(left) && left >= 0 && left + 340 <= 391, "left=" + M.dock.style.left);
  check("landscape-parked spot is pulled back on-screen vertically",
    isFinite(top) && top >= 0 && top < 844, "top=" + M.dock.style.top);
}
{
  const M = dockWorld({ crumbs_meldock: JSON.stringify({ x: 20, y: 100 }) });
  M.placeMelDock();
  M.openMelDock();
  check("a sane parked spot (20,100) is kept exactly",
    parseFloat(M.dock.style.left) === 20 && parseFloat(M.dock.style.top) === 100,
    "left=" + M.dock.style.left + " top=" + M.dock.style.top);
}
{
  const M = dockWorld({});
  M.placeMelDock();
  M.openMelDock();
  const left = parseFloat(M.dock.style.left), top = parseFloat(M.dock.style.top);
  check("no parked spot: the dock still opens on-screen (default corner)",
    M.dock.hidden === false && isFinite(left) && left >= 0 && left + 340 <= 391 &&
    isFinite(top) && top >= 0 && top < 844,
    "left=" + M.dock.style.left + " top=" + M.dock.style.top);
}

console.log("== M1: the drag flag belongs to its own gesture ==");
{
  // slice the real wiring: from `let melFabMoved` to just before the
  // melody-min onclick assignment that follows the pointerdown block
  const s = html.indexOf("let melFabMoved = false;");
  const e = html.indexOf('$("melody-min").onclick', s);
  if (s < 0 || e < 0) throw new Error("FAB wiring anchors not found");
  const wiring = html.slice(s, e);

  const dock = { hidden: true };
  const fab = {
    style: {}, offsetLeft: 320, offsetTop: 760, offsetWidth: 52, offsetHeight: 52,
    classList: { add() {}, remove() {} },
    setPointerCapture() {},
    _pd: null,
    addEventListener(type, fn) { if (type === "pointerdown") this._pd = fn; },
  };
  const winHandlers = {};
  const body =
    "let melFabDodged = false;\n" +
    "const MELODY = { open: false };\n" +
    "const ELS = { 'melody-fab': FAB, 'melody-dock': DOCK, 'mel-talk': {} };\n" +
    "const $ = id => ELS[id];\n" +
    "const window = { addEventListener(t, fn) { (WIN[t] = WIN[t] || []).push(fn); }," +
    " removeEventListener(t, fn) { const a = WIN[t] || []; const i = a.indexOf(fn);" +
    " if (i >= 0) a.splice(i, 1); } };\n" +
    "const localStorage = { getItem: () => null, setItem() {} };\n" +
    "function clampMelFab() {}\n" +
    "function openMelDock() { DOCK.hidden = false; MELODY.open = true; }\n" +
    wiring +
    "\nreturn { fab: FAB, dock: DOCK };";
  const M = new Function("FAB", "DOCK", "WIN", body)(fab, dock, winHandlers);
  const fire = (t, ev) => (winHandlers[t] || []).slice().forEach(fn => fn(ev));
  const down = (x, y) => fab._pd({ clientX: x, clientY: y, pointerId: 1, preventDefault() {} });
  const move = (x, y) => fire("pointermove", { clientX: x, clientY: y });
  const up = () => fire("pointerup", {});
  const click = () => fab.onclick();

  dock.hidden = true;
  down(340, 780); up(); click();
  check("a clean tap opens the dock", dock.hidden === false);

  dock.hidden = true;
  down(340, 780); move(370, 780); up();  // drag ends; browser suppresses its click
  down(340, 780); up(); click();         // the next, genuine tap
  check("a tap after a click-less drag still opens the dock",
    dock.hidden === false, "the drag's stale melFabMoved ate the tap");

  dock.hidden = true;
  down(340, 780); move(370, 780); up(); click();
  check("the click that follows a drag is still swallowed (by design)",
    dock.hidden === true);

  dock.hidden = true;
  down(340, 780); move(344, 782); up(); click();
  check("a jitter tap (4px, under the drag threshold) opens the dock",
    dock.hidden === false);
}

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
