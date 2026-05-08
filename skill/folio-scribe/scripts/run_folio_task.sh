#!/usr/bin/env bash
# run_folio_task.sh — Scheduled folio-scribe task runner (Skill path)
#
# Usage:  run_folio_task.sh [hk_plan|hk_review|us_plan|us_review]
#
# Without arguments, auto-detects task type from current time:
#   05:00–08:29  →  us_review   (美股收盘后总结，写入昨日笔记)
#   08:30–12:59  →  hk_plan     (港股开盘前计划)
#   13:00–19:59  →  hk_review   (港股收盘后总结)
#   20:00–04:59  →  us_plan     (美股开盘前计划)
#
# With argument, uses that task type directly (override).
#
# Set FOLIO_SCRIBE_LANG=en for English prompts and note headings (default: zh).
#
# Flow:
#   1. Skip sessions that do not map to an open market day
#   2. Ensure Futu OpenD is running (auto-launch if needed)
#   3. Invoke claude -p with /folio-scribe skill

set -euo pipefail

# ── Configuration (override via environment variables) ───────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/Trading}"
OPEND_APP="${FOLIO_SCRIBE_OPEND_APP:-$HOME/Applications/Futu_OpenD/FutuOpenD.app}"
OPEND_PORT="${FOLIO_SCRIBE_OPEND_PORT:-11111}"
CLAUDE="${FOLIO_SCRIBE_CLAUDE:-$(command -v claude 2>/dev/null || echo /opt/homebrew/bin/claude)}"
LANG_PREF="${FOLIO_SCRIBE_LANG:-zh}"   # zh | en
LOG_DIR="$VAULT/.logs"
MAX_OPEND_WAIT=90
MAX_BUDGET="0.80"
MAX_TURNS=20
CLAUDE_PERMISSION_MODE="${FOLIO_SCRIBE_CLAUDE_PERMISSION_MODE:-acceptEdits}"
ALLOWED_TOOLS="${FOLIO_SCRIBE_ALLOWED_TOOLS:-Read,Write,Bash(python3 *read_futu_snapshot.py*),Bash(python3 *write_daily_note.py*)}"

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

    if   [ "$total" -ge 300  ] && [ "$total" -lt 510  ]; then echo "us_review" # 05:00-08:29
    elif [ "$total" -ge 510  ] && [ "$total" -lt 780  ]; then echo "hk_plan"   # 08:30-12:59
    elif [ "$total" -ge 780  ] && [ "$total" -lt 1200 ]; then echo "hk_review" # 13:00-19:59
    else                                                       echo "us_plan"   # 20:00-04:59
    fi
}

if [ $# -ge 1 ]; then
    TASK_TYPE="$1"
else
    TASK_TYPE=$(detect_task_type)
fi

# Validate
case "$TASK_TYPE" in
    hk_plan|hk_review|us_plan|us_review) ;;
    *) echo "ERROR: Invalid task type '$TASK_TYPE'. Use: hk_plan|hk_review|us_plan|us_review"; exit 1 ;;
esac

# ── Logging ──────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/folio-$(date +%Y%m%d)-${TASK_TYPE}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo ""
echo "================================================================"
echo "  $(date '+%Y-%m-%d %H:%M:%S') | folio-scribe | $TASK_TYPE"
echo "================================================================"

# ── Session-aware weekend guard ──────────────────────────────────────
DOW=$(date +%u)   # 1=Mon … 7=Sun
case "$TASK_TYPE" in
    us_review)
        # In Asia time zones, the US Friday close review runs on local Saturday
        # morning. Local Monday morning maps to a Sunday US session, so skip it.
        if [ "$DOW" -eq 7 ] || [ "$DOW" -eq 1 ]; then
            echo "No completed US regular session for local day $DOW, skipping."
            exit 0
        fi
        ;;
    *)
        if [ "$DOW" -gt 5 ]; then
            echo "Weekend (day $DOW), skipping."
            exit 0
        fi
        ;;
esac

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

