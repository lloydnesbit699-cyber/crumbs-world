#!/usr/bin/env node
// touch_arbitration_test.js — v5.45.1 touch arbitration tests.
// Drives the pure gesture language from editor.html (arbiterNew/Down/Move/
// Up/LongCheck): one finger paints, a quick tap is a tap, a ~500ms still
// hold opens the menu, two fingers always pan, the third is ignored, and a
// pan collapsing back to one finger restarts as a fresh touch.
// Run: node touch_arbitration_test.js
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

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

eval(extract("arbiterNew"));
eval(extract("arbiterDown"));
eval(extract("arbiterMove"));
eval(extract("arbiterUp"));
eval(extract("arbiterLongCheck"));

console.log("== paint flow ==");
{
  const st = arbiterNew();
  check("first finger -> brush", arbiterDown(st, 1, 100, 100, 0) === "brush");
  check("small move stays undecided", arbiterMove(st, 1, 105, 103, 50) === null);
  check("drag past threshold -> paint", arbiterMove(st, 1, 130, 100, 100) === "paint");
  check("further moves stay paint", arbiterMove(st, 1, 160, 100, 150) === null && st.mode === "paint");
  check("lift ends the stroke", arbiterUp(st, 1, 160, 100, 200) === "paint-end");
  check("idle after all fingers lift", st.mode === "idle");
}

console.log("== tap flow ==");
{
  const st = arbiterNew();
  arbiterDown(st, 1, 50, 50, 0);
  check("quick still lift -> tap", arbiterUp(st, 1, 51, 50, 120) === "tap");
  const st2 = arbiterNew();
  arbiterDown(st2, 1, 50, 50, 0);
  check("slow lift is not a tap", arbiterUp(st2, 1, 50, 50, 900) === null);
}

console.log("== long-press flow ==");
{
  const st = arbiterNew();
  arbiterDown(st, 1, 200, 200, 0);
  check("too early -> no menu", arbiterLongCheck(st, 1, 400) === null);
  check("still 600ms -> menu", arbiterLongCheck(st, 1, 600) === "menu");
  check("menu mode latched", st.mode === "menu" && st.menu === true);
  check("lift after menu -> menu-end", arbiterUp(st, 1, 200, 200, 700) === "menu-end");
  check("fresh down after menu -> brush", arbiterDown(st, 1, 10, 10, 800) === "brush");
}
{
  const st = arbiterNew();
  arbiterDown(st, 1, 200, 200, 0);
  arbiterMove(st, 1, 230, 200, 100);   // dragged -> paint
  check("long check during a drag -> nothing", arbiterLongCheck(st, 1, 900) === null);
}
{
  const st = arbiterNew();
  arbiterDown(st, 1, 200, 200, 0);
  arbiterMove(st, 1, 204, 203, 100);   // jitter under the fat-finger threshold
  check("jitter doesn't kill the long-press", arbiterLongCheck(st, 1, 900) === "menu");
}

console.log("== two fingers ==");
{
  const st = arbiterNew();
  check("first finger -> brush", arbiterDown(st, 1, 100, 100, 0) === "brush");
  check("second finger -> pan wins", arbiterDown(st, 2, 300, 300, 50) === "pan");
  check("moves route to pan", arbiterMove(st, 1, 110, 110, 100) === "pan");
  check("long-press can't fire mid-pan", arbiterLongCheck(st, 1, 900) === null);
  check("lifting the second finger -> nothing", arbiterUp(st, 2, 300, 300, 200) === null);
  check("pan collapsed: remaining finger is a fresh touch", st.mode === "one");
  check("fresh finger paints on drag", arbiterMove(st, 1, 140, 100, 250) === "paint");
  check("lift ends it", arbiterUp(st, 1, 140, 100, 300) === "paint-end");
}
{
  const st = arbiterNew();
  arbiterDown(st, 1, 0, 0, 0);
  arbiterDown(st, 2, 0, 0, 0);
  check("third finger ignored", arbiterDown(st, 3, 0, 0, 0) === null);
  check("unknown finger move ignored", arbiterMove(st, 9, 0, 0, 0) === null);
  check("unknown finger up ignored", arbiterUp(st, 9, 0, 0, 0) === null);
}

console.log("== RESULT: " + PASS + " passed, " + FAIL + " failed ==");
process.exit(FAIL ? 1 : 0);
