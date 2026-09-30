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

    def test_2027_hk_holidays_are_bundled(self) -> None:
        closed = self.calendar.market_status("HK", dt.date(2027, 2, 8))
        open_day = self.calendar.market_status("HK", dt.date(2027, 2, 10))

        self.assertFalse(closed.open)
        self.assertIn("Lunar New Year", closed.reason)
        self.assertTrue(open_day.open)

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

    def assert_session_dates(self, runs: list[tuple[str, str, str, dt.date]]) -> None:
        for market, task, now, expected in runs:
            with self.subTest(market=market, task=task, now=now):
                actual = self.calendar.session_date(market, task, dt.datetime.fromisoformat(now))
                self.assertEqual(actual, expected)

    def test_session_date_matches_original_hkt_schedule(self) -> None:
        day = dt.date(2026, 9, 29)
        self.assert_session_dates([
            ("HK", "plan", "2026-09-29T08:15:00+08:00", day),
            ("HK", "review", "2026-09-29T16:15:00+08:00", day),
            ("US", "plan", "2026-09-29T16:30:00+08:00", day),
            ("US", "plan", "2026-09-29T20:45:00+08:00", day),
            ("US", "review", "2026-09-30T06:45:00+08:00", day),
        ])

    def test_session_date_on_pacific_schedule(self) -> None:
        day = dt.date(2026, 9, 29)
        self.assert_session_dates([
            ("HK", "plan", "2026-09-28T16:45:00-07:00", day),
            ("HK", "review", "2026-09-29T01:15:00-07:00", day),
            ("US", "plan", "2026-09-29T01:30:00-07:00", day),
            ("US", "plan", "2026-09-29T05:45:00-07:00", day),
            ("US", "review", "2026-09-29T15:45:00-07:00", day),
        ])

    def test_session_date_on_pacific_schedule_after_dst_ends(self) -> None:
        day = dt.date(2026, 11, 2)
        self.assert_session_dates([
            ("HK", "plan", "2026-11-01T16:45:00-08:00", day),
            ("HK", "review", "2026-11-02T01:15:00-08:00", day),
            ("US", "plan", "2026-11-02T05:45:00-08:00", day),
            ("US", "review", "2026-11-02T15:45:00-08:00", day),
        ])

    def test_session_date_rolls_over_at_the_close(self) -> None:
        self.assert_session_dates([
            ("US", "plan", "2026-09-29T16:00:00-04:00", dt.date(2026, 9, 30)),
            ("US", "review", "2026-09-29T15:59:00-04:00", dt.date(2026, 9, 28)),
            ("HK", "review", "2026-09-29T08:00:00+08:00", dt.date(2026, 9, 28)),
        ])

    def test_session_date_requires_an_offset(self) -> None:
        with self.assertRaises(ValueError):
            self.calendar.session_date("US", "plan", dt.datetime(2026, 9, 29, 8, 45))

    def test_cli_prints_session_date(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "session-date",
                "--market",
                "US",
                "--task",
                "review",
                "--now",
                "2026-09-29T15:45:00-07:00",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "2026-09-29")


if __name__ == "__main__":
    unittest.main()
