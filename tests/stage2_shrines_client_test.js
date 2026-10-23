#!/usr/bin/env node
// stage2_shrines_client_test.js — Stage 2 (§15, Ball Room item 11):
// shrine badges render in WORLD view only, at a fixed sane screen size.
// Discovery rules (full / dim / hidden) are unchanged — shrines_client_test.js
// still owns those; this suite owns WHERE and HOW BIG the badge draws.
// Run: node stage2_shrines_client_test.js
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
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}

const consts = (html.match(/^const PLAY_[^\n]*$/gm) || []).join("\n") + "\n" +
               (html.match(/^const SHRINE_[^\n]*$/gm) || []).join("\n");
const preamble = `
let playMode = true, buildBreak = false, hero = { x: 2, y: 2 }, W = 500, H = 500;
let lensFull = false, tiles = new Array(600);
let playFirst = false, playN = 500, playHeroSize = 1, tilePx = 2;
let rgActive = true, rgScale = 1, rgOx = 0, rgOy = 0;
let shrineList = [], shrineUn = new Set(["star_beacon"]),
    shrineDisc = new Set(["star_beacon", "tide_mermaid"]);
let stage = { clientWidth: 1000, clientHeight: 1000 };
let canvas = { width: 1000, height: 1000 };
let draws = [];
let ctx = {
  globalAlpha: 1, fillStyle: "", font: "", textAlign: "", textBaseline: "",
  save() {}, restore() {}, beginPath() {}, fill() {},
  arc(x, y, r) { draws.push({ type: "arc", r, alpha: this.globalAlpha }); },
  fillText(t, x, y) { draws.push({ type: "text", text: t, x, y, font: this.font, alpha: this.globalAlpha }); }
};
`;
const body = preamble + consts + "\n" +
  ["shrineState", "playWorldN", "playSurveyN", "playModeTargets", "playHeroTiles",
   "playRegionOn", "playModeName", "lensRegionOn", "drawShrines"].map(extract).join("\n") + `
return { drawShrines, playModeName, SHRINE_MARKER_PX,
  set(o) {
    if ("playN" in o) playN = o.playN;
    if ("playFirst" in o) playFirst = o.playFirst;
    if ("playMode" in o) playMode = o.playMode;
    if ("lensFull" in o) lensFull = o.lensFull;
    if ("tilePx" in o) tilePx = o.tilePx;
    if ("rgScale" in o) rgScale = o.rgScale;
    if ("shrineList" in o) shrineList = o.shrineList;
  },
  clear() { draws = []; },
  texts() { return draws.filter(d => d.type === "text"); },
  arcs() { return draws.filter(d => d.type === "arc"); } };`;
const S = new Function(body)();

const SHRINES = [
  { id: "star_beacon", name: "Star Beacon", icon: "⭐", x: 2, y: 2 },
  { id: "tide_mermaid", name: "Tide Mermaid", icon: "🧜", x: 3, y: 2 },
  { id: "frost_reaper", name: "Frost Reaper", icon: "❄", x: 4, y: 2 },
];
// 500x500 map, aspect 1, hero 1 tile -> world target N = 500, survey 64, ground 6.
function run(mode) {
  S.clear();
  if (mode === "WORLD") S.set({ playN: 500, playFirst: false });
  if (mode === "ALTITUDE") S.set({ playN: 200, playFirst: false });
  if (mode === "SURVEY") S.set({ playN: 64, playFirst: false });
  if (mode === "GROUND") S.set({ playN: 6, playFirst: false });
  if (mode === "FIRST") S.set({ playN: 4, playFirst: true });
  S.drawShrines();
  return S.texts();
}

console.log("== the harness drives the real mode ladder ==");
S.set({ shrineList: SHRINES });
S.set({ playN: 500, playFirst: false }); check("N=world reads WORLD", S.playModeName() === "WORLD", S.playModeName());
S.set({ playN: 200 }); check("between survey and world reads ALTITUDE", S.playModeName() === "ALTITUDE", S.playModeName());
S.set({ playN: 64 }); check("N=survey reads SURVEY", S.playModeName() === "SURVEY", S.playModeName());
S.set({ playN: 6 }); check("N=ground reads GROUND", S.playModeName() === "GROUND", S.playModeName());
S.set({ playFirst: true }); check("playFirst reads FIRST", S.playModeName() === "FIRST", S.playModeName());
S.set({ playFirst: false });

console.log("== badges render in WORLD view only ==");
check("GROUND: no badge glyphs", run("GROUND").length === 0);
check("FIRST: no badge glyphs", run("FIRST").length === 0);
check("SURVEY: no badge glyphs", run("SURVEY").length === 0);
check("ALTITUDE (between survey and world): no badge glyphs", run("ALTITUDE").length === 0);

console.log("== WORLD keeps the discovery rules ==");
const w = run("WORLD");
check("WORLD: discovered shrines draw (full + dim), hidden does not",
  w.length === 2 && w[0].text === "⭐" && w[1].text === "🧜",
  JSON.stringify(w.map(t => t.text)));
check("WORLD: unlocked shrine is full alpha", w.length === 2 && w[0].alpha === 1);
check("WORLD: discovered-but-locked shrine is dimmed", w.length === 2 && w[1].alpha === 0.4);

console.log("== sane size: fixed screen size, never tile-scaled ==");
check("glyph font is SHRINE_MARKER_PX at rgScale 1",
  w.length === 2 && w.every(t => t.font === Math.round(S.SHRINE_MARKER_PX) + "px sans-serif"),
  w.length ? w[0].font : "no draws");
check("badge backer circle is 0.62 of the fixed size",
  S.arcs().length === 2 && Math.abs(S.arcs()[0].r - S.SHRINE_MARKER_PX * 0.62) < 1e-9);
S.set({ tilePx: 80 });   // ground-level tile size; WORLD gate already passed at N=500
S.clear(); S.drawShrines();
check("tilePx does not change the badge size",
  S.texts().length === 2 && S.texts().every(t => t.font === Math.round(S.SHRINE_MARKER_PX) + "px sans-serif"));
S.set({ tilePx: 2, rgScale: 2 });
S.clear(); S.drawShrines();
check("the only scaling left is the canvas backing scale (like every screen-space draw)",
  S.texts().length === 2 && S.texts().every(t => t.font === Math.round(S.SHRINE_MARKER_PX * 2) + "px sans-serif"));
S.set({ rgScale: 1 });
check("the old tile-scaled size formula is gone from the source",
  !/Math\.max\(tilePx \* 2, 20\)/.test(html));

console.log("== the Build (dev) World lens keeps its badges (Lloyd's ruling) ==");
S.set({ playMode: false, lensFull: true });   // Build, lens open: mode name is ""
check("Build lens: mode name is empty outside Play", S.playModeName() === "");
S.clear(); S.drawShrines();
check("Build lens: discovered badges still draw (owner's workbench)",
  S.texts().length === 2, JSON.stringify(S.texts().map(t => t.text)));
S.set({ lensFull: false });                    // Build, lens closed
S.clear(); S.drawShrines();
check("Build without the lens: no badges", S.texts().length === 0);
S.set({ playMode: true });

console.log(PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
