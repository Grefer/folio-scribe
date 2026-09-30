#!/usr/bin/env bash
# run_folio_task.sh — Scheduled folio-scribe task runner (Skill path)
#
# Usage:  run_folio_task.sh [hk_plan|hk_review|us_plan|us_review]
#
# Without arguments, auto-detects task type from current time:
#   05:00–08:14  →  us_review   (美股收盘后总结，写入昨日笔记)
#   08:15–12:59  →  hk_plan     (港股开盘前计划)
#   16:15–16:29  →  hk_review   (港股收盘后总结)
#   16:30–04:59  →  us_plan     (美股盘前计划；16:30 初版，20:45 后刷新版)
#   Other times   →  no-op
#
# With argument, uses that task type directly (override).
#
# Set FOLIO_SCRIBE_LANG=en for English prompts and note headings (default: zh).
# Set FOLIO_SCRIBE_NOTE_DATE=YYYY-MM-DD to backfill or regenerate a specific note date.
#
# Flow:
#   1. Skip sessions that do not map to an open market day
#   2. Ensure Futu OpenD is running (auto-launch if needed)
#   3. Read the Futu snapshot directly in this runner
#   4. For US tasks, read IBKR through the connected app when Codex is selected,
#      or through the local read-only Gateway/TWS helper when Claude is selected
#   5. Invoke the configured AI CLI in text-only mode with inline Folio Scribe instructions
#   6. Write the generated section into the daily note

set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
    echo "ERROR: run_folio_task.sh requires macOS (uses BSD date flags, open, and launchd scheduling assumptions)."
    exit 1
fi

# ── Configuration (override via environment variables) ───────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/TradingNote}"
NOTE_DATE_OVERRIDE="${FOLIO_SCRIBE_NOTE_DATE:-}"
OPEND_APP="${FOLIO_SCRIBE_OPEND_APP:-$HOME/Applications/Futu_OpenD/FutuOpenD.app}"
OPEND_PORT="${FOLIO_SCRIBE_OPEND_PORT:-11111}"
IBKR_SNAPSHOT_MODE="${FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE:-auto}"  # auto | plugin | gateway | off | required
IBKR_SNAPSHOT_MODE=$(printf '%s' "$IBKR_SNAPSHOT_MODE" | tr '[:upper:]' '[:lower:]')
IBKR_HOST="${FOLIO_SCRIBE_IBKR_HOST:-127.0.0.1}"
IBKR_PORT="${FOLIO_SCRIBE_IBKR_PORT:-4001}"
IBKR_CLIENT_ID="${FOLIO_SCRIBE_IBKR_CLIENT_ID:-91}"
IBKR_TIMEOUT="${FOLIO_SCRIBE_IBKR_TIMEOUT:-45}"
IBKR_ACCOUNT="${FOLIO_SCRIBE_IBKR_ACCOUNT:-}"
AI_CLI="${FOLIO_SCRIBE_AI_CLI:-claude}"
AI_CLI=$(printf '%s' "$AI_CLI" | tr '[:upper:]' '[:lower:]')
AI_FALLBACK_CLI="${FOLIO_SCRIBE_AI_FALLBACK_CLI:-auto}"
AI_FALLBACK_CLI=$(printf '%s' "$AI_FALLBACK_CLI" | tr '[:upper:]' '[:lower:]')
DETERMINISTIC_FALLBACK="${FOLIO_SCRIBE_DETERMINISTIC_FALLBACK:-1}"
NOTIFY="${FOLIO_SCRIBE_NOTIFY:-1}"                              # 1|0：AI 降级时发 macOS 通知
AI_LAST_FAILURE_REASON=""
DETERMINISTIC_FALLBACK=$(printf '%s' "$DETERMINISTIC_FALLBACK" | tr '[:upper:]' '[:lower:]')
CLAUDE="${FOLIO_SCRIBE_CLAUDE:-$(command -v claude 2>/dev/null || echo /opt/homebrew/bin/claude)}"
CLAUDE_SETTINGS="${FOLIO_SCRIBE_CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
CLAUDE_BARE="${FOLIO_SCRIBE_CLAUDE_BARE:-0}"
CLAUDE_BARE=$(printf '%s' "$CLAUDE_BARE" | tr '[:upper:]' '[:lower:]')
CLAUDE_EFFORT="${FOLIO_SCRIBE_CLAUDE_EFFORT:-xhigh}"   # 定时任务单独的思考强度，不跟随交互会话的默认值
CLAUDE_EFFORT=$(printf '%s' "$CLAUDE_EFFORT" | tr '[:upper:]' '[:lower:]')
CODEX="${FOLIO_SCRIBE_CODEX:-$(command -v codex 2>/dev/null || echo /opt/homebrew/bin/codex)}"
CODEX_CONFIG="${FOLIO_SCRIBE_CODEX_CONFIG:-$HOME/.codex/config.toml}"
CODEX_PROFILE="${FOLIO_SCRIBE_CODEX_PROFILE:-}"
CODEX_SANDBOX="${FOLIO_SCRIBE_CODEX_SANDBOX:-read-only}"
CODEX_DISABLE_FEATURES="${FOLIO_SCRIBE_CODEX_DISABLE_FEATURES:-plugins}"
CC_SWITCH_DB="${FOLIO_SCRIBE_CC_SWITCH_DB:-$HOME/.cc-switch/cc-switch.db}"
WEB_EXPORT_DIR="${FOLIO_SCRIBE_WEB_EXPORT_DIR:-}"
WEB_TITLE="${FOLIO_SCRIBE_WEB_TITLE:-Folio Scribe Journal}"
WEB_DEPLOY="${FOLIO_SCRIBE_WEB_DEPLOY:-}"
WATCHLIST_MODE="${FOLIO_SCRIBE_WATCHLIST_MODE:-dynamic}"  # dynamic | manual | off
WATCHLIST_LIMIT="${FOLIO_SCRIBE_WATCHLIST_LIMIT:-24}"
HK_WATCHLIST_SYMBOLS="${FOLIO_SCRIBE_HK_WATCHLIST:-}"
US_WATCHLIST_SYMBOLS="${FOLIO_SCRIBE_US_WATCHLIST:-}"
PLAN_PHASE="${FOLIO_SCRIBE_PLAN_PHASE:-}"
PLAN_PHASE=$(printf '%s' "$PLAN_PHASE" | tr '[:upper:]' '[:lower:]')
ALLOW_NON_TRADING_DAY="${FOLIO_SCRIBE_ALLOW_NON_TRADING_DAY:-0}"
ALLOW_NON_TRADING_DAY=$(printf '%s' "$ALLOW_NON_TRADING_DAY" | tr '[:upper:]' '[:lower:]')
LANG_PREF="${FOLIO_SCRIBE_LANG:-zh}"   # zh | en
LOG_DIR="${FOLIO_SCRIBE_LOG_DIR:-$VAULT/.logs}"
NOTIFY_FILE="${FOLIO_SCRIBE_NOTIFY_FILE:-$LOG_DIR/ai-degraded.log}"
MAX_OPEND_WAIT=90
MAX_SNAPSHOT_READY_WAIT="${FOLIO_SCRIBE_SNAPSHOT_READY_WAIT:-60}"
SNAPSHOT_READY_INTERVAL="${FOLIO_SCRIBE_SNAPSHOT_READY_INTERVAL:-5}"
AI_TIMEOUT_SECONDS="${FOLIO_SCRIBE_AI_TIMEOUT_SECONDS:-300}"
MAX_BUDGET="${FOLIO_SCRIBE_MAX_BUDGET_USD:-}"   # 留空 = 不设上限；单轮调用超限时 CLI 只会丢弃已生成的结果
MAX_TURNS=20
AI_MODEL="${FOLIO_SCRIBE_AI_MODEL:-}"
AI_MODEL_EXPLICIT=0
AI_MODEL_LABEL=""
CLAUDE_FALLBACK_MODEL="${FOLIO_SCRIBE_CLAUDE_FALLBACK_MODEL:-}"
LOCK_DIR=""
SENSITIVE_TMP_DIR=""

cleanup() {
    local status=$?
    if [ -n "$SENSITIVE_TMP_DIR" ]; then
        rm -rf "$SENSITIVE_TMP_DIR" 2>/dev/null || true
    fi
    if [ -n "$LOCK_DIR" ]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
    exit "$status"
}

if [ -n "${FOLIO_SCRIBE_AI_MODEL:-}" ]; then
    AI_MODEL_EXPLICIT=1
fi

case "$AI_CLI" in
    claude)
        if [ -z "$AI_MODEL" ] && [ -n "${FOLIO_SCRIBE_CLAUDE_MODEL:-}" ]; then
            AI_MODEL="$FOLIO_SCRIBE_CLAUDE_MODEL"
            AI_MODEL_EXPLICIT=1
        fi
        if [ -z "$AI_MODEL" ] && [ -r "$CLAUDE_SETTINGS" ]; then
            AI_MODEL=$(python3 -c 'import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle).get("model", ""))
' "$CLAUDE_SETTINGS" 2>/dev/null || true)
        fi
        ;;
    codex)
        if [ -z "$AI_MODEL" ] && [ -n "${FOLIO_SCRIBE_CODEX_MODEL:-}" ]; then
            AI_MODEL="$FOLIO_SCRIBE_CODEX_MODEL"
            AI_MODEL_EXPLICIT=1
        fi
        if [ -z "$AI_MODEL" ] && [ -r "$CODEX_CONFIG" ]; then
            AI_MODEL=$(python3 -c 'import re, sys
path = sys.argv[1]
try:
    import tomllib
    with open(path, "rb") as handle:
        print(tomllib.load(handle).get("model", ""))
except Exception:
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    match = re.search(r"(?m)^model\s*=\s*[\"\x27]?([^\"\x27#\n]+)", text)
    print(match.group(1).strip() if match else "")
' "$CODEX_CONFIG" 2>/dev/null || true)
        fi
        ;;
    *)
        echo "ERROR: Unsupported FOLIO_SCRIBE_AI_CLI '$AI_CLI'. Use: claude|codex"
        exit 1
        ;;
esac

case "$AI_FALLBACK_CLI" in
    ""|none|auto|claude|codex) ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_AI_FALLBACK_CLI '$AI_FALLBACK_CLI'. Use: auto|claude|codex|none"; exit 1 ;;
esac

case "$DETERMINISTIC_FALLBACK" in
    0|false|no|off|"") DETERMINISTIC_FALLBACK=0 ;;
    1|true|yes|on) DETERMINISTIC_FALLBACK=1 ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_DETERMINISTIC_FALLBACK '$DETERMINISTIC_FALLBACK'. Use: 0|1"; exit 1 ;;
esac

case "$CLAUDE_EFFORT" in
    low|medium|high|xhigh|max) ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_CLAUDE_EFFORT '$CLAUDE_EFFORT'. Use: low|medium|high|xhigh|max"; exit 1 ;;
esac

case "$NOTIFY" in
    0|false|no|off|"") NOTIFY=0 ;;
    1|true|yes|on) NOTIFY=1 ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_NOTIFY '$NOTIFY'. Use: 0|1"; exit 1 ;;
esac

case "$IBKR_SNAPSHOT_MODE" in
    plugin|auto|gateway|off|required) ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE '$IBKR_SNAPSHOT_MODE'. Use: plugin|gateway|off|required"; exit 1 ;;
esac

case "$CLAUDE_BARE" in
    0|false|no|off|"") ;;
    1|true|yes|on) ;;
    *) echo "ERROR: Unsupported FOLIO_SCRIBE_CLAUDE_BARE '$CLAUDE_BARE'. Use: 0|1"; exit 1 ;;
esac

uses_ibkr_plugin() {
    [ "$IBKR_SNAPSHOT_MODE" = "plugin" ] \
        || { [ "$IBKR_SNAPSHOT_MODE" = "auto" ] && [ "$AI_CLI" = "codex" ]; }
}

if [ -n "$AI_MODEL" ]; then
    AI_MODEL_LABEL="${AI_CLI}:${AI_MODEL}"
