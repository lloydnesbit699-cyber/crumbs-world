#!/usr/bin/env node
// panelvis_test.js — v5.47.4 regression tests.
// The v5.29 panel-visibility control (◨: opacity slider + hide-all) drives a
// --panel-op CSS var and a body.panels-hidden class, consumed by selector
// lists in the stylesheet. But #hud-sheet never carried class "sheet" — its
// classes are the peek/half/full detents — so both lists silently missed it:
// the bottom sheet, the docked brush bar, and the ••• tools ignored the
// transparency slider and survived hide-all. Both lists now name #hud-sheet
// explicitly (children inherit, so the docked bar and more-sheet ride along).
// Run: node panelvis_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

function extract(name) {
  let start = html.indexOf("function " + name + "(");
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
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

// -- root cause guard: the sheet's classes are detents, not "sheet" ---------
const sheetClass = (html.match(/<div id="hud-sheet" class="([^"]*)"/) || [])[1] || "";
console.log("== root cause (static) ==");
check("hud-sheet markup carries no .sheet class (why the lists missed it)",
  !sheetClass.split(/\s+/).includes("sheet"), "class=\"" + sheetClass + "\"");

// -- opacity selector group -------------------------------------------------
console.log("== --panel-op coverage (static) ==");
const opGroups = [...html.matchAll(/([^{}]+)\{\s*opacity:\s*var\(--panel-op\);\s*\}/g)]
  .map(m => m[1].replace(/\s+/g, " "));
check("a --panel-op rule names #hud-sheet",
  opGroups.some(g => /(^|[\s,])#hud-sheet([\s,]|$)/.test(g)),
  JSON.stringify(opGroups));
check("the classic panel group still rides --panel-op (no regression)",
  opGroups.some(g => g.includes("#topbar") && g.includes(".tray") && g.includes(".sheet")));
check("play FAB + budget strip still ride --panel-op (no regression)",
  opGroups.some(g => g.includes("#btn-play-fab") && g.includes("#budget-strip")));

// -- hide-all selector group ------------------------------------------------
console.log("== panels-hidden coverage (static) ==");
check("hide-all names body.panels-hidden #hud-sheet",
  /body\.panels-hidden #hud-sheet[\s,]/.test(html));
check("hide-all still covers the classic panels (no regression)",
  /body\.panels-hidden #topbar[\s,]/.test(html) &&
  /body\.panels-hidden \.tray[\s,]/.test(html));

// -- live drive of applyPanelPrefs with a stub DOM --------------------------
console.log("== applyPanelPrefs (stub DOM) ==");
const seen = { props: {}, classes: [] };
const fakeBody = {
  style: { setProperty: (k, v) => { seen.props[k] = v; } },
  classList: { toggle: (c, f) => { seen.classes.push([c, !!f]); } },
};
const fakes = {
  "panel-opacity": { value: null },
  "panel-op-val": { textContent: null },
  "panel-hide-btn": { innerHTML: null, classList: { toggle: () => {} } },
};
const src = extract("applyPanelPrefs");
const drive = new Function(
  "panelOpacity", "panelsHidden", "$", "document",
  src + "\napplyPanelPrefs();\nreturn { props: document.body.__seen.props, classes: document.body.__seen.classes };"
);
// wire the stub's seen store onto the fake body
fakeBody.__seen = seen;
const $stub = (id) => fakes[id] || null;
const docStub = { body: fakeBody };
drive(0.5, true, $stub, docStub);
check("slider value writes --panel-op to the body", seen.props["--panel-op"] === 0.5,
  "got " + JSON.stringify(seen.props["--panel-op"]));
check("hide flag toggles body.panels-hidden",
  seen.classes.some(([c, f]) => c === "panels-hidden" && f === true));
check("slider + label reflect the 50% value",
  fakes["panel-opacity"].value === 50 && fakes["panel-op-val"].textContent === "50%");

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
