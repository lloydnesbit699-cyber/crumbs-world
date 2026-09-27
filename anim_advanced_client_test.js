#!/usr/bin/env node
// anim_advanced_client_test.js — v5.44 Advanced animation filmstrip.
// Extracts the pure, phone-first filmstrip logic from editor.html and
// exercises it against stubbed globals:
//   filmstripFrames  — the state's validated frame sequence
//   frameModsFor     — per-frame mods ("this frame" tweaks)
//   stateTick        — the tween-aware playhead (variable durations,
//                      tween in-betweens, duration-preserving loops)
//   mergeBeginnerPreset — beginner card tap MERGES onto the shared record
//   fxMoveLayer/fxToggleLayer — FX layer reorder + eye toggles
//   onionVisible     — onion skin only when toggled on AND paused
// Plus static checks that the Advanced panel carries the required surface:
// labeled tag chips, filmstrip cards with duration badges + dup/del,
// scrubber, onion toggle, earlier/later, up/down layer controls, the tween
// slider, all four export formats, and no drag-only timeline.
// Run: node anim_advanced_client_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

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
function extractConst(name) {
  const m = html.match(new RegExp("const " + name + " = (\\{[\\s\\S]*?\\};|\\[[\\s\\S]*?\\];)"));
  if (!m) throw new Error("const not found: " + name);
  return "global." + name + " = " + m[1];
}

// ---- stubbed browser globals -------------------------------------------
let fakeNow = 1000000;
global.performance = { now: () => fakeNow };

eval(extractConst("ANIM_STATE_DEFAULTS"));
eval(extractConst("ANIM_PRESETS"));
eval(extractConst("FX_LAYER_KINDS"));
eval(extract("filmstripFrames"));
eval(extract("frameModsFor"));
eval(extract("stateTick"));
eval(extract("stateParams"));
eval(extract("mergeBeginnerPreset"));
eval(extract("fxMoveLayer"));
eval(extract("fxToggleLayer"));
eval(extract("onionVisible"));

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " " + detail : "")); }
}
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// == filmstripFrames ======================================================
console.log("== filmstripFrames: the state's validated sequence ==");
{
  const t = { frames: 4, frame_ms: 400,
              anim: { states: { idle: { frames: [0, 2, 9, -1, 2.5] } } } };
  check("explicit list validated against art", eq(filmstripFrames(t, "idle"), [0, 2]),
        JSON.stringify(filmstripFrames(t, "idle")));
}
{
  const t = { frames: 3, frame_ms: 400,
              anim: { states: { idle: { act: "bounce" } } } };
  check("no list -> every frame in order", eq(filmstripFrames(t, "idle"), [0, 1, 2]));
}
{
  const t = { frames: 3, frame_ms: 400,
              anim: { states: { idle: { frames: [] } } } };
  check("empty list -> every frame in order", eq(filmstripFrames(t, "idle"), [0, 1, 2]));
}
{
  const t = { frames: 2, frame_ms: 400,
              anim: { default: "idle",
                      states: { idle: { frames: [0, 1] },
                                walk: { act: "bounce" } } } };
  check("state without a list still shows art", eq(filmstripFrames(t, "walk"), [0, 1]));
}

// == frameModsFor ==========================================================
console.log("== frameModsFor: this-frame mods ==");
{
  const p = { frame_mods: { 0: { ms: 200 }, "2": { hue: 40 } } };
  check("int key", eq(frameModsFor(p, 0), { ms: 200 }));
  check("string key (server round-trip)", eq(frameModsFor(p, 2), { hue: 40 }));
  check("absent -> null", frameModsFor(p, 1) === null);
  check("no frame_mods -> null", frameModsFor({}, 0) === null);
}

