#!/usr/bin/env node
// clipauto_client_test.js — v5.53 auto-clips tests.
// She films herself: when Melody drops a new build ghost, the game records
// the next 30s by itself (max 2/day). Clips wait in a gallery — never the
// share sheet uninvited. Game world only: canvas + SFX, no mic, no camera.
// Her voice can't be captured (speechSynthesis isn't routable), so her words
// burn in as captions.
// Run: node clipauto_client_test.js
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

function section(name) {
  const start = html.indexOf("// ---- v5.53: auto clips");
  if (start < 0) return "";
  const end = html.indexOf("// ---- v5.51: birth certificates", start);
  return html.slice(start, end < 0 ? undefined : end);
}

console.log("== auto-clip gate logic (evaluated, not just static) ==");
const gateSrc = fnBody("clipAutoAllow");
check("clipAutoAllow exists", !!gateSrc);
let gate = null;
try { gate = new Function("const CLIP_CAP = 2; return (" + gateSrc + ")")(); } catch (e) {}
check("gate evaluates", typeof gate === "function", "could not eval clipAutoAllow");
if (gate) {
  check("fires when idle", gate(false, false, false, 0) === true);
  check("blocked while recording", gate(true, false, false, 0) === false);
  check("blocked on hidden tab", gate(false, true, false, 0) === false);
  check("blocked in play mode", gate(false, false, true, 0) === false);
  check("blocked at daily cap", gate(false, false, false, 2) === false);
  check("allowed under cap", gate(false, false, false, 1) === true);
}

console.log("== cap constants ==");
const capM = html.match(/const CLIP_CAP = (\d+), CLIP_SECS = (\d+);/);
check("CLIP_CAP is 2/day", !!capM && capM[1] === "2");
check("CLIP_SECS is 30", !!capM && capM[2] === "30");

console.log("== trigger wiring ==");
const poll = fnBody("suggestPoll");
check("suggestPoll kicks an auto-clip on new ghost",
  !!poll && /clipAutoKick\("melody-build"\)/.test(poll),
  "the build moment must start the camera");
const kick = fnBody("clipAutoKick");
check("kick double-checks the gate after its delay",
  !!kick && (kick.match(/clipAutoAllow/g) || []).length >= 2,
  "a lot can change in 1.5s");
check("kick waits for the ghost to render", !!kick && /setTimeout/.test(kick) && /1500/.test(kick));

console.log("== captions (her voice, burned in) ==");
const say = fnBody("melSay");
check("melSay captions her words while an auto-clip rolls",
  !!say && /clipSetCaption\(text\)/.test(say));
const render = fnBody("render");
check("render draws the caption bar", !!render && /drawClipCaption\(\)/.test(render));
const capFn = fnBody("drawClipCaption");
check("expired captions clear themselves", !!capFn && /clipCaption = null/.test(capFn));
check("caption labels her by name", !!capFn && /Melody: /.test(capFn));

console.log("== recording plumbing ==");
const start = fnBody("startRecording");
check("startRecording takes opts", !!start && /opts\.auto/.test(start));
check("auto clips get the 30s cap", !!start && /recAuto \? CLIP_SECS : 60/.test(start));
check("game SFX tapped into the recording",
  !!start && /Sfx\.recStream\(\)/.test(start));
const sfx = html.match(/recStream\(\) \{[\s\S]{0,400}?createMediaStreamDestination/);
check("Sfx.recStream taps the master bus", !!sfx);
const fin = fnBody("finishRecording");
check("auto clips skip the share sheet ambush",
  !!fin && /if \(wasAuto\)[\s\S]{0,300}clipSave\(blob/.test(fin),
  "auto-clips wait in the gallery");

console.log("== gallery ==");
check("clips persist in IndexedDB", /indexedDB\.open\("crumbs-clips"/.test(html));
check("gallery has preview/share/delete", /clipPreview/.test(html) && /clipShare/.test(html) && /clipDel/.test(html));
check("Clips button + sheet exist",
  /id="btn-clips"/.test(html) && /id="sheet-clips"/.test(html));

console.log("== privacy: game world only ==");
const sec = section("v5.53");
check("v5.53 section exists", sec.length > 100);
check("no mic/camera capture in auto clips", !/getUserMedia/.test(sec),
  "canvas + SFX only — never the player's mic or camera");

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
