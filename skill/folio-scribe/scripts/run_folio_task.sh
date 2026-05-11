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
#   3. Read the Futu snapshot directly in this runner
#   4. Invoke the configured AI CLI in text-only mode with inline Folio Scribe instructions
#   5. Write the generated section into the daily note

set -euo pipefail

# ── Configuration (override via environment variables) ───────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/Trading}"
OPEND_APP="${FOLIO_SCRIBE_OPEND_APP:-$HOME/Applications/Futu_OpenD/FutuOpenD.app}"
OPEND_PORT="${FOLIO_SCRIBE_OPEND_PORT:-11111}"
AI_CLI="${FOLIO_SCRIBE_AI_CLI:-claude}"
AI_CLI=$(printf '%s' "$AI_CLI" | tr '[:upper:]' '[:lower:]')
CLAUDE="${FOLIO_SCRIBE_CLAUDE:-$(command -v claude 2>/dev/null || echo /opt/homebrew/bin/claude)}"
CLAUDE_SETTINGS="${FOLIO_SCRIBE_CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
CODEX="${FOLIO_SCRIBE_CODEX:-$(command -v codex 2>/dev/null || echo /opt/homebrew/bin/codex)}"
CODEX_CONFIG="${FOLIO_SCRIBE_CODEX_CONFIG:-$HOME/.codex/config.toml}"
CODEX_PROFILE="${FOLIO_SCRIBE_CODEX_PROFILE:-}"
CODEX_SANDBOX="${FOLIO_SCRIBE_CODEX_SANDBOX:-read-only}"
CODEX_DISABLE_FEATURES="${FOLIO_SCRIBE_CODEX_DISABLE_FEATURES:-plugins apps}"
LANG_PREF="${FOLIO_SCRIBE_LANG:-zh}"   # zh | en
LOG_DIR="$VAULT/.logs"
MAX_OPEND_WAIT=90
MAX_BUDGET="${FOLIO_SCRIBE_MAX_BUDGET_USD:-0.80}"
MAX_TURNS=20
AI_MODEL="${FOLIO_SCRIBE_AI_MODEL:-}"
AI_MODEL_EXPLICIT=0
AI_MODEL_LABEL=""
CLAUDE_FALLBACK_MODEL="${FOLIO_SCRIBE_CLAUDE_FALLBACK_MODEL:-}"

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
            AI_MODEL=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("model", ""))' "$CLAUDE_SETTINGS" 2>/dev/null || true)
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
    text = open(path, encoding="utf-8", errors="replace").read()
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
    raw_file=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-snapshot-raw.XXXXXX")
    python3 "$SCRIPT_DIR/read_futu_snapshot.py" "$@" > "$raw_file"
    extract_snapshot_json "$raw_file" "$json_file"
}

SNAPSHOT_POSITIONS_JSON=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-positions.XXXXXX")
SNAPSHOT_JSON_FILE=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-snapshot.XXXXXX")
AI_CONTENT_FILE=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-content.XXXXXX")

echo "Reading Futu snapshot ..."
read_snapshot_json "$SNAPSHOT_POSITIONS_JSON"

SNAPSHOT_SYMBOLS=()
while IFS= read -r symbol; do
    if [ -n "$symbol" ]; then
        SNAPSHOT_SYMBOLS+=("$symbol")
    fi
done < <(python3 - "$SNAPSHOT_POSITIONS_JSON" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
seen = set()
for position in payload.get("positions", []):
    symbol = position.get("symbol")
    if symbol and symbol not in seen:
        print(symbol)
        seen.add(symbol)
PY
)

if [ "${#SNAPSHOT_SYMBOLS[@]}" -gt 0 ]; then
    echo "Reading quotes for ${#SNAPSHOT_SYMBOLS[@]} position symbols ..."
    read_snapshot_json "$SNAPSHOT_JSON_FILE" "${SNAPSHOT_SYMBOLS[@]}"
else
    cp "$SNAPSHOT_POSITIONS_JSON" "$SNAPSHOT_JSON_FILE"
fi

SNAPSHOT_CONTEXT=$(python3 - "$SNAPSHOT_JSON_FILE" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))

def value(item, key, default="-"):
    current = item.get(key)
    return default if current is None or current == "" else str(current)

lines = []
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
for position in payload.get("positions", []):
    lines.append(
        "- "
        f"{value(position, 'symbol')} {value(position, 'name')} | "
        f"qty={value(position, 'quantity')} | cost={value(position, 'cost')} | "
        f"market_value={value(position, 'market_value')} {value(position, 'currency', '')} | "
        f"unrealized_pnl={value(position, 'unrealized_pnl')} | realized_pnl={value(position, 'realized_pnl')}"
    )