# ── Determine note date ──────────────────────────────────────────────
case "$TASK_TYPE" in
    us_review)
        # 06:45 AM review covers the US session that started the previous evening
        NOTE_DATE=$(date -v-1d +%Y-%m-%d)
        ;;
    *)
        NOTE_DATE=$(date +%Y-%m-%d)
        ;;
esac
echo "Note date: $NOTE_DATE"

case "$TASK_TYPE" in
    hk_plan)   NOTE_SECTION="$SEC_HK_PLAN" ;;
    hk_review) NOTE_SECTION="$SEC_HK_REVIEW" ;;
    us_plan)   NOTE_SECTION="$SEC_US_PLAN" ;;
    us_review) NOTE_SECTION="$SEC_US_REVIEW" ;;
esac

SNAPSHOT_CMD="python3 \"$SCRIPT_DIR/read_futu_snapshot.py\""
WRITER_CMD="python3 \"$SCRIPT_DIR/write_daily_note.py\" --vault \"$VAULT\" --date \"$NOTE_DATE\" --section \"$NOTE_SECTION\""
if [ -n "$CHINESE_FLAG" ]; then
    WRITER_CMD="$WRITER_CMD $CHINESE_FLAG"
fi

# ── Common prompt suffix ─────────────────────────────────────────────
if [ "$LANG_PREF" = "en" ]; then
    PROMPT_SUFFIX="Additional requirement: after writing, update the frontmatter model field to your current model name (e.g. claude-opus-4-0-20250514). If the frontmatter contains total_assets, daily_pnl, leverage, or any per-position quantity fields (e.g. xiaomi_shares, qs_shares), remove them. Keep only date, type, tags, model, plan_score, discipline_score."
else
    PROMPT_SUFFIX="附加要求：写入完成后，更新笔记 frontmatter 中的 model 字段为你当前使用的模型名称（如 claude-opus-4-0-20250514）。如果 frontmatter 中存在 total_assets、daily_pnl、leverage 或任何持仓数量字段（如 xiaomi_shares、qs_shares），请删除这些字段，只保留 date、type、tags、model、plan_score、discipline_score。"
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

_build_prompt_zh() {
    local body
    case "$TASK_TYPE" in
        hk_plan)
            body=$(cat <<EOF
/folio-scribe 定时任务：生成港股交易计划。

执行步骤：
1. 用 Futu OpenD snapshot 读取当前持仓和行情（先不带 symbols 跑一次拿到持仓列表，再带 symbols 跑一次拿完整行情）。命令入口：${SNAPSHOT_CMD}
2. 读取今天已有的 Daily 笔记（如果有的话）
3. 生成 ${NOTE_DATE} 的港股交易计划，中文输出
4. 将正文写入临时 Markdown 文件，然后运行：${WRITER_CMD} --content <临时文件>

要求：内容遵循 SKILL.md 的 Trading Plan Requirements，中文输出。
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
/folio-scribe 定时任务：生成港股交易总结。

执行步骤：
1. 用 Futu OpenD snapshot 读取当前持仓、成交和盈亏数据。命令入口：${SNAPSHOT_CMD}
2. 读取今天的 Daily/${NOTE_DATE}.md，获取港股计划作为对比基准
3. 生成 ${NOTE_DATE} 的港股交易总结，中文输出
4. 将正文写入临时 Markdown 文件，然后运行：${WRITER_CMD} --content <临时文件>

要求：内容遵循 SKILL.md 的 Trading Review Requirements，逐条对照今天的计划评估执行纪律，中文输出。
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
/folio-scribe 定时任务：生成美股交易计划。

执行步骤：
1. 用 Futu OpenD snapshot 读取美股持仓和行情数据。命令入口：${SNAPSHOT_CMD}
2. 读取今天的 Daily/${NOTE_DATE}.md，参考港股部分的情绪和资金面
3. 生成 ${NOTE_DATE} 的美股交易计划，中文输出
4. 将正文写入临时 Markdown 文件，然后运行：${WRITER_CMD} --content <临时文件>

要求：注意美股交易时段从本地 21:30 到次日 04:00（夏令时）。内容遵循 SKILL.md 的 Trading Plan Requirements，中文输出。
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
/folio-scribe 定时任务：生成美股交易总结。

执行步骤：
1. 用 Futu OpenD snapshot 读取美股持仓、成交和盈亏数据。命令入口：${SNAPSHOT_CMD}
2. 读取 Daily/${NOTE_DATE}.md（昨晚的美股计划所在笔记），获取美股计划作为对比基准
3. 生成美股交易总结，写入 ${NOTE_DATE}.md（对应美股交易日期，不是今天本地日期），中文输出
4. 将正文写入临时 Markdown 文件，然后运行：${WRITER_CMD} --content <临时文件>

要求：内容遵循 SKILL.md 的 Trading Review Requirements，逐条对照昨晚的美股计划评估执行纪律，中文输出。
EOF
            )
            ;;
    esac
    printf '%s\n\n%s' "$body" "$PROMPT_SUFFIX"
}

