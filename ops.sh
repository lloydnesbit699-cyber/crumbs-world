#!/usr/bin/env bash
#
# ops.sh — Lloyd's permanent Replit workflow. Lives in the repo so it
# survives restarts, syncs, and fresh clones. Run from the repo root.
#
#   ./ops.sh boot                — for Replit's run button: sync to origin/main,
#                                  then start the server. Never leaves the
#                                  server down — if git fails it starts with
#                                  local code and says so.
#   ./ops.sh update              — THE one command: stop server, stash your
#                                  changes, pull --rebase, re-apply stash,
#                                  restart server. Safe on conflicts: aborts
#                                  and hands your files back untouched.
#                                  Spots a diverged branch first and offers
#                                  repair (type REPAIR) before touching
#                                  anything.
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
#   ./ops.sh backup              — snapshot your data (vaults/, users.json,
#                                  .crumbs_secret) into backups/. Keeps the 3
#                                  newest (law of three). Download one to your
#                                  phone and the data lives in three places.
#   ./ops.sh rollback            — restore the newest backup (asks first),
#                                  then restart. The "undo" for a bad update.
#   ./ops.sh repair              — fix a diverged branch: Replit's publish
#                                  flow writes local commits that fight
#                                  GitHub's main and wedge the updater.
#                                  Shows the local commits, asks for REPAIR,
#                                  then resets hard to origin/main and
#                                  restarts. The "un-wedge" for a bad pull.
#
set -u

PORT="${PORT:-5000}"
# PUBLIC=1 = multi-user server mode (--public), matching Replit's run button.
# PUBLIC=0 = local single-user mode. Override per-command: PUBLIC=0 ./ops.sh start
PUBLIC="${PUBLIC:-1}"
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
  if [ "$PUBLIC" = "1" ]; then
    say "starting server on port $PORT --public (log: $LOG)"
    PORT="$PORT" nohup python3 "$APP" --public >>"$LOG" 2>&1 &
  else
    say "starting server on port $PORT, local single-user mode (log: $LOG)"
    PORT="$PORT" nohup python3 "$APP" >>"$LOG" 2>&1 &
  fi
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

# How many commits the local branch has that origin/$BRANCH doesn't.
local_ahead() {
  git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0
}

unstage_secrets() {
  # Never let secret files sit staged: a later commit would publish them
  # to GitHub. (A stuck rebase once staged .crumbs_secret — this is the
  # guardrail so it can never ride along again.)
  local f staged
  staged="$(git diff --cached --name-only 2>/dev/null || true)"
  for f in .crumbs_secret users.json; do
    if printf '%s\n' "$staged" | grep -qx "$f"; then
      say "!! $f was staged — unstaging it (it must never be committed)"
      git reset -q HEAD -- "$f" 2>/dev/null || true
    fi
  done
}

check_divergence() {
  # Replit's publish flow writes local commits that wedge pull --rebase.
  # Ask once, up front, while the server is still running.
  local ahead ans=""
  ahead="$(local_ahead)"
  if [ "$ahead" = 0 ]; then return 0; fi
  echo "!! branch has diverged: $ahead local commit(s) not on origin/$BRANCH:"
  git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null || true
  echo "!! These are Replit's publish checkpoints fighting GitHub's main."
  echo "!! Your real work is safe — it lives in the commits Wren pushed."
  printf "Type REPAIR to drop them and continue the update: "
  read -r ans || true
  if [ "$ans" = "REPAIR" ]; then
    say "repairing: resetting to origin/$BRANCH"
    git reset --hard "origin/$BRANCH" || die "reset failed — fix git state first"
    unstage_secrets
  else
    die "cancelled — nothing changed (server still running). ./ops.sh repair does this on its own."
  fi
}

do_update() {
  # fetch -> repair check -> stop -> backup -> stash -> pull --rebase ->
  # pop stash -> start
  git fetch origin || die "git fetch failed — check network"
  check_divergence  # dies on decline; server still up at this point
  do_stop
  do_backup  # law of three: snapshot the live data BEFORE the risky part,
             # so a bad update can immediately pull the last working state
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
    unstage_secrets
    if [ "$dirty" = 1 ]; then git stash pop 2>/dev/null || true; fi
    unstage_secrets
    die "update aborted cleanly; nothing was lost"
  fi
  unstage_secrets
  local stash_failed=0
  if [ "$dirty" = 1 ]; then
    say "re-applying your stashed changes"
    if ! git stash pop; then
      say "!! stash pop hit a snag — your changes are SAFE in the stash."
      say "!! run './ops.sh stash-list' and sort it out by hand"
      stash_failed=1
    fi
    unstage_secrets
  fi
  say "now at: $(git log --oneline -1)"
  do_start
  if [ "$stash_failed" = 1 ]; then
    die "update finished, server is up — BUT your stashed changes still need attention (see above)"
  fi
  say "update done"
}

