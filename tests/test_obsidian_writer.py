from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from folio_scribe.journal.obsidian import write_daily_note


class ObsidianWriterTests(unittest.TestCase):
    def test_writes_chinese_market_sections_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            path = write_daily_note(vault, "2026-05-07", "港股计划", "### Plan\n\n- Hold.", chinese=True)
            write_daily_note(vault, "2026-05-07", "美股计划", "### US Plan\n\n- Watch QS.", chinese=True)

            text = path.read_text(encoding="utf-8")
            self.assertIn("## 09:45 港股交易计划", text)
            self.assertIn("### Plan", text)
            self.assertIn("## 21:45 美股交易计划", text)
            self.assertIn("### US Plan", text)
            self.assertIn("## 06:45 美股交易总结", text)


if __name__ == "__main__":
    unittest.main()