orders = payload.get("orders", [])
lines.append("")
lines.append(f"orders: {len(orders)}")
for order in orders:
    lines.append(
        "- "
        f"{value(order, 'symbol')} {value(order, 'side')} | "
        f"qty={value(order, 'quantity')} | price={value(order, 'price')} | status={value(order, 'status')}"
    )

fills = payload.get("fills", [])
lines.append("")
lines.append(f"fills: {len(fills)}")
for fill in fills:
    lines.append(
        "- "
        f"{value(fill, 'symbol')} {value(fill, 'side')} | "
        f"qty={value(fill, 'quantity')} | price={value(fill, 'price')} | at={value(fill, 'filled_at')}"
    )

quotes = payload.get("quotes", {})
lines.append("")
lines.append("quotes:")
for symbol, quote in quotes.items():
    lines.append(
        "- "
        f"{symbol} | price={value(quote, 'price')} | open={value(quote, 'open')} | "
        f"high={value(quote, 'high')} | low={value(quote, 'low')} | "
        f"prev_close={value(quote, 'previous_close')} | volume={value(quote, 'volume')} | "
        f"turnover={value(quote, 'turnover')}"
    )

print("\n".join(lines))
PY
)
NOTE_PATH="$VAULT/Daily/${NOTE_DATE}.md"
if [ -r "$NOTE_PATH" ]; then
    EXISTING_NOTE=$(python3 - "$NOTE_PATH" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
limit = 12000
if len(text) > limit:
    print(text[:limit])
    print("\n[Existing note truncated by runner.]")
else:
    print(text)
PY
)
else
    EXISTING_NOTE="(No existing daily note at ${NOTE_PATH}.)"
fi

# ── Common prompt suffix ─────────────────────────────────────────────
if [ "$LANG_PREF" = "en" ]; then
    PROMPT_SUFFIX="Output only the Markdown body for the target section. Do not include the second-level section heading, frontmatter, code fences, shell commands, or any tool-use instructions. The runner has already read data and will write the note after your response."
else
    PROMPT_SUFFIX="只输出目标 section 的 Markdown 正文。不要包含二级标题、frontmatter、代码围栏、shell 命令或任何工具调用说明。数据已由 runner 读取，写入也会由 runner 在你回复后完成。"
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
Folio Scribe 定时任务：生成港股交易计划。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily 笔记，生成 ${NOTE_DATE} 的港股交易计划，中文输出。

要求：包含账户快照、主要风险敞口、当前持仓、工作订单、标的计划、期权计划、观察清单、风险边界和今日不做什么。建议必须是条件式触发，不要给无条件预测，不要提出下单、改单或撤单动作，只做决策支持和日志内容。中文输出。

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成港股交易总结。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily/${NOTE_DATE}.md，生成 ${NOTE_DATE} 的港股交易总结，中文输出。

要求：包含账户和持仓变化、成交与计划对照、纪律评分、错过机会、风险漂移、下一交易时段触发价。只做复盘和日志内容，不提出自动下单、改单或撤单。中文输出。

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成美股交易计划。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily 笔记，生成 ${NOTE_DATE} 的美股交易计划，中文输出。

要求：注意美股交易时段从本地 21:30 到次日 04:00（夏令时）。包含账户快照、风险敞口、当前持仓、工作订单、标的计划、观察清单、风险边界和今日不做什么。建议必须是条件式触发，只做决策支持和日志内容。中文输出。

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
Folio Scribe 定时任务：生成美股交易总结。

任务：基于下面的 Futu OpenD JSON 快照和已有 Daily/${NOTE_DATE}.md，生成美股交易总结，写入 ${NOTE_DATE}.md 对应的美股交易日期，中文输出。

要求：包含账户和持仓变化、成交与计划对照、纪律评分、错过机会、风险漂移、下一交易时段触发价。只做复盘和日志内容，不提出自动下单、改单或撤单。中文输出。

Futu OpenD 摘要：
${SNAPSHOT_CONTEXT}

已有 Daily 笔记：
${EXISTING_NOTE}
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
Folio Scribe scheduled task: generate HK trading plan.

Task: generate the HK trading plan for ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: include account snapshot, major risk exposures, current positions, working orders, instrument plan, option plan, watchlist, risk boundaries, and what not to do. Use conditional triggers, not unconditional predictions. Do not suggest automated order entry, modification, or cancellation. Output in English.

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        hk_review)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate HK trading review.

Task: generate the HK trading review for ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: include account and position changes, fills versus plan, discipline assessment, missed opportunities, risk drift, and next-session triggers. Do not suggest automated order entry, modification, or cancellation. Output in English.

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        us_plan)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate US trading plan.

