#!/usr/bin/env bash
#
# ops.sh — Lloyd's permanent Replit workflow. Lives in the repo so it
# survives restarts, syncs, and fresh clones. Run from the repo root.
#
#   ./ops.sh update              — THE one command: stop server, stash your
#                                  changes, pull --rebase, re-apply stash,
#                                  restart server. Safe on conflicts: aborts
#                                  and hands your files back untouched.
#   ./ops.sh status              — is the server running? which version?
#   ./ops.sh start               — start the server (PORT=5000 pinned)
#   ./ops.sh stop                — stop it for real (kills stuck processes)
#   ./ops.sh restart             — stop + start
#   ./ops.sh logs                — tail the server log
#   ./ops.sh cherry-pick <sha>   — fetch origin, pick ONE commit, restart.
#                                  Aborts cleanly on conflict.
#   ./ops.sh stash               — stash local changes (timestamped)
#   ./ops.sh stash-pop           — re-apply the latest stash
#   ./ops.sh stash-list          — show stashes
#
set -u

PORT="${PORT:-5000}"
APP="crumbs_hud.py"
LOG="server.log"
BRANCH="${OPS_BRANCH:-main}"

die() { echo "!! $*" >&2; exit 1; }
say() { echo ">> $*"; }

server_pids() {
  # Full-command-line match; the [c] trick keeps pgrep from matching itself.
  pgrep -f "[c]rumbs_hud[.]py" 2>/dev/null || true
}

code_version() {
  grep -m1 '^APP_VERSION' "$APP" 2>/dev/null | cut -d'"' -f2 || echo "?"
}

do_stop() {
  local pids
  pids="$(server_pids)"
  if [ -z "$pids" ]; then
    say "server already stopped"
    return 0
  fi
  say "stopping server (PIDs: $pids)"
  kill $pids 2>/dev/null || true
  sleep 2
  pids="$(server_pids)"
  if [ -n "$pids" ]; then
    say "still alive — force killing: $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
  # Belt and suspenders: free the port itself too.
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
  fi
  if [ -z "$(server_pids)" ]; then
    say "server stopped"
  else
    die "could not stop the server — check it manually"
  fi
}

do_start() {
  if [ -n "$(server_pids)" ]; then
    say "server already running: $(server_pids)"
    return 0
  fi
  [ -f "$APP" ] || die "can't find $APP — run this from the repo root"
  say "starting server on port $PORT (log: $LOG)"
  PORT="$PORT" nohup python3 "$APP" >>"$LOG" 2>&1 &
  sleep 3
  if [ -n "$(server_pids)" ]; then
    say "server running: $(server_pids)"
    do_status
  else
    die "server didn't start — run ./ops.sh logs"
  fi
}

do_status() {
  local pids health
  pids="$(server_pids)"
  if [ -z "$pids" ]; then
    echo "server: STOPPED   code version: $(code_version)"
    return 0
  fi
  health="$(curl -s -m 5 "http://127.0.0.1:${PORT}/api/melody/health" \
    2>/dev/null | grep -o '"version": *"[^"]*"' | head -1 | cut -d'"' -f4 || true)"
  echo "server: RUNNING (PID $pids) port $PORT  code $(code_version)${health:+  live $health}"
}

do_update() {
  # stop -> stash -> pull --rebase -> pop stash -> start
  do_stop
  git fetch origin || die "git fetch failed — check network"
  local dirty=0
  if [ -n "$(git status --porcelain)" ]; then dirty=1; fi
  if [ "$dirty" = 1 ]; then
    say "stashing your local changes"
    git stash push -u -m "ops.sh auto-stash $(date '+%F %T')" \
      || die "stash failed — fix git state first"
  fi
  say "pulling --rebase origin/$BRANCH"
  if ! git pull --rebase "origin" "$BRANCH"; then
    say "pull hit conflicts — aborting, giving your files back"
    git rebase --abort 2>/dev/null || true
    if [ "$dirty" = 1 ]; then git stash pop 2>/dev/null || true; fi
    die "update aborted cleanly; nothing was lost"
  fi
  local stash_failed=0
  if [ "$dirty" = 1 ]; then
    say "re-applying your stashed changes"
    if ! git stash pop; then
      say "!! stash pop hit a snag — your changes are SAFE in the stash."
      say "!! run './ops.sh stash-list' and sort it out by hand"
      stash_failed=1
    fi
  fi
  say "now at: $(git log --oneline -1)"
  do_start
  if [ "$stash_failed" = 1 ]; then
    die "update finished, server is up — BUT your stashed changes still need attention (see above)"
  fi
  say "update done"
}

do_cherry_pick() {
  local sha="${1:-}"
  [ -n "$sha" ] || die "usage: ./ops.sh cherry-pick <commit-sha>"
  do_stop
  git fetch origin || die "git fetch failed — check network"
  say "cherry-pick $sha"
  if git cherry-pick "$sha"; then
    say "picked: $(git log --oneline -1)"
  else
    git cherry-pick --abort 2>/dev/null || true
    do_start
    die "conflict — aborted cleanly, server restarted, nothing changed"
  fi
  do_start
}

do_stash() {
  git stash push -u -m "ops.sh manual stash $(date '+%F %T')"
  say "stashed"
}

do_stash_pop() { git stash pop; }
do_stash_list() { git stash list; }
do_logs() {
  if [ -f "$LOG" ]; then tail -n 50 "$LOG"; else echo "no log yet"; fi
}

cmd="${1:-help}"
case "$cmd" in
  start)      do_start ;;
  stop)       do_stop ;;
  restart)    do_stop; do_start ;;
  status)     do_status ;;
  logs)       do_logs ;;
  update)     do_update ;;
  cherry-pick|cherrypick|cp) do_cherry_pick "${2:-}" ;;
  stash)      do_stash ;;
  stash-pop)  do_stash_pop ;;
  stash-list) do_stash_list ;;
  help|--help|-h) sed -n '2,17p' "$0" ;;
  *) die "unknown command: $cmd  (try: ./ops.sh help)" ;;
esac
