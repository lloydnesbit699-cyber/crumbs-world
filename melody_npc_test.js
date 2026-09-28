#!/usr/bin/env node
// melody_npc_test.js — v5.50 client+server tests.
// Static checks: Melody becomes a character in Play mode — she spawns on the
// nearest walkable tile to your spawn, waits there (no patrol), and walking
// up lets you talk to her (chip, tapping her, or the FAB open her dock).
// She is chat-only in the world: Law 18 holds, she never touches the map,
// and pockets keep their own cast. Run: node melody_npc_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");
const py = fs.readFileSync(path.join(__dirname, "crumbs_hud.py"), "utf8");

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

console.log("== she spawns into the world ==");
check("the talk chip exists and starts hidden",
  /id="mel-talk"/.test(html) && /<button id="mel-talk" hidden>/.test(html));
check("the talk chip is styled", /#mel-talk \{/.test(html));
const spawn = fnBody("spawnMelodyNpc");
check("spawnMelodyNpc exists", !!spawn);
check("she asks the server for the nearest walkable tile",
  !!spawn && /\/api\/play\/melody_spot/.test(spawn));
check("she joins the world's cast as a flagged npc",
  !!spawn && /melody: true/.test(spawn) && /npcs\.push\(melodyNpc\)/.test(spawn));
check("she has no patrol loop — she waits for you",
  !!spawn && /loop: \[\]/.test(spawn));
check("her body tile prefers a Melody-named tile, then a map character, then your hero",
  /function melodyBodyTile/.test(html) && /\/melody\/i\.test\(t\.name/.test(html) &&
  /flagHeroes\(\)\.find/.test(html) && /return playHeroTid/.test(html));
check("play start spawns her after the cast is built",
  /await buildNpcs\(\);[\s\S]*?melodyHomeMap = currentFile[\s\S]*?await spawnMelodyNpc\(\);/.test(html));
check("leaving play mode takes her home too",
  /melodyNpc = null; melodyGreeted = false; \$\("mel-talk"\)\.hidden = true;/.test(html));

console.log("== walk up and talk to her ==");
const prox = fnBody("melodyProximity");
check("melodyProximity exists", !!prox);
check("the chip shows within 2 tiles and hides beyond",
  !!prox && /<= 2/.test(prox) && /chip\.hidden = !near/.test(prox));
check("she greets once per run when you first walk up",
  !!prox && /melodyGreeted/.test(prox) && /toast\("💜 Melody:/.test(prox));
check("every hero step checks proximity", /melodyProximity\(\);   \/\/ v5\.50/.test(html));
check("tapping her tile while standing close opens chat, no walk",
  /tapping Melody herself while standing close = talk/.test(html) &&
  /openMelDock\(\); return;/.test(html));
check("openMelDock is the one door in — FAB, chip, and tap-her all use it",
  /function openMelDock\(\)/.test(html) &&
  /\$\("melody-fab"\)\.onclick[\s\S]*?openMelDock\(\)/.test(html) &&
  /\$\("mel-talk"\)\.onclick = \(\) => openMelDock\(\);/.test(html));
check("the FAB still toggles (open via openMelDock, close directly)",
  /if \(\$\("melody-dock"\)\.hidden\) openMelDock\(\);/.test(html));

console.log("== she is herself on screen ==");
const draw = fnBody("drawNpc");
check("drawNpc draws her marker — glow ring, heart, nameplate",
  !!draw && /n\.melody/.test(draw) && /190,120,255/.test(draw) &&
  /fillText\("💜"/.test(draw) && /fillText\("Melody"/.test(draw));
check("her marker draws even without a body tile",
  !!draw && /if \(n\.melody\) \{[\s\S]*?\}[\s\S]*?if \(!im\) return;/.test(draw));

console.log("== pockets are not her home ==");
check("warping clears her and only respawns on her home map",
  /melodyNpc = null; \$\("mel-talk"\)\.hidden = true;\s*\n\s*if \(r\.warp\.file === melodyHomeMap\) await spawnMelodyNpc\(\);/.test(html));

console.log("== Law 18: chat-only, never touches the map ==");
check("the server spot endpoint is read-only (no run-state writes)",
  /\/api\/play\/melody_spot"[\s\S]*?return self\._send_json\(\{"ok": True, "spot": spot\}\)/.test(py) &&
  !/\/api\/play\/melody_spot"[\s\S]{0,400}?play\[/.test(py));
check("the client never gives her a map-mutating call",
  !!spawn && !/\/api\/(paint|stroke|objects|tiles|play\/move|play\/step)/.test(spawn));

console.log("== the server finds her a place to stand ==");
check("_near_walkable searches ring by ring",
  /def _near_walkable\(sx, sy/.test(py) && /for r in range\(1, radius/.test(py));
check("a walled-in spawn comes back empty (she sits the run out)",
  /return None/.test(py) && /if \(!spot\) return;/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