_build_prompt_en() {
    local body
    case "$TASK_TYPE" in
        hk_plan)
            body=$(cat <<EOF
/folio-scribe Scheduled task: generate HK trading plan.

Steps:
1. Read current positions and quotes via Futu OpenD snapshot (run once without symbols for positions, then with symbols for full quotes). Command entry: ${SNAPSHOT_CMD}
2. Read the current existing Daily note (if any)
3. Generate the HK trading plan for ${NOTE_DATE}
4. Write the body to a temporary Markdown file, then run: ${WRITER_CMD} --content <temp-file>

Requirements: follow SKILL.md Trading Plan Requirements. Output in English.
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
/folio-scribe Scheduled task: generate HK trading review.

Steps:
1. Read current positions, fills, and P/L via Futu OpenD snapshot. Command entry: ${SNAPSHOT_CMD}
2. Read the current Daily/${NOTE_DATE}.md and use the HK plan as the baseline
3. Generate the HK trading review for ${NOTE_DATE}
4. Write the body to a temporary Markdown file, then run: ${WRITER_CMD} --content <temp-file>

Requirements: follow SKILL.md Trading Review Requirements. Compare each decision against the current plan. Output in English.
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
/folio-scribe Scheduled task: generate US trading plan.

Steps:
1. Read US positions and quotes via Futu OpenD snapshot. Command entry: ${SNAPSHOT_CMD}
2. Read the current Daily/${NOTE_DATE}.md for HK session context
3. Generate the US trading plan for ${NOTE_DATE}
4. Write the body to a temporary Markdown file, then run: ${WRITER_CMD} --content <temp-file>

Requirements: note US session runs 21:30–04:00 local (daylight saving). Follow SKILL.md Trading Plan Requirements. Output in English.
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
/folio-scribe Scheduled task: generate US trading review.

Steps:
1. Read US positions, fills, and P/L via Futu OpenD snapshot. Command entry: ${SNAPSHOT_CMD}
2. Read Daily/${NOTE_DATE}.md (the previous evening US plan) as the baseline
3. Generate US trading review, write to ${NOTE_DATE}.md (US session date, not the current local date)
4. Write the body to a temporary Markdown file, then run: ${WRITER_CMD} --content <temp-file>

Requirements: follow SKILL.md Trading Review Requirements. Compare each decision against the previous evening US plan. Output in English.
EOF
            )
            ;;
    esac
    printf '%s\n\n%s' "$body" "$PROMPT_SUFFIX"
}

PROMPT=$(build_prompt)
echo "Prompt:"
echo "$PROMPT"
echo "---"

# ── Run Claude with /folio-scribe skill ──────────────────────────────
echo "Calling Claude with /folio-scribe skill ..."

"$CLAUDE" -p "$PROMPT" \
    --add-dir "$VAULT" \
    --add-dir "$SKILL_DIR" \
    --fallback-model sonnet \
    --max-turns "$MAX_TURNS" \
    --max-budget-usd "$MAX_BUDGET" \
    --no-session-persistence \
    --permission-mode "$CLAUDE_PERMISSION_MODE" \
    --allowed-tools "$ALLOWED_TOOLS" \
    2>&1 || {
    echo "ERROR: Claude CLI failed (exit $?)."
    exit 1
}

echo ""
echo "=== Done at $(date '+%Y-%m-%d %H:%M:%S') ==="
