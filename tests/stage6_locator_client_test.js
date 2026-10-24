#!/usr/bin/env node
// stage6_locator_client_test.js — Stage 6 (§19): the Melody-build locator.
// Lloyd's ruling: a COMMISSIONED Melody build gets a temporary event pin —
// visible at every view level, jumpable — while her autonomous builds are
// never pinned. These tests pin the split, the marker's freedom from the
// shrine WORLD gate, the jump behavior per mode, and the list rules.
// Run: node stage6_locator_client_test.js
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}
function extract(name) {
  let start = html.indexOf("async function " + name + "(");
  if (start < 0) start = html.indexOf("function " + name + "(");
  if (start < 0) throw new Error("not found: " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(start, j + 1); }
  }
  throw new Error("unbalanced braces in " + name);
}

// ---------------------------------------------------------------------------
console.log("== the furniture: list lives in Melody's workshop ==");
check("locator list element in the workshop sheet", /id="melody-locator"/.test(html));
check("clear-all button wired to locatorClear",
  /id="melody-locator-clear"/.test(html) && html.includes('$("melody-locator-clear").onclick = () => locatorClear();'));
check("workshop open paints the list", /locatorPaint\(\);   \/\/ Stage 6/.test(html));
check("the top pill row (§18) gained no locator furniture",
  !/id="[^"]*(pill[^"]*locator|locator[^"]*pill)/.test(html));

console.log("== producers: every completion point passes the commission ==");
check("designer room pins its center, commissioned",
  /locatorAdd\(\{ label: roomStyle \+ " room", x: x \+ Math\.floor\(w \/ 2\), y: y \+ Math\.floor\(h \/ 2\), kind: "design-room", commissioned: true \}\)/.test(html));
check("designer populate pins its center, commissioned",
  /locatorAdd\(\{ label: "populated area", x: cx, y: cy, kind: "design-populate", commissioned: true \}\)/.test(html));
check("an accepted ghost pins where it landed, commissioned",
  /locatorSuggestionSpot\(g\)/.test(html) &&
  /kind: "suggestion-" \+ g\.kind, commissioned: true/.test(html));
check("mission apply pins its first objective, commissioned",
  /kind: "mission", commissioned: true/.test(html));