else
    AI_MODEL_LABEL="$AI_CLI"
fi

# ── Language-dependent section names and flags ──────────────────────
case "$LANG_PREF" in
    en)
        SEC_HK_PLAN="hk_plan";    SEC_HK_REVIEW="hk_review"
        SEC_US_PLAN="us_plan";    SEC_US_REVIEW="us_review"
        CHINESE_FLAG=""
        ;;
    *)  # zh (default)
        SEC_HK_PLAN="港股计划";   SEC_HK_REVIEW="港股总结"
        SEC_US_PLAN="美股计划";   SEC_US_REVIEW="美股总结"
        CHINESE_FLAG="--chinese"
        ;;
esac

# ── Auto-detect task type from current time ──────────────────────────
detect_task_type() {
    local hour minute total
    hour=$((10#$(date +%H)))
    minute=$((10#$(date +%M)))
    total=$((hour * 60 + minute))

    if   [ "$total" -ge 300  ] && [ "$total" -lt 495  ]; then echo "us_review" # 05:00-08:14
    elif [ "$total" -ge 495  ] && [ "$total" -lt 780  ]; then echo "hk_plan"   # 08:15-12:59
    elif [ "$total" -ge 975  ] && [ "$total" -lt 990  ]; then echo "hk_review" # 16:15-16:29
    elif [ "$total" -ge 990  ] || [ "$total" -lt 300  ]; then echo "us_plan"   # 16:30-04:59
    else                                                       echo "none"
    fi
}

if [ $# -ge 1 ]; then
    TASK_TYPE="$1"
else
    TASK_TYPE=$(detect_task_type)
fi

if [ "$TASK_TYPE" = "none" ]; then
    echo "No folio-scribe task is scheduled for the current time window; exiting."
    exit 0
fi

# Validate
case "$TASK_TYPE" in
    hk_plan|hk_review|us_plan|us_review) ;;
    *) echo "ERROR: Invalid task type '$TASK_TYPE'. Use: hk_plan|hk_review|us_plan|us_review"; exit 1 ;;
esac

case "$WATCHLIST_MODE" in
    dynamic|manual|off) ;;
    *) echo "ERROR: Invalid FOLIO_SCRIBE_WATCHLIST_MODE '$WATCHLIST_MODE'. Use: dynamic|manual|off"; exit 1 ;;
esac

case "$PLAN_PHASE" in
    ""|early|initial|final|refresh) ;;
    *) echo "ERROR: Invalid FOLIO_SCRIBE_PLAN_PHASE '$PLAN_PHASE'. Use: early|final"; exit 1 ;;
esac

case "$ALLOW_NON_TRADING_DAY" in
    0|false|no|off|"") ;;
    1|true|yes|on) ;;
    *) echo "ERROR: Invalid FOLIO_SCRIBE_ALLOW_NON_TRADING_DAY '$ALLOW_NON_TRADING_DAY'. Use: 0|1"; exit 1 ;;
esac

case "$AI_TIMEOUT_SECONDS" in
    ""|*[!0-9]*) echo "ERROR: FOLIO_SCRIBE_AI_TIMEOUT_SECONDS must be a non-negative integer"; exit 1 ;;
esac

infer_us_plan_phase() {
    local hour minute total
    if [ "$TASK_TYPE" != "us_plan" ]; then
        return 0
    fi

    if [ -z "$PLAN_PHASE" ]; then
        hour=$((10#$(date +%H)))
        minute=$((10#$(date +%M)))
        total=$((hour * 60 + minute))
        if [ "$total" -ge 990 ] && [ "$total" -lt 1245 ]; then
            PLAN_PHASE="early"
        else
            PLAN_PHASE="final"
        fi
    fi

    case "$PLAN_PHASE" in
        initial) PLAN_PHASE="early" ;;
        refresh) PLAN_PHASE="final" ;;
    esac
}

infer_us_plan_phase

# ── Logging ──────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
LOCK_DIR="${FOLIO_SCRIBE_TASK_LOCK:-$LOG_DIR/folio-${TASK_TYPE}.lock}"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Previous $TASK_TYPE still running; exiting."
    exit 0
fi
trap cleanup EXIT

SENSITIVE_TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/folio-scribe-${TASK_TYPE}.XXXXXX")
LOG_FILE="$LOG_DIR/folio-$(date +%Y%m%d)-${TASK_TYPE}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo ""
echo "================================================================"
echo "  $(date '+%Y-%m-%d %H:%M:%S') | folio-scribe | $TASK_TYPE"
echo "================================================================"

# ── Determine note/session date ─────────────────────────────────────
case "$TASK_TYPE" in
    us_review)
        # 06:45 AM review covers the US session that started the previous evening.
        NOTE_DATE=$(date -v-1d +%Y-%m-%d)
        ;;
    *)
        NOTE_DATE=$(date +%Y-%m-%d)
        ;;
esac
if [ -n "$NOTE_DATE_OVERRIDE" ]; then
    case "$NOTE_DATE_OVERRIDE" in
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
        *) echo "ERROR: FOLIO_SCRIBE_NOTE_DATE must be YYYY-MM-DD, got '$NOTE_DATE_OVERRIDE'"; exit 1 ;;
    esac
    if ! date -j -f "%Y-%m-%d" "$NOTE_DATE_OVERRIDE" +%Y-%m-%d >/dev/null 2>&1; then
        echo "ERROR: FOLIO_SCRIBE_NOTE_DATE is not a valid date: '$NOTE_DATE_OVERRIDE'"
        exit 1
    fi
    NOTE_DATE="$NOTE_DATE_OVERRIDE"
    echo "Note date override: $NOTE_DATE"
fi
echo "Note date: $NOTE_DATE"

# ── Market calendar guard ───────────────────────────────────────────
case "$TASK_TYPE" in
    hk_*) MARKET_CALENDAR="HK" ;;
    us_*) MARKET_CALENDAR="US" ;;
esac

if [ ! -f "$SCRIPT_DIR/market_calendar.py" ]; then
    echo "ERROR: market_calendar.py not found in $SCRIPT_DIR"
    exit 1
fi

set +e
MARKET_STATUS=$(python3 "$SCRIPT_DIR/market_calendar.py" is-open --market "$MARKET_CALENDAR" --date "$NOTE_DATE" 2>&1)
MARKET_STATUS_CODE=$?
set -e
echo "$MARKET_STATUS"
if [ "$MARKET_STATUS_CODE" -ne 0 ]; then
    if [ "$MARKET_STATUS_CODE" -ne 1 ]; then
        echo "ERROR: Market calendar check failed for $MARKET_CALENDAR $NOTE_DATE."
        exit 1
    fi
    case "$ALLOW_NON_TRADING_DAY" in
        1|true|yes|on)
            echo "FOLIO_SCRIBE_ALLOW_NON_TRADING_DAY is enabled; continuing despite closed market."
            ;;
        *)
            echo "No $MARKET_CALENDAR trading session for $NOTE_DATE, skipping $TASK_TYPE."
            exit 0
            ;;
    esac
fi

# ── Ensure Futu OpenD is running ─────────────────────────────────────
ensure_opend() {
    if nc -z 127.0.0.1 "$OPEND_PORT" 2>/dev/null; then
        echo "OpenD already running on port $OPEND_PORT."
        return 0
    fi

    echo "OpenD not responding on port $OPEND_PORT, launching $OPEND_APP ..."
    open "$OPEND_APP"

    local waited=0
    while ! nc -z 127.0.0.1 "$OPEND_PORT" 2>/dev/null; do
        sleep 3
        waited=$((waited + 3))
        if [ "$waited" -ge "$MAX_OPEND_WAIT" ]; then
            echo "ERROR: OpenD did not start within ${MAX_OPEND_WAIT}s."
            return 1
        fi
        echo "  waiting for OpenD ... ${waited}s"
    done
    echo "OpenD is now available (took ${waited}s)."
}

if ! ensure_opend; then
    echo "FATAL: Cannot reach Futu OpenD. Aborting."
    exit 1
fi

case "$TASK_TYPE" in
    hk_plan)   NOTE_SECTION="$SEC_HK_PLAN" ;;
    hk_review) NOTE_SECTION="$SEC_HK_REVIEW" ;;
    us_plan)   NOTE_SECTION="$SEC_US_PLAN" ;;
    us_review) NOTE_SECTION="$SEC_US_REVIEW" ;;
esac

case "$TASK_TYPE" in
    hk_*)
        MARKET_LABEL_ZH="港股"
        MARKET_LABEL_EN="HK"
        MARKET_PREFIX="HK."
        OTHER_MARKET_LABEL_ZH="美股"
        OTHER_MARKET_LABEL_EN="US"
        OTHER_MARKET_PREFIX="US."
        ;;
    us_*)
        MARKET_LABEL_ZH="美股"
        MARKET_LABEL_EN="US"
        MARKET_PREFIX="US."
        OTHER_MARKET_LABEL_ZH="港股"
        OTHER_MARKET_LABEL_EN="HK"
        OTHER_MARKET_PREFIX="HK."
        ;;
esac

US_PLAN_PHASE_LABEL_ZH=""
US_PLAN_PHASE_LABEL_EN=""
US_PLAN_PHASE_GUIDANCE_ZH=""
US_PLAN_PHASE_GUIDANCE_EN=""
if [ "$TASK_TYPE" = "us_plan" ]; then
    case "$PLAN_PHASE" in
        early)
            US_PLAN_PHASE_LABEL_ZH="16:30 美股早盘前初版计划"
            US_PLAN_PHASE_LABEL_EN="16:30 US early pre-market draft plan"
            US_PLAN_PHASE_GUIDANCE_ZH="本次是 16:30 初版计划：重点是提前筛选美股候选、梳理账户风险、给出初步触发区间。必须明确标注这是初版，提示 20:45 会用更接近开盘的盘前价格和新闻刷新；不要把初版写成最终执行计划。"
            US_PLAN_PHASE_GUIDANCE_EN="This is the 16:30 early draft plan: focus on early US candidate screening, account risk, and preliminary trigger zones. Explicitly label it as a draft and note that the 20:45 run will refresh it with fresher pre-market prices and news; do not present it as the final execution plan."
            ;;
        *)
            US_PLAN_PHASE_LABEL_ZH="20:45 美股开盘前刷新版计划"
            US_PLAN_PHASE_LABEL_EN="20:45 US pre-open refreshed plan"
            US_PLAN_PHASE_GUIDANCE_ZH="本次是 20:45 开盘前刷新版计划：以最新 Futu 快照为准，重写并收敛 16:30 初版中的观察清单、触发价和风险边界。输出应作为本交易时段的最终盘前计划。"
            US_PLAN_PHASE_GUIDANCE_EN="This is the 20:45 pre-open refreshed plan: use the latest Futu snapshot to rewrite and narrow the 16:30 draft watchlist, triggers, and risk boundaries. Treat this as the final pre-market plan for the session."
            ;;
    esac
fi
if [ "$TASK_TYPE" = "us_plan" ]; then
    echo "US plan phase: ${US_PLAN_PHASE_LABEL_EN:-$PLAN_PHASE}"
fi

