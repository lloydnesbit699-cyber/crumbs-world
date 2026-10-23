#!/usr/bin/env node
// World lens v1 tests: bounded cell window and event-driven data rendering.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

function extract(name) {
  const start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  const brace = html.indexOf("{", start); let depth = 0;
  for (let i = brace; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}" && --depth === 0) return html.slice(start, i + 1);
  }
  throw new Error("unbalanced function: " + name);
}

let pass = 0, fail = 0;
function check(name, condition, detail) {
  if (condition) { pass++; console.log("  ok: " + name); }
  else { fail++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

let W = 500, H = 500;
let worldLens = { fx: 250, fy: 250, px: 20 };
eval(extract("lensWindow"));

console.log("== bounded lens window ==");
let win = lensWindow(520, 380);
check("500x500 max-size lens never exceeds 26x19 cells",
  win.width <= 26 && win.height <= 19 && win.width * win.height <= 26 * 19,
  JSON.stringify(win));
worldLens.fx = 0; worldLens.fy = 0;
win = lensWindow(520, 380);
check("top-left focus clamps to map edge", win.x0 === 0 && win.y0 === 0,
  JSON.stringify(win));
worldLens.fx = 499; worldLens.fy = 499;
win = lensWindow(520, 380);
check("bottom-right focus clamps to map edge", win.x1 === 499 && win.y1 === 499,
  JSON.stringify(win));
W = 25; H = 15; worldLens.fx = 12; worldLens.fy = 7;
win = lensWindow(520, 380);
check("lens larger than map returns the whole map", win.x0 === 0 && win.y0 === 0 &&
  win.x1 === 24 && win.y1 === 14, JSON.stringify(win));

console.log("== rendering and lifecycle contract ==");
const paint = extract("paintLens");
check("lens reads tile data at its own pixel size", /tileFrameImage\(id\)[\s\S]*drawImage\(im, p\.x, p\.y, S, S\)/.test(paint));
check("lens never magnifies the main or cached canvas", !/drawImage\(\s*(?:canvas|baseCv)/.test(paint));
check("lens work is attached to render()", /paintLens\(\);\s*\/\/ v6\.1/.test(html));
check("render queue remains the only lens scheduler", !/setInterval|setTimeout|requestAnimationFrame/.test(paint));
check("lens failure is isolated from the main renderer", /catch \(err\)[\s\S]*worldLens\.on = false[\s\S]*lens unavailable/.test(paint));
check("lens detail is fixed at 20px in v1", /worldLens\.px = 20; \/\/ fixed readable detail in v1/.test(html));
check("hero renders at its selected size in the lens", /drawPerson\(hero\.x, hero\.y,[\s\S]*playHeroSize/.test(paint));
check("lens position and size persist per device", /crumbs_world_lens/.test(html) && /localStorage\.setItem\(WORLD_LENS_PREF_KEY/.test(html));
check("build focus follows hero/selection, never the pointer (§17 item 15)", !/worldLens\.pointer/.test(html) && /function updateWorldLensFocus/.test(html));
check("lens passes Ctrl-wheel through to the main zoom handler", /panel\.addEventListener\("wheel", onCanvasWheel/.test(html));
check("lens frame drag and resize clamp within the stage", /function clampLensPanel[\s\S]*stage\.getBoundingClientRect\(\)/.test(html) && /world-lens-resize/.test(html));
check("lens previews remain read-only and paint from data", /drawGhostCell\(c, cell\.pv/.test(paint) && /pointer-events:\s*none/.test(html.slice(html.indexOf("#world-lens {"), html.indexOf("#world-lens\[hidden\]"))));
const styleBlock = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
check("lens canvas lets map pointer input pass through", /#world-lens\s*\{[^}]*pointer-events:\s*none/.test(styleBlock));
check("only the draggable lens frame receives pointer input", /#world-lens-head\s*\{[^}]*pointer-events:\s*auto/.test(styleBlock));
check("lens furniture clamps to the stage on resize", /function clampLensPanel\([\s\S]*stage\.getBoundingClientRect\(\)/.test(html) && /window\.addEventListener\("resize", \(\) => \{[\s\S]{0,180}clampLensPanel/.test(html));

console.log(`\n${pass} passed, ${fail} failed`);
process.exitCode = fail ? 1 : 0;
