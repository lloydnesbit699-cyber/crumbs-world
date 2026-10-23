#!/usr/bin/env node
// sheet_dismiss_test.js — client tests, rewritten 2026-10-23 for the
// Docked editor (PR #3 + Harley local fixes). The bottom sheet this file
// was named for is retired — #hud-sheet is display:none for good and the
// palette bar is the bottom surface now — so the suite guards the same
// two promises against the new design: (1) modal dialogs render ABOVE
// the editor's panel surfaces, so an "Install update" tap can always
// land (the v5.49.2 bug: the update sheet opened underneath the tile
// panel); (2) the bottom surface can actually be dismissed — and there
// is always a way back in. The sheet's drag detents have no equivalent:
// dismissing the palette bar is an explicit [x] / Esc, the FAB is the
// way back, and in Docked the side trays are pinned — they never close.
// Run: node sheet_dismiss_test.js
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
  if (start < 0) return null;
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  return null;
}

// z-index of the LAST rule whose selector is exactly `sel` at a rule
// start. (The sheet-era helper used lastIndexOf(sel + " {"), which the
// body.docked override rules silently broke — e.g. ".menu-drop" matched
// the docked left-offset rule, which carries no z-index.)
function ruleZ(sel) {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp("(?:^|[}\\n])\\s*" + esc + "\\s*\\{([^}]*)\\}", "g");
  let m, z = null;
  while ((m = re.exec(html)) !== null) {
    const zm = m[1].match(/z-index:\s*(\d+);/);
    if (zm) z = parseInt(zm[1], 10);
  }
  return z;
}

console.log("== modal layer stack: dialogs above the panel surfaces ==");
const sheetZ = ruleZ(".sheet"), scrimZ = ruleZ("#scrim"), menuZ = ruleZ(".menu-drop"),
      dockZ = ruleZ("#nwc-palette-dock"),
      dTrayZ = ruleZ("body.docked .tray"), dDockZ = ruleZ("body.docked #nwc-palette-dock"),
      dHotZ = ruleZ("body.docked #nwc-hotbar");
check("the retired sheet can never cover a dialog (#hud-sheet display:none)",
  /#hud-sheet \{ display: none !important; \}.*retired: the palette bar replaces the bottom panel/.test(html));
check("modal .sheet above the palette bar (" + sheetZ + " > " + dockZ + ")",
  sheetZ !== null && dockZ !== null && sheetZ > dockZ);
check("scrim above the palette bar, below .sheet (" + scrimZ + ")",
  scrimZ !== null && sheetZ !== null && dockZ !== null && scrimZ > dockZ && scrimZ < sheetZ,
  "tap-outside dismissal has to land on the scrim, not the panel");
check("in Docked, .sheet above pinned trays, palette dock and hotbar (" +
      dTrayZ + "/" + dDockZ + "/" + dHotZ + ")",
  sheetZ !== null && dTrayZ !== null && dDockZ !== null && dHotZ !== null &&
  sheetZ > dTrayZ && sheetZ > dDockZ && sheetZ > dHotZ);
check("scrim above every Docked surface (" + scrimZ + ")",
  scrimZ !== null && dTrayZ !== null && dDockZ !== null && dHotZ !== null &&
  scrimZ > dTrayZ && scrimZ > dDockZ && scrimZ > dHotZ);
check(".menu-drop above the scrim (" + menuZ + " > " + scrimZ + ")",
  menuZ !== null && scrimZ !== null && menuZ > scrimZ,
  "menus keep their old relative order, just lifted with the stack");

console.log("== the bottom surface can be dismissed — and brought back ==");
const hide = fnBody("hidePalette"), open = fnBody("openPalette"), sync = fnBody("syncDockState");
check("the palette head's [x] names its gesture (title: hide (Esc))",
  /id="nwc-palette-hide" title="hide \(Esc\)">×<\/button>/.test(html));
check("the [x] is wired straight to hidePalette",
  /document\.getElementById\("nwc-palette-hide"\)\.onclick=hidePalette;/.test(html));
check("Esc dismisses the palette bar too",
  /document\.addEventListener\("keydown",function\(e\)\{if\(e\.key==="Escape"\)\{hidePalette\(\);\}\}\);/.test(html));
check("hidePalette hides the bar, collapses the dock, raises the FAB",
  !!hide && /pal\.hidden=true;/.test(hide) &&
          /dockEl\.classList\.add\("nwc-collapsed"\)/.test(hide) &&
          /fab\.hidden=false;/.test(hide));
check("the FAB is the way back in — it reopens the palette",
  /fab\.onclick=openPalette;/.test(html) &&
  !!open && /pal\.hidden=false;/.test(open) && /fab\.hidden=true;/.test(open),
  "the 🎨 Palette button replaces the TILES edge tab as the way back in");
check("while hidden, the map reclaims the bar's space",
  !!sync && /classList\.toggle\("nwc-dock-off",dockEl\.classList\.contains\("nwc-collapsed"\)\)/.test(sync) &&
          /body\.docked\.nwc-dock-off #stage \{ bottom: 0; \}/.test(html));
check("no accidental dismiss: the dock grip only resizes, never below 90px",
  /var h=Math\.max\(90,Math\.min\(window\.innerHeight\*0\.6/.test(html),
  "dragging the palette bar's grip can't drag it shut");
check("docked trays have no dismiss at all — pinned by design",
  /function toggleOverlay\(id\) \{[\s\S]*?document\.body\.classList\.contains\("docked"\) && id\.startsWith\("tray-"\)\) return;/.test(html) &&
  /function closeOverlays\(\) \{[\s\S]*?dockTrays\(\);/.test(html),
  "toggleOverlay refuses tray toggles and closeOverlays re-pins them");

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