extract_snapshot_json() {
    local raw_file="$1"
    local json_file="$2"
    python3 - "$raw_file" "$json_file" <<'PY'
import json
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
start = text.find("{")
end = text.rfind("}")
if start < 0 or end < start:
    raise SystemExit("ERROR: snapshot output did not contain a JSON object")
payload = json.loads(text[start:end + 1])
Path(sys.argv[2]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

read_snapshot_json() {
    local json_file="$1"
    shift
    local raw_file
    raw_file=$(mktemp "$SENSITIVE_TMP_DIR/snapshot-raw.XXXXXX")
    python3 "$SCRIPT_DIR/read_futu_snapshot.py" "$@" > "$raw_file"
    extract_snapshot_json "$raw_file" "$json_file"
}

write_ibkr_plugin_request_json() {
    local json_file="$1"
    python3 - "$json_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "account": None,
    "accounts": {},
    "positions": [],
    "orders": [],
    "fills": [],
    "quotes": {},
    "raw": {
        "source": "ibkr_codex_app",
        "readonly": True,
        "trading_status": "agent_read_required",
        "trading_error": (
            "The scheduled Codex agent must call the connected IBKR app for "
            "positions, account metrics, balances, live orders, and trades."
        ),
    },
}
Path(sys.argv[1]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
PY
}

write_unavailable_ibkr_snapshot_json() {
    local json_file="$1"
    local error_file="$2"
    python3 - "$json_file" "$error_file" "$IBKR_HOST" "$IBKR_PORT" "$IBKR_CLIENT_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

json_file, error_file, host, port, client_id = sys.argv[1:6]
error_text = Path(error_file).read_text(encoding="utf-8", errors="replace").strip()
payload = {
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "account": None,
    "accounts": {},
    "positions": [],
    "orders": [],
    "fills": [],
    "quotes": {},
    "raw": {
        "source": "ibkr_tws_gateway",
        "host": host,
        "port": port,
        "client_id": client_id,
        "readonly": True,
        "trading_status": "unavailable",
        "trading_error": error_text or "IBKR snapshot command failed without stderr output.",
    },
}
Path(json_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

read_ibkr_snapshot_json() {
    local json_file="$1"
    shift || true
    local raw_file error_file
    local -a ibkr_args
    raw_file=$(mktemp "$SENSITIVE_TMP_DIR/ibkr-snapshot-raw.XXXXXX")
    error_file=$(mktemp "$SENSITIVE_TMP_DIR/ibkr-snapshot-error.XXXXXX")

    if uses_ibkr_plugin; then
        write_ibkr_plugin_request_json "$json_file"
        return 0
    fi

    if [ "$IBKR_SNAPSHOT_MODE" = "off" ]; then
        printf 'IBKR snapshot disabled by FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE=off.\n' > "$error_file"
        write_unavailable_ibkr_snapshot_json "$json_file" "$error_file"
        return 0
    fi

    ibkr_args=(
        --host "$IBKR_HOST"
        --port "$IBKR_PORT"
        --client-id "$IBKR_CLIENT_ID"
        --timeout "$IBKR_TIMEOUT"
    )
    if [ -n "$IBKR_ACCOUNT" ]; then
        ibkr_args+=(--account "$IBKR_ACCOUNT")
    fi

    if python3 "$SCRIPT_DIR/read_ibkr_snapshot.py" "${ibkr_args[@]}" "$@" > "$raw_file" 2> "$error_file"; then
        extract_snapshot_json "$raw_file" "$json_file"
        return 0
    fi

    if [ "$IBKR_SNAPSHOT_MODE" = "required" ]; then
        echo "ERROR: IBKR snapshot failed and FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE=required."
        python3 "$SCRIPT_DIR/account_alias.py" mask < "$error_file"
        return 1
    fi

    echo "WARNING: IBKR snapshot unavailable; continuing with Futu snapshot only."
    if [ -s "$error_file" ]; then
        echo "IBKR error excerpt:"
        python3 "$SCRIPT_DIR/account_alias.py" mask < "$error_file" | sed -n '1,12p'
    fi
    write_unavailable_ibkr_snapshot_json "$json_file" "$error_file"
}

snapshot_has_trade_data() {
    local json_file="$1"
    python3 - "$json_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
account = payload.get("account") or {}

def populated(value):
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in {"", "-"}:
        return False
    return True

has_account = any(
    populated(account.get(key))
    for key in ("total_assets", "cash", "buying_power", "currency")
)
has_trade_rows = any(
    payload.get(key)
    for key in ("positions", "orders", "fills")
)

raise SystemExit(0 if has_account or has_trade_rows else 1)
PY
}

read_initial_snapshot_when_ready() {
    local waited=0

    while true; do
        read_snapshot_json "$SNAPSHOT_POSITIONS_JSON"
        if snapshot_has_trade_data "$SNAPSHOT_POSITIONS_JSON"; then
            if [ "$waited" -gt 0 ]; then
                echo "Futu snapshot is ready (took ${waited}s)."
            fi
            return 0
        fi

        if [ "$waited" -ge "$MAX_SNAPSHOT_READY_WAIT" ]; then
            echo "ERROR: Futu snapshot still has no account or position data after ${waited}s."
            echo "       OpenD may be reachable but not fully logged in or trade data is not ready."
            return 1
        fi

        waited=$((waited + SNAPSHOT_READY_INTERVAL))
        echo "Futu snapshot has no account/position data yet; waiting ${waited}s/${MAX_SNAPSHOT_READY_WAIT}s ..."
        sleep "$SNAPSHOT_READY_INTERVAL"
    done
}

SNAPSHOT_POSITIONS_JSON=$(mktemp "$SENSITIVE_TMP_DIR/positions.XXXXXX")
SNAPSHOT_JSON_FILE=$(mktemp "$SENSITIVE_TMP_DIR/snapshot.XXXXXX")
IBKR_SNAPSHOT_JSON_FILE=$(mktemp "$SENSITIVE_TMP_DIR/ibkr-snapshot.XXXXXX")
AI_CONTENT_FILE=$(mktemp "$SENSITIVE_TMP_DIR/content.XXXXXX")

echo "Reading Futu snapshot ..."
read_initial_snapshot_when_ready

declare -a SNAPSHOT_SYMBOLS=()
declare -a WATCHLIST_SYMBOLS=()
WATCHLIST_CANDIDATE_CSV=""

add_symbol_unique() {
    local symbol="$1"
    local existing
    [ -n "$symbol" ] || return 0
    symbol=$(printf '%s' "$symbol" | tr '[:lower:]' '[:upper:]')
    if [ "${#SNAPSHOT_SYMBOLS[@]}" -gt 0 ]; then
        for existing in "${SNAPSHOT_SYMBOLS[@]}"; do
            if [ "$existing" = "$symbol" ]; then
                return 0
            fi
        done
    fi
    SNAPSHOT_SYMBOLS+=("$symbol")
}

add_watchlist_symbol() {
    local symbol="$1"
    local existing
    [ -n "$symbol" ] || return 0
    symbol=$(printf '%s' "$symbol" | tr '[:lower:]' '[:upper:]')
    case "$symbol" in
        "$MARKET_PREFIX"*) ;;
        *) return 0 ;;
    esac
    if [ "${#WATCHLIST_SYMBOLS[@]}" -gt 0 ]; then
        for existing in "${WATCHLIST_SYMBOLS[@]}"; do
            if [ "$existing" = "$symbol" ]; then
                return 0
            fi
        done
    fi
    WATCHLIST_SYMBOLS+=("$symbol")
    add_symbol_unique "$symbol"
}

while IFS= read -r symbol; do
    if [ -n "$symbol" ]; then
        add_symbol_unique "$symbol"
    fi
done < <(python3 - "$SNAPSHOT_POSITIONS_JSON" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
seen = set()
for position in payload.get("positions", []):
    symbol = position.get("symbol")
    if symbol and symbol not in seen:
        print(symbol)
        seen.add(symbol)
PY
)

case "$TASK_TYPE" in
    hk_*) WATCHLIST_RAW="$HK_WATCHLIST_SYMBOLS" ;;
    us_*) WATCHLIST_RAW="$US_WATCHLIST_SYMBOLS" ;;
esac

if [ "$WATCHLIST_MODE" != "off" ] && [ "$WATCHLIST_MODE" != "manual" ]; then
    DYNAMIC_WATCHLIST_FILE=$(mktemp "$SENSITIVE_TMP_DIR/watchlist.XXXXXX")
    echo "Selecting dynamic ${MARKET_LABEL_EN} watchlist candidates from Futu ..."
    if python3 "$SCRIPT_DIR/select_watchlist_candidates.py" \
        --market "$MARKET_LABEL_EN" \
        --host 127.0.0.1 \
        --port "$OPEND_PORT" \
        --limit "$WATCHLIST_LIMIT" \
        > "$DYNAMIC_WATCHLIST_FILE"; then
        while IFS= read -r symbol; do
            add_watchlist_symbol "$symbol"
        done < "$DYNAMIC_WATCHLIST_FILE"
        echo "Dynamic watchlist candidates selected: ${#WATCHLIST_SYMBOLS[@]}"
    else
        echo "WARNING: Dynamic watchlist scanner failed; continuing without dynamic candidates."
    fi
fi

WATCHLIST_RAW="${WATCHLIST_RAW//,/ }"
WATCHLIST_RAW="${WATCHLIST_RAW//;/ }"
if [ "$WATCHLIST_MODE" != "off" ] && [ -n "$WATCHLIST_RAW" ]; then
    echo "Adding manually configured ${MARKET_LABEL_EN} watchlist symbols ..."
    for symbol in $WATCHLIST_RAW; do
        add_watchlist_symbol "$symbol"
    done
fi

if [ "${#WATCHLIST_SYMBOLS[@]}" -gt 0 ]; then
    WATCHLIST_CANDIDATE_CSV=$(IFS=,; printf '%s' "${WATCHLIST_SYMBOLS[*]}")
fi

if [ "${#SNAPSHOT_SYMBOLS[@]}" -gt 0 ]; then
    echo "Reading quotes for ${#SNAPSHOT_SYMBOLS[@]} symbols (positions + watchlist candidates) ..."
    read_snapshot_json "$SNAPSHOT_JSON_FILE" "${SNAPSHOT_SYMBOLS[@]}"
else
    cp "$SNAPSHOT_POSITIONS_JSON" "$SNAPSHOT_JSON_FILE"
fi

if [ "$MARKET_LABEL_EN" = "US" ]; then
    if uses_ibkr_plugin; then
        echo "Preparing direct IBKR app read for the scheduled Codex agent ..."
    else
        echo "Reading optional IBKR Gateway/TWS fallback snapshot ..."
    fi
    read_ibkr_snapshot_json "$IBKR_SNAPSHOT_JSON_FILE"
else
    python3 - "$IBKR_SNAPSHOT_JSON_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "account": None,
    "accounts": {},
    "positions": [],
    "orders": [],
    "fills": [],
    "quotes": {},
    "raw": {
        "source": "ibkr_tws_gateway",
        "trading_status": "not_used_for_market",
    },
}
Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
fi

# Swap raw IBKR account ids (keys, fields, error text) for 主/次 aliases before
# anything formats the snapshot: prompts, fallback tables, and notes only ever
# see aliases. The raw id is needed only for the Gateway request above.
IBKR_ALIAS_ARGS=(sanitize-snapshot "$IBKR_SNAPSHOT_JSON_FILE")
if [ -n "$IBKR_ACCOUNT" ]; then
    IBKR_ALIAS_ARGS+=(--account-id "$IBKR_ACCOUNT")
fi
python3 "$SCRIPT_DIR/account_alias.py" "${IBKR_ALIAS_ARGS[@]}"

