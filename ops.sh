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
#   ./ops.sh advise              — git status in plain English: shows what's
#                                  changed, ahead/behind, stashed, and how the
#                                  server looks, then offers a numbered menu
#                                  of the right next actions (stash, update,
#                                  commit, repair…).
#
# Re-exec guard: Lloyd runs things with `sh` out of habit and `sh` is dash,
# which chokes on bash-isms (arrays, [[ ]], etc.). This must stay the first
# executable statement — dash parses incrementally, so the exec fires before
# it ever reaches the bash-only lines below.
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi

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

live_version() {
  # Extracted from do_status so advise can reuse the same check.
  curl -s -m 5 "http://127.0.0.1:${PORT}/api/melody/health" \
    2>/dev/null | grep -o '"version": *"[^"]*"' | head -1 | cut -d'"' -f4 || true
}

do_status() {
  local pids health
  pids="$(server_pids)"
  if [ -z "$pids" ]; then
    echo "server: STOPPED   code version: $(code_version)"
    return 0
  fi
  health="$(live_version)"
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
  local f staged bad
  staged="$(git diff --cached --name-only 2>/dev/null || true)"
  for f in .crumbs_secret users.json; do
    if printf '%s\n' "$staged" | grep -qx "$f"; then
      say "!! $f was staged — unstaging it (it must never be committed)"
      git reset -q HEAD -- "$f" 2>/dev/null || true
    fi
  done
  # Same for the data dirs (vaults/, backups/): they're gitignored, but a
  # forced add or a stale index entry could still stage them, so sweep
  # any staged path under them too.
  bad="$(printf '%s\n' "$staged" | grep -E '^(vaults|backups)/' || true)"
  if [ -n "$bad" ]; then
    say "!! data files were staged — unstaging them (they must never be committed)"
    printf '%s\n' "$bad" | xargs git reset -q HEAD -- 2>/dev/null || true
  fi
}

