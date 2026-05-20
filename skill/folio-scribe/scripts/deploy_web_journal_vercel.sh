#!/usr/bin/env bash
# deploy_web_journal_vercel.sh — Safe Vercel deploy for the static web journal.
#
# Defaults are intentionally private:
#   - enable Vercel SSO protection before deploying
#   - deploy to the preview environment
#   - return a unique deployment URL instead of updating *.vercel.app aliases

set -euo pipefail

OUT_DIR="${FOLIO_SCRIBE_WEB_EXPORT_DIR:-$HOME/Documents/TradingWeb}"
PROJECT="${FOLIO_SCRIBE_VERCEL_PROJECT:-vercel-trading-journal}"
SCOPE="${FOLIO_SCRIBE_VERCEL_SCOPE:-}"
TARGET="${FOLIO_SCRIBE_VERCEL_TARGET:-preview}"
TARGET_EXPLICIT=0
DOMAIN="${FOLIO_SCRIBE_VERCEL_DOMAIN:-}"
ENABLE_SSO="${FOLIO_SCRIBE_VERCEL_ENABLE_SSO:-1}"
SKIP_DOMAIN="${FOLIO_SCRIBE_VERCEL_SKIP_DOMAIN:-1}"
PUBLIC_ALIAS=0

usage() {
    cat <<'EOF'
Usage:
  deploy_web_journal_vercel.sh [--out PATH] [--project NAME] [--scope TEAM] [--target production|preview] [--domain HOST]
  deploy_web_journal_vercel.sh --help

Options:
  --out PATH              Static dashboard output directory
  --project NAME          Vercel project name (default: vercel-trading-journal)
  --scope TEAM            Vercel team slug
  --target TARGET         Vercel target: preview or production (default: preview)
  --domain HOST           Custom domain to keep aliased to production
  --public-alias          Allow production domain aliasing (not recommended for private journals)
  --no-sso                Do not enable Vercel SSO protection before deploy

Environment:
  FOLIO_SCRIBE_WEB_EXPORT_DIR
  FOLIO_SCRIBE_VERCEL_PROJECT
  FOLIO_SCRIBE_VERCEL_SCOPE
  FOLIO_SCRIBE_VERCEL_TARGET
  FOLIO_SCRIBE_VERCEL_DOMAIN
  FOLIO_SCRIBE_VERCEL_ENABLE_SSO
  FOLIO_SCRIBE_VERCEL_SKIP_DOMAIN
  FOLIO_SCRIBE_VERCEL_CMD       Optional command, e.g. "npx -y vercel@latest"
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT_DIR="$2"; shift 2 ;;
        --project) PROJECT="$2"; shift 2 ;;
        --scope) SCOPE="$2"; shift 2 ;;
        --target) TARGET="$2"; TARGET_EXPLICIT=1; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --public-alias) PUBLIC_ALIAS=1; SKIP_DOMAIN=0; shift ;;
        --no-sso) ENABLE_SSO=0; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

OUT_DIR="${OUT_DIR/#\~/$HOME}"

if [ -n "$DOMAIN" ] && [ "$TARGET_EXPLICIT" -eq 0 ]; then
    TARGET="production"
fi

case "$TARGET" in
    production|preview) ;;
    *) echo "ERROR: --target must be production or preview"; exit 1 ;;
esac

if [ "$TARGET" = "production" ] && [ "$PUBLIC_ALIAS" -eq 0 ] && [ -z "$DOMAIN" ]; then
    echo "ERROR: production deploys can create public Vercel aliases."
    echo "Use --target preview, pass --domain for a custom protected hostname, or pass --public-alias explicitly."
    exit 1
fi

[ -d "$OUT_DIR" ] || { echo "ERROR: Web export directory not found: $OUT_DIR"; exit 1; }
[ -f "$OUT_DIR/index.html" ] || { echo "ERROR: index.html not found in $OUT_DIR"; exit 1; }
[ -f "$OUT_DIR/vercel.json" ] || { echo "ERROR: vercel.json not found in $OUT_DIR"; exit 1; }

if [ -n "${FOLIO_SCRIBE_VERCEL_CMD:-}" ]; then
    # shellcheck disable=SC2206
    VERCEL_CMD=(${FOLIO_SCRIBE_VERCEL_CMD})
elif command -v vercel >/dev/null 2>&1; then
    VERCEL_CMD=(vercel)
else
    VERCEL_CMD=(npx -y vercel@latest)
fi

SCOPE_ARGS=()
if [ -n "$SCOPE" ]; then
    SCOPE_ARGS+=(--scope "$SCOPE")
fi

