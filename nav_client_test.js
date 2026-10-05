#!/usr/bin/env node
// nav_client_test.js — v5.55 panel navigation tests (Steph's feedback).
// Exercises PanelSys view history (back/forward) against stubbed globals,
// plus static assertions that overlay back buttons, the portal trail chip,
// and the + Interior button are wired up.
// Run: node nav_client_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

function extractBlock(startMarker) {
  const start = html.indexOf(startMarker);
  if (start < 0) throw new Error("not found: " + startMarker);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces after " + startMarker);
}

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}

// ---- stubbed globals ----------------------------------------------------
let sheetView = "tiles";
let trayTab = { left: "tiles", right: "tools" };
const PANEL_MODULES = [
  { id: "paint", tray: "left" },
  { id: "tiles", tray: "left" },
  { id: "inspect", tray: "right" },
];
let closedOverlays = 0;
function closeOverlays() { closedOverlays++; }
const TrayRenderer = { render() {} };
const SheetRenderer = { render() {} };

const src = extractBlock("const PanelSys = {").replace("const PanelSys =", "var PanelSys =");
eval(src);

console.log("== view history ==");
PanelSys.setView("paint");
check("first view recorded", PanelSys.hist.join(",") === "paint" && PanelSys.hix === 0,
  JSON.stringify(PanelSys.hist));
PanelSys.setView("inspect");
check("second view recorded", PanelSys.hist.join(",") === "paint,inspect" && PanelSys.hix === 1);
PanelSys.setView("inspect");
check("repeat view not duplicated", PanelSys.hist.length === 2 && PanelSys.hix === 1);
PanelSys.back();
check("back walks history", sheetView === "paint" && PanelSys.hix === 0,
  "sheetView=" + sheetView);
PanelSys.back();
check("back at start returns to map", closedOverlays === 1,
  "closedOverlays=" + closedOverlays);
PanelSys.fwd();
check("forward walks history", sheetView === "inspect" && PanelSys.hix === 1);
PanelSys.back();   // hix 0 again — now navigate somewhere new
PanelSys.setView("tiles");
check("new view truncates forward branch", PanelSys.hist.join(",") === "paint,tiles" && PanelSys.hix === 1,
  JSON.stringify(PanelSys.hist));
PanelSys.setView("bogus");
check("unknown view ignored", PanelSys.hist.join(",") === "paint,tiles");
// history is bounded
for (let i = 0; i < 40; i++) PanelSys.setView(i % 2 ? "inspect" : "paint");
check("history bounded at 30", PanelSys.hist.length === 30, "len=" + PanelSys.hist.length);

console.log("== static wiring ==");
check("initSheetBackButtons defined", html.includes("function initSheetBackButtons("));
check("back buttons installed at boot",
  /function initPanelSystem\(\)\s*{[^}]*initSheetBackButtons\(\)/.test(html) ||
  html.includes("initSheetBackButtons();"));
check("overlay back button targets tray-head",
  html.includes('sh.querySelector(":scope > .tray-head")'));
check("tray tab bars have nav buttons", html.includes('mkNav("‹"'));
check("sheet tab row has nav buttons", html.includes('mkN("‹"'));
check("portal trail declared", html.includes("let portalTrail = [];"));
check("enterPortal pushes trail", html.includes("portalTrail.push({ file: currentFile })"));
check("trail chip rendered", html.includes('id = "portal-trail"') || html.includes("portal-trail"));
check("manual load clears trail",
  html.includes("if (!opts || !opts.keepTrail) { portalTrail = [];"));
check("+ Interior button in load sheet", html.includes('id="btn-new-interior"'));
check("interior posts kind=interior",
  /btn-new-interior[\s\S]{0,600}kind:\s*"interior"/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
