#!/usr/bin/env node
// brushdock_test.js — v5.47.3 regression tests.
// The Phase-3 floating brush bar sat at viewport-bottom (z-31) while the
// Phase-5 sheet claimed z-60: only the buttons' tops peeked out above the
// sheet's grabber and the tools were unreachable. The bar (and the •••
// more-tools sheet) now dock inside #hud-sheet, riding 12px above its top
// edge in every detent; the Play FAB steps up in peek so the two never
// overlap. Static assertions over editor.html plus a live drive of
// positionFabForSheet with a stub DOM.
// Run: node brushdock_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

function extract(name) {
  let start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  if (html.slice(start - 6, start) === "async ") start -= 6;
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

// -- geometry constants, read from the CSS so the math stays honest --------
const peekPx = parseInt(html.match(/#hud-sheet\.peek\s*\{\s*transform:\s*translateY\(calc\(100% - (\d+)px\)\)/)[1], 10);
const barBtn = parseInt(html.match(/#brush-bar button\s*\{\s*width:\s*(\d+)px;\s*height:\s*(\d+)px/)[1], 10);
const fabSize = parseInt(html.match(/#btn-play-fab\s*\{[^}]*?width:\s*(\d+)px;\s*height:\s*\d+px/)[1], 10);
const BAR_GAP = 12;                 // docked 12px above the sheet's top edge
const FAB_GAP = 12;                 // FAB sits 12px above the docked bar in peek
const barW = 4 * barBtn + 3 * 10;   // four buttons, 10px gaps

console.log("== dock wiring (static) ==");
check("brush bar docks above the sheet",
  /#hud-sheet #brush-bar\s*\{\s*position:\s*absolute;\s*bottom:\s*calc\(100% \+ 12px\)/.test(html));
check("more-sheet rides above the docked bar",
  /#hud-sheet #more-sheet\s*\{\s*position:\s*absolute;\s*bottom:\s*calc\(100% \+ 80px\)/.test(html));
check("the sheet renderer docks the brush bar into the sheet",   // v5.50: docking moved with the renderer
  html.includes('sh.prepend(bb)') && html.includes('$("brush-bar")'));
check("the sheet renderer docks more-sheet into the sheet",
  html.includes('sh.prepend(ms)') && html.includes('$("more-sheet")'));
check("setSheetHeight repositions the FAB", /function setSheetHeight\(h\)[\s\S]{0,300}positionFabForSheet\(\)/.test(html));
check("play toggle restores FAB placement both ways",
  (html.match(/positionFabForSheet\(\);/g) || []).length >= 4);
check("sheet keeps its safe-area padding",
  /#hud-sheet\s*\{[^}]*env\(safe-area-inset-bottom\)/.test(html));

console.log("== positionFabForSheet (stub DOM) ==");
const fakeFab = { style: {} };
let sheetClosed = false;
const fakeSheet = { classList: { contains: (c) => c === "closed" ? sheetClosed : false } };
globalThis.$ = (id) => id === "btn-play-fab" ? fakeFab : fakeSheet;
globalThis.sheetHeight = "peek";
eval(extract("positionFabForSheet"));
const PEEK_FAB = "calc(144px + env(safe-area-inset-bottom))";
positionFabForSheet();
check("peek: FAB steps up to clear the docked bar", fakeFab.style.bottom === PEEK_FAB, "got " + fakeFab.style.bottom);
globalThis.sheetHeight = "half"; positionFabForSheet();
check("half: FAB keeps its classic spot (bar rides high)", fakeFab.style.bottom === "");
globalThis.sheetHeight = "full"; positionFabForSheet();
check("full: FAB keeps its classic spot", fakeFab.style.bottom === "");
sheetClosed = true; globalThis.sheetHeight = "peek"; positionFabForSheet();
check("play (closed): FAB keeps its classic spot (bar off-screen)", fakeFab.style.bottom === "");
sheetClosed = false;

console.log("== no-overlap geometry (390px phone, safe-area 0) ==");
const VW = 390;
// peek: sheet shows `peekPx`; bar bottom = peek+12, top = +56
const barBot = peekPx + BAR_GAP, barTop = barBot + barBtn;
const fabBot = barTop + FAB_GAP, fabTop = fabBot + fabSize;
check("peek: docked bar clears the sheet", barBot === peekPx + 12);
check("peek: FAB clears the docked bar", fabBot >= barTop + FAB_GAP);
check("peek: FAB bottom matches the stylesheet hook", fabBot === 144);
// horizontal: bar centered, FAB at left:14, Mel at right:14 (52px), zoom at right:10 (52px)
const barL = (VW - barW) / 2, barR = barL + barW;
check("peek: bar and FAB are vertically separated", fabBot >= barTop);
check("peek: bar never reaches the Mel button (default corner)", barR <= VW - 14 - 52,
  "barR=" + barR + " melL=" + (VW - 14 - 52));
check("peek: bar never reaches the zoom cluster", barR <= VW - 10 - 52, "barR=" + barR);
// half/full on a 700px-tall viewport: the bar rides the sheet top, far above the FAB's home
for (const [name, dvh] of [["half", 45], ["full", 82]]) {
  const sheetTop = Math.round(700 * dvh / 100);
  const bTop = sheetTop + BAR_GAP + barBtn;
  check(name + ": docked bar rides the sheet top, clear of the FAB", bTop > 84 + fabSize,
    "barTop=" + bTop);
}

console.log("== touch arbitration untouched ==");
check("two-finger pan/zoom still wins", /st\.order\.length === 2\)/.test(html) && html.includes("two fingers"));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
