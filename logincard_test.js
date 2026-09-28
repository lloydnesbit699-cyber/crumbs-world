#!/usr/bin/env node
// logincard_test.js — v5.47.4 regression tests.
// On Lloyd's phone the signup card's "Protect with authenticator app" row
// rendered a giant card-wide white checkbox with the label text shoved off
// the right edge of the card. Root cause, two colliding rules:
//   1. `#login-box input { display:block; width:100% }` (specificity 1,0,1)
//      beat `.login-2fa-opt input { width:18px }` (0,1,1) — the checkbox
//      went full card width;
//   2. the global `button, select, input` touch sizing (44px min-height,
//      10px 12px padding) also applied to the checkbox.
// The full-width rule now excludes checkboxes and the opt-in checkbox resets
// the touch sizing and pins itself to 18px with flex: 0 0 auto so it can
// never stretch or shove its label again.
// Run: node logincard_test.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "editor.html"), "utf8");

let PASS = 0, FAIL = 0;
function check(name, cond, detail) {
  if (cond) { PASS++; console.log("  ok: " + name); }
  else { FAIL++; console.log("  FAIL: " + name + (detail ? " — " + detail : "")); }
}

function ruleBody(selectorRe) {
  const m = html.match(new RegExp(selectorRe + "\\s*\\{([^}]*)\\}", "s"));
  return m ? m[1].replace(/\s+/g, " ") : null;
}

console.log("== checkbox vs full-width rule (static) ==");
check("login-box full-width rule excludes checkboxes",
  /#login-box input:not\(\[type=checkbox\]\)\s*\{/.test(html));
const optBody = ruleBody("\\.login-2fa-opt input");
check("opt-in checkbox rule exists", !!optBody);
check("checkbox pinned to 18px", !!optBody && /width:\s*18px/.test(optBody) && /height:\s*18px/.test(optBody), optBody);
check("checkbox cannot stretch in the flex row", !!optBody && /flex:\s*0 0 auto/.test(optBody), optBody);
check("checkbox opts out of global touch sizing",
  !!optBody && /min-height:\s*0/.test(optBody) && /padding:\s*0/.test(optBody), optBody);
check("checkbox keeps its gold accent", !!optBody && /accent-color:\s*#ffd75f/.test(optBody), optBody);

console.log("== 2FA opt-in intact (static) ==");
check("signup still offers the authenticator checkbox",
  html.includes('id="su-2fa"') && html.includes("Protect with authenticator app"));
check("text inputs still get the full-width rule",
  /#login-box input:not\(\[type=checkbox\]\)[^}]*width:\s*100%/.test(html));

console.log(`\n${PASS} passed, ${FAIL} failed`);
process.exit(FAIL ? 1 : 0);
