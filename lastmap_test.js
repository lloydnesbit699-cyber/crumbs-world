#!/usr/bin/env node
// lastmap_test.js — v5.47.2 regression tests.
// 1. The boot black-map bug: peekInfo() referenced `semLayer`, which was never
//    declared — every boot died in initHudSheet() -> renderSheet() ->
//    peekInfo() with a ReferenceError, refresh() never ran, canvas stayed
//    blank. (v5.50 renamed initHudSheet to initPanelSystem.) Asserts the
//    reference is gone and the paint peek line resolves
//    against the real `logicalLayer`.
// 2. Last map per player: remember/restore keyed by username (no cross-user
//    leak), stale stored maps fall back to the default, and the boot/hooks
//    wiring exists in editor.html.
// Run: node lastmap_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}
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

console.log("== boot black-map regression (v5.47.1 ReferenceError) ==");
// strip line comments so the v5.47.2 fix note (which names the old identifier)
// can't trip the check — we care about live code references only.
const codeNoComments = html.replace(/\/\/[^\n]*/g, "");
check("no `semLayer` reference remains anywhere", !/[^a-zA-Z]semLayer[^a-zA-Z]/.test(codeNoComments));
check("peekInfo reads the real `logicalLayer`", /SEM_LAYER_DEFS\[logicalLayer\]/.test(extract("peekInfo")));

// eval peekInfo's paint branch with stubbed globals
const peekSrc = extract("peekInfo")
  .replace(/^function peekInfo\(\)/, "function __peek()");
const bootStubs = `
  var sheetView = "paint";
  var SEM_LAYER_DEFS = { ground: { name: "Ground" }, walls: {} };
  var logicalLayer = "ground", brushTool = "stamp";
  var selTile = null, inspectPos = null, npcSelectedId = null, ghostSug = null, animRevert = null;
  function tileLabel() { return "t"; }
  function beginnerTargetTile() { return null; }
`;
const peekVal = eval(bootStubs + peekSrc + "; sheetView='paint'; __peek();");
check("paint peek line shows layer name + brush", peekVal === "Ground · stamp", JSON.stringify(peekVal));
const peekVal2 = eval(bootStubs + peekSrc + "; sheetView='paint'; logicalLayer='walls'; SEM_LAYER_DEFS={}; __peek();");
check("paint peek line falls back to layer key", peekVal2 === "walls · stamp", JSON.stringify(peekVal2));

// initPanelSystem must run inside init's try (before the first refresh) without
// referencing anything in a temporal dead zone at that point
const initSrc = extract("init");
check("init calls initPanelSystem before first refresh",
  initSrc.indexOf("initPanelSystem()") > 0 && initSrc.indexOf("initPanelSystem()") < initSrc.indexOf("await refresh()"));

console.log("== last map per player ==");
// --- eval the last-map helpers with stubbed env ---
const helpers = ["lastMapKey", "rememberLastMap", "forgetLastMap", "restoreLastMap"]
  .map(extract).join("\n");
function makeEnv(username) {
  const store = {};
  const calls = [];
  const env = {
    ME: username ? { username } : null,
    currentFile: "hud_map.json",
    localStorage: {
      getItem: k => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: k => { delete store[k]; },
    },
    api: async (path, body) => { calls.push({ path, body }); return env._apiResult; },
    _apiResult: { ok: true },
    _store: store, _calls: calls,
  };
  return env;
}
// All four helpers share one scope with a local `currentFile`, exactly like
// the page: restoreLastMap()'s assignment lands on the local.
function makeScope(env) {
  const src = ["lastMapKey", "rememberLastMap", "forgetLastMap", "restoreLastMap"]
    .map(extract).join("\n");
  const fn = new Function("ME", "localStorage", "api",
    "var currentFile = 'hud_map.json';\n" + src +
    "\nreturn { lastMapKey, rememberLastMap, forgetLastMap,\n" +
    "  restore: async () => { await restoreLastMap(); return currentFile; } };");
  return fn(env.ME, env.localStorage, env.api);
}

(async () => {
  // keying: per-user, never cross-user
  let e1 = makeEnv("lloyd"), h1 = makeScope(e1);
  h1.rememberLastMap("deep.json");
  check("remember stores under the player's own key",
    e1._store["crumbs.lastMap.lloyd"] === "deep.json", JSON.stringify(e1._store));
  let e2 = makeEnv("melody"), h2 = makeScope(e2);
  check("another player's key is untouched", !("crumbs.lastMap.melody" in e2._store));
  h2.rememberLastMap("sky.json");
  check("second player stores under their own key",
    e2._store["crumbs.lastMap.melody"] === "sky.json");
  check("first player's value unchanged", e1._store["crumbs.lastMap.lloyd"] === "deep.json");

  // local (single-user) mode still works
  let e0 = makeEnv(null), h0 = makeScope(e0);
  h0.rememberLastMap("solo.json");
  check("local mode uses the device key", e0._store["crumbs.lastMap.local"] === "solo.json");

  // restore: stored map loads -> currentFile follows
  let e3 = makeEnv("lloyd");
  e3._store["crumbs.lastMap.lloyd"] = "deep.json";
  e3._apiResult = { ok: true };
  const cur3 = await makeScope(e3).restore();
  check("restore switches to the stored map", cur3 === "deep.json", cur3);
  check("restore asked the server to load it",
    e3._calls.length === 1 && e3._calls[0].body.filename === "deep.json",
    JSON.stringify(e3._calls));

  // restore: stored map gone -> key forgotten, default kept
  let e4 = makeEnv("lloyd");
  e4._store["crumbs.lastMap.lloyd"] = "gone.json";
  e4._apiResult = { ok: false, error: "file not found" };
  const cur4 = await makeScope(e4).restore();
  check("stale stored map falls back to default", cur4 === "hud_map.json", cur4);
  check("stale key is forgotten", !("crumbs.lastMap.lloyd" in e4._store));

  // restore: nothing stored -> no server call
  let e5 = makeEnv("lloyd");
  e5._apiResult = { ok: true };
  const cur5 = await makeScope(e5).restore();
  check("no stored map means no load call", cur5 === "hud_map.json" && e5._calls.length === 0);

  // restore: stored == default -> no server call
  let e6 = makeEnv("lloyd");
  e6._store["crumbs.lastMap.lloyd"] = "hud_map.json";
  e6._apiResult = { ok: true };
  const cur6 = await makeScope(e6).restore();
  check("stored default means no load call", cur6 === "hud_map.json" && e6._calls.length === 0);

  // wiring in editor.html
  check("boot restores the last map before setFile/refresh",
    /await restoreLastMap\(\);[^\n]*\n\s*setFile\(currentFile\);\s*\n\s*await refresh\(\);/.test(html));
  check("boot fills the budget strip (always-visible since v5.47)",
    /await refresh\(\);\s*\n\s*refreshBudget\(\);/.test(initSrc));
  for (const [fn, why] of [["loadMapFile", "map switch"], ["enterPortal", "portal enter"],
                            ["warpRefresh", "play warp"], ["doSave", "save"],
                            ["doSaveAs", "save as"]])
    check(why + " remembers the map (" + fn + ")",
      new RegExp("function " + fn + "[\\s\\S]*?rememberLastMap\\(").test(
        (html.match(new RegExp("(async )?function " + fn + "\\(")) ? extract(fn) : "")));

  console.log(`\n${PASS} passed, ${FAIL} failed`);
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.error("TEST HARNESS FAIL:", e); process.exit(1); });