check_divergence() {
  # Replit's publish flow writes local commits that wedge pull --rebase.
  # Ask once, up front, while the server is still running.
  local ahead ans=""
  ahead="$(local_ahead)"
  if [ "$ahead" = 0 ]; then return 0; fi
  echo "!! branch has diverged: $ahead local commit(s) not on origin/$BRANCH:"
  git --no-pager log --oneline "origin/$BRANCH..HEAD" 2>/dev/null || true
  echo "!! These are Replit's publish checkpoints fighting GitHub's main."
  echo "!! Vault data (tiles, imports, accounts) is NOT in git — it gets"
  echo "!! snapshotted to backups/ first, then verified intact after the reset."
  printf "Type REPAIR to drop them and continue the update: "
  read -r ans || true
  if [ "$ans" = "REPAIR" ]; then
    say "repairing: resetting to origin/$BRANCH"
    local vsnap
    vsnap="$(vault_snapshot)"
    do_backup  # law of three: every destructive git move gets a backup first
    git reset --hard "origin/$BRANCH" || die "reset failed — fix git state first"
    unstage_secrets
    vault_verify "$vsnap"
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
  local vsnap
  vsnap="$(vault_snapshot)"  # and fingerprint it, so the update must prove
                             # the data survived on the other side
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
  vault_verify "$vsnap"  # warn LOUD if the update shrank the vault data;
                         # never auto-restores — Lloyd runs ./ops.sh rollback
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
  git --no-pager log --oneline "origin/$BRANCH..HEAD" 2>/dev/null || true
  echo "!! These are Replit's publish checkpoints fighting GitHub's main."
  echo "!! Vault data (tiles, imports, accounts) is NOT in git — it gets"
  echo "!! snapshotted to backups/ first, then verified intact after the reset."
  printf "Type REPAIR to drop the local commits and sync: "
  read -r ans || true
  [ "$ans" = "REPAIR" ] || die "cancelled — nothing changed"
  local vsnap
  vsnap="$(vault_snapshot)"
  do_stop
  do_backup  # law of three: every destructive git move gets a backup first
  git reset --hard "origin/$BRANCH" || die "reset failed — fix git state first"
  # 2026-10-07: reset --hard does NOT clear a stale CHERRY_PICK_HEAD left by
  # a failed cherry-pick. --quit ends the cherry-pick while keeping the
  # just-reset tree exactly as it is (unlike --abort, which would move HEAD).
  git cherry-pick --quit 2>/dev/null || true
  unstage_secrets
  vault_verify "$vsnap"
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

vault_snapshot() {
  # Read-only fingerprint of the live user data. Prints three numbers:
  #   <custom-tile files under vaults/*/custom_tiles/> <users in users.json> <secret 0/1>
  # users = -1 when users.json is missing or unreadable. Never touches the
  # data — only counts it. Call BEFORE any destructive git move.
  local tiles=0 users=-1 secret=0
  if [ -d vaults ]; then
    tiles="$(find vaults -path '*/custom_tiles/*' -type f 2>/dev/null | wc -l | tr -d ' ')"
    [ -z "$tiles" ] && tiles=0
  fi
  if [ -f users.json ]; then
    users="$(python3 -c "import json;d=json.load(open('users.json'));print(len(d) if isinstance(d,dict) else -1)" 2>/dev/null || echo -1)"
  fi
  [ -f .crumbs_secret ] && secret=1
  printf '%s %s %s' "$tiles" "$users" "$secret"
}

vault_verify() {
  # $1 = vault_snapshot output from BEFORE the risky part. Re-snapshots now
  # and compares. Intact -> "vault check: intact — N tile files, M users".
  # Anything shrank or vanished -> LOUD warning naming exactly what changed
  # plus the rollback pointer. Never auto-restores: Lloyd decides.
  # Returns 0 intact, 1 if anything was lost.
  local before="${1:-}" after
  local bt bu bs at au as lost=0
  after="$(vault_snapshot)"
  bt="${before%% *}"; bu="${before#* }"; bu="${bu% *}"; bs="${before##* }"
  at="${after%% *}"; au="${after#* }"; au="${au% *}"; as="${after##* }"
  if [ -z "$bt" ]; then
    say "vault check: skipped (no before-snapshot)"
    return 0
  fi
  if [ "$at" -lt "$bt" ] 2>/dev/null; then
    echo "!!   custom tile files: $bt -> $at  ($((bt - at)) FEWER)"
    lost=1
  fi
  if [ "$bu" -ge 0 ] 2>/dev/null; then
    if [ "$au" = "-1" ]; then
      echo "!!   users.json is GONE (had $bu users)"
      lost=1
    elif [ "$au" -lt "$bu" ] 2>/dev/null; then
      echo "!!   users in users.json: $bu -> $au  ($((bu - au)) FEWER — possible fresh-empty-vault scenario)"
      lost=1
    fi
  fi
  if [ "$bs" = "1" ] && [ "$as" = "0" ]; then
    echo "!!   .crumbs_secret is GONE (was present)"
    lost=1
  fi
  if [ "$lost" = "1" ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!! VAULT DATA SHRANK ACROSS THIS OPERATION (details above)."
    echo "!! Your pre-operation backup is the newest file in backups/."
    echo "!! To restore it:  ./ops.sh rollback"
    echo "!! (rollback snapshots your current state first — it's undoable)"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    return 1
  fi
  local ud="$au"; [ "$au" = "-1" ] && ud="no users.json"
  say "vault check: intact — $at custom tile files, $ud users"
  return 0
}
# ---- end backup protocol ---------------------------------------------------

# ---- advise: git status in plain English + a numbered menu ----------------
do_push() {
  say "pushing to origin/$BRANCH"
  git push "origin" "$BRANCH" || die "push failed — check network/access"
  say "pushed"
}

do_commit() {
  local msg=""
  printf "commit message (one line): "
  read -r msg || true
  [ -n "$msg" ] || die "cancelled — nothing changed"
  git add -A
  unstage_secrets  # secrets + data dirs can never ride along
  if [ -z "$(git diff --cached --name-only 2>/dev/null)" ]; then
    say "nothing to commit — only secrets/data changed, and those never commit"
    return 0
  fi
  git commit -q -m "$msg" || die "commit failed"
  say "committed: $(git log --oneline -1)"
}

do_discard() {
  local ans=""
  echo "!! This THROWS AWAY every local change — edited files AND new (untracked) files."
  printf "Type DISCARD to continue: "
  read -r ans || true
  [ "$ans" = "DISCARD" ] || die "cancelled — nothing changed"
  git reset -q --hard HEAD
  git clean -fdq
  unstage_secrets
  say "local changes discarded"
}

do_drop_stash() {
  local top ans=""
  top="$(git stash list | head -1)"
  [ -n "$top" ] || { say "no stashes"; return 0; }
  echo "!! This PERMANENTLY deletes the newest stash: $top"
  printf "Type DROP to continue: "
  read -r ans || true
  [ "$ans" = "DROP" ] || die "cancelled — nothing changed"
  git stash drop -q || die "drop failed"
  say "stash dropped"
}

do_advise() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "not a git repo — run this from the repo root"
  local fetched=1
  say "advise: checking..."
  git fetch origin >/dev/null 2>&1 \
    || { fetched=0; say "!! fetch failed (offline?) — advising from local info only"; }

  while true; do
    # ---- diagnose (read-only) ----
    local porcelain n_modified n_untracked n_deleted names line
    porcelain="$(git status --porcelain 2>/dev/null || true)"
    n_modified=0; n_untracked=0; n_deleted=0
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      case "$line" in
        '??'*) n_untracked=$((n_untracked + 1)) ;;
        ?D*|D?*) n_deleted=$((n_deleted + 1)) ;;
        *)     n_modified=$((n_modified + 1)) ;;
      esac
    done <<< "$porcelain"
    names="$(printf '%s\n' "$porcelain" | cut -c4- | head -6 | tr '\n' ' ')"

    local ahead=0 behind=0 counts
    if [ "$fetched" = 1 ] \
       && git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
      counts="$(git rev-list --left-right --count "HEAD...origin/$BRANCH" 2>/dev/null || printf '0\t0')"
      ahead="${counts%%$'\t'*}"; behind="${counts##*$'\t'}"
    fi

    local n_stash pids code live dirty
    n_stash="$(git stash list 2>/dev/null | wc -l | tr -d ' ')"
    pids="$(server_pids)"
    code="$(code_version)"
    live=""
    [ -n "$pids" ] && live="$(live_version)"
    dirty=0
    [ "$((n_modified + n_untracked + n_deleted))" != 0 ] && dirty=1

    # ---- summarize ----
    echo "---"
    if [ "$dirty" = 1 ]; then
      echo "worktree: $n_modified modified, $n_untracked untracked, $n_deleted deleted"
      [ -n "$names" ] && echo "  $names"
    else
      echo "worktree: clean"
    fi
    if [ "$fetched" = 0 ]; then
      echo "branch: unknown (fetch failed)"
    elif [ "$ahead" != 0 ] && [ "$behind" != 0 ]; then
      echo "branch: DIVERGED — ahead $ahead, behind $behind"
    elif [ "$ahead" != 0 ]; then
      echo "branch: ahead of origin/$BRANCH by $ahead"
    elif [ "$behind" != 0 ]; then
      echo "branch: behind origin/$BRANCH by $behind"
    else
      echo "branch: in sync with origin/$BRANCH"
    fi
    if [ "$n_stash" = 0 ]; then echo "stash: none"; else echo "stash: $n_stash saved"; fi
    if [ -z "$pids" ]; then
      echo "server: STOPPED (code $code)"
    elif [ -n "$live" ] && [ "$code" != "$live" ]; then
      echo "server: RUNNING, but code $code != live $live"
    else
      echo "server: RUNNING, code $code${live:+, live $live}"
    fi
    echo "---"

    # ---- numbered menu: only what fits the current state ----
    local labels=() actions=()
    if [ "$dirty" = 1 ]; then
      labels+=("stash my changes");              actions+=(stash)
      labels+=("update: stash + pull + restart"); actions+=(update)
      labels+=("commit my changes");             actions+=(commit)
      labels+=("DISCARD all local changes");     actions+=(discard)
    fi
    if [ "$ahead" != 0 ] && [ "$behind" != 0 ]; then
      labels+=("repair diverged branch");        actions+=(repair)
    elif [ "$ahead" != 0 ]; then
      labels+=("push to origin/$BRANCH");        actions+=(push)
    elif [ "$behind" != 0 ]; then
      labels+=("update: pull + restart");        actions+=(update)
    fi
    if [ "$n_stash" != 0 ]; then
      labels+=("pop the newest stash");          actions+=(pop)
      labels+=("list stashes");                 actions+=(list)
      labels+=("DROP the newest stash");        actions+=(drop)
    fi
    if [ -z "$pids" ]; then
      labels+=("start the server");              actions+=(start)
    elif [ -n "$live" ] && [ "$code" != "$live" ]; then
      labels+=("restart (code $code, live $live)"); actions+=(restart)
    fi
    if [ "${#labels[@]}" = 0 ]; then
      echo "all good — nothing needs doing."
      labels+=("show server log");               actions+=(logs)
    fi

    local i pick=""
    for i in "${!labels[@]}"; do
      printf "  %d) %s\n" "$((i + 1))" "${labels[$i]}"
    done
    printf "  0) nothing — quit\n"
    if [ ! -t 0 ]; then
      say "not a terminal — run ./ops.sh advise on the shell to pick an action"
      return 0
    fi
    printf "pick a number: "
    if ! read -r pick; then echo; say "bye"; return 0; fi
    case "$pick" in
      0) say "nothing changed"; return 0 ;;
      ''|*[!0-9]*) echo "not a number — try again"; continue ;;
    esac
    if [ "$pick" -lt 1 ] || [ "$pick" -gt "${#labels[@]}" ]; then
      echo "pick 0–${#labels[@]}"; continue
    fi
    case "${actions[$((pick - 1))]}" in
      stash)   do_stash ;;
      update)  do_update ;;
      commit)  do_commit ;;
      discard) do_discard ;;
      push)    do_push ;;
      repair)  do_repair ;;
      pop)     do_stash_pop ;;
      list)    do_stash_list ;;
      drop)    do_drop_stash ;;
      start)   do_start ;;
      restart) do_stop; do_start ;;
      logs)    do_logs ;;
    esac
    echo ""
    # loop: re-diagnose so the menu always matches the new state
  done
}
# ---- end advise ------------------------------------------------------------

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
  advise)     do_advise ;;
  help|--help|-h) sed -n '2,44p' "$0" ;;
  *) die "unknown command: $cmd  (try: ./ops.sh help)" ;;
esac
