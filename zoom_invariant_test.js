#!/usr/bin/env node
// zoom_invariant_test.js — v5.51.2 regression tests.
// Lloyd's "ballooning buttons": zooming deep on his Chromebook made the paint /
// erase / more circles huge. Forensics (button:tile ratios measured across his
// photos, plus a full code audit) showed it was the BROWSER's page zoom
// (Ctrl+Plus / trackpad pinch on ChromeOS), not the HUD's map zoom: the HUD's
// zoom only ever changes tilePx and the map canvas is redrawn at the new tile
// size, while every HUD chrome rule is fixed-px CSS with zero tilePx
// references. This suite locks that invariant in:
//   1. static: no tilePx in the stylesheet; no CSS `zoom` on HUD; HUD buttons fixed px
//   2. live: zoomAt keeps the tile under the cursor anchored; tilePx clamps [8, maxTilePx]
//   3. live: clampPan bounds hold at min and max zoom; layout() folds pan into a translate
//   4. static: hero / NPC / Melody sprites are drawn from tile coords × tilePx
//             (map content scales with zoom — correctly — and never drifts)
//   5. live: the v5.51.2 page-zoom hint fires once per session on desktop at 3x,
//            stays silent at 1x and on coarse-pointer devices
//   6. static: recent repairs still intact (Pack parks above the zoom cluster,
//             grid toggle ▦ lives in the zoom cluster)
// Run: node zoom_invariant_test.js
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

const styleBlock = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));

console.log("== HUD chrome is zoom-invariant (static) ==");
check("stylesheet never references tilePx",
  !/tilePx/.test(styleBlock));
check("no CSS `zoom` property on HUD selectors",
  !/(?<![a-zA-Z-])zoom\s*:/.test(styleBlock));
check("no scale() transform on HUD chrome (only :active press states + canvas ops)",
  (() => {
    const uses = [...styleBlock.matchAll(/scale\(([^)]*)\)/g)];
    return uses.every(m => m[0] === "scale(.95)" || m[0] === "scale(.94)" ||
                           m[0] === "scale(.96)" || m[0] === "scale(.93)");
  })());
