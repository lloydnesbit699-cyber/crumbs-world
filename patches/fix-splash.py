#!/usr/bin/env python3
r"""Fix the fullscreen splash logo flash-then-overwrite (v5.62).

Root cause (verified in editor.html): shellBoot() yanks the fullscreen
splash instantly, so the shield only shows for the JS-startup gap, then
the shell's dark screen paints over it.

Fix: shellBoot waits out the splash's 600ms minimum + fade before
painting the shell UI, so the shield displays instead of flashing past.
Classic boot path untouched (it already honors the 600ms minimum).

Run on Harley in the game folder:
    cd C:\Users\lloyd\OneDrive\Desktop\Vault\crumbs-world
    python fix-splash.py

Idempotent: safe to re-run.
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

with open("editor.html", encoding="utf-8") as f:
    src = f.read()

old = '  if (spl) spl.classList.add("gone");  // classic splash must not cover the shell'
new = '''  // v5.62: let the splash shield play its full beat (600ms minimum +
  // fade) before the shell paints over it — no more flash-then-overwrite.
  var _splashWait = Math.max(0, 600 - (Date.now() - _splashT0));
  if (_splashWait > 0) await new Promise(function (r) { setTimeout(r, _splashWait); });
  if (spl) spl.classList.add("gone");  // classic splash must not cover the shell
  await new Promise(function (r) { setTimeout(r, 500); });  // let the fade finish'''

if "_splashWait" in src:
    print("[skip] already applied")
elif old in src:
    src = src.replace(old, new, 1)
    with open("editor.html", "w", encoding="utf-8") as f:
        f.write(src)
    print("[ok] shellBoot waits for splash fade")
else:
    print("[MISS] shellBoot splash line not found — send Wren this output.")
    sys.exit(1)

print("Done. Next: git commit -am \"splash: shield plays full beat before shell paints\" && git push, then restart the server.")
