#!/usr/bin/env node
// stage4_pills_client_test.js — Stage 4 (§18, Ball Room item 19):
// the top pill row. One row of pop-open pills under the black HUD bar;
// the right-edge bubble stack retired into pill homes; the budget
// strip became the persistent health/status pill (undo LEFT it for
// the left-side edit pill); the Palette pill's home is the row
// (item 13); Melody's bubble is NOT in the row and stays a circle.
// Run: node stage4_pills_client_test.js
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}
// slice of html between two markers ("" if either is missing)
function between(a, b) {
  const i = html.indexOf(a), j = html.indexOf(b, i + 1);
  return (i < 0 || j < 0) ? "" : html.slice(i, j);
}
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

const rowSlice = between('id="pill-row"', 'id="pill-panel-camera"');
const camSlice = between('id="pill-panel-camera"', 'id="pill-panel-world"');
const worldSlice = between('id="pill-panel-world"', 'id="edit-pill"');
const clusterSlice = between('id="zoom-cluster"', "</div>");

console.log("== the one row at the top ==");
check("pill row exists", rowSlice.length > 0);
check("Camera pill in the row", rowSlice.includes('id="pill-camera"'));
check("World-systems pill in the row", rowSlice.includes('id="pill-world"'));
check("Survey pill in the row is the world-lens toggle itself",
  rowSlice.includes('id="world-lens-toggle"') && rowSlice.includes("Survey"));