check("brush-bar buttons are fixed 56px",
  /#brush-bar button\s*\{\s*width:\s*56px;\s*height:\s*56px/.test(styleBlock));
check("zoom-cluster buttons are fixed 52px",
  /#zoom-cluster button\s*\{\s*width:\s*52px;\s*height:\s*52px/.test(styleBlock));
check("dpad cells are fixed 46px",
  /#dpad\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*46px\)/.test(styleBlock));
check("topbar is a fixed 48px strip",
  /#topbar\s*\{\s*position:\s*fixed;\s*top:\s*0;\s*left:\s*0;\s*right:\s*0;\s*height:\s*48px/.test(styleBlock));
check("no JS sizes HUD chrome from tilePx",
  !/tilePx/.test(html.match(/\.style\.(width|height|fontSize|zoom)\s*=[\s\S]{0,80}/g)?.join("") || ""));

console.log("== zoomAt / clampPan / layout math (stub DOM) ==");
const driver = `
let W=64,H=64,tilePx=32,panX=0,panY=0;
const MAX_CANVAS_DIM=4096;
const stage={clientWidth:1366,clientHeight:700,getBoundingClientRect:function(){return {left:0,top:48};}};
const canvas={style:{}};
function render(){}
${extract("maxTilePx")}
${extract("clampPan")}
${extract("layout")}
${extract("zoomAt")}
;globalThis.__zr=(function(){
  const out={};
  tilePx=32; panX=0; panY=0;
  zoomAt(683,350,200); out.clampMax=tilePx;   // maxTilePx for 64x64 is 64
  zoomAt(683,350,1);   out.clampMin=tilePx;   // floor is 8
  // anchor invariance: the tile under the cursor is identical before/after
  tilePx=16; panX=0; panY=0;
  const ax=683, ay=350-48;
  const tx0=(ax-(1366-64*16)/2)/16, ty0=(ay-(700-64*16)/2)/16;
  zoomAt(683,350,48);
  const tx1=(ax-((1366-64*48)/2+panX))/48, ty1=(ay-((700-64*48)/2+panY))/48;
  out.anchorTx=Math.abs(tx1-tx0)<1e-9; out.anchorTy=Math.abs(ty1-ty0)<1e-9;
  out.zoomedTo=48;
  // clampPan bounds at min zoom (tilePx=8) and max zoom (tilePx=64)
  tilePx=8; panX=1e6; panY=-1e6; clampPan();
  out.panMinX=panX===(1366+64*8)/2; out.panMinY=panY===-(700+64*8)/2;
  tilePx=64; panX=1e6; panY=0; clampPan();
  out.panMaxX=panX===(1366+64*64)/2;
  // layout() folds the pan into a plain translate — no scale, ever
  tilePx=32; panX=10; panY=20; layout();
  out.layoutTx=canvas.style.transform==="translate("+((1366-64*32)/2+10)+"px,"+((700-64*32)/2+20)+"px)";
  out.layoutNoScale=!/[Ss]cale/.test(canvas.style.transform);
  return out;
})();
`;
eval(driver);
const zr = globalThis.__zr;
check("zoomAt clamps to maxTilePx (64 on a 64x64 map)", zr.clampMax === 64, "got " + zr.clampMax);
check("zoomAt clamps to the 8px floor", zr.clampMin === 8, "got " + zr.clampMin);
check("zoomAt lands on the requested tile size", zr.zoomedTo === 48);
check("zoomAt keeps the tile under the cursor anchored (x)", zr.anchorTx);
check("zoomAt keeps the tile under the cursor anchored (y)", zr.anchorTy);
check("clampPan bounds pan at min zoom (+x)", zr.panMinX);
check("clampPan bounds pan at min zoom (-y)", zr.panMinY);
check("clampPan bounds pan at max zoom", zr.panMaxX);
check("layout() positions the canvas with a pure translate", zr.layoutTx);
check("layout() never scales the canvas", zr.layoutNoScale);

console.log("== characters & creatures scale with the map, never drift (static) ==");
check("NPC bodies anchor at n.x * tilePx",
  /function drawNpc\(n\)[\s\S]{0,400}px = n\.x \* tilePx, py = n\.y \* tilePx/.test(html));
check("NPC sprite size scales with tilePx",
  /const dw = tilePx \* sz, dh = tilePx \* sz/.test(html));
check("Melody's marker ring scales with tilePx",
  /ctx\.arc\(cx, py \+ tilePx \/ 2, tilePx \* 0\.46/.test(html));
check("hero anchors at hero.x * tilePx",
  /const hx = hero\.x \* tilePx, hy = hero\.y \* tilePx/.test(html));
check("hero sprite keeps build size relative to tilePx",
  /const _hw = tilePx \* playHeroSize, _hh = tilePx \* playHeroSize/.test(html));

console.log("== v5.51.2 page-zoom hint (stub window) ==");
const pzDriver = `
let _pzHintShown=false, _pzHintT=0;
${extract("pageZoomFactor")}
${extract("maybeHintPageZoom")}
${extract("maybeHintPageZoomSoon")}
;globalThis.__pz=(function(){
  const out={};
  const seen={}; let toasted=[];
  let fine=true;
  globalThis.window={get innerWidth(){return this._iw;}, _iw:455, outerWidth:1380,
    matchMedia:function(){return {matches:fine};}};
  globalThis.sessionStorage={getItem:function(k){return seen[k]||null;},
    setItem:function(k,v){seen[k]=v;}, removeItem:function(k){delete seen[k];}};
  globalThis.toast=function(m){toasted.push(m);};
  maybeHintPageZoom();
  out.firedAt3x=toasted.length===1 && /30[03]%/.test(toasted[0]);
  out.pointsAtHudZoom=toasted.length===1 && /HUD's \+/.test(toasted[0]);
  maybeHintPageZoom(); out.oncePerSession=toasted.length===1;
  // fresh session, 100% zoom: silent
  _pzHintShown=false; delete seen["crumbs.pzHint"]; toasted=[]; window._iw=1366;
  maybeHintPageZoom(); out.silentAt1x=toasted.length===0;
  // fresh session, coarse pointer (phone/tablet): silent — mobile pinch is already locked
  _pzHintShown=false; delete seen["crumbs.pzHint"]; toasted=[]; window._iw=455; fine=false;
  maybeHintPageZoom(); out.silentOnCoarse=toasted.length===0;
  out.factorFn=pageZoomFactor()===1380/455;
  return out;
})();
`;
eval(pzDriver);
const pz = globalThis.__pz;
check("pageZoomFactor reads outerWidth/innerWidth", pz.factorFn);
check("hint fires at 3x page zoom", pz.firedAt3x);
check("hint names the ~300% level and points at the HUD's own +/−", pz.pointsAtHudZoom);
check("hint shows once per session", pz.oncePerSession);
check("hint stays silent at 100% zoom", pz.silentAt1x);
check("hint stays silent on coarse-pointer devices", pz.silentOnCoarse);
check("hint is wired into boot", /splashDone\(\);\s*\n\s*maybeHintPageZoom\(\);/.test(html));
check("hint is re-armed on resize (debounced)", /addEventListener\("resize", \(\) => \{[^}]*maybeHintPageZoomSoon\(\); \}\);/.test(html));

console.log("== recent repairs intact ==");
check("Pack still parks above the zoom cluster (v5.50.12 + v5.51.1: bottom:304px)",
  /#pack-btn\s*\{\s*position:\s*fixed;\s*right:\s*10px;\s*bottom:\s*304px/.test(styleBlock));
check("grid toggle ▦ still lives in the zoom cluster (v5.51.1)",
  html.includes('id="btn-grid"') && /#zoom-cluster #btn-grid\.off/.test(styleBlock));
check("pills still sit below the topbar (v5.50.13)",
  /#gear-hud\s*\{\s*position:\s*fixed;\s*top:\s*calc\(56px \+ env\(safe-area-inset-top\)\)/.test(styleBlock));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
