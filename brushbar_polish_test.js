#!/usr/bin/env node
// brushbar_polish_test.js — v5.45.3 brush-bar polish tests.
// clampDensity (the scatter 0% edge), the STAMP_SHAPES key regression guard
// (the "2x2" default bug), plus static assertions over editor.html for the
// phone contract: exactly four visible brush buttons, stamp the default,
// commit-on-release, two-finger cancellation, and long-press wiring.
// Run: node brushbar_polish_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

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
function extractConstObj(name) {
  const start = html.indexOf("const " + name + " =");
  if (start < 0) throw new Error("not found: const " + name);
  let i = html.indexOf("{", start), depth = 0;
  for (let j = i; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") { depth--; if (!depth) return html.slice(i, j + 1); }
  }
  throw new Error("unbalanced braces in const " + name);
}

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

eval(extract("clampDensity"));
const STAMP_SHAPES = eval("(" + extractConstObj("STAMP_SHAPES") + ")");

console.log("== clampDensity (the scatter 0% edge) ==");
check("normal value passes through", clampDensity(60) === 60);
check("string value coerces", clampDensity("75") === 75);
check("floor is 10", clampDensity(5) === 10 && clampDensity("5") === 10);
check("ceiling is 100", clampDensity(200) === 100 && clampDensity("250") === 100);
check("0 falls back to the 60 default", clampDensity(0) === 60);
check('"0" falls back too', clampDensity("0") === 60);
check("garbage falls back", clampDensity("abc") === 60);
check("null/undefined fall back", clampDensity(null) === 60 && clampDensity(undefined) === 60);
check("boundaries hold", clampDensity(10) === 10 && clampDensity(100) === 100);

console.log("== stamp shape keys (the 2x2 default bug) ==");
check('shape key "b2" exists', !!STAMP_SHAPES.b2);
check('no stale "2x2" key', !("2x2" in STAMP_SHAPES));
check('default initializes to "b2"', html.includes('let stampShape = "b2"'));
check('persisted default is "b2"', html.includes('lsGet("cw_stampShape", "b2")'));

console.log("== phone contract (static) ==");
{
  const barStart = html.indexOf('<div id="brush-bar"');
  const bar = html.slice(barStart, html.indexOf("</div>", barStart));
  const ids = ["bb-stamp", "bb-paint", "bb-erase", "bb-more"];
  check("exactly the four brush buttons exist",
    ids.every(id => bar.includes('id="' + id + '"')) &&
    (bar.match(/<button/g) || []).length === 4,
    "buttons=" + ((bar.match(/<button/g) || []).length));
  check("stamp is first in the bar", bar.indexOf("bb-stamp") < bar.indexOf("bb-paint"));
}
check("stamp is the armed default on boot",
  html.includes('$("bb-stamp").classList.add("on")'));
check("commit-on-release: endStroke lands the ghost",
  html.includes("commitStrokeCells(s);"));
check("two-finger down drops the ghost stroke",
  /ptrs\.size === 2\)[\s\S]{0,400}stroke = null; hideScope\(\); queueRender\(\);/.test(html));
check("two-finger down drops the height ghost",
  /ptrs\.size === 2\)[\s\S]{0,600}hstroke = null; queueRender\(\);/.test(html));
check("long-press menu wired (~500ms hold -> ctx menu)",
  html.includes("openCtxMenu(cell, p.x, p.y)") && html.includes("}, 520);"));
check("ctx menu element exists", html.includes('id="ctx-menu"'));
check("haptics guarded", /function buzz\(ms\)[\s\S]{0,200}navigator\.vibrate/.test(html));
check("undo is thumb-sized (44px)",
  /#topbar-undo button \{[^}]*min-height: 44px/.test(html));

console.log("== RESULT: " + PASS + " passed, " + FAIL + " failed ==");
process.exit(FAIL ? 1 : 0);
