#!/bin/sh
# Crumbs HUD launcher for Mac - double-click to run.
cd "$(dirname "$0")"

if [ ! -f crumbs_hud.py ]; then
  echo "The zip wasn't fully extracted. Double-click crumbs-hud-v1.8.zip"
  echo "to extract it, then double-click start_mac.command inside the"
  echo "extracted folder."
  printf "Press Enter to close..."
  read dummy
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found."
  echo "Install it free from https://www.python.org/downloads/"
  echo "(or run: xcode-select --install), then double-click"
  echo "start_mac.command again."
  printf "Press Enter to close..."
  read dummy
  exit 1
fi

python3 crumbs_hud.py
