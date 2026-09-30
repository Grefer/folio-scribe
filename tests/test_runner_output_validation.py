from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_account_privacy import FUTU_SNAPSHOT, IBKR_SNAPSHOT, SKILL_DIR, _clean_env, _write_executable


US_PLAN_HEADINGS = [
    "### 账户快照与美股风险约束",
    "### 当前美股持仓",
    "### 美股盘前盘面",
    "### 本交易时段美股计划",
    "### 美股推荐关注清单",
    "### 风险边界",
    "### 本交易时段不做什么",
]

# What Claude wrote into the 2026-09-18 HK review when it tried to call tools with tools disabled.
TOOL_CALL_TEXT = 'Bash Tool\n{\n  "command": "cat Rules/交易策略.md",\n  "description": "Read strategy"\n}\n'


@unittest.skipUnless(sys.platform == "darwin", "run_folio_task.sh requires macOS")
class RunnerOutputValidationTests(unittest.TestCase):
    """End-to-end: the real runner rejects AI output that does not follow the section template."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.skill = self.tmp / "folio-scribe"
        shutil.copytree(SKILL_DIR, self.skill)
        scripts = self.skill / "scripts"
        _write_executable(scripts / "read_futu_snapshot.py", f"import json\nprint(json.dumps({FUTU_SNAPSHOT!r}))\n")
        _write_executable(scripts / "read_ibkr_snapshot.py", f"import json\nprint(json.dumps({IBKR_SNAPSHOT!r}))\n")
        self.vault = self.tmp / "vault"
        self.logs = self.tmp / "logs"
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()

    def tearDown(self) -> None:
        self.listener.close()
        self._tmp.cleanup()

    def run_us_plan(self, result_text: str) -> subprocess.CompletedProcess[str]:
        payload = {"type": "result", "is_error": False, "result": result_text, "modelUsage": {"fake-model": {}}}
        payload_file = self.tmp / "claude-result.json"
        payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _write_executable(self.tmp / "fake-claude", f"#!/bin/bash\ncat '{payload_file}'\n")
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        return subprocess.run(
            [str(self.skill / "scripts" / "run_folio_task.sh"), "us_plan"],
            cwd=self.tmp,
            env=_clean_env(
                HOME=str(home),
                FOLIO_SCRIBE_VAULT=str(self.vault),
                FOLIO_SCRIBE_LOG_DIR=str(self.logs),
                FOLIO_SCRIBE_NOTE_DATE="2026-09-17",
                FOLIO_SCRIBE_PLAN_PHASE="final",
                FOLIO_SCRIBE_ALLOW_NON_TRADING_DAY="1",
                FOLIO_SCRIBE_OPEND_PORT=str(self.listener.getsockname()[1]),
                FOLIO_SCRIBE_WATCHLIST_MODE="off",
                FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE="gateway",
                FOLIO_SCRIBE_AI_CLI="claude",
                FOLIO_SCRIBE_CLAUDE=str(self.tmp / "fake-claude"),
                FOLIO_SCRIBE_AI_FALLBACK_CLI="none",
                FOLIO_SCRIBE_NOTIFY="0",
            ),
            text=True, capture_output=True, check=False, timeout=120,
        )

    def read_note(self) -> str:
        return (self.vault / "Daily" / "2026-09-17.md").read_text(encoding="utf-8")

    def test_tool_call_text_falls_back_to_data_only_section(self) -> None:
        result = self.run_us_plan(TOOL_CALL_TEXT)

        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        self.assertIn("AI output failed validation: contains tool-call text", result.stdout)
        note = self.read_note()
        self.assertIn("model: runner:deterministic-fallback", note)
        self.assertNotIn("Bash Tool", note)

    def test_missing_template_heading_falls_back(self) -> None:
        body = "\n\n".join(f"{heading}\n\n测试内容。" for heading in US_PLAN_HEADINGS if heading != "### 风险边界")

        result = self.run_us_plan(body)

        self.assertIn("missing headings: 风险边界", result.stdout)
        self.assertIn("model: runner:deterministic-fallback", self.read_note())

    def test_output_with_all_template_headings_is_written(self) -> None:
        body = "\n\n".join(f"{heading}\n\n测试内容。" for heading in US_PLAN_HEADINGS)

        result = self.run_us_plan(body)

        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        self.assertNotIn("failed validation", result.stdout)
        note = self.read_note()
        self.assertIn("### 本交易时段不做什么", note)
        self.assertNotIn("runner:deterministic-fallback", note)


if __name__ == "__main__":
    unittest.main()
