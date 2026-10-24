#!/usr/bin/env node
// recovery_bridge_test.js — Stage 8.5 regression tests (Lloyd, 2026-10-23:
// "those particular buttons aren't working, at least not in my instance").
// The shell (public) login's Forgot username/password buttons called
// openLoginRecovery() directly — which flips panes inside the classic
// #login-overlay that the shell deliberately keeps HIDDEN. The clicks
// landed, the pane flipped invisibly, and the buttons looked dead. The
// classic overlay's own buttons worked because the overlay is already
// visible there. Fix: the shell buttons cross the same bridge the 2FA
// fallback uses (shellOpenRecovery): hide the shell, show the overlay,
// open the recovery pane, and let loginComplete route back via
// window._loginResolve.
// Run: node recovery_bridge_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

console.log("== static wiring ==");
check("shellOpenRecovery exists", /function shellOpenRecovery\(kind\) \{/.test(html));
check("shell forgot buttons cross the bridge",
  html.includes('$("sh-forgot-user").onclick = function () { shellOpenRecovery("username"); };') &&
  html.includes('$("sh-forgot-password").onclick = function () { shellOpenRecovery("password"); };'));
check("shell forgot buttons no longer call openLoginRecovery directly",
  !html.includes('$("sh-forgot-user").onclick = function () { openLoginRecovery(') &&
  !html.includes('$("sh-forgot-password").onclick = function () { openLoginRecovery('));
check("classic overlay buttons still open recovery directly",
  html.includes('$("recover-user-open").onclick = () => openLoginRecovery("username");') &&
  html.includes('$("recover-password-open").onclick = () => openLoginRecovery("password");'));
{
  const om = html.match(/function openLoginRecovery\(kind\) \{[\s\S]*?\n\}/);
  check("openLoginRecovery itself never touches overlay classes (the bridge owns showing it)",
    !!om && !/classList/.test(om[0]));
}

console.log("== behaviour: the bridge, with stubbed DOM ==");
{
  const m = html.match(/function shellOpenRecovery\(kind\) \{[\s\S]*?\n\}/);
  check("bridge source extractable", !!m);
  if (m) {
    const root = { style: {} };
    const overlay = { classList: { _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); } } };
    const calls = [], routed = [];
    const win = {};
    const factory = new Function("document", "$", "window", "openLoginRecovery", "shellAuthComplete",
      m[0] + "\nreturn shellOpenRecovery;");
    const shellOpenRecovery = factory(
      { getElementById: id => (id === "shell-root" ? root : null) },
      id => (id === "login-overlay" ? overlay : null),
      win,
      k => calls.push(k),
      v => routed.push(v));
    shellOpenRecovery("password");
    check("shell root hidden", root.style.display === "none");
    check("classic overlay shown", overlay.classList.contains("show"));
    check("recovery pane opened with the requested kind", calls.length === 1 && calls[0] === "password");
    check("return route armed", typeof win._loginResolve === "function");
    win._loginResolve();
    check("return route hides the overlay and re-enters the shell flow",
      !overlay.classList.contains("show") && routed.length === 1 && routed[0] === false && win._loginResolve === null);
  }
}

console.log("recovery_bridge_test: " + PASS + " passed, " + FAIL + " failed");
process.exit(FAIL ? 1 : 0);
