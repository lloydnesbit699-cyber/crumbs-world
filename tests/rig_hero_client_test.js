#!/usr/bin/env node
// rig_hero_client_test.js — v6.3 hero facing + action animation through the rig.
// Run: node rig_hero_client_test.js
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
const line = n => html.match(new RegExp("^const " + n + " = [^\\n]*$", "m"))[0];
const body = ["RIG_DIRS", "RIG_CORE_ACTIONS", "RIG_FALLBACK", "RIG_SHEET_ROWS"].map(line).join("\n") + "\n" +
  ["rigDirFromFacing", "heroActionFor", "rigAutoRows", "ensureRig", "rigClip", "rigFrameIdx", "rigAddCore"].map(extract).join("\n") +
  "\nreturn {rigDirFromFacing,heroActionFor,rigAutoRows,ensureRig,rigClip,rigFrameIdx,rigAddCore};";
const R = new Function(body)();

console.log("== facing ==");
check("up/down/left/right", R.rigDirFromFacing({ dx: 0, dy: -1 }) === "up" && R.rigDirFromFacing({ dx: 0, dy: 1 }) === "down" &&
  R.rigDirFromFacing({ dx: -1, dy: 0 }) === "left" && R.rigDirFromFacing({ dx: 1, dy: 0 }) === "right");
check("null facing is down", R.rigDirFromFacing(null) === "down");

console.log("== action choice ==");
check("swim beats everything", R.heroActionFor(true, false, true, 10) === "swim" && R.heroActionFor(false, true, false, 10) === "swim");
check("recent step walks", R.heroActionFor(false, false, false, 100) === "walk");
check("recent step with run gear runs", R.heroActionFor(false, false, true, 100) === "run");
check("stopped is idle", R.heroActionFor(false, false, false, 900) === "idle");
check("never stepped is idle", R.heroActionFor(false, false, false, -1) === "idle");

console.log("== rig fallback + rows ==");
const t = { frames: 16, frame_ms: 200 };
R.ensureRig(t);
check("idle-only rig: run falls back to idle", R.rigClip(t, "run", "left") === t.rig.actions.idle.left);
t.rig.actions.walk = { down: { frames: [0, 1], frame_ms: 150 }, up: { frames: [2, 3], frame_ms: 150 }, left: { frames: [4, 5], frame_ms: 150 }, right: { frames: [6, 7], frame_ms: 150 } };
check("run falls back to walk before idle", R.rigClip(t, "run", "up").frames[0] === 2);
check("swim falls back to walk", R.rigClip(t, "swim", "right").frames[0] === 6);
R.rigAddCore(t);
check("core set adds all four", ["idle", "walk", "run", "swim"].every(a => t.rig.actions[a]));
check("run clips are faster than walk", t.rig.actions.run.down.frame_ms < t.rig.actions.walk.down.frame_ms);
const rows = R.rigAutoRows(16, 4);
check("4x4 sheet rows: down 0-3, left 4-7, right 8-11, up 12-15",
  rows.down.join() === "0,1,2,3" && rows.left.join() === "4,5,6,7" && rows.right.join() === "8,9,10,11" && rows.up.join() === "12,13,14,15");
check("short sheet never indexes past the end", R.rigAutoRows(6, 4).up.every(i => i < 6));

console.log("== wiring ==");
check("hero draws through the rig", /rigTileImage\(pcTid, _hAct, rigDirFromFacing\(playFacing\)/.test(html));
check("swim splash replaces the TODO", !/TODO\(swim\)/.test(html));
check("photo mode + quality keys", html.includes('case "p": case "P"') && html.includes("playCycleQuality()"));
check("flight speed lines drawn", html.includes("drawFlightLines()"));

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