Task: generate the US trading plan for ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: note US session runs 21:30–04:00 local (daylight saving). Include account snapshot, risk exposures, current positions, working orders, instrument plan, watchlist, risk boundaries, and what not to do. Use conditional triggers and output in English.

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
EOF
            )
            ;;
        us_review)
            body=$(cat <<EOF
Folio Scribe scheduled task: generate US trading review.

Task: generate the US trading review for the US session date ${NOTE_DATE} from the Futu OpenD JSON snapshot and existing Daily note below.

Requirements: include account and position changes, fills versus plan, discipline assessment, missed opportunities, risk drift, and next-session triggers. Compare decisions against the previous evening US plan. Output in English.

Futu OpenD summary:
${SNAPSHOT_CONTEXT}

Existing Daily note:
${EXISTING_NOTE}
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

# ── Run configured AI CLI text-only ─────────────────────────────────
run_claude_cli() {
    echo "Calling Claude text-only (tools disabled) ..."

    local args=(
        -p "$PROMPT"
        --bare
        --max-turns "$MAX_TURNS"
        --max-budget-usd "$MAX_BUDGET"
        --no-session-persistence
        --output-format json
        --tools ""
    )
    if [ -r "$CLAUDE_SETTINGS" ]; then
        args+=(--settings "$CLAUDE_SETTINGS")
        echo "Claude Code settings: $CLAUDE_SETTINGS"
    fi
    if [ -n "$AI_MODEL" ] && [ "$AI_MODEL_EXPLICIT" -eq 1 ]; then
        args+=(--model "$AI_MODEL")
        echo "Claude Code model: $AI_MODEL"
    elif [ -n "$AI_MODEL" ]; then
        echo "Claude Code configured model: $AI_MODEL"
    fi
    if [ -n "$CLAUDE_FALLBACK_MODEL" ]; then
        args+=(--fallback-model "$CLAUDE_FALLBACK_MODEL")
        echo "Claude Code fallback model: $CLAUDE_FALLBACK_MODEL"
    fi

    local claude_json model_label_file
    claude_json=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-claude-json.XXXXXX")
    model_label_file=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-claude-model.XXXXXX")

    "$CLAUDE" "${args[@]}" > "$claude_json" || {
        echo "ERROR: Claude CLI failed (exit $?)."
        if [ -s "$claude_json" ]; then
            echo "Claude output before failure:"
            sed -n '1,120p' "$claude_json"
        fi
        exit 1
    }

    python3 - "$claude_json" "$AI_CONTENT_FILE" "$model_label_file" "$AI_MODEL_LABEL" <<'PY'
import json
import sys
from pathlib import Path

json_path, content_path, label_path, fallback_label = sys.argv[1:5]
payload = json.loads(Path(json_path).read_text(encoding="utf-8"))

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
    AI_MODEL_LABEL=$(cat "$model_label_file")
    echo "Claude Code usage model: ${AI_MODEL_LABEL#claude:}"
}

run_codex_cli() {
    echo "Calling Codex exec text-only (runner controls data and writes) ..."

    local codex_log
    codex_log=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-codex.XXXXXX")
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
    if [ -n "$AI_MODEL" ] && [ "$AI_MODEL_EXPLICIT" -eq 1 ]; then
        args+=(--model "$AI_MODEL")
        echo "Codex model: $AI_MODEL"
    elif [ -n "$AI_MODEL" ]; then
        echo "Codex configured model: $AI_MODEL"
    fi
    echo "Codex sandbox: $CODEX_SANDBOX"
    if [ -n "$CODEX_DISABLE_FEATURES" ]; then
        echo "Codex disabled features: $CODEX_DISABLE_FEATURES"
    fi

    printf '%s' "$PROMPT" | "$CODEX" "${args[@]}" - > "$codex_log" 2>&1 || {
        echo "ERROR: Codex CLI failed (exit $?)."
        if [ -s "$codex_log" ]; then
            echo "Codex output before failure:"
            sed -n '1,120p' "$codex_log"
        fi
        exit 1
    }

    if [ ! -s "$AI_CONTENT_FILE" ]; then
        echo "ERROR: Codex CLI completed but did not produce a final message."
        if [ -s "$codex_log" ]; then
            echo "Codex output:"
            sed -n '1,120p' "$codex_log"
        fi
        exit 1
    fi
}

echo "AI CLI: $AI_CLI"
case "$AI_CLI" in
    claude) run_claude_cli ;;
    codex)  run_codex_cli ;;
esac

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

echo ""
echo "=== Done at $(date '+%Y-%m-%d %H:%M:%S') ==="
