#!/usr/bin/env bash
# install_schedule.sh — Install or uninstall folio-scribe launchd scheduled tasks
#
# Usage:
#   install_schedule.sh install   [--vault PATH] [--skill-dir PATH]
#   install_schedule.sh uninstall
#   install_schedule.sh status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHD_SRC="$SCRIPT_DIR/launchd"
LAUNCHD_DST="$HOME/Library/LaunchAgents"
LABELS=(
    com.folio-scribe.hk-plan
    com.folio-scribe.hk-review
    com.folio-scribe.us-plan
    com.folio-scribe.us-review
)

# ── Defaults (override with flags) ──────────────────────────────────
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/Trading}"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # parent of scripts/
AI_CLI="${FOLIO_SCRIBE_AI_CLI:-claude}"
AI_CLI=$(printf '%s' "$AI_CLI" | tr '[:upper:]' '[:lower:]')
AI_MODEL="${FOLIO_SCRIBE_AI_MODEL:-}"
WEB_EXPORT_DIR="${FOLIO_SCRIBE_WEB_EXPORT_DIR:-}"
WEB_DEPLOY="${FOLIO_SCRIBE_WEB_DEPLOY:-}"
VERCEL_PROJECT="${FOLIO_SCRIBE_VERCEL_PROJECT:-}"
VERCEL_SCOPE="${FOLIO_SCRIBE_VERCEL_SCOPE:-}"
VERCEL_TARGET="${FOLIO_SCRIBE_VERCEL_TARGET:-}"
VERCEL_DOMAIN="${FOLIO_SCRIBE_VERCEL_DOMAIN:-}"

usage() {
    cat <<'EOF'
Usage:
  install_schedule.sh install   [--vault PATH] [--skill-dir PATH]
  install_schedule.sh uninstall
  install_schedule.sh status

Commands:
  install     Install launchd plists (unloads existing ones first)
  uninstall   Unload and remove launchd plists
  status      Show current launchd status

Options (install only):
  --vault PATH       Obsidian vault path  (default: ~/Documents/Trading)
  --skill-dir PATH   Skill directory path (default: auto-detected from script location)

Environment:
  FOLIO_SCRIBE_VAULT      Alternative to --vault flag
  FOLIO_SCRIBE_AI_CLI     AI CLI for scheduled generation (claude or codex)
  FOLIO_SCRIBE_AI_MODEL   Optional model override for the selected AI CLI
  FOLIO_SCRIBE_WEB_EXPORT_DIR
                          Optional static web dashboard output directory
  FOLIO_SCRIBE_WEB_DEPLOY Optional web deploy target after export (vercel)
  FOLIO_SCRIBE_VERCEL_PROJECT
                          Vercel project name for web deploy
  FOLIO_SCRIBE_VERCEL_SCOPE
                          Vercel team slug for web deploy
  FOLIO_SCRIBE_VERCEL_TARGET
                          Vercel deploy target: production or preview
  FOLIO_SCRIBE_VERCEL_DOMAIN
                          Optional custom domain to keep on production deploys
EOF
    exit 1
}

# ── Parse args ───────────────────────────────────────────────────────
ACTION="${1:-}"
shift || true

while [ $# -gt 0 ]; do
    case "$1" in
        --vault)     VAULT="$2"; shift 2 ;;
        --skill-dir) SKILL_DIR="$2"; shift 2 ;;
        *)           echo "Unknown option: $1"; usage ;;
    esac
done

[ -z "$ACTION" ] && usage

# ── Unload existing agents ───────────────────────────────────────────
unload_agents() {
    for label in "${LABELS[@]}"; do
        local plist="$LAUNCHD_DST/${label}.plist"
        if launchctl list "$label" &>/dev/null; then
            echo "  Unloading $label ..."
            launchctl unload "$plist" 2>/dev/null || true
        fi
    done
}

