from __future__ import annotations

import datetime as dt
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "folio-scribe" / "scripts" / "market_calendar.py"


def load_market_calendar():
    spec = importlib.util.spec_from_file_location("market_calendar", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["market_calendar"] = module
    spec.loader.exec_module(module)
    return module


class MarketCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calendar = load_market_calendar()

    def test_may_25_2026_is_closed_for_hk_and_us(self) -> None:
        date = dt.date(2026, 5, 25)

        hk = self.calendar.market_status("HK", date)
        us = self.calendar.market_status("US", date)

        self.assertFalse(hk.open)
        self.assertIn("Birthday of the Buddha", hk.reason)
        self.assertFalse(us.open)
        self.assertEqual(us.reason, "Memorial Day")

    def test_next_day_is_open_for_hk_and_us(self) -> None:
        date = dt.date(2026, 5, 26)

        self.assertTrue(self.calendar.market_status("HK", date).open)
        self.assertTrue(self.calendar.market_status("US", date).open)

    def test_cli_returns_non_zero_for_closed_market(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "is-open",
                "--market",
                "US",
                "--date",
                "2026-05-25",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("closed", result.stdout)


if __name__ == "__main__":
    unittest.main()
