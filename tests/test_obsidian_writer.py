from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from folio_scribe.journal.obsidian import (
    SECTION_MARKERS,
    default_note,
    replace_section,
    set_frontmatter_model,
    write_daily_note,
)


class DefaultNoteTests(unittest.TestCase):
    """Tests for the default_note template."""

    def test_english_template_has_correct_headings(self) -> None:
        note = default_note("2026-05-08", chinese=False)
        self.assertIn("# 2026-05-08 Trading Journal", note)
        self.assertIn("## 08:45 HK Trading Plan", note)
        self.assertIn("## 16:15 HK Trading Review", note)
        self.assertIn("## 20:45 US Trading Plan", note)
        self.assertIn("## 06:45 US Trading Review", note)
        self.assertIn("Pending.", note)

    def test_chinese_template_has_correct_headings(self) -> None:
        note = default_note("2026-05-08", chinese=True)
        self.assertIn("# 2026-05-08 交易日志", note)
        self.assertIn("## 08:45 港股交易计划", note)
        self.assertIn("## 16:15 港股交易总结", note)
        self.assertIn("## 20:45 美股交易计划", note)
        self.assertIn("## 06:45 美股交易总结", note)
        self.assertIn("待更新。", note)

    def test_frontmatter_fields(self) -> None:
        note = default_note("2026-05-08", chinese=False)
        self.assertIn("date: 2026-05-08", note)
        self.assertIn("type: trading-daily", note)
        self.assertIn("tags: [trading, broker-journal]", note)
        self.assertIn("model:", note)
        self.assertIn("plan_score:", note)
        self.assertIn("discipline_score:", note)
        # Must NOT contain deprecated financial fields.
        self.assertNotIn("total_assets", note)
        self.assertNotIn("daily_pnl", note)
        self.assertNotIn("leverage", note)

    def test_template_starts_with_frontmatter_fence(self) -> None:
        note = default_note("2026-05-08", chinese=False)
        self.assertTrue(note.startswith("---\n"))
        # Second fence closes frontmatter.
        second_fence = note.index("---", 3)
        self.assertGreater(second_fence, 3)


class ReplaceSectionTests(unittest.TestCase):
    """Tests for the replace_section helper."""

    def test_replaces_existing_section_between_markers(self) -> None:
        note = (
            "## 08:45 HK Trading Plan\n\nOld content.\n\n"
            "## 16:15 HK Trading Review\n\nOld review.\n"
        )
        result = replace_section(
            note,
            "## 08:45 HK Trading Plan",
            "## 16:15 HK Trading Review",
            "New plan content.",
        )
        self.assertIn("New plan content.", result)
        self.assertNotIn("Old content.", result)
        # End-marker section must be preserved.
        self.assertIn("## 16:15 HK Trading Review", result)
        self.assertIn("Old review.", result)

    def test_replaces_last_section_no_end_marker(self) -> None:
        note = "## 06:45 US Trading Review\n\nOld review.\n"
        result = replace_section(
            note,
            "## 06:45 US Trading Review",
            None,
            "New review.",
        )
        self.assertIn("New review.", result)
        self.assertNotIn("Old review.", result)

    def test_appends_when_start_marker_missing(self) -> None:
        note = "## 08:45 HK Trading Plan\n\nPlan content.\n"
        result = replace_section(
            note,
            "## 16:15 HK Trading Review",
            None,
            "Review content.",
        )
        self.assertIn("## 08:45 HK Trading Plan", result)
        self.assertIn("Plan content.", result)
        self.assertIn("## 16:15 HK Trading Review", result)
        self.assertIn("Review content.", result)


class FrontmatterModelTests(unittest.TestCase):
    def test_sets_existing_model_field(self) -> None:
        note = "---\ndate: 2026-05-08\nmodel:\n---\n\n# Note\n"
        result = set_frontmatter_model(note, "opus")
        self.assertIn("model: opus", result)
        self.assertNotIn("model:\n", result)

    def test_inserts_model_field_when_missing(self) -> None:
        note = "---\ndate: 2026-05-08\n---\n\n# Note\n"
        result = set_frontmatter_model(note, "gpt-5.5")
        self.assertIn("model: gpt-5.5", result)
        self.assertTrue(result.startswith("---\ndate: 2026-05-08\nmodel: gpt-5.5\n---"))


