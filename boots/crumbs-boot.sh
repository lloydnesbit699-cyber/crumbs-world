#!/usr/bin/env bash
set -Eeuo pipefail

BOOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
GAME_DIR=$(cd -- "$BOOT_DIR/.." && pwd)
SERVER_FILE=crumbs_hud.py
SERVER_SCRIPT=$GAME_DIR/$SERVER_FILE
PORT=${PORT:-${CRUMBS_PORT:-8778}}
PID_FILE=$GAME_DIR/.crumbs_hud.pid
LOG_DIR=$GAME_DIR/logs
VENV_DIR=$GAME_DIR/.venv

usage() {
  cat <<'EOF'
Usage: crumbs-boot.sh [--stop] [--check]

Start or verify the local Crumbs World server. The server stays bound to
127.0.0.1; this script does not publish it to the network.

  --stop   Ask the local server to save and shut down; stop only a verified
           Crumbs process if its HTTP shutdown endpoint is unavailable.
  --check  Verify /api/health without starting or changing anything.
EOF
}
log() { printf 'crumbs-boot: %s\n' "$*"; }
warn() { printf 'crumbs-boot: WARNING: %s\n' "$*" >&2; }
die() { printf 'crumbs-boot: ERROR: %s\n' "$*" >&2; exit 1; }

STOP=0
CHECK=0
while (($#)); do
  case "$1" in
    --stop) STOP=1; shift ;;
    --check) CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (use --help)" ;;
  esac
done
[[ "$STOP" -eq 0 || "$CHECK" -eq 0 ]] || die "--stop and --check cannot be combined"
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] && ((10#$PORT >= 1 && 10#$PORT <= 65535)) ||
  die "PORT must be a number from 1 through 65535"
[[ -f "$SERVER_SCRIPT" ]] || die "server script not found: $SERVER_SCRIPT"
command -v curl >/dev/null 2>&1 || die "curl is required for the health check"
cd -- "$GAME_DIR"

HEALTH_URL=http://127.0.0.1:$PORT/api/health
health() {
  local body
  body=$(curl --fail --silent --show-error --max-time 2 "$HEALTH_URL" 2>/dev/null) || return 1
  grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' <<<"$body" || return 1
  printf '%s\n' "$body"
}

if ((CHECK)); then
  body=$(health) || die "Crumbs World did not answer health check at $HEALTH_URL"
  log "server is healthy: $body"
  exit 0
fi

process_matches_server() {
  local pid=$1 cmd
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  cmd=$(ps -p "$pid" -o command= 2>/dev/null) || return 1
  [[ "$cmd" == *"$SERVER_SCRIPT"* ]]
}

if ((STOP)); then
  if body=$(health); then
    log "requesting graceful save and shutdown"
    curl --silent --show-error --max-time 3 -X POST \
      -H 'Content-Type: application/json' -d '{}' \
      "http://127.0.0.1:$PORT/api/shutdown" >/dev/null ||
      warn "shutdown endpoint did not answer; checking owned PID"
  fi
  if [[ -f "$PID_FILE" ]]; then
    read -r old_pid <"$PID_FILE" || old_pid=
    if process_matches_server "$old_pid"; then
      kill -TERM "$old_pid" 2>/dev/null || true
      for _ in {1..10}; do
        kill -0 "$old_pid" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "$old_pid" 2>/dev/null; then
        die "server PID $old_pid did not stop; refusing to force-kill it"
      fi
      log "stopped server PID $old_pid"
    fi
    rm -f -- "$PID_FILE"
  fi
  exit 0
fi

if body=$(health); then
  log "server is already UP on port $PORT: $body"
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  read -r old_pid <"$PID_FILE" || old_pid=
  if process_matches_server "$old_pid"; then
    die "server process $old_pid is running but its health check failed; inspect logs before starting another instance"
  fi
  rm -f -- "$PID_FILE"
fi

PYTHON=
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON=$(command -v "$candidate"); break; fi
done
[[ -n "$PYTHON" ]] || die "Python 3 is required; install Python 3 and rerun this launcher"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  log "creating the project-local Python environment"
  "$PYTHON" -m venv "$VENV_DIR" || die "could not create .venv"
fi
PYTHON=$VENV_DIR/bin/python
"$PYTHON" "$GAME_DIR/tools/boot_preflight.py" ||
  die "boot preflight failed; repair the project .venv before serving login"

mkdir -p -- "$LOG_DIR" || die "cannot create log directory $LOG_DIR"
STAMP=$(date '+%Y%m%d-%H%M%S')
LOG_FILE=$LOG_DIR/crumbs_hud_$STAMP.out.log
umask 077
nohup env PORT="$PORT" CRUMBS_TESTER_SHELL="${CRUMBS_TESTER_SHELL:-1}" \
  "$PYTHON" "$SERVER_SCRIPT" >>"$LOG_FILE" 2>&1 </dev/null &
SERVER_PID=$!
PID_TMP=$(mktemp "$GAME_DIR/.crumbs_hud.pid.XXXXXX") ||
  die "cannot create temporary PID file"
printf '%s\n' "$SERVER_PID" >"$PID_TMP"
chmod 600 "$PID_TMP"
mv -f -- "$PID_TMP" "$PID_FILE"

for _ in {1..30}; do
  if body=$(health); then
    log "server is UP on port $PORT (pid $SERVER_PID): $body"
    log "log: $LOG_FILE"
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
  sleep 1
done

log "server did not become healthy; recent log output:"
tail -n 40 "$LOG_FILE" 2>/dev/null || true
if process_matches_server "$SERVER_PID"; then
  kill -TERM "$SERVER_PID" 2>/dev/null || true
fi
rm -f -- "$PID_FILE"
exit 1
