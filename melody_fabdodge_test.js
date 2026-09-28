#!/usr/bin/env node
// melody_fabdodge_test.js — v5.49.1 client tests.
// Static checks over editor.html: the draggable Mel button must never park
// on top of the open bottom sheet (it was covering brush sizes, tabs, and
// panel buttons). The dodge aims at the detent's *target* top edge because
// the sheet animates its detents with a transform.
// Run: node melody_fabdodge_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

function fnBody(name) {
  const start = html.indexOf("function " + name + "(");
  if (start < 0) return null;
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  return null;
}

console.log("== dodge targets the detent, not the animation ==");
const tgt = fnBody("melSheetTargetTop");
check("melSheetTargetTop exists", !!tgt);
check("closed sheet -> null (nothing to dodge)", !!tgt && /contains\("closed"\)\) return null/.test(tgt));
check("full/half/peek targets match the CSS detents",
  !!tgt && /0\.82/.test(tgt) && /0\.45/.test(tgt) && /vh - 64/.test(tgt),
  "must mirror #hud-sheet.full/half/peek transforms");

console.log("== dodgeMelFab behavior ==");
const dodge = fnBody("dodgeMelFab");
check("dodgeMelFab exists", !!dodge);
check("hidden fab is left alone", !!dodge && /fab\.hidden/.test(dodge));
check("already-clear fab is not touched",
  !!dodge && /fr\.bottom <= top \+ 4/.test(dodge) && /return;/.test(dodge));
check("overlapping fab steps above the sheet with air",
  !!dodge && /top - h - 10/.test(dodge) && /Math\.max\(48,/.test(dodge),
  "10px above the sheet top, never above the topbar");
check("the dodge is never persisted to localStorage",
  !!dodge && !/localStorage\.setItem/.test(dodge),
  "the parked spot must survive underneath the dodge");
check("sheet close hands back the parked spot when dodged",
  !!dodge && /melFabDodged/.test(dodge) && /placeMelFab\(\)/.test(dodge));

console.log("== wiring: dodge runs at every sheet move ==");
const setH = fnBody("setSheetHeight");
check("setSheetHeight calls dodgeMelFab",
  !!setH && /dodgeMelFab\(\);/.test(setH),
  "covers open, detent change, and close");
check("page load dodges after restoring the parked spot",
  /placeMelFab\(\);[^\n]*\n\s*dodgeMelFab\(\);/.test(html));
check("a manual drag clears the dodge (the park wins)",
  /melFabMoved = true;\s*\n?\s*melFabDodged = false;/.test(html));

console.log("== the fab stays off the boot screens (v5.49.3) ==");
function cssZ(sel) {
  const i = html.indexOf(sel + " {");
  if (i < 0) return null;
  const m = html.slice(i, html.indexOf("}", i)).match(/z-index:\s*([0-9]+)/);
  return m ? parseInt(m[1], 10) : null;
}
const fabZ = cssZ("#melody-fab"), splashZ = cssZ("#splash"),
      loginZ = cssZ("#login-overlay"), dockZ = cssZ("#melody-dock");
check("all four z-indexes readable from CSS",
  fabZ !== null && splashZ !== null && loginZ !== null && dockZ !== null);
check("fab sits below the splash title screen",
  fabZ !== null && splashZ !== null && fabZ < splashZ,
  `fab ${fabZ} vs splash ${splashZ}`);
check("fab sits below the login overlay",
  fabZ !== null && loginZ !== null && fabZ < loginZ,
  `fab ${fabZ} vs login ${loginZ}`);
check("the open dock still floats above the splash",
  dockZ !== null && splashZ !== null && dockZ > splashZ,
  `dock ${dockZ} vs splash ${splashZ}`);

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