console.log("== the split: no commission, no pin (behavioral) ==");
function fakeEl() {
  const el = { children: [], className: "", title: "",
    appendChild(c) { this.children.push(c); return c; } };
  let txt = "";
  Object.defineProperty(el, "textContent", {
    get: () => txt,
    set: v => { txt = v; if (v === "") el.children = []; },   // DOM semantics
  });
  return el;
}
function makeEnv() {
  const store = {};
  const calls = { render: 0, toast: [], goMode: [], lensCamSet: null };
  const box = fakeEl();
  const env = new Function("store", "calls", "box", "fakeEl", `
    let locatorPins = [], locatorStamp = 0;
    const LOCATOR_CAP = 12, LOCATOR_MARKER_PX = 18;
    let W = 100, H = 80, tilePx = 20, panX = 0, panY = 0;
    let playMode = false, hero = { x: 5, y: 5 }, playWaypoint = null;
    let inRegion = false, inLens = false, lensCam = { x: 0, y: 0 };
    const localStorage = {
      getItem: k => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
    };
    const document = {
      getElementById: id => (id === "melody-locator" ? box : null),
      createElement: () => fakeEl(),
    };
    const queueRender = () => {}, render = () => { calls.render++; };
    const toast = m => calls.toast.push(m);
    const clampPan = () => {};
    const playRegionOn = () => inRegion, lensRegionOn = () => inLens;
    const playGoMode = n => calls.goMode.push(n);
    const skyPaint = () => {};
    const lensClampCam = (c) => { calls.lensCamSet = c; return c; };
    const waypointInfo = (h, wp) => ({ dist: Math.round(Math.hypot(wp.x - h.x, wp.y - h.y)), ang: 0 });
    const suggestRoomCells = g => g._cells || [];
    ${extract("locatorSave")}
    ${extract("locatorForMap")}
    ${extract("locatorAdd")}
    ${extract("locatorDismiss")}
    ${extract("locatorClear")}
    ${extract("locatorPaint")}
    ${extract("locatorJump")}
    ${extract("locatorCentroid")}
    ${extract("locatorSuggestionSpot")}
    return {
      locatorAdd, locatorDismiss, locatorClear, locatorJump, locatorSuggestionSpot,
      pins: () => locatorPins, mapPins: () => locatorForMap(), stamp: () => locatorStamp,
      setMap: (w, h) => { W = w; H = h; },
      setMode: (region, lens) => { inRegion = region; inLens = lens; playMode = region; },
      cam: () => [panX, panY], hero: () => hero, wp: () => playWaypoint,
    };`)(store, calls, box, fakeEl);
  return { env, store, calls, box };
}
{
  const { env, store } = makeEnv();
  check("a commissioned build creates a pin",
    env.locatorAdd({ label: "tavern room", x: 40, y: 30, kind: "design-room", commissioned: true }) === true &&
    env.mapPins().length === 1);
  const p = env.mapPins()[0];
  check("the pin carries label, coords, timestamp and the commissioned flag",
    p.label === "tavern room" && p.x === 40 && p.y === 30 &&
    typeof p.at === "number" && p.commissioned === true);
  check("the pin persists to localStorage",
    (JSON.parse(store["crumbs_locator"] || "[]")).length === 1);
  check("an autonomous build (commissioned:false) creates NO pin",
    env.locatorAdd({ label: "her own cottage", x: 1, y: 1, kind: "roam", commissioned: false }) === false &&
    env.mapPins().length === 1);
  check("a build with the flag missing creates NO pin",
    env.locatorAdd({ label: "flagless", x: 2, y: 2, kind: "roam" }) === false &&
    env.mapPins().length === 1);
  check("a build with no coords creates NO pin",
    env.locatorAdd({ label: "nowhere", commissioned: true }) === false &&
    env.mapPins().length === 1);
}
{
  const { env } = makeEnv();
  for (let i = 0; i < 14; i++)
    env.locatorAdd({ label: "build " + i, x: i, y: i, commissioned: true });
  check("the list caps at LOCATOR_CAP (12)", env.pins().length === 12,
    "kept " + env.pins().length);
  check("the cap drops the OLDEST pins",
    env.pins()[0].label === "build 13" && env.pins()[11].label === "build 2");
  const id = env.pins()[0].id;
  env.locatorDismiss(id);
  check("dismiss removes exactly that pin",
    env.pins().length === 11 && !env.pins().some(q => q.id === id));
  env.setMap(50, 50);
  env.locatorAdd({ label: "other map build", x: 9, y: 9, commissioned: true });
  check("pins are scoped per map (list follows the current map)",
    env.mapPins().length === 1 && env.mapPins()[0].label === "other map build");
  env.locatorClear();
  check("clear-all clears this map's pins only",
    env.mapPins().length === 0 && env.pins().length === 11);
}

console.log("== jump: the view goes, the hero never teleports ==");
{
  const { env, calls, box } = makeEnv();
  env.locatorAdd({ label: "chapel room", x: 40, y: 30, commissioned: true });
  const id = env.mapPins()[0].id;
  check("the painted list shows one row per pin, label + coords on it",
    box.children.length === 1 &&
    box.children[0].children[0].children[0].textContent.includes("chapel room") &&
    box.children[0].children[0].children[1].textContent.includes("(40, 30)"));
  box.children[0].children[2].onclick();   // the row's ✕ button
  check("the row's ✕ dismisses its pin", env.mapPins().length === 0);
  env.locatorAdd({ label: "chapel room", x: 40, y: 30, commissioned: true });
  box.children[0].children[1].onclick();   // the row's Go button (Build mode)
  check("the row's Go button jumps the view",
    env.cam()[0] === (100 / 2 - 40.5) * 20 && env.cam()[1] === (80 / 2 - 30.5) * 20);
  const id2 = env.mapPins()[0].id;
  env.setMode(false, false);   // Build stage
  env.locatorJump(id2);
  check("Build jump centers the stage camera on the pin",
    env.cam()[0] === (100 / 2 - 40.5) * 20 && env.cam()[1] === (80 / 2 - 30.5) * 20,
    "pan=" + env.cam());
  check("Build jump re-renders", calls.render >= 1);
  env.setMode(false, true);    // Build, full-screen lens
  env.locatorJump(id2);
  check("lens jump moves lensCam to the pin",
    calls.lensCamSet && calls.lensCamSet.x === 40.5 && calls.lensCamSet.y === 30.5);
  env.setMode(true, false);    // Play
  const heroBefore = JSON.stringify(env.hero());
  env.locatorJump(id2);
  check("Play jump sets the waypoint on the pin (compass guidance)",
    env.wp() && env.wp().x === 40 && env.wp().y === 30 && env.wp().locator === id2);
  check("Play jump pops the view to WORLD so the pin is on screen",
    calls.goMode.includes("world"));
  check("Play jump NEVER moves the hero (travel is shrines-only)",
    JSON.stringify(env.hero()) === heroBefore);
  check("jumping a dead pin id is a no-op", (() => {
    const before = calls.toast.length;
    env.locatorJump("loc-nope");
    return calls.toast.length === before;
  })());
}

