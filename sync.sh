#!/bin/bash
# sync.sh — one-command sync of this checkout with origin/main.
# Does the stash -> pull --rebase -> stash pop dance for you, safely.
#
# Your stuff is never at risk: maps, accounts, passwords and vaults live in
# gitignored files (vaults/, users.json, .crumbs_secret) that git won't touch.
#
# Usage:  bash sync.sh
# If the rebase hits a conflict it stops and tells you exactly how to back out.

set -u

echo "== fetching origin/main =="
git fetch origin || { echo "fetch failed — check network, then re-run"; exit 1; }

STASHED=0
if [ -n "$(git status --porcelain)" ]; then
  git stash -u -m "sync.sh autostash" || { echo "stash failed"; exit 1; }
  STASHED=1
  echo "parked local changes in the stash (git stash list to see it)"
fi

echo "== rebasing onto origin/main =="
if git pull --rebase origin main; then
  echo "rebase clean"
else
  echo ""
  echo "CONFLICT during rebase. Your work is safe. To back out, run:"
  echo ""
  echo "  git rebase --abort"
  echo ""
  echo "then tell Wren what the conflict was."
  exit 1
fi

if [ "$STASHED" = 1 ]; then
  echo "== restoring stashed changes =="
  git stash pop || {
    echo ""
    echo "stash pop hit a conflict. Resolve the files, then run: git stash drop"
    exit 1
  }
fi

echo ""
echo "done — now on $(git rev-parse --short HEAD): $(git log -1 --format=%s)"