SNAPSHOT_CONTEXT=$(python3 - "$SNAPSHOT_JSON_FILE" "$MARKET_PREFIX" "$MARKET_LABEL_EN" "$TASK_TYPE" "$WATCHLIST_CANDIDATE_CSV" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
market_prefix = sys.argv[2].upper()
market_label = sys.argv[3]
task_type = sys.argv[4]
candidate_symbols = [
    symbol.strip().upper()
    for symbol in (sys.argv[5] if len(sys.argv) > 5 else "").split(",")
    if symbol.strip()
]

def value(item, key, default="-"):
    current = item.get(key)
    return default if current is None or current == "" else str(current)

def symbol_of(item):
    return str(item.get("symbol") or "").upper()

def is_target_market_symbol(symbol):
    return str(symbol or "").upper().startswith(market_prefix)

def quote_display(quote):
    if market_label == "US" and task_type == "us_plan":
        for field, label in (
            ("pre_price", "pre_price"),
            ("overnight_price", "overnight_price"),
            ("after_price", "after_price"),
            ("price", "regular_close"),
        ):
            if value(quote, field) != "-":
                return value(quote, field), label
    return value(quote, "price"), "last_price"

def quote_line(symbol, quote):
    latest, source = quote_display(quote)
    pieces = [
        f"{symbol} {value(quote, 'name')}",
        f"latest={latest}",
        f"latest_source={source}",
        f"regular_close={value(quote, 'price')}",
        f"quote_time={value(quote, 'quote_time')}",
        f"open={value(quote, 'open')}",
        f"high={value(quote, 'high')}",
        f"low={value(quote, 'low')}",
        f"prev_close={value(quote, 'previous_close')}",
        f"volume={value(quote, 'volume')}",
        f"turnover={value(quote, 'turnover')}",
    ]
    if market_label == "US":
        pieces.extend([
            f"pre_price={value(quote, 'pre_price')}",
            f"pre_high={value(quote, 'pre_high_price')}",
            f"pre_low={value(quote, 'pre_low_price')}",
            f"pre_volume={value(quote, 'pre_volume')}",
            f"after_price={value(quote, 'after_price')}",
            f"overnight_price={value(quote, 'overnight_price')}",
        ])
    return " | ".join(pieces)

positions = [item for item in payload.get("positions", []) if is_target_market_symbol(symbol_of(item))]
held_symbols = {symbol_of(item) for item in positions}
orders = [item for item in payload.get("orders", []) if is_target_market_symbol(symbol_of(item))]
fills = [item for item in payload.get("fills", []) if is_target_market_symbol(symbol_of(item))]
quotes = {
    symbol: quote
    for symbol, quote in (payload.get("quotes") or {}).items()
    if is_target_market_symbol(symbol)
}
watchlist_candidates = [
    symbol
    for symbol in candidate_symbols
    if is_target_market_symbol(symbol) and symbol not in held_symbols
]

lines = []
lines.append(f"market_filter: {market_label} symbols only ({market_prefix}*)")
lines.append(f"captured_at: {payload.get('captured_at', '-')}")
account = payload.get("account") or {}
lines.append(
    "account: "
    f"total_assets={value(account, 'total_assets')} {value(account, 'currency', '')}, "
    f"cash={value(account, 'cash')}, buying_power={value(account, 'buying_power')}, "
    f"daily_pnl={value(account, 'daily_pnl')}, leverage={value(account, 'leverage')}"
)

lines.append("")
lines.append("positions:")
if not positions:
    lines.append(f"- (No {market_label} positions in snapshot.)")
for position in positions:
    lines.append(
        "- "
        f"{value(position, 'symbol')} {value(position, 'name')} | "
        f"qty={value(position, 'quantity')} | diluted_cost={value(position, 'cost')} | "
        f"market_value={value(position, 'market_value')} {value(position, 'currency', '')} | "
        f"pnl_diluted_basis={value(position, 'unrealized_pnl')} | "
        f"realized_pnl_reference={value(position, 'realized_pnl')}"
    )

lines.append("")
lines.append(f"orders: {len(orders)}")
for order in orders:
    lines.append(
        "- "
        f"{value(order, 'symbol')} {value(order, 'side')} | order_id={value(order, 'order_id')} | "
        f"qty={value(order, 'quantity')} | price={value(order, 'price')} | status={value(order, 'status')}"
        f" | dealt_qty={value(order, 'filled_quantity')} | dealt_avg_price={value(order, 'filled_avg_price')}"
        f" | created_at={value(order, 'submitted_at')}"
    )

lines.append("")
lines.append(f"fills: {len(fills)}")
for fill in fills:
    lines.append(
        "- "
        f"{value(fill, 'symbol')} {value(fill, 'side')} | deal_id={value(fill, 'deal_id')} | "
        f"order_id={value(fill, 'order_id')} | "
        f"qty={value(fill, 'quantity')} | price={value(fill, 'price')} | at={value(fill, 'filled_at')}"
    )

lines.append("")
lines.append("quotes:")
if not quotes:
    lines.append(f"- (No {market_label} quotes in snapshot.)")
for symbol, quote in quotes.items():
    lines.append("- " + quote_line(symbol, quote))

lines.append("")
lines.append("watchlist_candidates:")
if not watchlist_candidates:
    lines.append(f"- (No non-held {market_label} dynamic watchlist candidates available.)")
for symbol in watchlist_candidates:
    quote = quotes.get(symbol)
    if not quote:
        lines.append(f"- {symbol} | quote unavailable in current snapshot")
        continue
    lines.append("- " + quote_line(symbol, quote))

print("\n".join(lines))
PY
)

IBKR_CONTEXT=$(python3 - "$IBKR_SNAPSHOT_JSON_FILE" "$MARKET_PREFIX" "$MARKET_LABEL_EN" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

market_prefix = sys.argv[2].upper()
market_label = sys.argv[3]

def value(item, key, default="-"):
    current = item.get(key) if isinstance(item, dict) else None
    return default if current is None or current == "" else str(current)

def symbol_of(item):
    return str(item.get("symbol") or "").upper()

def is_target_market_symbol(symbol):
    return str(symbol or "").upper().startswith(market_prefix)

raw = payload.get("raw") or {}
status = raw.get("trading_status", "-")
lines = []
lines.append(f"ibkr_source: {raw.get('source', '-')}")
lines.append(f"ibkr_status: {status}")
lines.append(f"captured_at: {payload.get('captured_at', '-')}")
lines.append(f"managed_accounts: {', '.join(raw.get('managed_accounts') or []) or '-'}")

if market_label != "US":
    lines.append("(IBKR snapshot is not used for this non-US task.)")
    print("\n".join(lines))
    raise SystemExit

if status == "agent_read_required":
    lines.append(
        "ibkr_action: Call the connected IBKR app now; do not use this marker "
        "as evidence of an empty account."
    )
    print("\n".join(lines))
    raise SystemExit

if status not in {"ok"}:
    lines.append(f"ibkr_error: {raw.get('trading_error', '-')}")
    print("\n".join(lines))
    raise SystemExit

accounts = payload.get("accounts") or {}
lines.append("")
lines.append("accounts:")
if not accounts:
    lines.append("- (No IBKR account summary available.)")
for account_alias, account in accounts.items():
    lines.append(
        "- "
        f"{account_alias} | total_assets={value(account, 'total_assets')} {value(account, 'currency', '')} | "
        f"cash={value(account, 'cash')} | buying_power={value(account, 'buying_power')} | "
        f"leverage={value(account, 'leverage')}"
    )

positions = [
    item for item in payload.get("positions", [])
    if is_target_market_symbol(symbol_of(item))
]
orders = [
    item for item in payload.get("orders", [])
    if is_target_market_symbol(symbol_of(item))
]
fills = [
    item for item in payload.get("fills", [])
    if is_target_market_symbol(symbol_of(item))
]

lines.append("")
lines.append("positions:")
if not positions:
    lines.append("- (No IBKR US positions in snapshot.)")
for position in positions:
    raw_position = position.get("raw") or {}
    lines.append(
        "- "
        f"{value(position, 'symbol')} {value(position, 'name')} | "
        f"account={value(raw_position, 'account')} | qty={value(position, 'quantity')} | "
        f"avg_cost={value(position, 'cost')} | market_value={value(position, 'market_value')} {value(position, 'currency', '')} | "
        f"unrealized_pnl={value(position, 'unrealized_pnl')} | realized_pnl={value(position, 'realized_pnl')}"
    )

lines.append("")
lines.append(f"orders: {len(orders)}")
for order in orders:
    raw_order = order.get("raw") or {}
    lines.append(
        "- "
        f"{value(order, 'symbol')} {value(order, 'side')} | account={value(raw_order, 'account')} | "
        f"order_id={value(order, 'order_id')} | order_type={value(raw_order, 'order_type')} | "
        f"qty={value(order, 'quantity')} | price={value(order, 'price')} | status={value(order, 'status')} | "
        f"filled_qty={value(order, 'filled_quantity')} | filled_avg_price={value(order, 'filled_avg_price')}"
    )

lines.append("")
lines.append(f"fills: {len(fills)}")
for fill in fills:
    raw_fill = fill.get("raw") or {}
    lines.append(
        "- "
        f"{value(fill, 'symbol')} {value(fill, 'side')} | account={value(raw_fill, 'account')} | "
        f"deal_id={value(fill, 'deal_id')} | order_id={value(fill, 'order_id')} | "
        f"qty={value(fill, 'quantity')} | price={value(fill, 'price')} | at={value(fill, 'filled_at')}"
    )

print("\n".join(lines))
PY
)
NOTE_PATH="$VAULT/Daily/${NOTE_DATE}.md"
if [ -r "$NOTE_PATH" ]; then
    EXISTING_NOTE=$(python3 - "$NOTE_PATH" "$MARKET_LABEL_ZH" "$MARKET_LABEL_EN" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
market_zh = sys.argv[2]
market_en = sys.argv[3]
limit = 12000

lines = text.splitlines()
chunks = []
index = 0
while index < len(lines):
    line = lines[index]
    if not line.startswith("## "):
        index += 1
        continue

    heading = line
    block = [line]
    index += 1
    while index < len(lines) and not lines[index].startswith("## "):
        block.append(lines[index])
        index += 1

    heading_lower = heading.lower()
    if market_zh in heading or market_en.lower() in heading_lower:
        chunks.append("\n".join(block).strip())

if chunks:
    output = "\n\n---\n\n".join(chunk for chunk in chunks if chunk)
else:
    output = f"(No existing {market_en} market section found in {sys.argv[1]}.)"

if len(output) > limit:
    print(output[:limit])
    print("\n[Existing same-market note context truncated by runner.]")
else:
    print(output)
PY
)
else
    EXISTING_NOTE="(No existing daily note at ${NOTE_PATH}.)"
fi

RULES_DIR="$VAULT/Rules"
RULES_CONTEXT=$(python3 - "$RULES_DIR" "$MARKET_LABEL_ZH" "$MARKET_LABEL_EN" "$MARKET_PREFIX" <<'PY'
import sys
from pathlib import Path

rules_dir = Path(sys.argv[1])
market_zh = sys.argv[2]
market_en = sys.argv[3]
market_prefix = sys.argv[4].upper()
if not rules_dir.exists():
    print("(No standing rules directory found.)")
    raise SystemExit

paths = sorted(path for path in rules_dir.glob("*.md") if path.is_file())
if not paths:
    print("(No standing rule files found.)")
    raise SystemExit

total_limit = 20000
per_file_limit = 6000
used = 0
chunks = []

hk_markers = ("HK.", "港股", "小米", "恒生", "腾讯", "阿里", "01810")
us_markers = ("US.", "美股", "NYSE", "NASDAQ", "纳斯达克", "QuantumScape", "QS")

def market_markers_for(prefix):
    return hk_markers if prefix == "HK." else us_markers

def other_markers_for(prefix):
    return us_markers if prefix == "HK." else hk_markers

def keep_rule(path, text):
    haystack = f"{path.name}\n{text}"
    own = any(marker in haystack for marker in market_markers_for(market_prefix))
    other = any(marker in haystack for marker in other_markers_for(market_prefix))
    generic = not own and not other
    return own or generic

for path in paths:
    header = f"\n--- Rules/{path.name} ---\n"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not keep_rule(path, text):
        continue
    if len(text) > per_file_limit:
        text = text[:per_file_limit] + "\n[Rule file truncated by runner.]"
    chunk = header + text + "\n"
    if used + len(chunk) > total_limit:
        chunks.append("\n[Additional rule files omitted by runner due to context limit.]\n")
        break
    chunks.append(chunk)
    used += len(chunk)

if chunks:
    print("".join(chunks).strip())
else:
    print(f"(No standing rules matched {market_en} market.)")
PY
)

