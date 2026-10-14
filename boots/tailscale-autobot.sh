#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: tailscale-autobot.sh [--ssh] [--funnel PORT] [--hostname NAME] [--peer NAME_OR_IP] [--auth-key-file PATH]

Install Tailscale when supported, connect this device, and verify its status.
By default, Tailscale SSH is explicitly disabled and no new Funnel is created.

  --ssh             Enable Tailscale SSH after a separate typed confirmation.
  --funnel PORT     Publish a local HTTP service to the public internet after
                    a separate typed confirmation. PORT must already be serving.
  --hostname NAME   Set this device's Tailscale hostname.
  --peer NAME_OR_IP Optionally ping a known online peer after connecting.
  --auth-key-file  Read a Tailscale auth key from a private file; never pass
                   the key itself on the command line.
  -h, --help        Show this help.

Linux package installation uses Tailscale's official install script over HTTPS
and asks sudo to install it. macOS uses Homebrew's open-source Tailscale service.
EOF
}

log() { printf '[..] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[!!] %s\n' "$*" >&2; }
die() { printf '[FAIL] %s\n' "$*" >&2; exit "${2:-1}"; }

SSH_REQUESTED=0
FUNNEL_PORT=
HOSTNAME=
PEER=
AUTH_KEY_FILE=
while (($#)); do
  case "$1" in
    --ssh) SSH_REQUESTED=1; shift ;;
    --funnel)
      (($# >= 2)) || die "--funnel requires a local TCP port"
      FUNNEL_PORT=$2
      shift 2
      ;;
    --hostname)
      (($# >= 2)) || die "--hostname requires a name"
      HOSTNAME=$2
      shift 2
      ;;
    --peer)
      (($# >= 2)) || die "--peer requires a peer name or Tailscale IP"
      PEER=$2
      shift 2
      ;;
    --auth-key-file)
      (($# >= 2)) || die "--auth-key-file requires a path"
      AUTH_KEY_FILE=$2
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (use --help)" ;;
  esac
done

OS=$(uname -s)
if [[ -n "$FUNNEL_PORT" ]]; then
  [[ "$FUNNEL_PORT" =~ ^[0-9]{1,5}$ ]] || die "--funnel port must be a number from 1 through 65535"
  ((10#$FUNNEL_PORT >= 1 && 10#$FUNNEL_PORT <= 65535)) || die "--funnel port must be a number from 1 through 65535"
fi
if [[ -n "$HOSTNAME" && ! "$HOSTNAME" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,62}$ ]]; then
  die "hostname must be 1-63 letters, digits, or hyphens and start with a letter or digit"
fi
if [[ -n "$AUTH_KEY_FILE" ]]; then
  [[ -f "$AUTH_KEY_FILE" && ! -L "$AUTH_KEY_FILE" ]] ||
    die "auth-key file must be a regular, non-symlink file"
  AUTH_KEY_FILE=$(cd -- "$(dirname -- "$AUTH_KEY_FILE")" && pwd)/$(basename -- "$AUTH_KEY_FILE")
  if [[ "$OS" == Darwin ]]; then
    KEY_MODE=$(stat -f '%Lp' "$AUTH_KEY_FILE") || die "cannot inspect auth-key file permissions"
    KEY_OWNER=$(stat -f '%u' "$AUTH_KEY_FILE") || die "cannot inspect auth-key file owner"
  else
    KEY_MODE=$(stat -c '%a' "$AUTH_KEY_FILE") || die "cannot inspect auth-key file permissions"
    KEY_OWNER=$(stat -c '%u' "$AUTH_KEY_FILE") || die "cannot inspect auth-key file owner"
  fi
  ((KEY_OWNER == EUID && (8#$KEY_MODE & 077) == 0)) ||
    die "auth-key file must be owned by this user and have no group/other permissions (chmod 600)"
  [[ -s "$AUTH_KEY_FILE" ]] || die "auth-key file is empty"
fi

confirm_exposure() {
  local description=$1 answer
  [[ -r /dev/tty && -w /dev/tty ]] || die "refusing exposure change without an interactive terminal: $description"
  printf '\n[EXPOSURE WARNING] %s\n' "$description" >/dev/tty
  printf 'Type YES to continue; anything else cancels this exposure change: ' >/dev/tty
  IFS= read -r answer </dev/tty || answer=
  [[ "$answer" == YES ]]
}

ENABLE_SSH=0
if ((SSH_REQUESTED)); then
  if confirm_exposure "This enables Tailscale SSH on this machine. Tailnet policy may allow authorized tailnet users to open remote shell sessions."; then
    ENABLE_SSH=1
  else
    warn "SSH enablement cancelled; Tailscale SSH will remain disabled."
  fi
fi

ENABLE_FUNNEL=0
if [[ -n "$FUNNEL_PORT" ]]; then
  if confirm_exposure "This publishes the local HTTP service on port $FUNNEL_PORT to the public internet through Tailscale Funnel. Anyone with its URL may reach it; do not expose private or unreviewed services."; then
    ENABLE_FUNNEL=1
  else
    warn "Funnel enablement cancelled; no new public Funnel will be created."
  fi
fi

TAILSCALE=
TAILSCALE_ENV=()
SUDO=()
INSTALL_TMP=
cleanup() {
  if [[ -n "$INSTALL_TMP" ]]; then rm -f -- "$INSTALL_TMP"; fi
}
trap cleanup EXIT

find_tailscale() {
  if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE=$(command -v tailscale)
    return 0
  fi
  if [[ "$OS" == Darwin && -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]]; then
    TAILSCALE=/Applications/Tailscale.app/Contents/MacOS/Tailscale
    TAILSCALE_ENV=(env TAILSCALE_BE_CLI=1)
    return 0
  fi
  return 1
}

if ! find_tailscale; then
  case "$OS" in
    Linux)
      command -v curl >/dev/null 2>&1 || die "curl is required to download Tailscale's official installer"
      command -v sudo >/dev/null 2>&1 || die "sudo is required to install Tailscale; install it with your distribution's package manager first"
      INSTALL_TMP=$(mktemp "${TMPDIR:-/tmp}/tailscale-install.XXXXXX")
      chmod 600 "$INSTALL_TMP"
      log "downloading the official Tailscale installer over verified HTTPS"
      curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
        https://tailscale.com/install.sh -o "$INSTALL_TMP" ||
        die "could not download Tailscale's official installer"
      log "installing Tailscale's signed distribution package (sudo may ask for your password)"
      sudo sh "$INSTALL_TMP" || die "Tailscale installation failed"
      ;;
    Darwin)
      command -v brew >/dev/null 2>&1 ||
        die "Tailscale is missing. Install the official macOS app from https://tailscale.com/download/mac or install Homebrew, then rerun."
      log "installing Tailscale's open-source CLI service with Homebrew"
      brew install tailscale || die "Homebrew could not install Tailscale"
      brew services start tailscale || die "could not start the Homebrew Tailscale service"
      ;;
    *)
      die "unsupported operating system: $OS (supported: mainstream Linux and macOS)"
      ;;
  esac
  find_tailscale || die "installation completed, but the Tailscale CLI was not found; restart your terminal and rerun"
fi

if [[ "$OS" == Linux && $EUID -ne 0 ]]; then SUDO=(sudo); fi
ts() {
  if ((${#TAILSCALE_ENV[@]})); then
    "${TAILSCALE_ENV[@]}" "${SUDO[@]}" "$TAILSCALE" "$@"
  else
    "${SUDO[@]}" "$TAILSCALE" "$@"
  fi
}

log "Tailscale version: $(ts version | head -n 1)"
if ! ts status >/dev/null 2>&1; then
  if [[ "$OS" == Darwin ]] && [[ "$TAILSCALE" == /Applications/* ]]; then
    open -a Tailscale >/dev/null 2>&1 ||
      die "could not start the Tailscale macOS app"
  elif [[ "$OS" == Darwin ]] && command -v brew >/dev/null 2>&1 &&
    brew list --formula tailscale >/dev/null 2>&1; then
    brew services start tailscale ||
      die "could not start the Homebrew Tailscale service"
  fi
  if [[ "$OS" == Linux ]] && command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start tailscaled ||
      die "Tailscale service is not running; check systemctl status tailscaled"
  fi
  for _ in {1..15}; do
    STATUS_JSON=$(ts status --json 2>/dev/null || true)
    if grep -Eq '"BackendState"[[:space:]]*:' <<<"$STATUS_JSON"; then break; fi
    sleep 1
  done
  if ! grep -Eq '"BackendState"[[:space:]]*:' <<<"$STATUS_JSON"; then
    die "Tailscale daemon did not become ready; check its service and retry"
  fi
fi

STATUS_JSON=$(ts status --json 2>/dev/null || true)
if ! grep -Eq '"BackendState"[[:space:]]*:[[:space:]]*"Running"' <<<"$STATUS_JSON"; then
  log "connecting to Tailscale; complete sign-in in the browser if prompted"
  UP_ARGS=()
  [[ -n "$AUTH_KEY_FILE" ]] && UP_ARGS+=("--auth-key=file:$AUTH_KEY_FILE")
  ts up "${UP_ARGS[@]}" || die "Tailscale could not connect; complete sign-in and rerun"
else
  ok "device is already connected"
fi

if [[ -n "$HOSTNAME" ]]; then
  ts set "--hostname=$HOSTNAME" || die "could not set the requested Tailscale hostname"
fi

SSH_VALUE=false
if ((ENABLE_SSH)); then SSH_VALUE=true; fi
ts set "--ssh=$SSH_VALUE" ||
  die "could not set Tailscale SSH; update the Tailscale client and retry"
if ((ENABLE_SSH)); then ok "Tailscale SSH enabled after confirmation"; else ok "Tailscale SSH disabled"; fi

STATUS_JSON=$(ts status --json 2>/dev/null || true)
if ! grep -Eq '"BackendState"[[:space:]]*:[[:space:]]*"Running"' <<<"$STATUS_JSON"; then
  ts status || true
  die "Tailscale is not in the Running state after connection"
fi
ts status
ts netcheck || warn "network check failed; inspect Tailscale connectivity"
TS_IP=$(ts ip -4 2>/dev/null | head -n 1 || true)
[[ -n "$TS_IP" ]] && ok "connected with Tailscale IPv4 $TS_IP"

if [[ -n "$PEER" ]]; then
  ts ping --c=4 --timeout=10s "$PEER" ||
    die "could not verify connectivity to requested peer $PEER" 3
fi

if ((ENABLE_FUNNEL)); then
  command -v curl >/dev/null 2>&1 || die "curl is required to check the local HTTP service"
  HTTP_CODE=$(curl --silent --show-error --max-time 3 --output /dev/null \
    --write-out '%{http_code}' "http://127.0.0.1:$FUNNEL_PORT/" 2>/dev/null || true)
  [[ "$HTTP_CODE" =~ ^[234][0-9][0-9]$ ]] ||
    die "refusing to publish port $FUNNEL_PORT: no valid HTTP response from http://127.0.0.1:$FUNNEL_PORT/"
  log "publishing local HTTP port $FUNNEL_PORT to the public internet"
  FUNNEL_OUTPUT=$(ts funnel --bg "$FUNNEL_PORT" 2>&1) ||
    die "Tailscale Funnel failed: $FUNNEL_OUTPUT" 3
  printf '%s\n' "$FUNNEL_OUTPUT"
  ok "Funnel configuration accepted; verify the public URL above"
else
  log "no new Funnel requested; existing Funnel settings are unchanged"
  ts funnel status 2>&1 || warn "could not inspect existing Funnel configuration"
fi

printf '\n[OK] Tailscale setup finished\n'
printf '  connect: verified\n  SSH: %s\n  Funnel: %s\n' \
  "$([[ $ENABLE_SSH == 1 ]] && printf enabled || printf disabled)" \
  "$([[ $ENABLE_FUNNEL == 1 ]] && printf 'public port %s' "$FUNNEL_PORT" || printf 'not newly enabled')"
