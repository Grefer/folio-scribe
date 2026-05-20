#!/usr/bin/env bash
# install_schedule.sh — Install or uninstall folio-scribe launchd scheduled tasks
#
# Usage:
#   install_schedule.sh install   [--vault PATH] [--skill-dir PATH]
#   install_schedule.sh install-web-sync [--vault PATH] [--skill-dir PATH]
#   install_schedule.sh uninstall-web-sync
#   install_schedule.sh uninstall
#   install_schedule.sh status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHD_SRC="$SCRIPT_DIR/launchd"
LAUNCHD_DST="$HOME/Library/LaunchAgents"
SCHEDULE_LABELS=(
    com.folio-scribe.hk-plan
    com.folio-scribe.hk-review
    com.folio-scribe.us-plan-early
    com.folio-scribe.us-plan
    com.folio-scribe.us-review
    com.folio-scribe.weekly-summary
    com.folio-scribe.monthly-summary
)
WEB_SYNC_LABEL="com.folio-scribe.web-sync"
LABELS=("${SCHEDULE_LABELS[@]}" "$WEB_SYNC_LABEL")

# ── Defaults (override with flags) ──────────────────────────────────
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/Trading}"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # parent of scripts/
AI_CLI="${FOLIO_SCRIBE_AI_CLI:-codex}"
AI_CLI=$(printf '%s' "$AI_CLI" | tr '[:upper:]' '[:lower:]')
AI_FALLBACK_CLI="${FOLIO_SCRIBE_AI_FALLBACK_CLI:-codex}"
AI_MODEL="${FOLIO_SCRIBE_AI_MODEL:-}"
WEB_EXPORT_DIR="${FOLIO_SCRIBE_WEB_EXPORT_DIR:-}"
WEB_TITLE="${FOLIO_SCRIBE_WEB_TITLE:-Folio Scribe Journal}"
WEB_DEPLOY="${FOLIO_SCRIBE_WEB_DEPLOY:-}"
WEB_WATCH="${FOLIO_SCRIBE_WEB_WATCH:-}"
WEB_SYNC_DEBOUNCE="${FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE:-8}"
VERCEL_PROJECT="${FOLIO_SCRIBE_VERCEL_PROJECT:-}"
VERCEL_SCOPE="${FOLIO_SCRIBE_VERCEL_SCOPE:-}"
VERCEL_TARGET="${FOLIO_SCRIBE_VERCEL_TARGET:-}"
VERCEL_DOMAIN="${FOLIO_SCRIBE_VERCEL_DOMAIN:-}"
HK_PLAN_TIME="${FOLIO_SCRIBE_HK_PLAN_TIME:-08:15}"
HK_REVIEW_TIME="${FOLIO_SCRIBE_HK_REVIEW_TIME:-16:15}"
US_PLAN_EARLY_TIME="${FOLIO_SCRIBE_US_PLAN_EARLY_TIME:-16:30}"
US_PLAN_TIME="${FOLIO_SCRIBE_US_PLAN_TIME:-20:45}"
US_REVIEW_TIME="${FOLIO_SCRIBE_US_REVIEW_TIME:-06:45}"
WEEKLY_SUMMARY_TIME="${FOLIO_SCRIBE_WEEKLY_SUMMARY_TIME:-08:30}"
MONTHLY_SUMMARY_TIME="${FOLIO_SCRIBE_MONTHLY_SUMMARY_TIME:-08:45}"