# ── Common prompt suffix ─────────────────────────────────────────────
if [ "$LANG_PREF" = "en" ]; then
    if [ "$MARKET_LABEL_EN" = "US" ] && uses_ibkr_plugin; then
        PROMPT_SUFFIX="Before writing, call the connected Interactive Brokers (IBKR) app for open positions, account metrics, currency balances, live orders, and trades for the relevant session. Use those calls as the source of truth for the IBKR account. For every IBKR-held symbol that is missing a current quote in the supplied Futu summary, run the read-only helper \`python3 ${SCRIPT_DIR}/read_futu_snapshot.py <US.SYMBOL...> --quotes-only\` and use its OpenD result for quotes and triggers; never substitute an unsubscribed or delayed IBKR quote as a precise trigger. Output only the Markdown body for the target section. Do not include the second-level section heading, frontmatter, code fences, shell commands, or tool-use narration. The runner will write the note after your response."
    else
        PROMPT_SUFFIX="Output only the Markdown body for the target section. Do not include the second-level section heading, frontmatter, code fences, shell commands, or any tool-use instructions. The runner has already read data and will write the note after your response."
    fi
else
    if [ "$MARKET_LABEL_EN" = "US" ] && uses_ibkr_plugin; then
        PROMPT_SUFFIX="生成正文前，必须调用已连接的 Interactive Brokers（IBKR）插件，动态读取当前持仓、账户指标、分币种余额、未成交订单，以及对应交易时段的成交。IBKR 账户事实以插件结果为准。对插件返回但 runner 的 Futu 摘要中缺少当前行情的每个持仓代码，必须运行只读命令 \`python3 ${SCRIPT_DIR}/read_futu_snapshot.py <US.代码...> --quotes-only\` 补拉 OpenD 行情，并用该结果制定价格触发；不得把 IBKR 未订阅或延迟行情当作精确触发价。只输出目标 section 的 Markdown 正文，不要包含二级标题、frontmatter、代码围栏、shell 命令或工具调用过程。写入会由 runner 在你回复后完成。"
    else
        PROMPT_SUFFIX="只输出目标 section 的 Markdown 正文。不要包含二级标题、frontmatter、代码围栏、shell 命令或任何工具调用说明。数据已由 runner 读取，写入也会由 runner 在你回复后完成。"
    fi
fi

# ── Build /folio-scribe prompt ───────────────────────────────────────
build_prompt() {
    local body
    if [ "$LANG_PREF" = "en" ]; then
        _build_prompt_en
    else
        _build_prompt_zh
    fi
}

market_scope_zh() {
    cat <<EOF
市场隔离规则：
- 本次任务只处理${MARKET_LABEL_ZH}。只能使用 ${MARKET_PREFIX} 开头的标的、订单、成交、期权和行情。
- 不得提及${OTHER_MARKET_LABEL_ZH}、${OTHER_MARKET_PREFIX} 标的、${OTHER_MARKET_LABEL_ZH}持仓、${OTHER_MARKET_LABEL_ZH}订单、${OTHER_MARKET_LABEL_ZH}行情或${OTHER_MARKET_LABEL_ZH}观察清单。
- 账户总资产、现金和购买力可以作为总账户风险约束出现，但不能展开另一个市场的具体标的。
- 如果快照里没有目标市场持仓或订单，只写“无目标市场持仓/订单”，不要用另一个市场补充内容。
- “推荐关注清单”不是当前持仓清单；watchlist_candidates 来自 Futu 最新行情动态筛选，必须让 AI 从这些非持仓候选里直接选择。
- 推荐关注清单必须同时列出标的代码和股票名称；名称来自 watchlist_candidates，缺失时写“-”。
- 持仓数量、摊薄成本、市值和盈亏必须以 positions 为准；orders/fills 只用于解释执行过程，不得用订单列表手工反推或覆盖 positions 的最终持仓。
- positions 中 diluted_cost 是 Futu 摊薄成本口径；pnl_diluted_basis 是配套盈亏口径，不要写成平均成本口径的未实现盈亏。
- 美股计划里的 latest 字段已经按当前交易阶段选择：盘前优先 pre_price；regular_close 只是上一常规盘收盘价，不能当作盘前最新价。
- 美股任务必须通过已连接的 IBKR 插件动态读取账户持仓、成本、订单、成交、余额和保证金；插件结果是 IBKR 账户事实源。Futu OpenD 主要用于实时/盘前盘后行情、触发价和候选观察标的。不要把两个券商的持仓混为同一账户；不要因为本地 Gateway 关闭而把 IBKR 持仓写成空仓。
- 账户号是敏感信息，输出中不得出现任何原始账户号（如 U 加数字）。IBKR 账户一律用别名：总资产（净清算价值）最大的写 U****（主），其余写 U****（次）；超过两个账户时依次写 U****（次1）、U****（次2）。IBKR 摘要中已是别名的原样使用。
- 当前持仓、已有期权和已有订单只放在“当前持仓/标的计划/期权计划”里，不要列入推荐关注清单；如果没有候选行情，保留表头并说明“无候选标的数据”。
- 推荐关注清单只用于后续观察，不是买入建议。
EOF
}

market_scope_en() {
    cat <<EOF
Market isolation rules:
- This task is ${MARKET_LABEL_EN} market only. Use only symbols, orders, fills, options, and quotes whose symbols start with ${MARKET_PREFIX}.
- Do not mention ${OTHER_MARKET_LABEL_EN} symbols, positions, orders, quotes, or watchlists.
- Total assets, cash, and buying power may appear only as account-level risk constraints; do not expand into the other market's instruments.
- If the snapshot has no target-market positions or orders, say so directly and do not fill the gap with the other market.
- The recommended watchlist is not the current position list; watchlist_candidates are dynamically scanned from the latest Futu market data, and the AI must select directly from these non-held candidates.
- The recommended watchlist must include both symbol and stock name; use the name from watchlist_candidates, or "-" when unavailable.
- Position quantity, diluted cost, market value, and P/L must come from positions. Use orders/fills only to explain execution; do not manually net orders to override final positions.
- In positions, diluted_cost is Futu's diluted-cost basis; pnl_diluted_basis is the paired P/L basis. Do not describe it as average-cost unrealized P/L.
- For US plans, the latest field is already session-aware: pre-market uses pre_price first. regular_close is only the prior regular-session close and must not be treated as the current pre-market price.
- For US tasks, dynamically read positions, cost basis, orders, trades, balances, and margin from the connected IBKR app; its response is the source of truth for the IBKR account. Use Futu OpenD primarily for live and extended-hours quotes, triggers, and watchlist candidates. Do not merge the two brokers, and do not report the IBKR account as empty merely because local Gateway is closed.
- Account numbers are sensitive: never write a raw account number (such as U followed by digits). Refer to IBKR accounts only by alias: the account with the largest total assets (net liquidation) is U****（主）, the other U****（次）, or U****（次1）, U****（次2）… when there are more than two. Use aliases already present in the IBKR summary verbatim.
- Current positions, existing options, and working orders belong only in the positions/instrument/option sections. Do not list them in the recommended watchlist unless no candidate quotes are available, in which case keep the table header and state that candidate data is unavailable.
- Watchlist candidates are for observation only, not buy recommendations.
EOF
}

format_template_zh() {
    case "$TASK_TYPE" in
        hk_plan)
            cat <<'EOF'
**数据源：Futu OpenD 港股快照 | 生成时间：YYYY-MM-DD HH:mm HKT**

---

### 账户快照与港股风险约束

| 项目 | 数值 | 备注 |
|------|------|------|
| 总资产 |  | 账户口径，仅用于风险约束 |
| 现金余额 |  | 今日第一约束 |
| 购买力 |  | 不等于可无条件加仓 |
| 港股工作订单 |  | 只统计港股 |
| 港股今日成交 |  | 只统计港股 |

> **核心判断**：一句话总结今日港股主风险和操作基调。

### 当前港股持仓

| 标的 | 名称 | 数量 | 摊薄成本 | 现价 | 市值 | 盈亏 |
|------|------|------|------|------|------|----------|

### 港股开盘前盘面

- 只写港股标的、港股期权、港股指数/ETF。
- 写关键价位、成交量、强弱判断。

### 今日港股计划

#### HK.xxxxx 标的名称

| 情景 | 触发条件 | 操作倾向 | 目的 |
|------|----------|----------|------|

### 港股期权计划

| 合约 | 当前定位 | 触发条件 | 操作倾向 |
|------|----------|----------|----------|

### 港股推荐关注清单

| 标的 | 名称 | 关注理由 | 触发意义 |
|------|------|----------|----------|

### 风险边界

- 最大新增港股敞口：
- 最大减仓/调整范围：
- 价格失效条件：
- 现金/融资约束：

### 今日不做什么

1. 不在无触发条件时追价。
2. 不为摊低成本临时加码。
3. 不使用未计划的复杂期权结构。
4. 不扩大未被风险边界覆盖的港股风险。

### 收盘前自检

- 是否按触发条件执行？
- 是否出现计划外交易冲动？
- 是否遵守现金/融资约束？
EOF
            ;;
        hk_review)
            cat <<'EOF'
**数据源：Futu OpenD 港股收盘快照 | 生成时间：YYYY-MM-DD HH:mm HKT**

---

### 港股账户与持仓变化

| 项目 | 计划基准 | 收盘快照 | 变化 |
|------|----------|----------|------|

### 港股成交与订单

| 标的 | 方向 | 数量 | 价格 | 状态 | 是否符合计划 |
|------|------|------|------|------|--------------|

### 计划 vs 实际执行

| 计划场景 | 触发条件 | 当日实际 | 是否触发 | 实际操作 | 结论 |
|----------|----------|----------|----------|----------|------|

### 港股持仓表现

| 标的 | 开盘/计划价 | 收盘/快照价 | 变化 | 影响 |
|------|-------------|-------------|------|------|

### 纪律复盘

- 做对的部分：
- 风险漂移：
- 需要改进：
- 纪律评分：

### 下一港股交易日计划框架

| 情景 | 触发条件 | 操作倾向 | 风险备注 |
|------|----------|----------|----------|

### 明日港股推荐关注清单

| 标的 | 名称 | 继续观察理由 | 移除/保留 |
|------|------|--------------|-----------|
EOF
            ;;
        us_plan)
            cat <<'EOF'
**数据源：Futu OpenD 行情 + IBKR 插件账户数据 | 生成时间：YYYY-MM-DD HH:mm HKT**

---

### 账户快照与美股风险约束

| 项目 | 数值 | 备注 |
|------|------|------|
| 总资产 |  | 账户口径，仅用于风险约束 |
| 现金余额 |  | 本交易时段第一约束 |
| 购买力 |  | 不等于可无条件加仓 |
| 美股工作订单 |  | 只统计美股 |
| 美股今日成交 |  | 只统计美股 |

### 当前美股持仓

| 标的 | 名称 | 数量 | 摊薄成本 | 盘前/快照价 | 市值 | 盈亏 |
|------|------|------|------|-------------|------|----------|

### 美股盘前盘面

- 只写美股标的、美股期权、美股指数/ETF。
- 写关键价位、盘前波动、成交量/流动性。

### 本交易时段美股计划

#### US.xxxx 标的名称

| 情景 | 触发条件 | 操作倾向 | 目的 |
|------|----------|----------|------|

### 美股推荐关注清单

| 标的 | 名称 | 关注理由 | 触发意义 |
|------|------|----------|----------|

### 风险边界

- 最大新增美股敞口：
- 最大减仓/调整范围：
- 价格失效条件：
- 现金/融资约束：

### 本交易时段不做什么

1. 不在无触发条件时追价。
2. 不为摊低成本临时加码。
3. 不新增未计划的高波动风险。
4. 不扩大未被风险边界覆盖的美股风险。
EOF
            ;;
        us_review)
            cat <<'EOF'
**数据源：Futu OpenD 行情 + IBKR 插件账户数据 | 生成时间：YYYY-MM-DD HH:mm HKT**

---

### 美股账户与持仓变化

| 项目 | 计划基准 | 盘后快照 | 变化 |
|------|----------|----------|------|

### 美股成交与订单

| 标的 | 方向 | 数量 | 价格 | 状态 | 是否符合计划 |
|------|------|------|------|------|--------------|

### 计划 vs 实际执行

| 计划场景 | 触发条件 | 实际走势 | 是否触发 | 实际操作 | 结论 |
|----------|----------|----------|----------|----------|------|

### 美股持仓表现

