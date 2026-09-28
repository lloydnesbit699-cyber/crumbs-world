#!/usr/bin/env node
// melody_cobuild_client_test.js — v5.48 co-build client tests.
// Static checks over editor.html: her eyes (the world snapshot rides with
// every chat message), the room-draft plan helper (ghost preview and accept
// stroke come from the same roomPresetCells — the preview never lies), and
// the two new suggestion kinds in ghost render + accept.
// Run: node melody_cobuild_client_test.js
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

console.log("== eyes: the snapshot rides with chat ==");
const mw = fnBody("melodyWorld");
check("melodyWorld exists", !!mw);
check("snapshot caps placed characters", !!mw && /npcs\.length >= 12/.test(mw),
  "the model gets at most 12 NPCs");
check("snapshot never breaks send", !!mw && /try \{/.test(mw) && /catch \(e\) \{ return null; \}/.test(mw));
check("snapshot carries dims + budget + patrol count",
  !!mw && /w: W, h: H/.test(mw) && /budgetCounts/.test(mw) && /patrols/.test(mw));
const send = fnBody("melodySend");
check("melodySend posts the snapshot", !!send && /world: melodyWorld\(\)/.test(send),
  "eyes go dark if the body drops the world field");

console.log("== room draft: one layout, ghost and paint ==");
const plan = fnBody("suggestRoomPlan");
check("suggestRoomPlan exists", !!plan);
check("plan uses the HUD's own room layout", !!plan && /roomPresetCells/.test(plan),
  "ghost and accept must share roomPresetCells");
check("plan honors her spot, else visible center",
  !!plan && /where_xy/.test(plan) && /visibleTiles/.test(plan));
check("unknown room kinds fall through safely",
  !!plan && /boss_arena/.test(plan) && /dungeon_room/.test(plan));
const ghost = fnBody("drawSuggestGhost");
check("ghost renders room_draft", !!ghost && /room_draft/.test(ghost));
check("room ghost draws the plan's cells (preview never lies)",
  !!ghost && /suggestRoomCells\(ghostSug\)/.test(ghost));
check("ghost renders patrol_draft", !!ghost && /patrol_draft/.test(ghost));
check("patrol ghost rings the anchor", !!ghost && /anchor_xy/.test(ghost));

console.log("== accept: existing undoable endpoints ==");
const accept = fnBody("acceptSuggestion");
check("accept handles room_draft", !!accept && /g\.kind === "room_draft"/.test(accept));
check("room accept paints via the stroke endpoint (one undo)",
  !!accept && /room_draft[\s\S]{0,400}\/api\/semantic\/stroke/.test(accept));
check("accept handles patrol_draft", !!accept && /g\.kind === "patrol_draft"/.test(accept));
check("patrol accept assigns via the patrol endpoint (server re-validates)",
  !!accept && /patrol_draft[\s\S]{0,400}\/api\/patrols\/create/.test(accept));
check("no new server routes invented",
  !!accept && !/melody\/room/.test(accept) && !/melody\/patrol/.test(accept));

console.log("== suggest card ==");
const card = fnBody("renderSuggestCard");
check("card explains room drafts", !!card && /room_draft/.test(card));
check("card explains patrol drafts", !!card && /patrol_draft/.test(card));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