usage() {
    cat <<'EOF'
Usage:
  install_schedule.sh install   [--vault PATH] [--skill-dir PATH]
  install_schedule.sh uninstall
  install_schedule.sh status

Commands:
  install     Install launchd plists (unloads existing ones first)
  install-web-sync
              Install only the TradingWeb WatchPaths sync agent
  uninstall-web-sync
              Unload and remove only the TradingWeb WatchPaths sync agent
  uninstall   Unload and remove launchd plists
  status      Show current launchd status

Options (install only):
  --vault PATH       Obsidian vault path  (default: ~/Documents/Trading)
  --skill-dir PATH   Skill directory path (default: auto-detected from script location)

Environment:
  FOLIO_SCRIBE_VAULT      Alternative to --vault flag
  FOLIO_SCRIBE_AI_CLI     AI CLI for scheduled generation (codex or claude; default: codex)
  FOLIO_SCRIBE_AI_FALLBACK_CLI
                          Fallback CLI when Claude fails (codex or none; default: codex)
  FOLIO_SCRIBE_AI_MODEL   Optional model override for the selected AI CLI
  FOLIO_SCRIBE_WEB_EXPORT_DIR
                          Optional static web dashboard output directory
  FOLIO_SCRIBE_WEB_TITLE  Static web dashboard title
  FOLIO_SCRIBE_WEB_DEPLOY Optional web deploy target after export (vercel)
  FOLIO_SCRIBE_WEB_WATCH  Set to 1 to install a WatchPaths web sync agent
  FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE
                          Seconds to wait before WatchPaths sync (default: 8)
  FOLIO_SCRIBE_VERCEL_PROJECT
                          Vercel project name for web deploy
  FOLIO_SCRIBE_VERCEL_SCOPE
                          Vercel team slug for web deploy
  FOLIO_SCRIBE_VERCEL_TARGET
                          Vercel deploy target: production or preview
  FOLIO_SCRIBE_VERCEL_DOMAIN
                          Optional custom domain to keep on production deploys
  FOLIO_SCRIBE_HK_PLAN_TIME
                          HK plan schedule time, HH:MM local (default: 08:15)
  FOLIO_SCRIBE_HK_REVIEW_TIME
                          HK review schedule time, HH:MM local (default: 16:15)
  FOLIO_SCRIBE_US_PLAN_EARLY_TIME
                          US early draft plan time, HH:MM local (default: 16:30)
  FOLIO_SCRIBE_US_PLAN_TIME
                          US refreshed plan time, HH:MM local (default: 20:45)
  FOLIO_SCRIBE_US_REVIEW_TIME
                          US review schedule time, HH:MM local (default: 06:45)
  FOLIO_SCRIBE_WEEKLY_SUMMARY_TIME
                          Weekly review time on Saturday, HH:MM local (default: 08:30)
  FOLIO_SCRIBE_MONTHLY_SUMMARY_TIME
                          Monthly review time on day 1, HH:MM local (default: 08:45)
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

launchd_service_loaded() {
    local label="$1"
    launchctl print "gui/$(id -u)/${label}" &>/dev/null || launchctl list "$label" &>/dev/null
}

# ── Unload existing agents ───────────────────────────────────────────
unload_agents() {
    for label in "${LABELS[@]}"; do
        local plist="$LAUNCHD_DST/${label}.plist"
        if [ -f "$plist" ]; then
            echo "  Unloading $label ..."
            launchctl unload "$plist" 2>/dev/null || true
        fi
    done
}

web_watch_enabled() {
    case "$(printf '%s' "$WEB_WATCH" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

assign_schedule_time() {
    local name="$1"
    local value="$2"
    local hour_var="$3"
    local minute_var="$4"
    local hour minute

    case "$value" in
        [0-9]:[0-5][0-9]|[0-1][0-9]:[0-5][0-9]|2[0-3]:[0-5][0-9]) ;;
        *)
            echo "ERROR: $name must be HH:MM local time, got '$value'"
            exit 1
            ;;
    esac

    hour="${value%:*}"
    minute="${value#*:}"
    hour=$((10#$hour))
    minute=$((10#$minute))
    eval "$hour_var=\$hour"
    eval "$minute_var=\$minute"
}

prepare_schedule_times() {
    assign_schedule_time FOLIO_SCRIBE_HK_PLAN_TIME "$HK_PLAN_TIME" HK_PLAN_HOUR HK_PLAN_MINUTE
    assign_schedule_time FOLIO_SCRIBE_HK_REVIEW_TIME "$HK_REVIEW_TIME" HK_REVIEW_HOUR HK_REVIEW_MINUTE
    assign_schedule_time FOLIO_SCRIBE_US_PLAN_EARLY_TIME "$US_PLAN_EARLY_TIME" US_PLAN_EARLY_HOUR US_PLAN_EARLY_MINUTE
    assign_schedule_time FOLIO_SCRIBE_US_PLAN_TIME "$US_PLAN_TIME" US_PLAN_HOUR US_PLAN_MINUTE
    assign_schedule_time FOLIO_SCRIBE_US_REVIEW_TIME "$US_REVIEW_TIME" US_REVIEW_HOUR US_REVIEW_MINUTE
    assign_schedule_time FOLIO_SCRIBE_WEEKLY_SUMMARY_TIME "$WEEKLY_SUMMARY_TIME" WEEKLY_SUMMARY_HOUR WEEKLY_SUMMARY_MINUTE
    assign_schedule_time FOLIO_SCRIBE_MONTHLY_SUMMARY_TIME "$MONTHLY_SUMMARY_TIME" MONTHLY_SUMMARY_HOUR MONTHLY_SUMMARY_MINUTE
}

plist_schedule_time() {
    local plist="$1"
    if [ ! -f "$plist" ]; then
        printf '--:--'
        return
    fi

    local hour minute
    hour=$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Hour' "$plist" 2>/dev/null || true)
    minute=$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Minute' "$plist" 2>/dev/null || true)
    if [ -z "$hour" ] || [ -z "$minute" ]; then
        printf '--:--'
    else
        printf '%02d:%02d' "$hour" "$minute"
    fi
}

install_plist() {
    local label="$1"
    local src="$LAUNCHD_SRC/${label}.plist"
    local dst="$LAUNCHD_DST/${label}.plist"

    if [ ! -f "$src" ]; then
        echo "  WARNING: Template not found: $src, skipping"
        return
    fi

    sed \
        -e "s|__SKILL_DIR__|${SKILL_DIR}|g" \
        -e "s|__VAULT__|${VAULT}|g" \
        -e "s|__HOME__|${HOME}|g" \
        -e "s|__AI_CLI__|${AI_CLI}|g" \
        -e "s|__AI_FALLBACK_CLI__|${AI_FALLBACK_CLI}|g" \
        -e "s|__AI_MODEL__|${AI_MODEL}|g" \
        -e "s|__WEB_EXPORT_DIR__|${WEB_EXPORT_DIR}|g" \
        -e "s|__WEB_TITLE__|${WEB_TITLE}|g" \
        -e "s|__WEB_DEPLOY__|${WEB_DEPLOY}|g" \
        -e "s|__WEB_SYNC_DEBOUNCE__|${WEB_SYNC_DEBOUNCE}|g" \
        -e "s|__VERCEL_PROJECT__|${VERCEL_PROJECT}|g" \
        -e "s|__VERCEL_SCOPE__|${VERCEL_SCOPE}|g" \
        -e "s|__VERCEL_TARGET__|${VERCEL_TARGET}|g" \
        -e "s|__VERCEL_DOMAIN__|${VERCEL_DOMAIN}|g" \
        -e "s|__HK_PLAN_HOUR__|${HK_PLAN_HOUR:-8}|g" \
        -e "s|__HK_PLAN_MINUTE__|${HK_PLAN_MINUTE:-45}|g" \
        -e "s|__HK_REVIEW_HOUR__|${HK_REVIEW_HOUR:-16}|g" \
        -e "s|__HK_REVIEW_MINUTE__|${HK_REVIEW_MINUTE:-15}|g" \
        -e "s|__US_PLAN_EARLY_HOUR__|${US_PLAN_EARLY_HOUR:-16}|g" \
        -e "s|__US_PLAN_EARLY_MINUTE__|${US_PLAN_EARLY_MINUTE:-30}|g" \
        -e "s|__US_PLAN_HOUR__|${US_PLAN_HOUR:-20}|g" \
        -e "s|__US_PLAN_MINUTE__|${US_PLAN_MINUTE:-45}|g" \
        -e "s|__US_REVIEW_HOUR__|${US_REVIEW_HOUR:-6}|g" \
        -e "s|__US_REVIEW_MINUTE__|${US_REVIEW_MINUTE:-45}|g" \
        -e "s|__WEEKLY_SUMMARY_HOUR__|${WEEKLY_SUMMARY_HOUR:-8}|g" \
        -e "s|__WEEKLY_SUMMARY_MINUTE__|${WEEKLY_SUMMARY_MINUTE:-30}|g" \
        -e "s|__MONTHLY_SUMMARY_HOUR__|${MONTHLY_SUMMARY_HOUR:-8}|g" \
        -e "s|__MONTHLY_SUMMARY_MINUTE__|${MONTHLY_SUMMARY_MINUTE:-45}|g" \
        -e "s|__LOG_DIR__|${LOG_DIR}|g" \
        "$src" > "$dst"

    launchctl load "$dst"
    echo "  ✓ $label"
}

validate_web_sync_config() {
    [ -d "$VAULT" ]     || { echo "ERROR: Vault not found: $VAULT"; exit 1; }
    [ -d "$SKILL_DIR" ] || { echo "ERROR: Skill dir not found: $SKILL_DIR"; exit 1; }
    [ -n "$WEB_EXPORT_DIR" ] || {
        echo "ERROR: Web sync requires FOLIO_SCRIBE_WEB_EXPORT_DIR"
        exit 1
    }
    case "$WEB_DEPLOY" in
        ""|vercel) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_WEB_DEPLOY '$WEB_DEPLOY'. Use: vercel"; exit 1 ;;
    esac
    case "$WEB_SYNC_DEBOUNCE" in
        ""|*[!0-9]*) echo "ERROR: FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE must be a non-negative integer"; exit 1 ;;
    esac
    [ -x "$SKILL_DIR/scripts/sync_tradingweb.sh" ] || {
        echo "ERROR: sync_tradingweb.sh not found or not executable in $SKILL_DIR/scripts/"
        exit 1
    }
    if [ "$WEB_DEPLOY" = "vercel" ]; then
        [ -x "$SKILL_DIR/scripts/deploy_web_journal_vercel.sh" ] || {
            echo "ERROR: deploy_web_journal_vercel.sh not found or not executable in $SKILL_DIR/scripts/"
            exit 1
        }
    fi
}

# ── install ──────────────────────────────────────────────────────────
do_install() {
    echo "Installing folio-scribe scheduled tasks"
    echo "  Vault:     $VAULT"
    echo "  Skill dir: $SKILL_DIR"
    echo "  AI CLI:    $AI_CLI"
    if [ "$AI_CLI" = "claude" ]; then
        echo "  Fallback:  $AI_FALLBACK_CLI"
    fi
    if [ -n "$AI_MODEL" ]; then
        echo "  AI model:  $AI_MODEL"
    fi
    if [ -n "$WEB_EXPORT_DIR" ]; then
        echo "  Web out:   $WEB_EXPORT_DIR"
    fi
    if [ -n "$WEB_DEPLOY" ]; then
        echo "  Web deploy:$WEB_DEPLOY"
    fi
    if web_watch_enabled; then
        echo "  Web watch: yes"
    fi
    prepare_schedule_times
    echo "  Schedule:"
    printf '    %02d:%02d  hk_plan\n' "$HK_PLAN_HOUR" "$HK_PLAN_MINUTE"
    printf '    %02d:%02d  hk_review\n' "$HK_REVIEW_HOUR" "$HK_REVIEW_MINUTE"
    printf '    %02d:%02d  us_plan_early\n' "$US_PLAN_EARLY_HOUR" "$US_PLAN_EARLY_MINUTE"
    printf '    %02d:%02d  us_plan_refresh\n' "$US_PLAN_HOUR" "$US_PLAN_MINUTE"
    printf '    %02d:%02d  us_review\n' "$US_REVIEW_HOUR" "$US_REVIEW_MINUTE"
    printf '    %02d:%02d  weekly_summary (Saturday)\n' "$WEEKLY_SUMMARY_HOUR" "$WEEKLY_SUMMARY_MINUTE"
    printf '    %02d:%02d  monthly_summary (day 1)\n' "$MONTHLY_SUMMARY_HOUR" "$MONTHLY_SUMMARY_MINUTE"
    echo "  Log dir:   $VAULT/.logs"
    echo ""

    # Validate
    [ -d "$VAULT" ]     || { echo "ERROR: Vault not found: $VAULT"; exit 1; }
    [ -d "$SKILL_DIR" ] || { echo "ERROR: Skill dir not found: $SKILL_DIR"; exit 1; }
    case "$AI_CLI" in
        claude|codex) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_AI_CLI '$AI_CLI'. Use: claude|codex"; exit 1 ;;
    esac
    case "$(printf '%s' "$AI_FALLBACK_CLI" | tr '[:upper:]' '[:lower:]')" in
        ""|none|codex) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_AI_FALLBACK_CLI '$AI_FALLBACK_CLI'. Use: codex|none"; exit 1 ;;
    esac
    case "$WEB_DEPLOY" in
        ""|vercel) ;;
        *) echo "ERROR: Unsupported FOLIO_SCRIBE_WEB_DEPLOY '$WEB_DEPLOY'. Use: vercel"; exit 1 ;;
    esac
    case "$WEB_SYNC_DEBOUNCE" in
        ""|*[!0-9]*) echo "ERROR: FOLIO_SCRIBE_WEB_SYNC_DEBOUNCE must be a non-negative integer"; exit 1 ;;
    esac
    if web_watch_enabled && [ -z "$WEB_EXPORT_DIR" ]; then
        echo "ERROR: FOLIO_SCRIBE_WEB_WATCH=1 requires FOLIO_SCRIBE_WEB_EXPORT_DIR"
        exit 1
    fi
    [ -x "$SKILL_DIR/scripts/run_folio_task.sh" ] || {
        echo "ERROR: run_folio_task.sh not found or not executable in $SKILL_DIR/scripts/"
        exit 1
    }
    [ -x "$SKILL_DIR/scripts/write_periodic_summary.py" ] || {
        echo "ERROR: write_periodic_summary.py not found or not executable in $SKILL_DIR/scripts/"
        exit 1
    }
    if [ -n "$WEB_EXPORT_DIR" ] || web_watch_enabled; then
        [ -x "$SKILL_DIR/scripts/sync_tradingweb.sh" ] || {
            echo "ERROR: sync_tradingweb.sh not found or not executable in $SKILL_DIR/scripts/"
            exit 1
        }
    fi
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
    for label in "${SCHEDULE_LABELS[@]}"; do
        install_plist "$label"
    done
    if web_watch_enabled; then
        install_plist "$WEB_SYNC_LABEL"
    else
        local stale_web_plist="$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist"
        [ ! -f "$stale_web_plist" ] || rm "$stale_web_plist"
    fi

    echo ""
    echo "Done. Verify with:"
    echo "  launchctl list | grep folio-scribe"
    echo ""
    echo "Manual run:"
    echo "  $SKILL_DIR/scripts/run_folio_task.sh"
}