| 标的 | 计划价/盘前价 | 盘后价 | 变化 | 影响 |
|------|---------------|--------|------|------|

### 纪律复盘

- 做对的部分：
- 风险漂移：
- 需要改进：
- 纪律评分：

### 下一美股交易时段计划框架

| 情景 | 触发条件 | 操作倾向 | 风险备注 |
|------|----------|----------|----------|
EOF
            ;;
    esac
}

format_template_en() {
    case "$TASK_TYPE" in
        hk_plan)
            cat <<'EOF'
**Data source: Futu OpenD HK snapshot | Generated: YYYY-MM-DD HH:mm HKT**

---

### Account Snapshot and HK Risk Constraints

| Item | Value | Notes |
|------|-------|-------|

### Current HK Positions

| Symbol | Name | Quantity | Diluted Cost | Price | Market Value | P/L |
|--------|------|----------|------|-------|--------------|----------------|

### HK Pre-Market Setup

### Today's HK Plan

| Scenario | Trigger | Action Bias | Purpose |
|----------|---------|-------------|---------|

### HK Options Plan

| Contract | Role | Trigger | Action Bias |
|----------|------|---------|-------------|

### HK Watchlist Candidates

| Symbol | Name | Why Watch | Trigger Meaning |
|--------|------|-----------|-----------------|

### Risk Boundaries

### Do Not Do Today

### Pre-Close Checklist
EOF
            ;;
        hk_review)
            cat <<'EOF'
**Data source: Futu OpenD HK close snapshot | Generated: YYYY-MM-DD HH:mm HKT**

---

### HK Account and Position Changes

| Item | Plan Baseline | Close Snapshot | Change |
|------|---------------|----------------|--------|

### HK Fills and Orders

| Symbol | Side | Quantity | Price | Status | Plan-Compliant |
|--------|------|----------|-------|--------|----------------|

### Plan vs Actual

| Planned Scenario | Trigger | Actual | Triggered | Actual Action | Conclusion |
|------------------|---------|--------|-----------|---------------|------------|

### HK Position Performance

### Discipline Review

### Next HK Session Plan Framework

### Tomorrow's HK Watchlist Candidates

| Symbol | Name | Continue Watching | Keep/Remove |
|--------|------|-------------------|-------------|
EOF
            ;;
        us_plan)
            cat <<'EOF'
**Data source: Futu OpenD quotes + IBKR app account data | Generated: YYYY-MM-DD HH:mm HKT**

---

### Account Snapshot and US Risk Constraints

| Item | Value | Notes |
|------|-------|-------|

### Current US Positions

| Symbol | Name | Quantity | Diluted Cost | Pre-Market/Snapshot Price | Market Value | P/L |
|--------|------|----------|------|---------------------------|--------------|----------------|

### US Pre-Market Setup

### US Session Plan

| Scenario | Trigger | Action Bias | Purpose |
|----------|---------|-------------|---------|

### US Watchlist Candidates

| Symbol | Name | Why Watch | Trigger Meaning |
|--------|------|-----------|-----------------|

### Risk Boundaries

### Do Not Do This Session
EOF
            ;;
        us_review)
            cat <<'EOF'
**Data source: Futu OpenD quotes + IBKR app account data | Generated: YYYY-MM-DD HH:mm HKT**

---

### US Account and Position Changes

| Item | Plan Baseline | Post-Close Snapshot | Change |
|------|---------------|---------------------|--------|

### US Fills and Orders

| Symbol | Side | Quantity | Price | Status | Plan-Compliant |
|--------|------|----------|-------|--------|----------------|

### Plan vs Actual

| Planned Scenario | Trigger | Actual Move | Triggered | Actual Action | Conclusion |
|------------------|---------|-------------|-----------|---------------|------------|

### US Position Performance

### Discipline Review

### Next US Session Plan Framework
EOF
            ;;
    esac
}

_build_prompt_zh() {
    local body market_scope format_template
    market_scope=$(market_scope_zh)
    format_template=$(format_template_zh)
    case "$TASK_TYPE" in
        hk_plan)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成港股交易计划。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily 笔记，生成 ${NOTE_DATE} 的港股交易计划，中文输出。

要求：先读取并遵守下面的交易规则与长期策略。包含账户快照、主要风险敞口、当前持仓、工作订单、标的计划、期权计划、推荐关注清单、风险边界和今日不做什么。建议必须是条件式触发，不要给无条件预测，不要提出下单、改单或撤单动作，只做决策支持和日志内容。中文输出。

${market_scope}

固定输出模板：
必须严格使用下列 Markdown 结构、标题和表格列。模板中的日期、时间和标的占位要替换为实际数据；没有数据的表格也要保留表头，并在表格下用一句话说明“无对应数据”。

${format_template}

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