// == stateTick =============================================================
console.log("== stateTick: variable durations + tweening ==");
{
  const t = { frames: 3,
              anim: { states: { idle: { frames: [0, 1, 2], frame_ms: 100,
                                        frame_mods: { 1: { ms: 300 } } } } } };
  const k0 = stateTick(t, "idle", 0);
  const k1 = stateTick(t, "idle", 150);
  const k2 = stateTick(t, "idle", 450);
  check("frame 0 at loop start", k0.pos === 0 && k0.file === 0);
  check("long frame 1 covers 100..400", k1.pos === 1 && k1.file === 1);
  check("frame 2 at 450", k2.pos === 2 && k2.file === 2);
  check("loop wraps", stateTick(t, "idle", 500).pos === 0);
}
{
  // tween_steps=2: each frame's slot splits into 3 ticks (frame + 2
  // in-betweens); total loop time stays the frame total.
  const t = { frames: 3,
              anim: { states: { idle: { frames: [0, 1, 2], frame_ms: 90,
                                        tween_steps: 2 } } } };
  const total = 270;
  const a = stateTick(t, "idle", 0);
  const b = stateTick(t, "idle", 45);    // frame 0, in-between 1
  const c = stateTick(t, "idle", 95);    // frame 1, first tick
  check("tween keeps the frame slot", a.pos === 0 && a.step === 0 && a.blend === 0);
  check("in-between is the frame's own slot", b.pos === 0 && b.step === 1 && b.blend > 0);
  check("next frame after its slot", c.pos === 1 && c.step === 0);
  check("tweening preserves total duration",
        stateTick(t, "idle", total - 1).pos === 2 &&
        stateTick(t, "idle", total).pos === 0);
  check("phase advances with position", a.phase === 0 && c.phase === 1 / 3);
}
{
  const t = { frames: 2, anim: { states: { idle: {} } } };
  check("no tween -> no blend", stateTick(t, "idle", 50).blend === 0);
}

// == mergeBeginnerPreset =====================================================
console.log("== mergeBeginnerPreset: two views, same data ==");
{
  const adv = { v: 1, default: "idle",
    states: {
      idle: { act: "bounce", amp: 80, frame_ms: 400, frames: [0, 2],
              fx_layers: [{ kind: "aura", amp: 50, magic: "#7fe7ff" }],
              tween_steps: 2, frame_mods: { 0: { ms: 200 } } },
      talk: { act: "pulse", amp: 30 },
    },
    transitions: { "idle->walk": { blend_ms: 150 } } };
  const before = JSON.stringify(adv);
  const out = mergeBeginnerPreset(adv, "float", 70, "#ff9d5c");
  check("input not mutated", JSON.stringify(adv) === before);
  check("card dresses idle", out.states.idle.act === "float" &&
        out.states.idle.amp === 70 && out.states.idle.frame_ms === 900);
  check("card dresses walk", out.states.walk.act === "float" &&
        out.states.walk.frame_ms === 420);
  check("idle keeps its frame list", eq(out.states.idle.frames, [0, 2]));
  check("idle keeps its FX layers", eq(out.states.idle.fx_layers,
        [{ kind: "aura", amp: 50, magic: "#7fe7ff" }]));
  check("idle keeps tweening", out.states.idle.tween_steps === 2);
  check("idle keeps frame mods", eq(out.states.idle.frame_mods, { 0: { ms: 200 } }));
  check("untouched state survives", out.states.talk.act === "pulse");
  check("transitions survive", out.transitions["idle->walk"].blend_ms === 150);
  check("record stamps v2", out.v === 2);
  const m = mergeBeginnerPreset(adv, "magic", 60, "#ff9d5c");
  check("magic card lands its aura color", m.states.idle.magic === "#ff9d5c");
}

