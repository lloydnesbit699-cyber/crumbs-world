#!/usr/bin/env node
// hud_pass_test.js — v5.47 HUD-pass tests.
// The one bottom sheet (state machine, heights, auto views), the budget
// strip counts, play camera/selection snapshot round-trips, NPC plain-words
// event cards, room-preset planning, patrol pin hit-testing, plus static
// assertions over editor.html for the phone contract: one sheet slot, the
// always-visible Play FAB, the retired docks, and the ghost-suggestion
// lifecycle wiring.
// Run: node hud_pass_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");
const hud = fs.readFileSync(path.join(__dirname, "crumbs_hud.py"), "utf8");
const changelog = fs.readFileSync(path.join(__dirname, "CHANGELOG.md"), "utf8");
const melody = fs.readFileSync(path.join(__dirname, "melody_agent.py"), "utf8");

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
function extractConst(name) {
  // captures the literal up to its terminating semicolon (no semicolons inside)
  const re = new RegExp("const " + name + " = ([\\s\\S]*?);");
  const m = html.match(re);
  if (!m) throw new Error("not found: const " + name);
  return m[1];
}

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

// the pure blocks — eval'd in order (later ones reference earlier consts)
const SHEET_HEIGHTS = eval(extractConst("SHEET_HEIGHTS"));
const SHEET_VIEWS = eval(extractConst("SHEET_VIEWS"));
eval(extract("sheetNextHeight"));
eval(extract("sheetAutoView"));
eval(extract("sheetPeekLine"));
const FX_CELL_BUDGET = eval(html.match(/const FX_CELL_BUDGET = (\d+);/)[1]);
const NPC_SOFT_BUDGET = eval(html.match(/const NPC_SOFT_BUDGET = (\d+);/)[1]);
eval(extract("budgetCounts"));
eval(extract("snapViewState"));
eval(extract("restoreViewState"));
eval(extract("snapSelState"));
eval(extract("restoreSelState"));
eval(extract("npcSecsWords"));
const NPC_STATE_WORDS = eval("(" + extractConst("NPC_STATE_WORDS") + ")");
eval(extract("stopWords"));
eval(extract("npcRouteSummary"));
eval(extract("roomPresetCells"));
let patrols = [];
eval(extract("patrolPinAt"));

console.log("== sheet state machine ==");
check("heights are peek/half/full",
  JSON.stringify(SHEET_HEIGHTS) === JSON.stringify(["peek", "half", "full"]));
check("height cycles", sheetNextHeight("peek") === "half" &&
  sheetNextHeight("half") === "full" && sheetNextHeight("full") === "peek");
check("unknown height recovers to peek", sheetNextHeight("bogus") === "peek");
check("views cover the panel set",
  SHEET_VIEWS.indexOf("paint") >= 0 && SHEET_VIEWS.indexOf("tiles") >= 0 &&
  SHEET_VIEWS.indexOf("inspect") >= 0 && SHEET_VIEWS.indexOf("anim") >= 0 &&
  SHEET_VIEWS.indexOf("npc") >= 0 && SHEET_VIEWS.indexOf("suggest") >= 0);
check("idle -> paint", sheetAutoView({}) === "paint");
check("suggestion wins", sheetAutoView({ suggestion: true, npc: true, inspectPos: true }) === "suggest");
check("npc beats inspect", sheetAutoView({ npc: true, inspectPos: true }) === "npc");
check("anim beats tiles", sheetAutoView({ animOpen: true, tilesOpen: true }) === "anim");
check("inspect beats tiles", sheetAutoView({ inspectPos: true, tilesOpen: true }) === "inspect");
check("tiles when a tile is picked", sheetAutoView({ tilesOpen: true }) === "tiles");
check("peek lines are one-liners",
  sheetPeekLine("paint", { layerName: "ground", brush: "brush" }).indexOf("ground") >= 0 &&
  sheetPeekLine("npc", { npcName: "Goblin", stops: 4 }) === "Goblin · 4 stops" &&
  sheetPeekLine("suggest", { label: "Walls?" }) === "Walls?");

console.log("== budget counts ==");
const grid3 = [[1, null, 2], [null, null, null], [3, 4, null]];
const b = budgetCounts({ tags: grid3, objects: [[null]], patrols: [{}, {}],
  fxIds: new Set([9]), tiles: [[9, 1], [2, 9]], undoDepth: 3, redoDepth: 1 });
check("painted counts tags", b.painted === 4, JSON.stringify(b));
check("npcs counted", b.npcs === 2);
check("fx cells counted", b.fx === 2, JSON.stringify(b));
check("under budget flags clear", !b.fxOver && !b.npcsOver);
check("undo/redo depths carried", b.undoDepth === 3 && b.redoDepth === 1);
const big = [];
for (let i = 0; i < 500; i++) big.push([9]);
const b2 = budgetCounts({ tags: [], objects: [], patrols: new Array(25),
  fxIds: new Set([9]), tiles: big });