check("health pill (budget strip) lives in the row", rowSlice.includes('id="budget-strip"'));
check("Palette pill lives in the row (item 13's home)", rowSlice.includes('id="nwc-palette-fab"'));
check("row is one flex line with horizontal scroll as the phone safety net",
  /#pill-row\s*\{[^}]*overflow-x:\s*auto/.test(html));
check("under 520px the group pills collapse to icon-only (v5.23 precedent)",
  /@media \(max-width: 520px\)[\s\S]{0,400}\.pill-btn \.pill-lbl\s*\{\s*display: none/.test(html));

console.log("== camera pill hosts the camera controls (moved, not rewritten) ==");
check("altitude bar (#play-modes) moved into the camera panel", camSlice.includes('id="play-modes"'));
check("zoom out/in moved into the camera panel",
  camSlice.includes('id="zoom-out"') && camSlice.includes('id="zoom-in"'));
check("Fit moved into the camera panel", camSlice.includes('id="zoom-fit"'));
check("Move (btn-pan) moved into the camera panel", camSlice.includes('id="btn-pan"'));
check("full-screen lens toggle moved into the camera panel", camSlice.includes('id="lens-full-toggle"'));
check("camera panel starts hidden (pop-open)", /id="pill-panel-camera" hidden/.test(html));

console.log("== world-systems pill hosts the system toggles ==");
check("weather toggle in the world panel", worldSlice.includes('id="sky-toggle"'));
check("shrine toggle in the world panel", worldSlice.includes('id="shrine-toggle"'));
check("flight-test toggle in the world panel", worldSlice.includes('id="flight-toggle"'));
check("world panel starts hidden (pop-open)", /id="pill-panel-world" hidden/.test(html));

console.log("== the bubble stack is retired; the grid toggle keeps its home ==");
check("zoom cluster shell remains for the grid toggle", clusterSlice.includes('id="btn-grid"'));
check("no moved button is still inside the zoom cluster",
  !/id="(zoom-in|zoom-out|zoom-fit|btn-pan|lens-full-toggle|sky-toggle|shrine-toggle|flight-toggle|world-lens-toggle)"/.test(clusterSlice));

console.log("== moved controls keep their original handlers (by id) ==");
check("zoom-in handler intact", html.includes('$("zoom-in").onclick'));
check("zoom-out handler intact", html.includes('$("zoom-out").onclick'));
check("zoom-fit handler intact (lens Fit ruling preserved)",
  /\$\("zoom-fit"\)\.onclick = \(\) => \{ if \(lensRegionOn\(\)\)/.test(html));
check("btn-pan handler intact", html.includes('$("btn-pan").onclick'));
check("play-modes buttons still wired to playGoMode",
  html.includes('document.querySelectorAll("#play-modes button")'));
check("sky toggle flip intact", html.includes('$("sky-toggle").onclick'));
check("shrine flip intact (shrineWire)", html.includes("function shrineWire()") && html.includes("window.shrineToggle = flip"));
check("flight flip intact (flightWire)", html.includes("function flightWire()") && html.includes("window.flightToggle = flip"));
check("world-lens toggle handler intact", html.includes('$("world-lens-toggle").onclick'));
check("grid handler intact", html.includes('$("btn-grid").onclick'));

console.log("== §18d: undo left the health pill for the left-side edit pill ==");
const editSlice = between('id="edit-pill"', 'id="zoom-cluster"');
check("edit pill exists on the left with undo + redo",
  editSlice.includes('id="pill-undo"') && editSlice.includes('id="pill-redo"'));
check("edit pill is fixed to the left edge",
  /#edit-pill\s*\{[^}]*position:\s*fixed;[^}]*left:\s*8px/.test(html));
const rb = extract("refreshBudget");
const rbHtml = (rb.match(/b\.innerHTML =([\s\S]*?);/) || [])[1] || "";
check("health pill text no longer carries the undo segment", rbHtml.length > 0 && !rbHtml.includes("↩"));
check("health pill no longer says tap to undo", !rb.includes("tap to undo"));
check("pill-undo wired to the same doUndo as top bar + menu",
  /\$\("pill-undo"\)/.test(html) && /u\.onclick = doUndo/.test(html));
check("pill-redo wired to the same doRedo", /r\.onclick = doRedo/.test(html));

console.log("== Melody is not a tool: her circle is untouched ==");
check("Mel's FAB is NOT inside the pill row", !rowSlice.includes("melody-fab"));
check("Mel's FAB is NOT inside either pill panel",
  !camSlice.includes("melody-fab") && !worldSlice.includes("melody-fab"));
check("Mel's FAB is still a lone perfect circle, bottom-right",
  /#melody-fab\s*\{[^}]*border-radius:\s*50%/.test(html) &&
  /#melody-fab\s*\{[^}]*position:\s*fixed;[^}]*right:\s*14px/.test(html));
check("Mel's FAB wiring untouched (tap/drag handlers by id)",
  html.includes('$("melody-fab").onclick') && html.includes("placeMelFab"));

console.log("== behavior: pill exclusivity + system-panel solo (extracted) ==");
const preamble = `
const els = {};
function mkEl(id) {
  const listeners = {};
  const el = { id, hidden: true, onclick: null,
    classList: { _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
      contains(c) { return this._s.has(c); } },
    addEventListener(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    click() { if (this.onclick) this.onclick(); (listeners.click || []).forEach(f => f()); } };
  els[id] = el; return el;
}
["pill-panel-camera", "pill-panel-world", "pill-camera", "pill-world",
 "sky-panel", "sky-toggle", "shrine-panel", "shrine-toggle",
 "flight-panel", "flight-toggle", "pill-undo", "pill-redo"].forEach(mkEl);
const $ = id => els[id] || null;
let undoCalls = 0, redoCalls = 0;
var doUndo = () => { undoCalls++; }, doRedo = () => { redoCalls++; };
`;
const body = preamble +
  ["pillCloseAll", "pillToggle", "sysPanelSolo", "initPillRow"].map(extract).join("\n") + `
return { els, pillToggle, sysPanelSolo, initPillRow,
  counts: () => ({ undoCalls, redoCalls }) };`;
const S = new Function(body)();
S.initPillRow();

S.els["pill-camera"].click();
check("camera pill opens the camera panel only",
  !S.els["pill-panel-camera"].hidden && S.els["pill-panel-world"].hidden);
S.els["pill-world"].click();
check("world pill opens its panel and closes the camera panel (one at a time)",
  !S.els["pill-panel-world"].hidden && S.els["pill-panel-camera"].hidden);
S.els["pill-world"].click();
check("re-tapping a pill folds its panel shut",
  S.els["pill-panel-world"].hidden && S.els["pill-panel-camera"].hidden);

// system toggles: legacy flips are onclick properties in the real page;
// emulate one opening, then check the solo pass + launcher fold.
S.els["sky-panel"].hidden = false; S.els["shrine-panel"].hidden = false; S.els["flight-panel"].hidden = false;
S.els["shrine-toggle"].classList.add("on"); S.els["flight-toggle"].classList.add("on");
S.els["sky-toggle"].onclick = () => {};   // the real flip already ran (panel open)
S.els["pill-panel-world"].hidden = false;
S.els["sky-toggle"].click();
check("opening Weather solos the system panels (shrines/flight close, lights off)",
  !S.els["sky-panel"].hidden && S.els["shrine-panel"].hidden && S.els["flight-panel"].hidden &&
  !S.els["shrine-toggle"].classList.contains("on") && !S.els["flight-toggle"].classList.contains("on"));
check("firing a system toggle folds the world pill panel (launcher)",
  S.els["pill-panel-world"].hidden);

S.els["pill-undo"].click(); S.els["pill-redo"].click();
check("edit pill undo/redo call doUndo/doRedo",
  S.counts().undoCalls === 1 && S.counts().redoCalls === 1);

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
