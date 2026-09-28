#!/usr/bin/env node
// panel_system_test.js — v5.49.4 client tests.
// Static checks over editor.html: the panel content is now modular —
// tiles, paint, inspector, animation, NPC/patrol, melody-suggest and tools
// are content modules that don't know their container, and the bottom sheet
// vs side trays are interchangeable renderers behind the PanelSys facade.
// Run: node panel_system_test.js
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
function objBody(name) {
  const start = html.indexOf("const " + name + " = {");
  if (start < 0) return null;
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  return null;
}

console.log("== module registry: content that doesn't know its container ==");
check("PANEL_MODULES declares all seven modules",
  ["paint", "tiles", "tools", "inspect", "anim", "npc", "suggest"]
    .every(id => new RegExp('id: "' + id + '"').test(html)));
check("every module names its preferred tray (left/right)",
  /PANEL_MODULES = \[[\s\S]*?\{ id: "paint",[\s\S]*?tray: "left"[\s\S]*?\{ id: "tools",[\s\S]*?tray: "right"[\s\S]*?\];/.test(html));
check("panelRoot resolves tools to its wrapper, others to sheet views",
  /function panelRoot\(id\) \{[\s\S]*?id === "tools" \? \$\("tray-view-tools"\) : \$\("sheet-view-" \+ id\)/.test(html));

console.log("== renderer interface: both implement the same seam ==");
const sheet = objBody("SheetRenderer"), trays = objBody("TrayRenderer");
["mount", "render", "openView", "close", "reopen", "fabAvoid"].forEach(fn => {
  check("SheetRenderer." + fn + " exists", !!sheet && new RegExp(fn + "\\(").test(sheet));
  check("TrayRenderer." + fn + " exists", !!trays && new RegExp(fn + "\\(").test(trays));
});

console.log("== the sheet keeps its v5.47–v5.49 behavior ==");
check("sheet openView reopens a dismissed sheet to half",
  !!sheet && /sheetHeight === "closed"\) sheetHeight = "half"/.test(sheet));
check("sheet close() adds the closed class (play mode hides it)",
  !!sheet && /close\(\) \{[\s\S]*?classList\.add\("closed"\)/.test(sheet));
check("sheet mount docks the brush bar + more-sheet above the sheet",
  !!sheet && /prepend\(bb\)/.test(sheet) && /prepend\(ms\)/.test(sheet));
check("sheet fabAvoid still aims at the detent target top",
  !!sheet && /fabAvoid\(\) \{[\s\S]*?melSheetTargetTop\(\)/.test(sheet));

console.log("== the tray renderer resurrects the sides ==");
check("tray mount moves module roots into tray-left / tray-right",
  !!trays && /tray-" \+ m\.tray/.test(trays) || (!!trays && /tray-" \+ m.tray/.test(trays)),
  "modules land in their preferred tray");
check("tray openView opens the tray via toggleOverlay",
  !!trays && /openView\(view\) \{[\s\S]*?toggleOverlay\(tray\.id\)/.test(trays));
check("tray close() shuts overlays for play mode",
  !!trays && /close\(\) \{ closeOverlays\(\); \}/.test(trays));
const tabs = fnBody("renderTrayTabs");
check("tray tabs skip suggest when there's no ghost (Law 11: no dead buttons)",
  !!tabs && /m\.id === "suggest" && !ghostSug/.test(tabs));
check("tray tabs show only the active module's root",
  !!tabs && /r\.hidden = \(trayTab\[side\] !== m\.id\)/.test(tabs));

console.log("== PanelSys facade: the app talks to the seam, not the DOM ==");
const facade = objBody("PanelSys");
check("PanelSys exists with layout/renderer/setView/open/render/fabAvoid",
  !!facade && ["layout", "renderer()", "setView(", "open(", "render()", "fabAvoid()"]
    .every(k => facade.indexOf(k) >= 0));
check("openSheet survives as an alias", /function openSheet\(view, height\) \{ PanelSys\.open\(view, height\); \}/.test(html));
check("setSheetView survives as an alias", /function setSheetView\(v\) \{ PanelSys\.setView\(v\); \}/.test(html));
check("driveSheetView routes through the facade, not renderSheet",
  /if \(v !== sheetView\) PanelSys\.setView\(v\); else PanelSys\.render\(\);/.test(html));

console.log("== shared behaviors go through the active renderer ==");
const tp = fnBody("togglePlay");
check("play mode closes the active renderer's panels",
  !!tp && /PanelSys\.renderer\(\)\.close\(\)/.test(tp));
check("leaving play mode reopens the active renderer's panels",
  !!tp && /PanelSys\.renderer\(\)\.reopen\(\)/.test(tp));
const avo = fnBody("animViewOpen");
check("animViewOpen is layout-aware (tray open + tab, or sheet not closed)",
  !!avo && /PanelSys\.layout === "trays"/.test(avo) && /trayTab\.right === "anim"/.test(avo));
const dodge = fnBody("dodgeMelFab");
check("dodgeMelFab asks the active renderer what to avoid",
  !!dodge && /sys = PanelSys;/.test(dodge) && /sys\.fabAvoid\(\)/.test(dodge));
check("dodgeMelFab never throws before the facade exists (TDZ-safe)",
  !!dodge && /try \{ sys = PanelSys; \} catch/.test(dodge));
check("sheet mount un-hides the tools root (tray tabs may have hidden it)",
  !!sheet && /tw\.hidden = false/.test(sheet));
check("the tray renderer reports an avoid-rect when the right tray is open",
  !!trays && /fabAvoid\(\) \{[\s\S]*?return \{ left: r\.left \}/.test(trays));

console.log("== layout is a saved preference, not a rewrite ==");
check("the panel sheet carries a layout segmented control",
  /id="layout-seg"/.test(html) && /data-layout="trays"/.test(html) && /data-layout="sheet"/.test(html));
check("saveUiPrefs persists the layout", /panelLayout: PanelSys\.layout/.test(html));
check("boot restores the saved layout before first mount",
  /const p = readUiPrefs\(\);[\s\S]*?p\.panelLayout === "sheet"[\s\S]*?PanelSys\.layout = p\.panelLayout/.test(html));
check("tray tab bar styling exists", /\.tray-tabs \{/.test(html) && /\.tray-tabs button\.on/.test(html));

console.log("== v5.49.5: the little [x] on every panel ==");
check("the sheet's grabber row carries a close button",
  /id="sheet-close"/.test(html) && />×<\/button>/.test(html));
check("the sheet [x] dismisses the sheet without tripping the grabber drag",
  /sheet-close[\s\S]*?pointerdown[\s\S]*?stopPropagation/.test(html) &&
  /setSheetHeight\("closed"\)/.test(html));
check("every tray tab bar ends with an [x] that closes the overlays",
  /button\.tx[\s\S]*?x\.onclick = \(\) => closeOverlays\(\)/.test(html));
check("the tray [x] has its own styling", /\.tray-tabs button\.tx \{/.test(html));
check("the sheet [x] has its own styling", /#sheet-close \{/.test(html));
check("tap-the-map-to-close still works through the scrim",
  /\$\("scrim"\)\.onclick = closeOverlays/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
