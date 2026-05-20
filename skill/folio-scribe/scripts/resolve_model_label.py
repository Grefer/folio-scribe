#!/usr/bin/env python3
"""Resolve the model label written to daily-note frontmatter.

The scheduled runner may call Claude Code through a local gateway such as
CC Switch. In that setup Claude reports Claude-style model names in
``modelUsage`` while the gateway forwards the request to a different upstream
model. This helper keeps the note metadata aligned with the real upstream
model when the mapping is discoverable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any


def _split_label(label: str) -> tuple[str, list[str]]:
    provider, _, rest = label.partition(":")
    if not rest:
        return provider.strip(), []
    models = [item.strip() for item in rest.split(",") if item.strip()]
    return provider.strip(), models


def _models_from_claude_json(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    usage = payload.get("modelUsage")
    if not isinstance(usage, dict):
        return []

    def score(item: tuple[str, Any]) -> tuple[float, int]:
        _, stats = item
        if not isinstance(stats, dict):
            return (0.0, 0)
        cost = stats.get("costUSD") or 0
        output_tokens = stats.get("outputTokens") or 0
        try:
            cost_value = float(cost)
        except (TypeError, ValueError):
            cost_value = 0.0
        try:
            output_value = int(output_tokens)
        except (TypeError, ValueError):
            output_value = 0
        return (cost_value, output_value)

    ordered = sorted(usage.items(), key=score, reverse=True)
    return [str(model).strip() for model, _ in ordered if str(model).strip()]


def _load_current_cc_switch_provider(db_path: Path) -> dict[str, Any] | None:
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            select id, name, settings_config, meta
            from providers
            where app_type = 'claude' and is_current = 1
            order by sort_index
            limit 1
            """,
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if row is None:
        return None

    def parse_json(value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return {
        "id": row["id"],
        "name": row["name"],
        "settings": parse_json(row["settings_config"]),
        "meta": parse_json(row["meta"]),
    }


def _safe_prefix(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "claude"


def _provider_prefix(provider: dict[str, Any]) -> str:
    name = str(provider.get("name") or "")
    settings = provider.get("settings") if isinstance(provider.get("settings"), dict) else {}
    meta = provider.get("meta") if isinstance(provider.get("meta"), dict) else {}
    env = settings.get("env") if isinstance(settings.get("env"), dict) else {}
    base_url = str(env.get("ANTHROPIC_BASE_URL") or "").lower()
    provider_type = str(meta.get("providerType") or meta.get("provider_type") or "").lower()
    name_lower = name.lower()

    if "codex" in provider_type or "codex" in base_url or "codex" in name_lower:
        return "codex"
    if "deepseek" in provider_type or "deepseek" in base_url or "deepseek" in name_lower:
        return "deepseek"
    if "mimo" in provider_type or "mimo" in base_url or "mimo" in name_lower or "xiaomi" in name_lower:
        return "mimo"
    if "copilot" in provider_type or "copilot" in base_url or "copilot" in name_lower:
        return "github-copilot"
    if "openai" in provider_type or "openai" in base_url or "openai" in name_lower:
        return "openai"
    return _safe_prefix(name)


def _first_env(env: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = env.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _mapped_model(requested: str, env: dict[str, Any]) -> str:
    lowered = requested.lower()
    fallback = _first_env(env, "ANTHROPIC_MODEL")

    if "haiku" in lowered:
        return _first_env(
            env,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME",
            "ANTHROPIC_SMALL_FAST_MODEL",
            "ANTHROPIC_SMALL_FAST_MODEL_NAME",
            "ANTHROPIC_MODEL",
        ) or requested
    if "sonnet" in lowered:
        return _first_env(
            env,
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME",
            "ANTHROPIC_MODEL",
        ) or requested
    if "opus" in lowered:
        return _first_env(
            env,
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME",
            "ANTHROPIC_MODEL",
        ) or requested
    return fallback or requested


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolve_label(
    cli: str,
    label: str,
    claude_json: Path | None = None,
    cc_switch_db: Path | None = None,
) -> str:
    cli = cli.lower().strip()
    if cli != "claude":
        return label

    label_provider, label_models = _split_label(label)
    if label_provider and label_provider != "claude":
        return label

    db_path = cc_switch_db or Path.home() / ".cc-switch" / "cc-switch.db"
    provider = _load_current_cc_switch_provider(db_path)
    if not provider:
        return label

    settings = provider.get("settings") if isinstance(provider.get("settings"), dict) else {}
    env = settings.get("env") if isinstance(settings.get("env"), dict) else {}
    if not env:
        return label

    models = _models_from_claude_json(claude_json) or label_models
    if not models:
        default_model = _first_env(env, "ANTHROPIC_MODEL")
        if not default_model:
            return label
        models = [default_model]

    mapped = _dedupe([_mapped_model(model, env) for model in models])
    if not mapped:
        return label

    return f"{_provider_prefix(provider)}:{','.join(mapped)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve Folio Scribe model labels.")
    parser.add_argument("--cli", required=True, help="AI CLI name, e.g. claude or codex")
    parser.add_argument("--label", required=True, help="Existing model label")
    parser.add_argument("--claude-json", help="Claude JSON output file")
    parser.add_argument(
        "--cc-switch-db",
        default=os.environ.get("FOLIO_SCRIBE_CC_SWITCH_DB", "~/.cc-switch/cc-switch.db"),
        help="CC Switch sqlite database path",
    )
    args = parser.parse_args()

    claude_json = Path(args.claude_json).expanduser() if args.claude_json else None
    db_path = Path(args.cc_switch_db).expanduser()
    print(resolve_label(args.cli, args.label, claude_json, db_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