check("fx over the soft budget flags", b2.fxOver && b2.fx === 500);
check("npcs over the soft budget flag", b2.npcsOver && b2.npcs === 25);
check("soft budgets are advisory, not zero",
  FX_CELL_BUDGET === 400 && NPC_SOFT_BUDGET === 20);
const b3 = budgetCounts({ tags: [], objects: [], fxIds: [9], tiles: [[9]] });
check("fxIds works as an array too", b3.fx === 1);

console.log("== play camera/selection snapshot ==");
const S = { panX: 10, panY: 20, tilePx: 32, manualZoom: true,
  inspectPos: { x: 1, y: 2 }, selectedInstance: { x: 3, y: 4 },
  selTile: 42, logicalLayer: "objects" };
const vs = snapViewState(S), ss = snapSelState(S);
S.panX = 999; S.tilePx = 8; S.manualZoom = false;
S.inspectPos = null; S.selectedInstance = null; S.selTile = null; S.logicalLayer = "ground";
restoreViewState(S, vs); restoreSelState(S, ss);
check("camera round-trips", S.panX === 10 && S.panY === 20 &&
  S.tilePx === 32 && S.manualZoom === true);
check("selection round-trips", S.inspectPos.x === 1 && S.inspectPos.y === 2 &&
  S.selectedInstance.x === 3 && S.selectedInstance.y === 4 &&
  S.selTile === 42 && S.logicalLayer === "objects");
const S2 = { panX: 0, panY: 0, tilePx: 16, manualZoom: false,
  inspectPos: null, selectedInstance: null, selTile: null };
const ss2 = snapSelState(S2);
S2.inspectPos = { x: 9, y: 9 }; S2.selTile = 7;
restoreSelState(S2, ss2);
check("nulls stay null", S2.inspectPos === null && S2.selTile === null);
check("snapshots are copies, not aliases",
  vs.panX === 10 && ss.inspectPos.x === 1);

console.log("== NPC plain-words cards ==");
check("pass-through stop", stopWords({ secs: 0, mode: "stand" }, 0) === "walk through");
check("wait words", stopWords({ secs: 30, mode: "stand" }, 0) ===
  "wait here: stand and look around, 30s");
check("sleep words", stopWords({ secs: 300, mode: "sleep" }, 1) ===
  "wait here: sleep, 5m");
check("state arrow", stopWords({ secs: 0, mode: "stand", state: "talk" }, 2) ===
  "at stop 3 → Talk");
check("wait + state", stopWords({ secs: 60, mode: "stand", state: "sleep" }, 0) ===
  "wait here: stand and look around, 1m → Sleep");
check("seconds formatting", npcSecsWords(90) === "1.5m" && npcSecsWords(45) === "45s");
check("route summary",
  npcRouteSummary({ points: [[0, 0], [1, 1]], pauses: [{ secs: 10 }] }) ===
  "2 stops, waits at 1 · loops back to start");
check("no raw data on the pass-through card",
  stopWords({ secs: 0 }, 0) === "walk through");

console.log("== room presets ==");
const room = roomPresetCells("dungeon_room", 10, 10, 40, 40);
check("room plans two strokes", room.strokes.length === 2);
const wall = room.strokes[0], floor = room.strokes[1];
check("wall ring 11x9 boundary minus the door", wall.cells.length === 34,
  String(wall.cells.length));
check("door gap is floor, not wall",
  wall.cells.every(c => !(c.y === 14 && (c.x === 9 || c.x === 10))) &&
  floor.cells.some(c => c.x === 9 && c.y === 14));
check("floor fills the inside", floor.cells.length === 65, String(floor.cells.length));
check("cells clipped to the map",
  roomPresetCells("dungeon_room", 0, 0, 40, 40).strokes.every(
    s => s.cells.every(c => c.x >= 0 && c.y >= 0 && c.x < 40 && c.y < 40)));
const arena = roomPresetCells("boss_arena", 20, 20, 60, 60);
check("arena is 15x13", arena.strokes[0].cells.length + arena.strokes[1].cells.length ===
  15 * 13, String(arena.strokes[0].cells.length));
check("arena has four pillar stubs",
  arena.strokes[0].cells.filter(c => c.x >= 16 && c.x <= 17 && c.y >= 17 && c.y <= 18).length === 4 &&
  arena.strokes[0].cells.filter(c => c.x >= 23 && c.x <= 24 && c.y >= 17 && c.y <= 18).length === 4);
check("arena doors north and south",
  arena.strokes[1].cells.some(c => c.y === 14 && c.x === 20) &&
  arena.strokes[1].cells.some(c => c.y === 26 && c.x === 20));