# ── install web sync only ────────────────────────────────────────────
do_install_web_sync() {
    echo "Installing folio-scribe TradingWeb sync agent"
    echo "  Vault:     $VAULT"
    echo "  Skill dir: $SKILL_DIR"
    echo "  Web out:   $WEB_EXPORT_DIR"
    if [ -n "$WEB_DEPLOY" ]; then
        echo "  Web deploy:$WEB_DEPLOY"
    fi
    echo "  Debounce:  ${WEB_SYNC_DEBOUNCE}s"
    echo "  Log dir:   $VAULT/.logs"
    echo ""

    validate_web_sync_config

    LOG_DIR="$VAULT/.logs"
    mkdir -p "$LOG_DIR" "$LAUNCHD_DST"

    if [ -f "$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist" ]; then
        echo "  Unloading $WEB_SYNC_LABEL ..."
        launchctl unload "$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist" 2>/dev/null || true
    fi

    install_plist "$WEB_SYNC_LABEL"

    echo ""
    echo "Done. Verify with:"
    echo "  launchctl list $WEB_SYNC_LABEL"
}

# ── uninstall web sync only ──────────────────────────────────────────
do_uninstall_web_sync() {
    echo "Uninstalling folio-scribe TradingWeb sync agent"
    if [ -f "$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist" ]; then
        echo "  Unloading $WEB_SYNC_LABEL ..."
        launchctl unload "$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist" 2>/dev/null || true
    fi
    local plist="$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist"
    if [ -f "$plist" ]; then
        rm "$plist"
        echo "  ✓ Removed $plist"
    fi
    echo "Done."
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
    for label in "${SCHEDULE_LABELS[@]}"; do
        local plist="$LAUNCHD_DST/${label}.plist"
        if launchd_service_loaded "$label"; then
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
    printf '  %s  us_review   美股交易总结\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.us-review.plist")"
    printf '  %s  hk_plan     港股交易计划\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.hk-plan.plist")"
    printf '  %s  hk_review   港股交易总结\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.hk-review.plist")"
    printf '  %s  us_plan     美股初版计划\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.us-plan-early.plist")"
    printf '  %s  us_plan     美股刷新计划\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.us-plan.plist")"
    printf '  %s  weekly      交易周总结（周六）\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.weekly-summary.plist")"
    printf '  %s  monthly     月度交易总结（每月 1 日）\n' "$(plist_schedule_time "$LAUNCHD_DST/com.folio-scribe.monthly-summary.plist")"
    echo ""
    echo "Web sync:"
    if launchd_service_loaded "$WEB_SYNC_LABEL"; then
        echo "  ✓ WatchPaths enabled for Daily, Weekly, Monthly, and Rules"
    elif [ -f "$LAUNCHD_DST/${WEB_SYNC_LABEL}.plist" ]; then
        echo "  ○ WatchPaths plist exists but is not loaded"
    else
        echo "  (not installed; set FOLIO_SCRIBE_WEB_WATCH=1 during install)"
    fi
}

# ── Dispatch ─────────────────────────────────────────────────────────
case "$ACTION" in
    install)            do_install ;;
    install-web-sync)   do_install_web_sync ;;
    uninstall-web-sync) do_uninstall_web_sync ;;
    uninstall)          do_uninstall ;;
    status)             do_status ;;
    *)                  echo "Unknown action: $ACTION"; usage ;;
esac
