#!/usr/bin/env node
// sheet_dismiss_test.js — v5.49.2 client tests.
// Static checks over editor.html: (1) the tile panel can actually be
// dismissed — before this the grabber tap cycled peek/half/full forever and
// drag-down clamped at peek, so Play mode was the only way out; (2) modal
// dialogs (update!) render ABOVE the tile panel — before this the update
// sheet opened underneath it and "Install update" couldn't be tapped.
// Run: node sheet_dismiss_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

function cssZ(sel) {
  const m = html.match(new RegExp(sel + " \\{[\\s\\S]*?z-index:\\s*(\\d+);"));
  return m ? parseInt(m[1], 10) : null;
}

console.log("== modal layer stack: dialogs above the tile panel ==");
const sheetZ = cssZ("\\.sheet"), scrimZ = cssZ("#scrim"), trayZ = cssZ("\\.tray"),
      menuZ = cssZ("\\.menu-drop"), hudZ = cssZ("#hud-sheet");
check("modal .sheet above #hud-sheet (" + sheetZ + " > " + hudZ + ")",
  sheetZ !== null && hudZ !== null && sheetZ > hudZ);
check("scrim above #hud-sheet, below .sheet (" + scrimZ + ")",
  scrimZ !== null && sheetZ !== null && hudZ !== null && scrimZ > hudZ && scrimZ < sheetZ,
  "tap-outside dismissal has to land on the scrim, not the panel");
check(".tray above #hud-sheet (" + trayZ + " > " + hudZ + ")",
  trayZ !== null && hudZ !== null && trayZ > hudZ);
check(".menu-drop above the scrim (" + menuZ + " > " + scrimZ + ")",
  menuZ !== null && scrimZ !== null && menuZ > scrimZ,
  "menus keep their old relative order, just lifted with the stack");

console.log("== the panel can be dismissed ==");
check('drag order includes "closed"',
  /const order = \["closed", "peek", "half", "full"\];/.test(html));
check("a nudge doesn't close it — dismiss needs a deliberate drag",
  /if \(i === 0 && dy < 48\) i = 1;/.test(html));
check("tap still only cycles sizes (no accidental close on tap)",
  /const SHEET_HEIGHTS = \["peek", "half", "full"\];/.test(html));
check("openSheet reopens a dismissed sheet",
  /sheetHeight === "closed"\) sheetHeight = "half"/.test(html),
  "the TILES edge tab is the way back in");
check("grabber hint names the close gesture",
  /title="tap to resize · drag down to close"/.test(html));
check('"closed" detent slides the sheet fully off-screen',
  /#hud-sheet\.closed \{ transform: translateY\(103%\); \}/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