交易规则与长期策略：
${RULES_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成港股交易总结。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily/${NOTE_DATE}.md，生成 ${NOTE_DATE} 的港股交易总结，中文输出。

要求：先读取并遵守下面的交易规则与长期策略。纪律评分必须同时比较 Daily 计划和长期策略；如果后续用户规则更新覆盖了早盘计划，应说明覆盖关系，而不是直接判为纪律失败。包含账户和持仓变化、成交与计划对照、纪律评分、错过机会、风险漂移、下一交易时段触发价。只做复盘和日志内容，不提出自动下单、改单或撤单。中文输出。

${market_scope}

固定输出模板：
必须严格使用下列 Markdown 结构、标题和表格列。模板中的日期、时间和标的占位要替换为实际数据；没有数据的表格也要保留表头，并在表格下用一句话说明“无对应数据”。

${format_template}

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

交易规则与长期策略：
${RULES_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成美股交易计划。

任务：基于下面的 Futu OpenD 行情、动态调用的 IBKR 插件账户数据以及已有 Daily 笔记，生成 ${NOTE_DATE} 的美股交易计划，中文输出。

计划阶段：${US_PLAN_PHASE_LABEL_ZH}
阶段要求：${US_PLAN_PHASE_GUIDANCE_ZH}

要求：先读取并遵守下面的交易规则与长期策略。注意美股交易时段从本地 21:30 到次日 04:00（夏令时）。包含账户快照、风险敞口、当前持仓、工作订单、标的计划、推荐关注清单、风险边界和今日不做什么。建议必须是条件式触发，只做决策支持和日志内容。中文输出。

${market_scope}

固定输出模板：
必须严格使用下列 Markdown 结构、标题和表格列。模板中的日期、时间和标的占位要替换为实际数据；没有数据的表格也要保留表头，并在表格下用一句话说明“无对应数据”。

${format_template}

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

IBKR 插件/备用入口状态：
${IBKR_CONTEXT}

交易规则与长期策略：
${RULES_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成美股交易总结。

任务：基于下面的 Futu OpenD 行情、动态调用的 IBKR 插件账户数据以及已有 Daily/${NOTE_DATE}.md，生成美股交易总结，写入 ${NOTE_DATE}.md 对应的美股交易日期，中文输出。

要求：先读取并遵守下面的交易规则与长期策略。纪律评分必须同时比较 Daily 计划和长期策略；如果后续用户规则更新覆盖了早盘计划，应说明覆盖关系，而不是直接判为纪律失败。包含账户和持仓变化、成交与计划对照、纪律评分、错过机会、风险漂移、下一交易时段触发价。只做复盘和日志内容，不提出自动下单、改单或撤单。中文输出。

${market_scope}

固定输出模板：
必须严格使用下列 Markdown 结构、标题和表格列。模板中的日期、时间和标的占位要替换为实际数据；没有数据的表格也要保留表头，并在表格下用一句话说明“无对应数据”。

${format_template}

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

IBKR 插件/备用入口状态：
${IBKR_CONTEXT}

交易规则与长期策略：
${RULES_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
    esac
    printf '%s\n\n%s' "$body" "$PROMPT_SUFFIX"
}

_build_prompt_en() {
    local body market_scope format_template
    market_scope=$(market_scope_en)
    format_template=$(format_template_en)
    case "$TASK_TYPE" in
        hk_plan)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate HK trading plan.

Task: generate the HK trading plan for ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: read and apply the standing trading rules and strategy mandates below first. Include account snapshot, major risk exposures, current positions, working orders, instrument plan, option plan, watchlist, risk boundaries, and what not to do. Use conditional triggers, not unconditional predictions. Do not suggest automated order entry, modification, or cancellation. Output in English.

${market_scope}

Fixed output template:
Use the following Markdown structure, headings, and table columns exactly. Replace date, time, and symbol placeholders with actual data. Keep table headers even when no rows are available, then add one sentence explaining that no matching data exists.

${format_template}

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Standing trading rules and strategy mandates:
${RULES_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate HK trading review.

Task: generate the HK trading review for ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: read and apply the standing trading rules and strategy mandates below first. Discipline assessment must compare both the Daily plan and standing rules; if a newer user-authored rule supersedes the morning plan, explain that relationship instead of scoring it as an unexplained discipline failure. Include account and position changes, fills versus plan, discipline assessment, missed opportunities, risk drift, and next-session triggers. Do not suggest automated order entry, modification, or cancellation. Output in English.

${market_scope}

Fixed output template:
Use the following Markdown structure, headings, and table columns exactly. Replace date, time, and symbol placeholders with actual data. Keep table headers even when no rows are available, then add one sentence explaining that no matching data exists.

${format_template}

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Standing trading rules and strategy mandates:
${RULES_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate US trading plan.

Task: generate the US trading plan for ${NOTE_DATE} from the supplied Futu OpenD quotes, dynamically retrieved IBKR app account data, and the existing Daily note below.

Plan phase: ${US_PLAN_PHASE_LABEL_EN}
Phase requirements: ${US_PLAN_PHASE_GUIDANCE_EN}

Requirements: read and apply the standing trading rules and strategy mandates below first. Note US session runs 21:30–04:00 local (daylight saving). Include account snapshot, risk exposures, current positions, working orders, instrument plan, watchlist, risk boundaries, and what not to do. Use conditional triggers and output in English.

${market_scope}

Fixed output template:
Use the following Markdown structure, headings, and table columns exactly. Replace date, time, and symbol placeholders with actual data. Keep table headers even when no rows are available, then add one sentence explaining that no matching data exists.

${format_template}

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

IBKR app/fallback source status:
${IBKR_CONTEXT}

Standing trading rules and strategy mandates:
${RULES_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate US trading review.

Task: generate the US trading review for the US session date ${NOTE_DATE} from the supplied Futu OpenD quotes, dynamically retrieved IBKR app account data, and the existing Daily note below.

Requirements: read and apply the standing trading rules and strategy mandates below first. Include account and position changes, fills versus plan, discipline assessment, missed opportunities, risk drift, and next-session triggers. Compare decisions against the previous evening US plan and standing rules. Output in English.

${market_scope}

Fixed output template:
Use the following Markdown structure, headings, and table columns exactly. Replace date, time, and symbol placeholders with actual data. Keep table headers even when no rows are available, then add one sentence explaining that no matching data exists.

${format_template}

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

IBKR app/fallback source status:
${IBKR_CONTEXT}

Standing trading rules and strategy mandates:
${RULES_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
    esac
    printf '%s\n\n%s' "$body" "$PROMPT_SUFFIX"
}

PROMPT=$(build_prompt)
echo "Prompt built (${#PROMPT} characters; redacted from logs)."

# ── Run configured AI CLI text-only ─────────────────────────────────
run_with_timeout() {
    if [ "$AI_TIMEOUT_SECONDS" -eq 0 ]; then
        "$@"
        return
    fi

    python3 -c 'import subprocess, sys
timeout = int(sys.argv[1])
cmd = sys.argv[2:]
try:
    raise SystemExit(subprocess.run(cmd, timeout=timeout).returncode)
except subprocess.TimeoutExpired:
    print(f"ERROR: command timed out after {timeout}s: {cmd[0]}", file=sys.stderr)
    raise SystemExit(124)
' "$AI_TIMEOUT_SECONDS" "$@"
}

print_cli_failure_excerpt() {
    local path="$1"
    python3 - "$path" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit

lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
for index, line in enumerate(lines[:120], start=1):
    print(line)
    if line.strip() == "user":
        print("[prompt body redacted by runner]")
        break
if len(lines) > 120:
    print("[output truncated by runner]")
PY
}

# 从 CLI 的失败输出里提取一行人类可读的原因，供通知使用。
# 不打印任何 prompt 内容；只取结构化的错误字段或 ERROR 行。
capture_failure_reason() {
    local path="$1"
    AI_LAST_FAILURE_REASON=$(python3 - "$path" <<'PY'
import json, re, sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit

text = path.read_text(encoding="utf-8", errors="replace")

# Claude: --output-format json，错误在 result 字段
brace = text.find("{")
if brace >= 0:
    try:
        data = json.loads(text[brace:])
        if isinstance(data, dict) and data.get("is_error"):
            reason = str(data.get("result") or data.get("terminal_reason") or "").strip()
            if reason:
                print(reason[:200]); raise SystemExit
    except (json.JSONDecodeError, ValueError):
        pass

# Codex 及其他：取第一条不含 prompt 的 ERROR 行
for line in text.splitlines():
    line = line.strip()
    if re.match(r"^(ERROR|error):", line) and "prompt" not in line.lower():
        print(re.sub(r"^\w+:\s*", "", line)[:200]); raise SystemExit
PY
)
}

# AI 降级告警。level=fallback（主 CLI 失败、备用接管）或 degraded（两级都失败）。
# 主 CLI 失败就通知，是为了避免像 2026-09-14 那次：Claude 静默失败 4 天，
# 全靠 Codex 兜底，直到 Codex 额度耗尽才被发现。
notify_degraded() {
    local level="$1" summary="$2" reason="${3:-}"
    local stamp; stamp=$(date "+%Y-%m-%d %H:%M:%S %Z")
    local title subtitle

    case "$level" in
        fallback) title="Folio Scribe：AI 已降级" ;;
        degraded) title="Folio Scribe：AI 全部失败" ;;
        *)        title="Folio Scribe：AI 异常" ;;
    esac
    subtitle="${TASK_TYPE:-task} · ${NOTE_DATE:-}"

    # 落盘：即使通知被忽略也留痕，可 grep、可被巡检脚本读取
    mkdir -p "$(dirname "$NOTIFY_FILE")" 2>/dev/null || true
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$stamp" "$level" "${TASK_TYPE:-?}" "$summary" "${reason:-}" >> "$NOTIFY_FILE" 2>/dev/null || true

    echo "NOTIFY[$level] $summary${reason:+ — $reason}"

    [ "$NOTIFY" = "1" ] || return 0
    command -v osascript >/dev/null 2>&1 || return 0

    # osascript 字符串里的反斜杠和双引号必须转义，否则通知会静默丢失
    local body; body="$summary${reason:+ — $reason}"
    body=${body//\\/\\\\}; body=${body//\"/\\\"}
    subtitle=${subtitle//\\/\\\\}; subtitle=${subtitle//\"/\\\"}
    osascript -e "display notification \"${body}\" with title \"${title}\" subtitle \"${subtitle}\"" >/dev/null 2>&1 || true
}

write_deterministic_fallback_section() {
    if [ "$DETERMINISTIC_FALLBACK" != "1" ]; then
        return 1
    fi

    echo "WARNING: AI CLIs failed; writing deterministic data-only fallback section."
    python3 - \
        "$TASK_TYPE" \
        "$NOTE_DATE" \
        "$MARKET_LABEL_ZH" \
        "$MARKET_LABEL_EN" \
        "$MARKET_PREFIX" \
        "$SNAPSHOT_JSON_FILE" \
        "$IBKR_SNAPSHOT_JSON_FILE" \
        "$AI_CONTENT_FILE" \
        "$LANG_PREF" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_type, note_date, market_zh, market_en, market_prefix, futu_path, ibkr_path, out_path, lang = sys.argv[1:10]
is_zh = lang != "en"
market_prefix = market_prefix.upper()

def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {
            "captured_at": "",
            "account": None,
            "accounts": {},
            "positions": [],
            "orders": [],
            "fills": [],
            "quotes": {},
            "raw": {"trading_status": "unavailable", "trading_error": str(exc)},
        }

futu = load_json(futu_path)
ibkr = load_json(ibkr_path)

def value(item, key=None, default="-"):
    if key is not None:
        item = item.get(key) if isinstance(item, dict) else None
    if item is None or item == "":
        return default
    return str(item)

def symbol_of(item):
    return str(item.get("symbol") or "").upper()

def in_market(item):
    return symbol_of(item).startswith(market_prefix)

def table(headers, rows):
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    if rows:
        output.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    else:
        output.append("| - | " + " | ".join(["-"] * (len(headers) - 1)) + " |")
    return "\n".join(output)

def account_rows(source, payload):
    rows = []
    account = payload.get("account") or {}
    if account:
        rows.append([
            source,
            value(account, "total_assets"),
            value(account, "cash"),
            value(account, "buying_power"),
            value(account, "leverage"),
            value(account, "currency"),
        ])
    accounts = payload.get("accounts") or {}
    for account_alias, item in accounts.items():
        rows.append([
            f"{source}:{account_alias}",
            value(item, "total_assets"),
            value(item, "cash"),
            value(item, "buying_power"),
            value(item, "leverage"),
            value(item, "currency"),
        ])
    return rows

def position_rows(source, payload):
    rows = []
    for item in payload.get("positions") or []:
        if not in_market(item):
            continue
        rows.append([
            source,
            value(item, "symbol"),
            value(item, "name"),
            value(item, "quantity"),
            value(item, "cost"),
            value(item, "market_value"),
            value(item, "unrealized_pnl"),
        ])
    return rows

def order_rows(source, payload):
    rows = []
    for item in payload.get("orders") or []:
        if not in_market(item):
            continue
        rows.append([
            source,
            value(item, "symbol"),
            value(item, "side"),
            value(item, "quantity"),
            value(item, "price"),
            value(item, "status"),
            value(item, "filled_quantity"),
        ])
    return rows

def fill_rows(source, payload):
    rows = []
    for item in payload.get("fills") or []:
        if not in_market(item):
            continue
        rows.append([
            source,
            value(item, "symbol"),
            value(item, "side"),
            value(item, "quantity"),
            value(item, "price"),
            value(item, "filled_at"),
        ])
    return rows

def quote_rows(payload, limit=8):
    rows = []
    held = {symbol_of(item) for item in payload.get("positions") or [] if in_market(item)}
    for symbol, quote in (payload.get("quotes") or {}).items():
        symbol = str(symbol).upper()
        if not symbol.startswith(market_prefix) or symbol in held:
            continue
        rows.append([
            symbol,
            value(quote, "name"),
            value(quote, "price"),
            value(quote, "quote_time"),
        ])
        if len(rows) >= limit:
            break
    return rows

generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
is_plan = task_type.endswith("_plan")
title = "自动保底计划" if is_plan else "自动保底总结"
if not is_zh:
    title = "Data-only fallback plan" if is_plan else "Data-only fallback review"

account = account_rows("Futu", futu)
if market_en == "US":
    account.extend(account_rows("IBKR", ibkr))

positions = position_rows("Futu", futu)
if market_en == "US":
    positions.extend(position_rows("IBKR", ibkr))

orders = order_rows("Futu", futu)
fills = fill_rows("Futu", futu)
if market_en == "US":
    orders.extend(order_rows("IBKR", ibkr))
    fills.extend(fill_rows("IBKR", ibkr))

ibkr_status = value(ibkr.get("raw") or {}, "trading_status")
ibkr_error = value(ibkr.get("raw") or {}, "trading_error")

if is_zh:
    lines = [
        f"**数据源：Futu OpenD 结构化快照" + (" + IBKR 账户数据入口" if market_en == "US" else "") + f" | 生成时间：{generated_at} 本地时间**",
        "",
        "> **生成状态**：AI CLI 未返回可用正文，本节由 runner 自动写入，仅用于数据留痕和人工复核；不要把本节视为新增交易建议。",
        "",
        f"### {market_zh}账户快照",
        "",
        table(["来源", "总资产", "现金", "购买力", "杠杆", "币种"], account),
        "",
    ]
    if market_en == "US":
        lines.extend([
            f"> IBKR 状态：{ibkr_status}" + (f"；错误：{ibkr_error}" if ibkr_status != "ok" else ""),
            "",
        ])
    lines.extend([
        f"### 当前{market_zh}持仓",
        "",
        table(["来源", "标的", "名称", "数量", "成本口径", "市值", "盈亏"], positions),
        "",
        "### 工作订单",
        "",
        table(["来源", "标的", "方向", "数量", "价格", "状态", "已成交"], orders),
        "",
        "### 今日成交",
        "",
        table(["来源", "标的", "方向", "数量", "价格", "时间"], fills),
        "",
        "### 推荐关注清单",
        "",
        "AI 未完成筛选；以下仅列出快照中的非持仓候选行情，需人工复核后再使用。",
        "",
        table(["标的", "名称", "最新价", "时间"], quote_rows(futu)),
        "",
        f"### {title}",
        "",
    ])
    if is_plan:
        lines.extend([
            "- 新增交易：暂停，等待 AI 或人工复核后再执行。",
            "- 已有持仓：只按既有规则和已记录触发条件处理。",
            "- 风险控制：不扩大未被当前计划覆盖的敞口，不临时追加复杂期权结构。",
        ])
    else:
        lines.extend([
            "- 本节未完成 AI 复盘，不给纪律评分。",
            "- 请用上方订单和成交表核对实际执行，再补充计划符合度、纪律问题和下一交易日触发条件。",
            "- 如有成交但快照未显示，请优先以券商成交记录为准补记。",
        ])
else:
    lines = [
        f"**Data source: Futu OpenD structured snapshot" + (" + IBKR account-data source" if market_en == "US" else "") + f" | Generated: {generated_at} local time**",
        "",
        "> **Generation status**: AI CLI did not return usable content. The runner wrote this data-only fallback for auditability; do not treat it as new trading advice.",
        "",
        f"### {market_en} Account Snapshot",
        "",
        table(["Source", "Assets", "Cash", "Buying power", "Leverage", "Currency"], account),
        "",
        f"### Current {market_en} Positions",
        "",
        table(["Source", "Symbol", "Name", "Qty", "Cost basis", "Market value", "P/L"], positions),
        "",
        "### Working Orders",
        "",
        table(["Source", "Symbol", "Side", "Qty", "Price", "Status", "Filled"], orders),
        "",
        "### Fills",
        "",
        table(["Source", "Symbol", "Side", "Qty", "Price", "Time"], fills),
        "",
        f"### {title}",
        "",
        "- No new action should be taken from this fallback section.",
        "- Re-run with a healthy AI CLI or complete the review manually from the broker records.",
    ]

Path(out_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY
}

configured_codex_model() {
    if [ -n "${FOLIO_SCRIBE_CODEX_MODEL:-}" ]; then
        printf '%s' "$FOLIO_SCRIBE_CODEX_MODEL"
        return 0
    fi
    if [ -r "$CODEX_CONFIG" ]; then
        python3 -c 'import re, sys
path = sys.argv[1]
try:
    import tomllib
    with open(path, "rb") as handle:
        print(tomllib.load(handle).get("model", ""))
except Exception:
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    match = re.search(r"(?m)^model\s*=\s*[\"\x27]?([^\"\x27#\n]+)", text)
    print(match.group(1).strip() if match else "")
' "$CODEX_CONFIG" 2>/dev/null || true
    fi
}

configured_claude_model() {
    if [ -n "${FOLIO_SCRIBE_CLAUDE_MODEL:-}" ]; then
        printf '%s' "$FOLIO_SCRIBE_CLAUDE_MODEL"
        return 0
    fi
    if [ -r "$CLAUDE_SETTINGS" ]; then
        python3 -c 'import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle).get("model", ""))
' "$CLAUDE_SETTINGS" 2>/dev/null || true
    fi
}

resolved_fallback_cli() {
    case "$AI_FALLBACK_CLI" in
        ""|none)
            printf ''
            ;;
        auto)
            if [ "$MARKET_LABEL_EN" = "US" ] \
                && uses_ibkr_plugin \
                && [ "$AI_CLI" = "codex" ]; then
                # Claude cannot access the connected Codex app. A data-only
                # fallback is safer than writing a false empty IBKR account.
                printf ''
            elif [ "$AI_CLI" = "codex" ]; then
                printf 'claude'
            else
                printf 'codex'
            fi
            ;;
        claude|codex)
            if [ "$AI_FALLBACK_CLI" != "$AI_CLI" ]; then
                printf '%s' "$AI_FALLBACK_CLI"
            fi
            ;;
    esac
}

run_claude_cli() {
    echo "Calling Claude text-only (tools disabled) ..."

    local claude_model claude_model_explicit
    claude_model_explicit=0
    if [ "$AI_CLI" = "claude" ]; then
        claude_model="$AI_MODEL"
        claude_model_explicit="$AI_MODEL_EXPLICIT"
    else
        claude_model=$(configured_claude_model)
        if [ -n "${FOLIO_SCRIBE_CLAUDE_MODEL:-}" ]; then
            claude_model_explicit=1
        fi
    fi

    local args=(
        -p "$PROMPT"
        --max-turns "$MAX_TURNS"
        --no-session-persistence
        --output-format json
        --tools ""
    )
    if [ -n "$MAX_BUDGET" ]; then
        args+=(--max-budget-usd "$MAX_BUDGET")
    fi
    case "$CLAUDE_BARE" in
        1|true|yes|on)
            args+=(--bare)
            echo "Claude Code bare mode: enabled"
            ;;
    esac
    # 全局 settings 里的 env.CLAUDE_CODE_EFFORT_LEVEL 会压过 --effort 参数，
    # 所以复制一份 settings、只改这个变量，再作为命令行 settings（优先于用户 settings）传入。
    local claude_settings_file="$SENSITIVE_TMP_DIR/claude-settings.json"
    python3 - "$CLAUDE_SETTINGS" "$CLAUDE_EFFORT" "$claude_settings_file" <<'PY'
import json
import sys
from pathlib import Path

source, effort, target = sys.argv[1:4]
try:
    settings = json.loads(Path(source).read_text(encoding="utf-8"))
except (OSError, ValueError):
    settings = {}
if not isinstance(settings, dict):
    settings = {}
env = settings.get("env") if isinstance(settings.get("env"), dict) else {}
env["CLAUDE_CODE_EFFORT_LEVEL"] = effort
settings["env"] = env
Path(target).write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
PY
    args+=(--settings "$claude_settings_file")
    echo "Claude Code settings: $CLAUDE_SETTINGS (effort: $CLAUDE_EFFORT)"
    if [ -n "$claude_model" ] && [ "$claude_model_explicit" -eq 1 ]; then
        args+=(--model "$claude_model")
        echo "Claude Code model: $claude_model"
    elif [ -n "$claude_model" ]; then
        echo "Claude Code configured model: $claude_model"
    fi
    if [ -n "$claude_model" ]; then
        AI_MODEL_LABEL="claude:$claude_model"
    else
        AI_MODEL_LABEL="claude"
    fi
    if [ -n "$CLAUDE_FALLBACK_MODEL" ]; then
        args+=(--fallback-model "$CLAUDE_FALLBACK_MODEL")
        echo "Claude Code fallback model: $CLAUDE_FALLBACK_MODEL"
    fi

    local claude_json model_label_file
    claude_json=$(mktemp "$SENSITIVE_TMP_DIR/claude-json.XXXXXX")
    model_label_file=$(mktemp "$SENSITIVE_TMP_DIR/claude-model.XXXXXX")

    if run_with_timeout "$CLAUDE" "${args[@]}" > "$claude_json"; then
        :
    else
        local status=$?
        echo "ERROR: Claude CLI failed (exit $status)."
        capture_failure_reason "$claude_json"
        # 超时提示走 stderr，不在 claude_json 里；补上，免得通知里原因为空
        if [ -z "$AI_LAST_FAILURE_REASON" ] && [ "$status" -eq 124 ]; then
            AI_LAST_FAILURE_REASON="command timed out after ${AI_TIMEOUT_SECONDS}s: $CLAUDE"
        fi
        if [ -s "$claude_json" ]; then
            echo "Claude output before failure:"
            print_cli_failure_excerpt "$claude_json"
        fi
        return "$status"
    fi

    if python3 - "$claude_json" "$AI_CONTENT_FILE" "$model_label_file" "$AI_MODEL_LABEL" <<'PY'
import json
import sys
from pathlib import Path

json_path, content_path, label_path, fallback_label = sys.argv[1:5]
payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
if payload.get("is_error") is True:
    detail = payload.get("result") or payload.get("error") or "Claude JSON output was marked as an error"
    raise SystemExit(f"ERROR: Claude returned an error result: {detail}")

result = payload.get("result")
if not isinstance(result, str) or not result.strip():
    raise SystemExit("ERROR: Claude JSON output did not contain a non-empty result")

Path(content_path).write_text(result.strip() + "\n", encoding="utf-8")

model_usage = payload.get("modelUsage")
models = []
if isinstance(model_usage, dict):
    # Claude Code may report multiple internal models for one request; keep them all visible.
    models = [str(model) for model in model_usage.keys() if str(model).strip()]

if models:
    label = "claude:" + ",".join(models)
else:
    label = fallback_label or "claude"

Path(label_path).write_text(label, encoding="utf-8")
PY
    then
        :
    else
        echo "ERROR: Claude JSON output could not be used."
        if [ -s "$claude_json" ]; then
            echo "Claude output:"
            print_cli_failure_excerpt "$claude_json"
        fi
        return 1
    fi
    AI_MODEL_LABEL=$(cat "$model_label_file")
    local raw_model_label resolved_model_label
    raw_model_label="$AI_MODEL_LABEL"
    resolved_model_label=$(python3 "$SCRIPT_DIR/resolve_model_label.py" \
        --cli "claude" \
        --label "$AI_MODEL_LABEL" \
        --claude-json "$claude_json" \
        --cc-switch-db "$CC_SWITCH_DB" 2>/dev/null || true)
    if [ -n "$resolved_model_label" ]; then
        AI_MODEL_LABEL="$resolved_model_label"
    fi

    echo "Claude Code usage model: ${raw_model_label#claude:}"
    if [ "$AI_MODEL_LABEL" != "$raw_model_label" ]; then
        echo "Resolved upstream model: $AI_MODEL_LABEL"
    fi
    return 0
}

run_codex_cli() {
    echo "Calling Codex exec text-only (runner controls data and writes) ..."

    local codex_log codex_model codex_model_explicit
    codex_log=$(mktemp "$SENSITIVE_TMP_DIR/codex.XXXXXX")
    codex_model_explicit=0
    if [ "$AI_CLI" = "codex" ]; then
        codex_model="$AI_MODEL"
        codex_model_explicit="$AI_MODEL_EXPLICIT"
    else
        codex_model=$(configured_codex_model)
        if [ -n "${FOLIO_SCRIBE_CODEX_MODEL:-}" ]; then
            codex_model_explicit=1
        fi
    fi
    local args=(
        exec
        --skip-git-repo-check
        --ephemeral
        --sandbox "$CODEX_SANDBOX"
        --color never
        --output-last-message "$AI_CONTENT_FILE"
        --cd "$VAULT"
    )
    local feature
    for feature in $CODEX_DISABLE_FEATURES; do
        args+=(--disable "$feature")
    done
    if [ -n "$CODEX_PROFILE" ]; then
        args+=(--profile "$CODEX_PROFILE")
        echo "Codex profile: $CODEX_PROFILE"
    fi
    if [ -n "$codex_model" ] && [ "$codex_model_explicit" -eq 1 ]; then
        args+=(--model "$codex_model")
        echo "Codex model: $codex_model"
    elif [ -n "$codex_model" ]; then
        echo "Codex configured model: $codex_model"
    fi
    if [ -n "$codex_model" ]; then
        AI_MODEL_LABEL="codex:$codex_model"
    else
        AI_MODEL_LABEL="codex"
    fi
    echo "Codex sandbox: $CODEX_SANDBOX"
    if [ -n "$CODEX_DISABLE_FEATURES" ]; then
        echo "Codex disabled features: $CODEX_DISABLE_FEATURES"
    fi

    if printf '%s' "$PROMPT" | run_with_timeout "$CODEX" "${args[@]}" - > "$codex_log" 2>&1; then
        :
    else
        local status=$?
        echo "ERROR: Codex CLI failed (exit $status)."
        capture_failure_reason "$codex_log"
        if [ -s "$codex_log" ]; then
            echo "Codex output before failure:"
            print_cli_failure_excerpt "$codex_log"
        fi
        return "$status"
    fi

    if [ ! -s "$AI_CONTENT_FILE" ]; then
        echo "ERROR: Codex CLI completed but did not produce a final message."
        if [ -s "$codex_log" ]; then
            echo "Codex output:"
            print_cli_failure_excerpt "$codex_log"
        fi
        return 1
    fi
    return 0
}

run_selected_ai_cli() {
    local cli="$1"
    case "$cli" in
        claude) run_claude_cli ;;
        codex) run_codex_cli ;;
        *) echo "ERROR: Unsupported AI CLI '$cli'"; return 1 ;;
    esac
}

