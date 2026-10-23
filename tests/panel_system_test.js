#!/usr/bin/env node
// panel_system_test.js — client tests, rewritten 2026-10-23 for the
// Docked editor (PR #3 + Harley local fixes). The bottom sheet layout is
// retired: the layout switcher offers "docked" (trays pinned open, palette
// bar + hotbar in the centre column) and "trays" (the sliding Sides), and
// setPanelLayout coerces any other saved value — including "sheet" — to
// docked. These static checks over editor.html pin the modular panel
// system behind the PanelSys facade and the Docked behaviors that
// replaced the sheet-era ones (sheet detents, sheet [x], Bottom option).
// Run: node panel_system_test.js
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

console.log("== renderer interface: the seam the facade drives ==");
const trays = objBody("TrayRenderer");
["mount", "render", "openView", "close", "reopen", "fabAvoid"].forEach(fn => {
  check("TrayRenderer." + fn + " exists", !!trays && new RegExp(fn + "\\(").test(trays));
});
const facade0 = objBody("PanelSys");
check("PanelSys.renderer() serves the tray renderer for trays AND docked",
  !!facade0 && /renderer\(\) \{ return this\.layout === "sheet" \? SheetRenderer : TrayRenderer; \}/.test(facade0),
  "SheetRenderer is behind the seam for the retired layout only");

console.log("== the docked layout: pinned trays, the sheet retired ==");
const spl = fnBody("setPanelLayout");
check("setPanelLayout coerces every non-trays layout to docked (sheet retired)",
  !!spl && /which = which === "trays" \? "trays" : "docked";/.test(spl));
check("tray mount hides the retired sheet element",
  !!trays && /\$\("hud-sheet"\)\.style\.display = "none";/.test(trays));
check("tray mount floats the brush bar + more-sheet back to their homes",
  !!trays && /brushBarHome\.appendChild\(bb\)/.test(trays) && /moreSheetHome\.appendChild\(ms\)/.test(trays));
const dt = fnBody("dockTrays");
check("dockTrays pins both trays open, docked only",
  !!dt && /if \(!document\.body\.classList\.contains\("docked"\)\) return;/.test(dt) &&
          /\["tray-left", "tray-right"\]\.forEach\(id => \$\(id\)\.classList\.add\("open"\)\);/.test(dt));
check("closeOverlays re-pins the trays (docked panels never stay closed)",
  /function closeOverlays\(\) \{[\s\S]*?dockTrays\(\);/.test(html));
check("toggleOverlay refuses to toggle a tray while docked",
  /function toggleOverlay\(id\) \{[\s\S]*?document\.body\.classList\.contains\("docked"\) && id\.startsWith\("tray-"\)\) return;/.test(html));
check("tray openView renders in place when docked instead of toggling",
  !!trays && /if \(tray\.classList\.contains\("open"\) \|\| document\.body\.classList\.contains\("docked"\)\) this\.render\(\);/.test(trays) &&
          /else toggleOverlay\(tray\.id\);/.test(trays));
check("docked CSS pins the trays and centres the map column",
  /body\.docked \.tray \{ top: 0; width: 300px; transform: none; z-index: 46; \}/.test(html) &&
  /body\.docked #stage \{ left: 300px; right: 300px; \}/.test(html));

console.log("== the tray renderer resurrects the sides ==");
check("tray mount moves module roots into tray-left / tray-right",
  !!trays && /tray-" \+ m\.tray/.test(trays) || (!!trays && /tray-" \+ m.tray/.test(trays)),
  "modules land in their preferred tray");
check("tray openView opens the tray via toggleOverlay",
  !!trays && /openView\(view\) \{[\s\S]*?toggleOverlay\(tray\.id\)/.test(trays));
check("tray close() shuts overlays for play mode",
  !!trays && /close\(\) \{ closeOverlays\(\); \}/.test(trays));
const tabs = fnBody("renderTrayTabs");
check("tray tabs filter modules for the active layer",
  !!tabs && /const allowed = sheetViewsForLayer\(layer\)/.test(tabs) && /!allowed.includes\(m.id\)/.test(tabs));
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
check("tray reopen leaves trays shut — the edge tabs summon them",
  !!trays && /reopen\(\) \{\s*\/\* trays stay shut/.test(trays));
check("the tray renderer reports an avoid-rect when the right tray is open",
  !!trays && /fabAvoid\(\) \{[\s\S]*?return \{ left: r\.left \}/.test(trays));

console.log("== layout is a saved preference, not a rewrite ==");
check("the layout segmented control offers Docked + Sides, no Bottom/sheet",
  /id="layout-seg"/.test(html) && /data-layout="docked"/.test(html) &&
  /data-layout="trays"/.test(html) && !/data-layout="sheet"/.test(html));
check("saveUiPrefs persists the layout", /panelLayout: PanelSys\.layout/.test(html));
const ips = fnBody("initPanelSystem");
check("boot restores the saved layout; a saved 'sheet' migrates to docked",
  !!ips && /const p = readUiPrefs\(\);/.test(ips) &&
          /if \(p\.panelLayout === "trays"\) PanelSys\.layout = "trays";/.test(ips) &&
          /else PanelSys\.layout = "docked";\s*\/\/ saved "sheet" prefs migrate to docked/.test(ips));
check("layout-seg buttons are wired to setPanelLayout",
  !!ips && /b\.onclick = \(\) => setPanelLayout\(b\.dataset\.layout\);/.test(ips) &&
          /setPanelLayout\(PanelSys\.layout, \{ first: true \}\);/.test(ips));
check("docked needs a wide screen; narrow falls back to sliding trays",
  /const DOCK_MIN_WIDTH = 900;/.test(html) &&
  !!spl && /const dockedNow = which === "docked" && window\.innerWidth >= DOCK_MIN_WIDTH;/.test(spl));
check("tray tab bar styling exists", /\.tray-tabs \{/.test(html) && /\.tray-tabs button\.on/.test(html));

console.log("== the little [x] on every panel ==");
check("the palette bar's head carries a close button naming its gesture",
  /id="nwc-palette-hide" title="hide \(Esc\)">×<\/button>/.test(html));
check("the palette [x] is wired straight to hidePalette",
  /document\.getElementById\("nwc-palette-hide"\)\.onclick=hidePalette;/.test(html));
check("every tray tab bar ends with an [x] that closes the overlays",
  /button\.tx[\s\S]*?x\.onclick = \(\) => closeOverlays\(\)/.test(html));
check("the tray [x] has its own styling", /\.tray-tabs button\.tx \{/.test(html));
check("docked hides the tray [x] — pinned panels have nothing to close",
  /body\.docked \.tray-tabs button\.tx \{ display: none !important; \}/.test(html));
check("tap-the-map-to-close still works through the scrim",
  /\$\("scrim"\)\.onclick = closeOverlays/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