console.log("== suggestion spots: where an accepted ghost landed ==");
{
  const { env } = makeEnv();
  check("patrol draft pins its anchor",
    JSON.stringify(env.locatorSuggestionSpot({ kind: "patrol_draft", anchor_xy: [7, 9] })) === "[7,9]");
  check("room draft pins the centroid of the cells it painted",
    JSON.stringify(env.locatorSuggestionSpot({ kind: "room_draft", _cells: [{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 0, y: 2 }, { x: 2, y: 2 }] })) === "[1,1]");
  check("wall ring pins the centroid of its [x,y] cells",
    JSON.stringify(env.locatorSuggestionSpot({ kind: "wall_ring", cells: [[10, 10], [12, 10]] })) === "[11,10]");
  check("animation preset pins NOTHING (a tile type's motion has no one tile)",
    env.locatorSuggestionSpot({ kind: "animation_preset" }) === null);
  check("an unknown kind pins nothing",
    env.locatorSuggestionSpot({ kind: "whatever" }) === null);
}

console.log("== markers: every level, and NOT the shrine treatment ==");
{
  const markers = extract("drawLocatorMarkers");
  check("the region marker has NO mode gate (no playModeName, no WORLD test)",
    !/playModeName/.test(markers) && !/"WORLD"/.test(markers));
  const shrines = extract("drawShrines");
  check("the shrine gate is untouched by contrast (badges stay WORLD-only)",
    /playModeName\(\) !== "WORLD"/.test(shrines));
  check("render() calls the marker draw in the overlay pass, ungated",
    /if \(rgActive\) drawLocatorMarkers\(\);/.test(html) &&
    !/playModeName\(\)[^\n]*drawLocatorMarkers/.test(html));
  check("the Build stage draws the same pins in map coords",
    /if \(!rgActive\) drawLocatorStage\(\);/.test(html));
  check("the pin is a diamond, not the shrine circle badge",
    extract("locatorDiamond").includes("rotate(Math.PI / 4)") &&
    /LOCATOR_MARKER_PX = 18/.test(html));
  check("the marker is static — no pulse, no render-loop hook",
    !/queueRender/.test(markers) && !/performance\.now/.test(markers));
  check("the small lens repaints on pin changes (stamp in its cache key)",
    /\[lensWorldStamp, locatorStamp,/.test(html));
  check("the small lens draws pins inside its window",
    /Stage 6 \(§19\): locator pins inside the lens window/.test(html));
}
{
  // Behavioral: the diamond actually lands on the canvas in region space,
  // under each of the four ladder modes (the draw never consults the mode,
  // so simulate all four contexts and require a draw in every one).
  const draws = [];
  const ctxStub = {
    save() {}, restore() {}, translate() {}, rotate() {}, beginPath() {},
    arc() {}, fill() { draws.push("fill"); }, strokeRect() { draws.push("strokeRect"); },
    fillRect() { draws.push("fillRect"); }, set fillStyle(v) {}, set strokeStyle(v) {},
    set lineWidth(v) {}, set globalAlpha(v) {},
  };
  const env = new Function("ctxStub", `
    let locatorPins = [{ id: "a", label: "tavern room", x: 10, y: 10, at: 1, commissioned: true, w: 100, h: 80 }];
    let W = 100, H = 80, rgActive = true, rgOx = 0, rgOy = 0, rgScale = 1, tilePx = 8;
    const ctx = ctxStub, canvas = { width: 800, height: 640 };
    const LOCATOR_MARKER_PX = 18;
    let modeName = "GROUND";
    ${extract("locatorForMap")}
    ${extract("locatorDiamond")}
    ${extract("drawLocatorMarkers")}
    return { draw: () => drawLocatorMarkers(), setMode: m => { modeName = m; } };`)(ctxStub);
  for (const m of ["GROUND", "FIRST", "SURVEY", "WORLD"]) {
    draws.length = 0;
    env.setMode(m);
    env.draw();
    check("marker draws at " + m, draws.includes("fillRect") && draws.includes("fill"));
  }
}

console.log(`\nstage6_locator_client_test: ${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
