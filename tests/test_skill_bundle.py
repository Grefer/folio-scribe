from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skill" / "folio-scribe"


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


class SkillBundlePortabilityTests(unittest.TestCase):
    def test_openai_yaml_metadata_exists(self) -> None:
        metadata = SKILL_DIR / "agents" / "openai.yaml"

        self.assertTrue(metadata.exists())
        text = metadata.read_text(encoding="utf-8")
        self.assertIn('display_name: "Folio Scribe"', text)
        self.assertIn('default_prompt: "Use $folio-scribe', text)

    def test_copied_bundle_writer_runs_without_repo_package_import_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)
            content = tmp_path / "plan.md"
            content.write_text("Standalone bundle plan.\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "write_daily_note.py"),
                    "--vault",
                    str(tmp_path / "vault"),
                    "--date",
                    "2026-05-08",
                    "--section",
                    "hk_plan",
                    "--content",
                    str(content),
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            note = tmp_path / "vault" / "Daily" / "2026-05-08.md"
            self.assertIn("Standalone bundle plan.", note.read_text(encoding="utf-8"))

    def test_copied_bundle_futu_helper_help_does_not_need_repo_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)

            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "read_futu_snapshot.py"),
                    "--help",
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Read a Futu OpenD snapshot as JSON", result.stdout)

    def test_copied_bundle_watchlist_selector_help_does_not_need_repo_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)

            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "select_watchlist_candidates.py"),
                    "--help",
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Select dynamic", result.stdout)

    def test_copied_bundle_model_resolver_runs_without_repo_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)

            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "resolve_model_label.py"),
                    "--cli",
                    "claude",
                    "--label",
                    "claude:claude-opus-4-7",
                    "--cc-switch-db",
                    str(tmp_path / "missing.db"),
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "claude:claude-opus-4-7")

    def test_copied_bundle_web_sync_help_does_not_need_repo_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)

            result = subprocess.run(
                [
                    str(copied_skill / "scripts" / "sync_tradingweb.sh"),
                    "--help",
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Builds the static TradingWeb dashboard", result.stdout)

    def test_copied_bundle_periodic_summary_help_does_not_need_repo_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copied_skill = tmp_path / "folio-scribe"
            shutil.copytree(SKILL_DIR, copied_skill)

            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "write_periodic_summary.py"),
                    "--help",
                ],
                cwd=tmp_path,
                env=_clean_env(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Generate Weekly/Monthly", result.stdout)


if __name__ == "__main__":
    unittest.main()
