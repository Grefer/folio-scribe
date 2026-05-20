from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "skill" / "folio-scribe" / "scripts" / "resolve_model_label.py"

spec = importlib.util.spec_from_file_location("resolve_model_label", RESOLVER_PATH)
assert spec and spec.loader
resolve_model_label = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolve_model_label)


def _create_cc_switch_db(path: Path, provider_settings: dict[str, object]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            create table providers (
                id text not null,
                app_type text not null,
                name text not null,
                settings_config text not null,
                meta text not null default '{}',
                is_current integer not null default 0,
                sort_index integer
            )
            """,
        )
        conn.execute(
            """
            insert into providers
                (id, app_type, name, settings_config, meta, is_current, sort_index)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "codex-provider",
                "claude",
                "Codex",
                json.dumps(provider_settings),
                json.dumps({"providerType": "codex_oauth"}),
                1,
                0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


class ModelLabelResolverTests(unittest.TestCase):
    def test_maps_claude_usage_to_cc_switch_codex_upstream_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "cc-switch.db"
            claude_json = tmp_path / "claude.json"
            _create_cc_switch_db(
                db_path,
                {
                    "env": {
                        "ANTHROPIC_BASE_URL": "https://chatgpt.com/backend-api/codex",
                        "ANTHROPIC_MODEL": "gpt-5.5",
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-5.4-mini",
                        "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-5.5",
                        "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.5",
                    },
                },
            )
            claude_json.write_text(
                json.dumps(
                    {
                        "result": "plan",
                        "modelUsage": {
                            "claude-haiku-4-5-20251001": {
                                "outputTokens": 1178,
                                "costUSD": 0.007699,
                            },
                            "claude-opus-4-7": {
                                "outputTokens": 3318,
                                "costUSD": 0.09232,
                            },
                        },
                    },
                ),
                encoding="utf-8",
            )

            label = resolve_model_label.resolve_label(
                "claude",
                "claude:claude-haiku-4-5-20251001,claude-opus-4-7",
                claude_json,
                db_path,
            )

        self.assertEqual(label, "codex:gpt-5.5,gpt-5.4-mini")

    def test_falls_back_to_claude_label_without_cc_switch_db(self) -> None:
        label = resolve_model_label.resolve_label(
            "claude",
            "claude:claude-opus-4-7",
            None,
            Path("/does/not/exist.db"),
        )

        self.assertEqual(label, "claude:claude-opus-4-7")

    def test_leaves_codex_cli_label_unchanged(self) -> None:
        label = resolve_model_label.resolve_label(
            "codex",
            "codex:gpt-5.5",
            None,
            Path("/does/not/exist.db"),
        )

        self.assertEqual(label, "codex:gpt-5.5")


if __name__ == "__main__":
    unittest.main()
