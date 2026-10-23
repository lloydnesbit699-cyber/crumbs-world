#!/usr/bin/env node
// lens_range_client_test.js — Stage 3 (§16.1, item 12): the Build lens gets
// Play's altitude range — ground level for detailing, high for layout — as an
// extended continuous range plus named stops on Play's ladder words.
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
// The REAL range constants, parsed from the source (not re-declared here, so
// this suite fails if the shipped range ever shrinks back).
const cm = html.match(/const LENS_PX_MIN = ([\d.]+), LENS_PX_MAX = ([\d.]+), LENS_PX_DEFAULT = ([\d.]+);/);
check("lens range constants present in source", !!cm);
const PX_MIN = +cm[1], PX_MAX = +cm[2], PX_DEF = +cm[3];
const consts = "const LENS_PX_MIN = " + PX_MIN + ", LENS_PX_MAX = " + PX_MAX + ", LENS_PX_DEFAULT = " + PX_DEF + ";\n" +
  "const PLAY_GROUND_N = 6, PLAY_FLOOR_N = 4;\n";
const L = new Function(consts +
  ["playSurveyN", "playWorldN", "playModeTargets", "lensClampPx", "lensZoomAt", "lensBandPx", "lensBandName"]
    .map(extract).join("\n") +
  "\nreturn {playSurveyN,playWorldN,playModeTargets,lensClampPx,lensZoomAt,lensBandPx,lensBandName};")();

// Reference stage/map used throughout: desktop editor 1600x900, the game's
// real map size (the world generates at up to MAP_MAX = 500 tiles square).
const SW = 1600, SH = 900, MW = 500, MH = 500;

console.log("== the range itself ==");
check("range reaches layout height (min is 1px)", PX_MIN === 1);
check("range reaches detailing scale (max is 256px)", PX_MAX === 256);
check("default unchanged at 28px", PX_DEF === 28);
check("clamp enforces both ends", L.lensClampPx(0.2) === 1 && L.lensClampPx(9999) === 256);
check("bad px still falls back to default", L.lensClampPx(NaN) === 28);

console.log("== low end: WORLD / layout ==");
const fitPx = L.lensBandPx("world", SW, SH, MW, MH);
check("world stop is the true fit (900/500 = 1.8px)", fitPx === 1.8);
check("world fit actually fits the whole map", SW / fitPx >= MW && SH / fitPx >= MH);
check("at min px the full 500-tile map fits the stage", SH / PX_MIN >= MH && SW / PX_MIN >= MW);
check("sub-6 fit is not rounded past the map edge", L.lensClampPx(1.8) === 1.8);

console.log("== high end: GROUND / detailing ==");
const gPx = L.lensBandPx("ground", SW, SH, MW, MH);
check("ground stop = Play GROUND scale (stageH/6)", gPx === SH / 6 && gPx === 150);
check("at ground stop the stage shows 6 tiles down, like Play", SH / gPx === 6);
check("ground scale reachable on a tall stage too (1440/6 = 240 <= max)", L.lensBandPx("ground", 2560, 1440, MW, MH) === 240);
check("at max px the view is at/past GROUND detailing (<=6 tiles down)", SH / PX_MAX <= 6);

console.log("== mid-range behaves as before ==");
check("whole-pixel rounding unchanged at normal zooms", L.lensClampPx(40.4) === 40 && L.lensClampPx(28) === 28);
const cam = { x: 250, y: 250 };
const z = L.lensZoomAt(cam, 28, 56, 800, 450, SW, SH);
check("zoom about center keeps camera at default zoom", Math.abs(z.cam.x - 250) < 1e-9 && Math.abs(z.cam.y - 250) < 1e-9 && z.px === 56);
const zf = L.lensZoomAt(cam, 28, fitPx, 800, 450, SW, SH);
check("zoom-to-fit about center keeps camera and lands exact", Math.abs(zf.cam.x - 250) < 1e-9 && zf.px === 1.8);
const sPx = L.lensBandPx("survey", SW, SH, MW, MH);
check("survey stop = Play SURVEY scale (stageH/64 for a wide map)", sPx === Math.round(SH / 64) && SH / sPx > 60 && SH / sPx < 68);
check("band px fall back to default without a stage/map", L.lensBandPx("world", 0, 0, 0, 0) === 28);

console.log("== ladder labels (playModeName's tolerances, lens terms) ==");
check("fit zoom reads WORLD", L.lensBandName(fitPx, SW, SH, MW, MH) === "WORLD");
check("ground stop reads GROUND", L.lensBandName(gPx, SW, SH, MW, MH) === "GROUND");
check("survey stop reads SURVEY", L.lensBandName(sPx, SW, SH, MW, MH) === "SURVEY");
check("the old default 28px reads SURVEY on a desktop stage", L.lensBandName(28, SW, SH, MW, MH) === "SURVEY");
check("between bands reads as plain altitude (no label)", L.lensBandName(8, SW, SH, MW, MH) === "");
check("band name needs a real zoom/stage", L.lensBandName(0, SW, SH, MW, MH) === "" && L.lensBandName(28, 0, 0, MW, MH) === "");

console.log("== wiring ==");
check("keys 2/3/4 jump the lens bands (Play's digits, Play's words)",
  /case "2": if \(activePlay\) playGoMode\("ground"\); else if \(lensRegionOn\(\)\) lensGoBand\("ground"\)/.test(html) &&
  /case "3": if \(activePlay\) playGoMode\("survey"\); else if \(lensRegionOn\(\)\) lensGoBand\("survey"\)/.test(html) &&
  /case "4": if \(activePlay\) playGoMode\("world"\); else if \(lensRegionOn\(\)\) lensGoBand\("world"\)/.test(html));
check("key 1 stays Play-only (FIRST has no lens analogue)", !/lensGoBand\("first"\)/.test(html));
check("lensGoBand goes through lensSetPx + band px", /function lensGoBand\(band\) \{\s*if \(!lensRegionOn\(\)\) return;\s*lensSetPx\(lensBandPx\(/.test(html));
check("badge names the band", /lensBandName\(lensPx, stage\.clientWidth, stage\.clientHeight, W, H\)/.test(html));
check("Fit still resets lens zoom to default (guarded behavior, lens_full suite)",
  /zoom-fit"\)\.onclick = \(\) => \{ if \(lensRegionOn\(\)\) \{ lensSetPx\(LENS_PX_DEFAULT\)/.test(html));
check("zoom +/- still routes to the lens", /if \(lensRegionOn\(\)\) \{ lensZoomBy\(/.test(html));

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
