from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "skill" / "folio-scribe" / "scripts" / "build_web_journal.py"
spec = importlib.util.spec_from_file_location("build_web_journal", SCRIPT_PATH)
build_web_journal = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["build_web_journal"] = build_web_journal
spec.loader.exec_module(build_web_journal)


class WebJournalParsingTests(unittest.TestCase):
    def test_parse_frontmatter_lists_and_empty_fields(self) -> None:
        text = "---\ndate: 2026-05-11\ntags: [trading, broker-journal]\nmodel:\n---\n\n# Note\n"
        frontmatter, body = build_web_journal.parse_frontmatter(text)

        self.assertEqual(frontmatter["date"], "2026-05-11")
        self.assertEqual(frontmatter["tags"], ["trading", "broker-journal"])
        self.assertEqual(frontmatter["model"], "")
        self.assertEqual(body, "# Note")

    def test_parse_daily_note_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "2026-05-11.md"
            note.write_text(
                """---
date: 2026-05-11
model: claude:opus
plan_score: 8
discipline_score:
---

# 2026-05-11 交易日志

## 08:45 港股交易计划

### 账户快照

- Hold.

## 16:15 港股交易总结

待更新。
""",
                encoding="utf-8",
            )

            parsed = build_web_journal.parse_daily_note(note)

        self.assertEqual(parsed["date"], "2026-05-11")
        self.assertEqual(parsed["model"], "claude:opus")
        self.assertEqual(parsed["planScore"], "8")
        self.assertEqual(parsed["sectionCount"], 2)
        self.assertEqual(parsed["completedSectionCount"], 1)
        self.assertEqual(parsed["sections"][0]["key"], "hk_plan")
        self.assertFalse(parsed["sections"][0]["pending"])
        self.assertTrue(parsed["sections"][1]["pending"])

    def test_pending_section_ignores_trailing_rule(self) -> None:
        sections = build_web_journal.parse_sections("## 20:45 美股交易计划\n\n待更新。\n\n---\n")

        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0].pending)
        self.assertEqual(sections[0].content, "待更新。")


class WebJournalBuildTests(unittest.TestCase):
    def test_build_site_writes_static_assets_and_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            daily = vault / "Daily"
            daily.mkdir(parents=True)
            (daily / "2026-05-11.md").write_text(
                """---
date: 2026-05-11
model: gpt-5.5
plan_score:
discipline_score:
---

# 2026-05-11 交易日志

## 08:45 港股交易计划

Plan body.
""",
                encoding="utf-8",
            )
            out = root / "site"

            data = build_web_journal.build_site(vault, out, "Trading Journal")

            self.assertEqual(data["stats"]["noteCount"], 1)
            self.assertTrue((out / "index.html").exists())
            self.assertTrue((out / "assets" / "app.css").exists())
            self.assertTrue((out / "assets" / "app.js").exists())
            self.assertTrue((out / "assets" / "journal-data.js").exists())
            self.assertTrue((out / "data" / "journal.json").exists())
            self.assertTrue((out / "middleware.js").exists())
            self.assertTrue((out / "package.json").exists())
            self.assertIn("Disallow: /", (out / "robots.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
