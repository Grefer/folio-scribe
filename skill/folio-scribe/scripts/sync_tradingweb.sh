#!/usr/bin/env bash
# sync_tradingweb.sh — Build the static TradingWeb journal and optionally deploy it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/TradingNote}"
OUT_DIR="${FOLIO_SCRIBE_WEB_EXPORT_DIR:-$HOME/Documents/TradingWeb}"
TITLE="${FOLIO_SCRIBE_WEB_TITLE:-Folio Scribe Journal}"
DEPLOY="${FOLIO_SCRIBE_WEB_DEPLOY:-}"
DEBOUNCE_SECONDS="${FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE:-0}"
QUIET=0

usage() {
    cat <<'EOF'
Usage:
  sync_tradingweb.sh [--vault PATH] [--out PATH] [--title TITLE]
                     [--deploy none|vercel] [--debounce SECONDS] [--quiet]
  sync_tradingweb.sh --help

Builds the static TradingWeb dashboard from an Obsidian trading vault.
If --deploy vercel, deploy_web_journal_vercel.sh is called after the build.

Fails closed: the secrets guard must pass before the build, and again on the
built output before a deploy, or nothing is built/deployed and the exit is 1.

Environment:
  FOLIO_SCRIBE_VAULT
  FOLIO_SCRIBE_WEB_EXPORT_DIR
  FOLIO_SCRIBE_WEB_TITLE
  FOLIO_SCRIBE_WEB_DEPLOY          Optional deploy target: vercel
  FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE   Optional delay before syncing, useful for launchd WatchPaths
  FOLIO_SCRIBE_SECRETS_GUARD       Python scanner run as GUARD and GUARD --path OUT; exit 0 = clean
                                   (default: <vault>/_tools/check_secrets.py; "none" disables it)
  FOLIO_SCRIBE_LOG_DIR             Log and lock directory (default: ~/Library/Logs/folio-scribe)
  FOLIO_SCRIBE_VERCEL_PROJECT
  FOLIO_SCRIBE_VERCEL_SCOPE
  FOLIO_SCRIBE_VERCEL_TARGET
  FOLIO_SCRIBE_VERCEL_DOMAIN
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --vault)    VAULT="$2"; shift 2 ;;
        --out)      OUT_DIR="$2"; shift 2 ;;
        --title)    TITLE="$2"; shift 2 ;;
        --deploy)   DEPLOY="$2"; shift 2 ;;
        --debounce) DEBOUNCE_SECONDS="$2"; shift 2 ;;
        --quiet)    QUIET=1; shift ;;
        --help|-h)  usage; exit 0 ;;
        *)          echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

case "$DEPLOY" in
    ""|none) DEPLOY="" ;;
    vercel) ;;
    *) echo "ERROR: Unsupported deploy target '$DEPLOY'. Use: none|vercel"; exit 1 ;;
esac

case "$DEBOUNCE_SECONDS" in
    ""|*[!0-9]*) echo "ERROR: --debounce must be a non-negative integer"; exit 1 ;;
esac

[ -d "$VAULT" ] || { echo "ERROR: Vault not found: $VAULT"; exit 1; }
SECRETS_GUARD="${FOLIO_SCRIBE_SECRETS_GUARD:-$VAULT/_tools/check_secrets.py}"
[ -f "$SCRIPT_DIR/build_web_journal.py" ] || {
    echo "ERROR: build_web_journal.py not found in $SCRIPT_DIR"
    exit 1
}
if [ "$DEPLOY" = "vercel" ] && [ ! -x "$SCRIPT_DIR/deploy_web_journal_vercel.sh" ]; then
    echo "ERROR: deploy_web_journal_vercel.sh not found or not executable in $SCRIPT_DIR"
    exit 1
fi

LOG_DIR="${FOLIO_SCRIBE_LOG_DIR:-$HOME/Library/Logs/folio-scribe}"
mkdir -p "$LOG_DIR"
LOCK_DIR="${FOLIO_SCRIBE_WEB_SYNC_LOCK:-$LOG_DIR/web-sync.lock}"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    [ "$QUIET" -eq 1 ] || echo "TradingWeb sync already running; skipping this trigger."
    exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if [ "$DEBOUNCE_SECONDS" -gt 0 ]; then
    [ "$QUIET" -eq 1 ] || echo "Waiting ${DEBOUNCE_SECONDS}s for file changes to settle ..."
    sleep "$DEBOUNCE_SECONDS"
fi

# Daily/ Weekly/ Monthly/ are published, so account numbers or keys there must
# stop the sync. The guard masks its own findings; they and the refusal go to
# stderr (the launchd .err log).
run_secrets_guard() {
    local output status=0
    [ "$SECRETS_GUARD" = "none" ] && return 0
    if [ ! -f "$SECRETS_GUARD" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: secrets guard not found: $SECRETS_GUARD" >&2
        echo "TradingWeb sync aborted; nothing was deployed. Set FOLIO_SCRIBE_SECRETS_GUARD to a scanner, or to \"none\" to opt out." >&2
        return 1
    fi
    output=$(python3 "$SECRETS_GUARD" "$@" 2>&1) || status=$?
    if [ "$status" -ne 0 ]; then
        printf '%s\n' "$output" >&2
        echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: secrets guard failed (exit $status): $SECRETS_GUARD${*:+ $*}" >&2
        echo "TradingWeb sync aborted; nothing was deployed. Clean the findings above, then re-run." >&2
        return 1
    fi
    [ "$QUIET" -eq 1 ] || printf '%s\n' "$output"
}

run_secrets_guard || exit 1

[ "$QUIET" -eq 1 ] || echo "Building TradingWeb from $VAULT ..."
python3 "$SCRIPT_DIR/build_web_journal.py" \
    --vault "$VAULT" \
    --out "$OUT_DIR" \
    --title "$TITLE" \
    --quiet

case "$DEPLOY" in
    "")
        [ "$QUIET" -eq 1 ] || echo "TradingWeb build complete: $OUT_DIR"
        ;;
    vercel)
        # Re-scan the built output: it is exactly what gets uploaded, and a note
        # edited between the first scan and the build would otherwise slip through.
        run_secrets_guard --path "$OUT_DIR" || exit 1
        [ "$QUIET" -eq 1 ] || echo "Deploying TradingWeb to Vercel ..."
        FOLIO_SCRIBE_WEB_EXPORT_DIR="$OUT_DIR" \
            "$SCRIPT_DIR/deploy_web_journal_vercel.sh"
        ;;
esac
