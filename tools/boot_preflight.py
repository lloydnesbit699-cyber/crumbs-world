#!/usr/bin/env python3
"""Repair and verify Crumbs' pinned Python environment before serving login."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def install() -> bool:
    print("[preflight] repairing pinned Python dependencies")
    result = run(sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                 "-r", str(REQUIREMENTS))
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        print("[preflight] dependency repair failed: " + detail[-2000:], file=sys.stderr)
        return False
    return True


def verify() -> tuple[bool, str]:
    deps = run(sys.executable, "-m", "pip", "check")
    if deps.returncode:
        return False, "pip check failed: " + (deps.stdout + deps.stderr).strip()[-2000:]
    imports = run(sys.executable, "-c",
                  "import PIL, crumbs_core, crumbs_recovery, melody_agent")
    if imports.returncode:
        return False, "game/Melody imports failed: " + (imports.stdout + imports.stderr).strip()[-2000:]
    return True, "pinned dependencies and game/Melody imports are healthy"


def main() -> int:
    ok, message = verify()
    if not ok:
        print("[preflight] " + message)
        if not install():
            return 1
        ok, message = verify()
    if not ok:
        print("[preflight] " + message, file=sys.stderr)
        return 1
    print("[preflight] " + message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
