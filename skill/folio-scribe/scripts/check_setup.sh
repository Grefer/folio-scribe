#!/usr/bin/env bash
# check_setup.sh — Verify that folio-scribe prerequisites are in place
#
# Usage:  check_setup.sh [--vault PATH]
#
# Checks:
#   1. Python ≥ 3.10 available
#   2. folio-scribe package importable
#   3. Claude CLI installed and on PATH
#   4. Obsidian vault exists with Daily/ directory
#   5. Futu OpenD reachable on expected port
#   6. launchd agents loaded (macOS only)
#   7. write_daily_note.py runnable
#
# Exit code: 0 if all critical checks pass, 1 otherwise.
# Non-critical warnings (e.g. OpenD not running) do not cause failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="${FOLIO_SCRIBE_VAULT:-$HOME/Documents/Trading}"
OPEND_PORT="${FOLIO_SCRIBE_OPEND_PORT:-11111}"

# ── Parse args ──────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --vault) VAULT="$2"; shift 2 ;;
        *)       echo "Unknown option: $1"; exit 1 ;;
    esac
done

PASS=0
WARN=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
warn() { WARN=$((WARN + 1)); echo "  ⚠ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ✗ $1"; }

echo "folio-scribe setup check"
echo "========================"
echo ""

# ── 1. Python ───────────────────────────────────────────────────────
echo "Python:"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        pass "python3 $PY_VER"
    else
        fail "python3 $PY_VER (need ≥ 3.10)"
    fi
else
    fail "python3 not found"
fi

# ── 2. folio-scribe package ─────────────────────────────────────────
echo ""
echo "Package:"
if python3 -c "import folio_scribe" &>/dev/null; then
    pass "folio_scribe importable"
else
    fail "folio_scribe not importable (run: pip install -e .)"
fi

if python3 -c "from folio_scribe.journal.obsidian import write_daily_note" &>/dev/null; then
    pass "journal.obsidian module"
else
    fail "journal.obsidian module not importable"
fi

# ── 3. Claude CLI ───────────────────────────────────────────────────
echo ""
echo "Claude CLI:"
CLAUDE="${FOLIO_SCRIBE_CLAUDE:-$(command -v claude 2>/dev/null || echo "")}"
if [ -n "$CLAUDE" ] && [ -x "$CLAUDE" ]; then
    pass "claude at $CLAUDE"
else
    fail "claude CLI not found (install from https://docs.anthropic.com/en/docs/claude-code)"
fi

# ── 4. Obsidian vault ──────────────────────────────────────────────
echo ""
echo "Vault ($VAULT):"
if [ -d "$VAULT" ]; then
    pass "vault directory exists"
else
    fail "vault directory not found: $VAULT"
fi

if [ -d "$VAULT/Daily" ]; then
    NOTE_COUNT=$(find "$VAULT/Daily" -name "*.md" -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')
    pass "Daily/ directory ($NOTE_COUNT notes)"
else
    warn "Daily/ directory does not exist yet (will be created on first run)"
fi

# ── 5. Futu OpenD ──────────────────────────────────────────────────
echo ""
echo "Futu OpenD (port $OPEND_PORT):"
if nc -z 127.0.0.1 "$OPEND_PORT" 2>/dev/null; then
    pass "OpenD responding on port $OPEND_PORT"
else
    warn "OpenD not responding (start Futu OpenD before running tasks)"
fi

if python3 -c "import futu" &>/dev/null; then
    pass "futu-api package installed"
else
    warn "futu-api not installed (run: pip install futu-api)"
fi

# ── 6. launchd agents (macOS) ──────────────────────────────────────
echo ""
echo "Scheduled tasks:"
if [ "$(uname)" = "Darwin" ]; then
    LABELS=(
        com.folio-scribe.hk-plan
        com.folio-scribe.hk-review
        com.folio-scribe.us-plan
        com.folio-scribe.us-review
    )
    LOADED=0
    for label in "${LABELS[@]}"; do
        if launchctl list "$label" &>/dev/null; then
            pass "$label loaded"
            LOADED=$((LOADED + 1))
        else
            warn "$label not loaded"
        fi
    done
    if [ "$LOADED" -eq 0 ]; then
        warn "No agents loaded. Install with: scripts/install_schedule.sh install"
    fi
else
    warn "Not macOS — launchd check skipped"
fi

# ── 7. Scripts ──────────────────────────────────────────────────────
echo ""
echo "Scripts:"
if [ -x "$SCRIPT_DIR/run_folio_task.sh" ]; then
    pass "run_folio_task.sh executable"
else
    fail "run_folio_task.sh not found or not executable"
fi

if [ -f "$SCRIPT_DIR/write_daily_note.py" ]; then
    if python3 "$SCRIPT_DIR/write_daily_note.py" --help &>/dev/null; then
        pass "write_daily_note.py runnable"
    else
        fail "write_daily_note.py import error"
    fi
else
    fail "write_daily_note.py not found"
fi

if [ -f "$SCRIPT_DIR/read_futu_snapshot.py" ]; then
    pass "read_futu_snapshot.py present"
else
    warn "read_futu_snapshot.py not found"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────"
echo "  ✓ $PASS passed   ⚠ $WARN warnings   ✗ $FAIL failed"
echo "────────────────────────────"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Fix the failures above before running folio-scribe tasks."
    exit 1
else
    if [ "$WARN" -gt 0 ]; then
        echo ""
        echo "All critical checks passed. Resolve warnings for full functionality."
    else
        echo ""
        echo "All checks passed. Ready to run."
    fi
    exit 0
fi
