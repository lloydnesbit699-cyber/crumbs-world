#!/usr/bin/env node
// lens_full_client_test.js — full-screen world lens (own zoom + camera).
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");
function extract(name) {
  const start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces in " + name);
}
let PASS = 0, FAIL = 0;
function check(name, cond) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name); }
}
const consts = "const LENS_PX_MIN = 6, LENS_PX_MAX = 160, LENS_PX_DEFAULT = 28;\n";
const L = new Function(consts + ["lensClampPx", "lensZoomAt", "lensClampCam"].map(extract).join("\n") +
  "\nreturn {lensClampPx,lensZoomAt,lensClampCam};")();

console.log("== pure helpers ==");
check("px clamps to range", L.lensClampPx(1) === 6 && L.lensClampPx(999) === 160 && L.lensClampPx(40.4) === 40);
check("bad px falls back to default", L.lensClampPx(NaN) === 28);
const cam = { x: 50, y: 40 };
let z = L.lensZoomAt(cam, 20, 40, 400, 300, 800, 600);
check("zoom about center keeps camera", Math.abs(z.cam.x - 50) < 1e-9 && Math.abs(z.cam.y - 40) < 1e-9 && z.px === 40);
z = L.lensZoomAt(cam, 20, 40, 100, 80, 800, 600);
const wBefore = 50 - 400 / 20 + 100 / 20, wAfter = z.cam.x - 400 / 40 + 100 / 40;
check("point under cursor stays fixed", Math.abs(wBefore - wAfter) < 1e-9);
check("camera clamps to map", JSON.stringify(L.lensClampCam({ x: -5, y: 99 }, 64, 48)) === '{"x":0,"y":48}');

console.log("== wiring ==");
check("region renderer serves the lens", /playRegionOn\(\) \|\| lensRegionOn\(\)/.test(html));
check("lens needs Build mode", /function lensRegionOn\(\) \{ return lensFull && !playMode/.test(html));
check("zoom +/- routes to lens", /if \(lensRegionOn\(\)\) \{ lensZoomBy\(/.test(html));
check("wheel routes to lens", /if \(lensRegionOn\(\)\) \{\s*\/\/ ?full-screen lens|lensRegionOn\(\)\) \{\s+\/\/ full-screen lens: wheel/.test(html));
check("Fit in the lens fits the whole map (Lloyd's ruling 2026-10-23: Fit means fit, same as key 4)", /zoom-fit"\)\.onclick = \(\) => \{ if \(lensRegionOn\(\)\) \{ lensGoBand\("world"\)/.test(html));
check("drag does NOT pan the lens camera (§17 item 16: keys pan the lens)", !/lensCam = lensClampCam\(\{ x: panStart\.cx/.test(html) && /lensPanBy\(/.test(html));
check("toggle button + L/Esc keys (Esc cancels a grab first, §17 Stage 5)", /id="lens-full-toggle"/.test(html) && /case "l": case "L"/.test(html) && /case "Escape": if \(moveArmed\) cancelGrab\(\); else if \(lensFull\)/.test(html));
check("small magnifier yields to full lens", /if \(lensFull \|\| !LENS_ENABLED/.test(html));
check("Play start leaves the lens", /if \(lensFull && playMode\) lensLeave\(\);/.test(html));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