// == FX layer ops ============================================================
console.log("== fxMoveLayer / fxToggleLayer ==");
{
  const L = [{ kind: "bounce" }, { kind: "aura" }, { kind: "pulse" }];
  check("move down swaps", eq(fxMoveLayer(L, 0, 1).map(l => l.kind),
        ["aura", "bounce", "pulse"]));
  check("move up swaps", eq(fxMoveLayer(L, 2, -1).map(l => l.kind),
        ["bounce", "pulse", "aura"]));
  check("top can't go up", eq(fxMoveLayer(L, 0, -1).map(l => l.kind),
        ["bounce", "aura", "pulse"]));
  check("bottom can't go down", eq(fxMoveLayer(L, 2, 1).map(l => l.kind),
        ["bounce", "aura", "pulse"]));
  check("move returns a copy", fxMoveLayer(L, 0, 1) !== L &&
        eq(L.map(l => l.kind), ["bounce", "aura", "pulse"]));
  const vis = [{ kind: "bounce", visible: true }];
  check("eye hides", fxToggleLayer(vis, 0)[0].visible === false);
  check("eye shows again", fxToggleLayer(fxToggleLayer(vis, 0), 0)[0].visible === true);
  check("missing flag counts as visible", fxToggleLayer([{ kind: "x" }], 0)[0].visible === false);
}

// == onionVisible ============================================================
console.log("== onionVisible: default off, never while playing ==");
{
  check("off by default", onionVisible(false, false) === false);
  check("on + paused -> drawn", onionVisible(true, false) === true);
  check("on + playing -> hidden", onionVisible(true, true) === false);
}

// == static: the v5.44 Advanced surface ======================================
console.log("== static: v5.44 Advanced surface ==");
{
  check("state tags are labeled chips",
        /<span class="te">🌿<\/span><span class="tl">Idle<\/span><span class="tc">/.test(html));
  check("all six tags carry frame counts",
        ["Idle", "Walk", "Sleep", "Talk", "Hurt", "Magic"]
          .every(n => new RegExp('<span class="te">[\\s\\S]{1,4}</span><span class="tl">' + n + "</span><span class=\"tc\">").test(html)));
  check("filmstrip container exists", html.indexOf('id="filmstrip"') >= 0);
  check("filmstrip cards have duplicate + delete",
        html.indexOf('data-op="dup"') >= 0 && html.indexOf('data-op="del"') >= 0);
  check("filmstrip cards carry duration badges", html.indexOf('class="fms') >= 0);
  check("transport: play button", html.indexOf('id="film-play"') >= 0);
  check("transport: scrubber", html.indexOf('id="film-scrub"') >= 0);
  check("onion toggle button", html.indexOf('id="film-onion"') >= 0);
  check("onion defaults OFF in code", /let onionOn = false/.test(html));
  check("onion auto-disables during playback",
        /onion skinning auto-disables during playback/.test(html));
  check("earlier/later frame buttons",
        html.indexOf('id="fe-left"') >= 0 && html.indexOf('id="fe-right"') >= 0);
  check("frame editor: per-frame timing", html.indexOf('id="fe-ms"') >= 0);
  check("frame editor: per-frame tint", html.indexOf('id="fe-tint"') >= 0);
  check("FX layer add row", html.indexOf('id="fx-add"') >= 0);
  check("FX layers reorder with up/down buttons",
        html.indexOf('data-k="up"') >= 0 && html.indexOf('data-k="down"') >= 0);
  check("FX layers have eye toggles", html.indexOf('data-k="eye"') >= 0);
  check("tween slider", html.indexOf('id="anim-tween"') >= 0);
  check("export: GIF", html.indexOf('data-x="gif"') >= 0);
  check("export: PNG sequence", html.indexOf('data-x="pngseq"') >= 0);
  check("export: sprite sheet", html.indexOf('data-x="sheet"') >= 0);
  check("export: JSON", html.indexOf('data-x="json"') >= 0);
  check("JSON import input", html.indexOf('id="anim-import-file"') >= 0);
  const stripHtml = html.slice(html.indexOf('id="filmstrip-wrap"'),
                               html.indexOf('id="filmstrip-wrap"') + 4000);
  check("no drag-only timeline in filmstrip",
        stripHtml.indexOf("draggable") < 0 &&
        stripHtml.indexOf("dragstart") < 0);
  check("filmstrip ops hit the server API",
        html.indexOf("/api/anim/frame") >= 0);
  check("exports hit the server API", html.indexOf("/api/anim/export") >= 0);
}

console.log("\n" + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