echo "Vercel project: $PROJECT"
if [ -n "$SCOPE" ]; then
    echo "Vercel scope:   $SCOPE"
fi
if [ -n "$DOMAIN" ]; then
    echo "Custom domain:  $DOMAIN"
fi
echo "Deploy target:  $TARGET"
if [ "$PUBLIC_ALIAS" -eq 1 ]; then
    echo "Public alias:   enabled"
elif [ -n "$DOMAIN" ]; then
    echo "Public alias:   custom domain only"
fi

(
    cd "$OUT_DIR"

        "${VERCEL_CMD[@]}" link \
        --yes \
        --project "$PROJECT" \
        ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} \
        --no-color

    if [ "$ENABLE_SSO" = "1" ]; then
        "${VERCEL_CMD[@]}" project protection enable "$PROJECT" \
            --sso \
            ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} \
            --no-color
    fi

    if [ -n "$DOMAIN" ]; then
        "${VERCEL_CMD[@]}" domains add "$DOMAIN" \
            ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} \
            --no-color || true
    fi

    DEPLOY_ARGS=(
        deploy .
        --yes
        --target "$TARGET"
        --format json
        --no-color
    )

    DEPLOY_JSON=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-vercel-deploy-json.XXXXXX")
    DEPLOY_LOG=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-vercel-deploy-log.XXXXXX")
    if ! "${VERCEL_CMD[@]}" "${DEPLOY_ARGS[@]}" ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} > "$DEPLOY_JSON" 2> "$DEPLOY_LOG"; then
        cat "$DEPLOY_LOG" >&2
        cat "$DEPLOY_JSON" >&2
        exit 1
    fi
    cat "$DEPLOY_LOG" >&2

    python3 - "$DEPLOY_JSON" "$DEPLOY_LOG" "$PUBLIC_ALIAS" <<'PY'
import json
import re
import sys
from pathlib import Path

json_text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").strip()
log_text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
public_alias = sys.argv[3] == "1"

try:
    payload = json.loads(json_text) if json_text else {}
except json.JSONDecodeError:
    payload = {}


def walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)
    elif isinstance(value, str):
        yield value

values = list(walk(payload))
deployment_urls = [
    value if value.startswith("http") else f"https://{value}"
    for value in values
    if ".vercel.app" in value and not value.startswith("https://vercel.com/")
]
inspect_urls = [value for value in values if value.startswith("https://vercel.com/")]

for match in re.finditer(r"(?:Preview|Production):\s+(https://[^\s\[]+)", log_text):
    deployment_urls.append(match.group(1))
for match in re.finditer(r"Inspect:\s+(https://[^\s\[]+)", log_text):
    inspect_urls.append(match.group(1))

target = ""
target_match = re.search(r"\b(Preview|Production):", log_text)
if target_match:
    target = target_match.group(1).lower()
elif isinstance(payload, dict):
    target = str(payload.get("target") or "")

print("Vercel deployment ready")
if target:
    print(f"  target:  {target}")
if deployment_urls:
    print(f"  url:     {deployment_urls[-1]}")
if inspect_urls:
    print(f"  inspect: {inspect_urls[-1]}")
if not public_alias:
    print("  alias:   automatic *.vercel.app aliases will be removed")
PY

    if [ "$PUBLIC_ALIAS" -eq 0 ]; then
        ALIAS_LIST=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-vercel-alias-list.XXXXXX")
        ALIASES_TO_REMOVE=$(mktemp "${TMPDIR:-/tmp}/folio-scribe-vercel-alias-remove.XXXXXX")
        if "${VERCEL_CMD[@]}" alias list ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} --no-color > "$ALIAS_LIST"; then
            python3 - "$ALIAS_LIST" "$PROJECT" > "$ALIASES_TO_REMOVE" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
project = sys.argv[2]

for line in text.splitlines():
    parts = line.split()
    if len(parts) < 2:
        continue
    source, alias = parts[0], parts[1]
    if not source.startswith(project + "-"):
        continue
    if not alias.endswith(".vercel.app"):
        continue
    if alias.startswith(project + "-") or alias == f"{project}.vercel.app":
        print(alias)
PY
            if [ -s "$ALIASES_TO_REMOVE" ]; then
                echo "Removing automatic Vercel aliases ..."
                while IFS= read -r alias; do
                    [ -n "$alias" ] || continue
                    "${VERCEL_CMD[@]}" alias remove "$alias" \
                        --yes \
                        ${SCOPE_ARGS[@]+"${SCOPE_ARGS[@]}"} \
                        --no-color
                done < "$ALIASES_TO_REMOVE"
            fi
        fi
    fi
)