console.log("== patrol pin hit-testing ==");
patrols = [{ id: 1, points: [[2, 2], [5, 5]] }, { id: 2, points: [[8, 8]] }];
check("pin centers hit", patrolPinAt(2.5, 2.5).id === 1);
check("near a pin hits", patrolPinAt(5.7, 5.4).id === 1);
check("far away misses", patrolPinAt(0, 0) === null);
check("single-stop patrol draws no pins, none hit", patrolPinAt(8.5, 8.5) === null);
patrols = [];

console.log("== static: one sheet, retired docks, play FAB ==");
const sheetCount = (html.match(/id="hud-sheet"/g) || []).length;
check("exactly one bottom-sheet slot", sheetCount === 1, String(sheetCount));
check("sheet has peek/half/full CSS",
  html.includes("#hud-sheet.peek") && html.includes("#hud-sheet.half") &&
  html.includes("#hud-sheet.full"));
check("grab cycles heights", html.includes("sheetNextHeight(sheetHeight)"));
check("Play FAB exists", html.includes('id="btn-play-fab"'));
check("FAB hold gesture wired (550ms)", html.includes("550"));
check("budget strip exists", html.includes('id="budget-strip"'));
check("strip taps to undo", html.includes('$("budget-strip").onclick'));
check("semantic dock retired", html.includes("#sem-dock { display: none !important; }"));
check("sheet built before sem wiring",
  html.indexOf("initHudSheet();         // v5.47") <
  html.indexOf("initSemDock();          // v5.46"));
check("animation menu opens the sheet", html.includes('openSheet("anim")'));
check("tiles tab opens the sheet", html.includes('openSheet("tiles")'));
check("pin tap opens the event card", html.includes("selectNpcPatrol(pinHit)"));
check("play exit restores camera+selection", html.includes("restoreCameraSel()"));
check("status poll feeds the strip", html.includes("refreshBudget();") &&
  html.includes("suggestPoll();"));
check("ghost accept is undoable", html.includes("one tap on ↩ undoes it") ||
  html.includes("undo is one tap away"));
check("room preset buttons exist", html.includes('id="btn-room"') &&
  html.includes('id="btn-arena"'));
check("batch stroke endpoint used", hud.includes('"/api/semantic/stroke"') &&
  hud.includes('"strokes"'));
check("server version bumped", hud.includes('APP_VERSION = "5.47.3"'));
check("changelog has 5.47.3", changelog.includes("5.47.3"));

console.log("== animation ghost (v5.47.1) ==");
// stubs for the ghost lifecycle: the merge is real, the plumbing is fake
let customById = {};
let beginnerMagic = "#ffd75f";
let animGhost = null;
function mirrorLegacyFx(t) { t._mirrored = true; }
function rebuildFxOnMap() {}
function queueRender() {}
const ANIM_PRESETS = eval("(" + extractConst("ANIM_PRESETS") + ")");
const animABBefore = eval("new Map()");
eval(extract("mergeBeginnerPreset"));
eval(extract("applyAnimGhost"));
eval(extract("clearAnimGhost"));
{
  const tile = { id: 7, name: "Torch", frames: ["f1"], anim: null };
  customById = { 7: tile };
  const sug = { kind: "animation_preset", preset: "pulse",
                target: { tile_id: 7, tile_name: "Torch", x: 4, y: 4 } };
  check("ghost applies", applyAnimGhost(sug) === true);
  check("ghost merges the preset motion",
    !!(tile.anim && tile.anim.states && Object.keys(tile.anim.states).length),
    JSON.stringify(tile.anim && tile.anim.states));
  check("before snapshot kept", animABBefore.has(7) && animABBefore.get(7) === null);
  check("ghost tracked unaccepted",
    !!(animGhost && animGhost.tileId === 7 && animGhost.accepted === false));
  check("bad preset refuses",
    applyAnimGhost({ preset: "explode", target: { tile_id: 7 } }) === false);
  check("missing tile refuses",
    applyAnimGhost({ preset: "pulse", target: { tile_id: 999 } }) === false);
  clearAnimGhost(true);
  check("decline reverts byte-identical", tile.anim === null);
  check("ghost cleared", animGhost === null);
  applyAnimGhost(sug);
  animGhost.accepted = true;
  clearAnimGhost(true);
  check("accepted ghost is NOT reverted by clear",
    tile.anim !== null && animGhost === null);
  check("server knows the preset catalog",
    hud.includes('"pulse": "Pulse"') && hud.includes('"magic": "Magic Aura"'));
  check("melody validates the preset",
    melody.includes('"alive", "bounce", "float", "pulse", "shake", "magic"'));
  check("tool schema carries the preset arg", melody.includes('"preset"'));
  check("card offers a motion revert", html.includes("revertAnimSuggestion"));
  check("manual edits retire the revert card",
    html.includes("animRevert = null;   // v5.47.1"));
}

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