echo "AI CLI: $AI_CLI"
if run_selected_ai_cli "$AI_CLI"; then
    :
else
    primary_status=$?
    FALLBACK_CLI=$(resolved_fallback_cli)
    if [ -n "$FALLBACK_CLI" ]; then
        echo "WARNING: ${AI_CLI} failed; falling back to ${FALLBACK_CLI} CLI for this run."
        notify_degraded fallback "主 CLI ${AI_CLI} 失败，本次由 ${FALLBACK_CLI} 接管" "$AI_LAST_FAILURE_REASON"
        : > "$AI_CONTENT_FILE"
        if run_selected_ai_cli "$FALLBACK_CLI"; then
            :
        else
            fallback_status=$?
            notify_degraded degraded "主备 CLI（${AI_CLI} / ${FALLBACK_CLI}）均失败，笔记只有数据无分析" "$AI_LAST_FAILURE_REASON"
            if write_deterministic_fallback_section; then
                AI_MODEL_LABEL="runner:deterministic-fallback"
            else
                exit "$fallback_status"
            fi
        fi
    else
        notify_degraded degraded "CLI ${AI_CLI} 失败且未配置备用，笔记只有数据无分析" "$AI_LAST_FAILURE_REASON"
        if write_deterministic_fallback_section; then
            AI_MODEL_LABEL="runner:deterministic-fallback"
        else
            exit "$primary_status"
        fi
    fi
fi

if [ ! -s "$AI_CONTENT_FILE" ]; then
    echo "ERROR: AI CLI produced an empty section."
    exit 1
fi

echo "Writing generated section to Daily note ..."
WRITER_ARGS=(
    python3 "$SCRIPT_DIR/write_daily_note.py"
    --vault "$VAULT"
    --date "$NOTE_DATE"
    --section "$NOTE_SECTION"
    --content "$AI_CONTENT_FILE"
)
if [ -n "$CHINESE_FLAG" ]; then
    WRITER_ARGS+=(--chinese)
fi
if [ -n "$AI_MODEL_LABEL" ]; then
    WRITER_ARGS+=(--model "$AI_MODEL_LABEL")
fi
"${WRITER_ARGS[@]}"

if [ -n "$WEB_EXPORT_DIR" ]; then
    echo "Refreshing web journal export ..."
    "$SCRIPT_DIR/sync_tradingweb.sh" \
        --vault "$VAULT" \
        --out "$WEB_EXPORT_DIR" \
        --title "$WEB_TITLE" \
        --deploy "${WEB_DEPLOY:-none}" \
        --quiet
fi

echo ""
echo "=== Done at $(date '+%Y-%m-%d %H:%M:%S') ==="
