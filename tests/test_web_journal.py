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
            self.assertEqual(data["summaries"]["weekly"], [])
            self.assertEqual(data["summaries"]["monthly"], [])
            self.assertTrue((out / "index.html").exists())
            self.assertTrue((out / "assets" / "app.css").exists())
            self.assertTrue((out / "assets" / "app.js").exists())
            self.assertTrue((out / "assets" / "journal-data.js").exists())
            self.assertTrue((out / "data" / "journal.json").exists())
            self.assertTrue((out / "middleware.js").exists())
            self.assertTrue((out / "package.json").exists())
            self.assertIn("Disallow: /", (out / "robots.txt").read_text(encoding="utf-8"))

    def test_build_site_exports_weekly_and_monthly_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            daily = vault / "Daily"
            weekly = vault / "Weekly"
            monthly = vault / "Monthly"
            daily.mkdir(parents=True)
            weekly.mkdir()
            monthly.mkdir()
            (daily / "2026-05-11.md").write_text(
                """---
date: 2026-05-11
model: gpt-5.5
---

# 2026-05-11 交易日志

## 08:45 港股交易计划

Plan body.
""",
                encoding="utf-8",
            )
            (weekly / "2026-W20.md").write_text(
                """---
period: weekly
id: 2026-W20
type: trading-weekly
start_date: 2026-05-11
end_date: 2026-05-17
daily_count: 1
completed_sections: 1
total_sections: 4
tags: [trading, broker-journal, periodic-review, weekly-review]
model: codex:gpt-5.5
generated_at: 2026-05-18T00:00:00+00:00
---

# 2026-W20 交易周总结

Weekly body.
""",
                encoding="utf-8",
            )
            (monthly / "2026-05.md").write_text(
                """---
period: monthly
id: 2026-05
type: trading-monthly
start_date: 2026-05-01
end_date: 2026-05-31
daily_count: 1
completed_sections: 1
total_sections: 4
tags: [trading, broker-journal, periodic-review, monthly-review]
model: codex:gpt-5.5
generated_at: 2026-05-18T00:00:00+00:00
---

# 2026-05 月度交易总结

Monthly body.
""",
                encoding="utf-8",
            )

            data = build_web_journal.build_site(vault, root / "site", "Trading Journal")

            self.assertEqual(data["stats"]["weeklyCount"], 1)
            self.assertEqual(data["stats"]["monthlyCount"], 0)
            self.assertEqual(data["summaries"]["weekly"][0]["id"], "2026-W20")
            self.assertEqual(data["summaries"]["weekly"][0]["dailyCount"], "1")
            self.assertEqual(data["summaries"]["weekly"][0]["anchorDate"], "2026-05-11")
            self.assertEqual(data["summaries"]["weekly"][0]["displayRange"], "2026-05-11 - 2026-05-11")
            self.assertIn("Weekly body.", data["summaries"]["weekly"][0]["rawMarkdown"])

    def test_build_site_exports_ready_monthly_summary_on_month_end_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            daily = vault / "Daily"
            monthly = vault / "Monthly"
            daily.mkdir(parents=True)
            monthly.mkdir()
            (daily / "2026-04-30.md").write_text(
                """---
date: 2026-04-30
model: gpt-5.5
---

# 2026-04-30 交易日志

## 08:45 港股交易计划

Plan body.
""",
                encoding="utf-8",
            )
            (monthly / "2026-04.md").write_text(
                """---
period: monthly
id: 2026-04
type: trading-monthly
start_date: 2026-04-01
end_date: 2026-04-30
daily_count: 1
completed_sections: 1
total_sections: 4
tags: [trading, broker-journal, periodic-review, monthly-review]
model: codex:gpt-5.5
generated_at: 2026-05-01T00:00:00+00:00
---

# 2026-04 月度交易总结

Monthly body.
""",
                encoding="utf-8",
            )

            data = build_web_journal.build_site(vault, root / "site", "Trading Journal")

            self.assertEqual(data["stats"]["monthlyCount"], 1)
            self.assertEqual(data["summaries"]["monthly"][0]["id"], "2026-04")
            self.assertEqual(data["summaries"]["monthly"][0]["anchorDate"], "2026-04-30")
            self.assertEqual(data["summaries"]["monthly"][0]["displayRange"], "2026-04-01 - 2026-04-30")


if __name__ == "__main__":
    unittest.main()