# ── install ──────────────────────────────────────────────────────────
do_install() {
    echo "Installing folio-scribe scheduled tasks"
    echo "  Vault:     $VAULT"
    echo "  Skill dir: $SKILL_DIR"
    echo "  AI CLI:    $AI_CLI"
    if [ -n "$AI_MODEL" ]; then
        echo "  AI model:  $AI_MODEL"
    fi
    if [ -n "$WEB_EXPORT_DIR" ]; then
        echo "  Web out:   $WEB_EXPORT_DIR"
    fi
    if [ -n "$WEB_DEPLOY" ]; then
        echo "  Web deploy:$WEB_DEPLOY"
    fi
    echo "  Log dir:   $VAULT/.logs"
    echo ""

    # Validate
    [ -d "$VAULT" ]     || { echo "ERROR: Vault not found: $VAULT"; exit 1; }
    [ -d "$SKILL_DIR" ] || { echo "ERROR: Skill dir not found: $SKILL_DIR"; exit 1; }
    case "$AI_CLI" in
        claude|codex) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_AI_CLI '$AI_CLI'. Use: claude|codex"; exit 1 ;;
    esac
    case "$WEB_DEPLOY" in
        ""|vercel) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_WEB_DEPLOY '$WEB_DEPLOY'. Use: vercel"; exit 1 ;;
    esac
    [ -x "$SKILL_DIR/scripts/run_folio_task.sh" ] || {
        echo "ERROR: run_folio_task.sh not found or not executable in $SKILL_DIR/scripts/"
        exit 1
    }
    if [ "$WEB_DEPLOY" = "vercel" ]; then
        [ -x "$SKILL_DIR/scripts/deploy_web_journal_vercel.sh" ] || {
            echo "ERROR: deploy_web_journal_vercel.sh not found or not executable in $SKILL_DIR/scripts/"
            exit 1
        }
    fi

    LOG_DIR="$VAULT/.logs"
    mkdir -p "$LOG_DIR" "$LAUNCHD_DST"

    # Unload any existing agents first
    unload_agents

    # Generate and install plists from templates
    for label in "${LABELS[@]}"; do
        local src="$LAUNCHD_SRC/${label}.plist"
        local dst="$LAUNCHD_DST/${label}.plist"

        if [ ! -f "$src" ]; then
            echo "  WARNING: Template not found: $src, skipping"
            continue
        fi

        sed \
            -e "s|__SKILL_DIR__|${SKILL_DIR}|g" \
            -e "s|__VAULT__|${VAULT}|g" \
            -e "s|__HOME__|${HOME}|g" \
            -e "s|__AI_CLI__|${AI_CLI}|g" \
            -e "s|__AI_MODEL__|${AI_MODEL}|g" \
            -e "s|__WEB_EXPORT_DIR__|${WEB_EXPORT_DIR}|g" \
            -e "s|__WEB_DEPLOY__|${WEB_DEPLOY}|g" \
            -e "s|__VERCEL_PROJECT__|${VERCEL_PROJECT}|g" \
            -e "s|__VERCEL_SCOPE__|${VERCEL_SCOPE}|g" \
            -e "s|__VERCEL_TARGET__|${VERCEL_TARGET}|g" \
            -e "s|__VERCEL_DOMAIN__|${VERCEL_DOMAIN}|g" \
            -e "s|__LOG_DIR__|${LOG_DIR}|g" \
            "$src" > "$dst"

        launchctl load "$dst"
        echo "  ✓ $label"
    done

    echo ""
    echo "Done. Verify with:"
    echo "  launchctl list | grep folio-scribe"
    echo ""
    echo "Manual run:"
    echo "  $SKILL_DIR/scripts/run_folio_task.sh"
}

# ── uninstall ────────────────────────────────────────────────────────
do_uninstall() {
    echo "Uninstalling folio-scribe scheduled tasks"
    unload_agents

    for label in "${LABELS[@]}"; do
        local plist="$LAUNCHD_DST/${label}.plist"
        if [ -f "$plist" ]; then
            rm "$plist"
            echo "  ✓ Removed $plist"
        fi
    done
    echo "Done."
}

# ── status ───────────────────────────────────────────────────────────
do_status() {
    echo "folio-scribe scheduled tasks:"
    echo ""
    local found=0
    for label in "${LABELS[@]}"; do
        local plist="$LAUNCHD_DST/${label}.plist"
        if launchctl list "$label" &>/dev/null; then
            local info
            info=$(launchctl list "$label" 2>/dev/null | grep -E "PID|Status" || true)
            echo "  ✓ $label  (loaded)"
            found=1
        elif [ -f "$plist" ]; then
            echo "  ○ $label  (plist exists but not loaded)"
            found=1
        fi
    done

    if [ "$found" -eq 0 ]; then
        echo "  (none installed)"
    fi

    echo ""
    echo "Schedule:"
    echo "  06:45  us_review   美股交易总结"
    echo "  08:45  hk_plan     港股交易计划"
    echo "  16:15  hk_review   港股交易总结"
    echo "  20:45  us_plan     美股交易计划"
}

# ── Dispatch ─────────────────────────────────────────────────────────
case "$ACTION" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    *)         echo "Unknown action: $ACTION"; usage ;;
esac
