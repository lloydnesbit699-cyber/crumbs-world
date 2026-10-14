#!/usr/bin/env python3
r"""Crumbs World rename finisher — applies the 5 player-visible strings
Lloyd's commit missed, syncs the title probe, and adds /api/launcher-version.

Run on Harley in the game folder:
    cd C:\Users\lloyd\OneDrive\Desktop\Vault\crumbs-world
    python finish-rename.py

Idempotent: safe to re-run.
"""
import os
import re
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def replace_once(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        if new in src:
            print(f"  [skip] {label} — already applied")
            return True
        print(f"  [MISS] {label} — pattern not found")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new, 1))
    print(f"  [ok] {label}")
    return True

ok = True
print("editor.html — the 5 player-visible spots:")
e = "editor.html"
ok &= replace_once(e, "<title>Crumbs HUD", "<title>Crumbs World", "browser tab title")
ok &= replace_once(e, '<span id="title">Crumbs HUD', '<span id="title">Crumbs World', "header")
ok &= replace_once(e, "<h2>Crumbs HUD</h2>", "<h2>Crumbs World</h2>", "login screen")
ok &= replace_once(e, '<div class="splash-title">Crumbs HUD</div>',
                   '<div class="splash-title">Crumbs World</div>', "splash screen")
ok &= replace_once(e, "Welcome to Crumbs HUD", "Welcome to Crumbs World", "welcome toast")

print("crumbs_hud.py — probe sync + launcher endpoint:")
p = "crumbs_hud.py"
ok &= replace_once(p, 'if "<title>Crumbs HUD" not in body:',
                   'if "<title>Crumbs World" not in body:', "title probe (keep in sync)")

with open(p, encoding="utf-8") as f:
    src = f.read()
m = re.search(r'^APP_VERSION = "[^"]+"$', src, re.M)
if m and "LAUNCHER_VERSION_ANDROID" not in src:
    consts = m.group(0) + (
        "\n# v5.62: mobile launcher versions. The Android/iOS wrappers check\n"
        "# /api/launcher-version on every launch and self-update when these bump.\n"
        "# Set CRUMBS_LAUNCHER_APK_URL to the public URL of crumbs-world-launcher.apk\n"
        "# (drop the APK next to the server; it is served as a static file).\n"
        'LAUNCHER_VERSION_ANDROID = int(os.environ.get("CRUMBS_LAUNCHER_ANDROID", "1"))\n'
        'LAUNCHER_VERSION_IOS = int(os.environ.get("CRUMBS_LAUNCHER_IOS", "1"))\n'
        'LAUNCHER_APK_URL = os.environ.get("CRUMBS_LAUNCHER_APK_URL", "")')
    src = src.replace(m.group(0), consts, 1)
    print("  [ok] launcher version constants")
elif "LAUNCHER_VERSION_ANDROID" in src:
    print("  [skip] launcher version constants — already applied")
else:
    print("  [MISS] launcher version constants — APP_VERSION line not found")
    ok = False

ok &= replace_once(
    p,
    '''                             "instance": INSTANCE_ID})
        elif path == "/api/auth/me":''',
    '''                             "instance": INSTANCE_ID})
        elif path == "/api/launcher-version":
            # v5.62: no auth — lets the mobile launchers check for wrapper
            # updates. Bump LAUNCHER_VERSION_* when shipping a new wrapper;
            # drop the new APK next to the server as crumbs-world-launcher.apk
            # (served statically) and point apk_url at it.
            self._send_json({"ok": True,
                             "android_version": LAUNCHER_VERSION_ANDROID,
                             "android_apk_url": LAUNCHER_APK_URL,
                             "ios_version": LAUNCHER_VERSION_IOS})
        elif path == "/api/auth/me":''',
    "/api/launcher-version endpoint")

with open(p, "w", encoding="utf-8") as f:
    f.write(src)

print()
if ok:
    print("All applied. Next: git commit -am \"rename: last player-visible HUD strings\" && git push")
else:
    print("Some edits MISSED — send Wren the [MISS] lines.")
    sys.exit(1)