do_boot() {
  # Boot-safe auto-update, wired to Replit's run button (.replit points here).
  # Same shape as update, but it NEVER dies before the server is up: any git
  # failure just means "start with local code" plus a loud warning in the log.
  do_stop
  local synced="no"
  if git fetch origin 2>/dev/null; then
    local dirty=0
    if [ -n "$(git status --porcelain)" ]; then dirty=1; fi
    if [ "$dirty" = 1 ]; then
      say "stashing local changes for boot pull"
      git stash push -u -m "ops.sh boot-stash $(date '+%F %T')" 2>/dev/null || dirty=0
    fi
    if git pull --rebase origin "$BRANCH" 2>/dev/null; then
      synced="yes"
      say "boot synced: $(git log --oneline -1)"
    else
      git rebase --abort 2>/dev/null || true
      say "!! boot pull failed — starting with local code"
    fi
    if [ "$dirty" = 1 ]; then
      git stash pop 2>/dev/null \
        || say "!! boot stash needs attention — './ops.sh stash-list'; files are safe in the stash"
    fi
  else
    say "!! boot fetch failed (offline?) — starting with local code"
  fi
  if [ "$synced" = "no" ]; then
    say "now at (local): $(git log --oneline -1)"
  else
    say "now at: $(git log --oneline -1)"
  fi
  do_start
  say "boot done"
}

do_repair() {
  # Standalone un-wedger for a diverged branch. Same repair check_divergence
  # does inside update, without the stop/backup/pull dance.
  git fetch origin || die "git fetch failed — check network"
  local ahead behind ans=""
  ahead="$(local_ahead)"
  if [ "$ahead" = 0 ]; then
    say "branch is not ahead of origin/$BRANCH — nothing to repair"
    return 0
  fi
  behind="$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"
  echo "!! $ahead local commit(s) to drop, $behind commit(s) behind origin/$BRANCH:"
  git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null || true
  echo "!! These are Replit's publish checkpoints fighting GitHub's main."
  echo "!! Your real work is safe — it lives in the commits Wren pushed."
  printf "Type REPAIR to drop the local commits and sync: "
  read -r ans || true
  [ "$ans" = "REPAIR" ] || die "cancelled — nothing changed"
  do_stop
  git reset --hard "origin/$BRANCH" || die "reset failed — fix git state first"
  unstage_secrets
  say "now at: $(git log --oneline -1)"
  do_start
  say "repair done"
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

# ---- Law of Three: backup protocol ---------------------------------------
# Three copies, each runnable: the server that runs (rolling snapshots in
# backups/), the repo that ships (full git history on GitHub), and Lloyd's
# phone (a downloaded snapshot). One goes down, the other two pick it up.
BACKUP_DIR="backups"
KEEP_BACKUPS=3  # the law of three: three rolling snapshots, no more

do_backup() {
  mkdir -p "$BACKUP_DIR"
  local stamp file
  # PID in the name: two backups inside the same second must never share a
  # filename, or the newer silently overwrites the older (rollback's
  # pre-restore snapshot once ate the snapshot it was about to restore).
  stamp="$(date '+%Y%m%d-%H%M%S')-$$"
  file="$BACKUP_DIR/crumbs-data-$stamp.tar.gz"
  # Only pack what actually exists — never fail on a missing piece.
  local items=()
  [ -d vaults ] && items+=(vaults)
  [ -f users.json ] && items+=(users.json)
  [ -f .crumbs_secret ] && items+=(.crumbs_secret)
  if [ "${#items[@]}" = 0 ]; then
    say "nothing to back up (no vaults/, users.json, or .crumbs_secret)"
    return 0
  fi
  tar -czf "$file" "${items[@]}" || die "backup failed"
  say "backup written: $file"
  # Prune to the newest $KEEP_BACKUPS.
  local old
  old="$(ls -t "$BACKUP_DIR"/crumbs-data-*.tar.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) || true)"
  if [ -n "$old" ]; then
    echo "$old" | xargs rm -f
    say "pruned older snapshots (keeping $KEEP_BACKUPS)"
  fi
  say "tip: download $file from the file pane to your phone — then your data lives in three places"
}

do_rollback() {
  local latest target ans
  latest="$(ls -t "$BACKUP_DIR"/crumbs-data-*.tar.gz 2>/dev/null | head -1 || true)"
  [ -n "$latest" ] || die "no backups in $BACKUP_DIR — run ./ops.sh backup first"
  echo "!! This OVERWRITES your live data with: $latest"
  echo "!! vaults/, users.json, .crumbs_secret will be replaced."
  printf "Type RESTORE to continue: "
  read -r ans
  [ "$ans" = "RESTORE" ] || die "cancelled — nothing changed"
  target="$latest"
  do_stop
  say "snapshotting current state first (so this rollback is undoable)"
  do_backup >/dev/null 2>&1 || true
  say "restoring from $target"
  tar -xzf "$target" || die "restore failed — your pre-restore snapshot is the newest file in $BACKUP_DIR"
  do_start
  say "rollback done — server is back on the restored data"
}
# ---- end backup protocol ---------------------------------------------------

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
  boot)       do_boot ;;
  cherry-pick|cherrypick|cp) do_cherry_pick "${2:-}" ;;
  stash)      do_stash ;;
  stash-pop)  do_stash_pop ;;
  stash-list) do_stash_list ;;
  backup)     do_backup ;;
  rollback)   do_rollback ;;
  repair)     do_repair ;;
  help|--help|-h) sed -n '2,24p' "$0" ;;
  *) die "unknown command: $cmd  (try: ./ops.sh help)" ;;
esac