class WriteDailyNoteTests(unittest.TestCase):
    """Integration tests for write_daily_note."""

    def test_creates_new_note_with_all_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(
                vault, "2026-05-08", "hk_plan", "### Morning Plan\n\n- Watch market.", chinese=False,
            )
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("## 08:45 HK Trading Plan", text)
            self.assertIn("### Morning Plan", text)
            self.assertIn("## 16:15 HK Trading Review", text)
            self.assertIn("## 20:45 US Trading Plan", text)
            self.assertIn("## 06:45 US Trading Review", text)

    def test_writes_chinese_market_sections_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(vault, "2026-05-07", "港股计划", "### Plan\n\n- Hold.", chinese=True)
            write_daily_note(vault, "2026-05-07", "美股计划", "### US Plan\n\n- Watch QS.", chinese=True)

            text = path.read_text(encoding="utf-8")
            self.assertIn("## 08:45 港股交易计划", text)
            self.assertIn("### Plan", text)
            self.assertIn("## 20:45 美股交易计划", text)
            self.assertIn("### US Plan", text)
            self.assertIn("## 06:45 美股交易总结", text)

    def test_updates_existing_section_preserves_others(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            write_daily_note(vault, "2026-05-08", "hk_plan", "V1 plan.", chinese=True)
            path = write_daily_note(vault, "2026-05-08", "hk_plan", "V2 plan.", chinese=True)

            text = path.read_text(encoding="utf-8")
            self.assertIn("V2 plan.", text)
            self.assertNotIn("V1 plan.", text)
            # Other sections still intact.
            self.assertIn("## 16:15 港股交易总结", text)

    def test_auto_detects_chinese_from_section_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(vault, "2026-05-08", "港股计划", "Plan.", chinese=False)
            text = path.read_text(encoding="utf-8")
            # Even without chinese=True, Chinese section names trigger Chinese template.
            self.assertIn("# 2026-05-08 交易日志", text)

    def test_unknown_section_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_daily_note(Path(tmp), "2026-05-08", "nonexistent", "Content.")

    def test_daily_dir_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(vault, "2026-05-08", "hk_plan", "Test.", daily_dir="Notes")
            self.assertEqual(path.parent.name, "Notes")
            self.assertTrue(path.exists())

    def test_model_argument_updates_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(
                vault,
                "2026-05-08",
                "港股计划",
                "Plan.",
                chinese=True,
                model="opus",
            )
            self.assertIn("model: opus", path.read_text(encoding="utf-8"))


class SectionMarkersConsistencyTests(unittest.TestCase):
    """Sanity checks for the SECTION_MARKERS dict."""

    def test_all_markers_present(self) -> None:
        expected = {
            "plan", "review",
            "hk_plan", "hk_review", "us_plan", "us_review",
            "计划", "总结",
            "港股计划", "港股总结", "美股计划", "美股总结",
        }
        self.assertEqual(set(SECTION_MARKERS.keys()), expected)

    def test_markers_use_correct_times(self) -> None:
        for key, (start, end) in SECTION_MARKERS.items():
            self.assertTrue(
                start.startswith("## "),
                f"Section '{key}' start marker must begin with '## '",
            )
            if end is not None:
                self.assertTrue(
                    end.startswith("## "),
                    f"Section '{key}' end marker must begin with '## '",
                )

    def test_hk_plan_times(self) -> None:
        start, end = SECTION_MARKERS["hk_plan"]
        self.assertIn("08:45", start)
        self.assertIn("16:15", end)

    def test_us_plan_times(self) -> None:
        start, end = SECTION_MARKERS["us_plan"]
        self.assertIn("20:45", start)
        self.assertIn("06:45", end)


if __name__ == "__main__":
    unittest.main()
