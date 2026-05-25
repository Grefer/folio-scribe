#!/usr/bin/env python3
"""Small bundled market-day calendar for Folio Scribe scheduled tasks.

The daily runner only needs a conservative open/closed decision before it
starts OpenD and AI generation.  Keep this file dependency-free so copied skill
bundles work without installing exchange calendar packages.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketStatus:
    market: str
    date: dt.date
    open: bool
    reason: str


HKEX_HOLIDAYS: dict[int, dict[dt.date, str]] = {
    2026: {
        dt.date(2026, 1, 1): "The first day of January",
        dt.date(2026, 2, 17): "Lunar New Year's Day",
        dt.date(2026, 2, 18): "The second day of Lunar New Year",
        dt.date(2026, 2, 19): "The third day of Lunar New Year",
        dt.date(2026, 4, 3): "Good Friday",
        dt.date(2026, 4, 6): "The day following Ching Ming Festival",
        dt.date(2026, 4, 7): "The day following Easter Monday",
        dt.date(2026, 5, 1): "Labour Day",
        dt.date(2026, 5, 25): "The day following the Birthday of the Buddha",
        dt.date(2026, 6, 19): "Tuen Ng Festival",
        dt.date(2026, 7, 1): "Hong Kong Special Administrative Region Establishment Day",
        dt.date(2026, 10, 1): "National Day",
        dt.date(2026, 10, 19): "The day following Chung Yeung Festival",
        dt.date(2026, 12, 25): "Christmas Day",
    },
}


class UnsupportedCalendarYear(ValueError):
    pass


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def easter_sunday(year: int) -> dt.date:
    """Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    day = dt.date(year, month, 1)
    delta = (weekday - day.weekday()) % 7
    return day + dt.timedelta(days=delta + (n - 1) * 7)


def last_weekday(year: int, month: int, weekday: int) -> dt.date:
    day = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    delta = (day.weekday() - weekday) % 7
    return day - dt.timedelta(days=delta)


def observed_fixed(year: int, month: int, day: int) -> dt.date:
    actual = dt.date(year, month, day)
    if actual.weekday() == 5:
        return actual - dt.timedelta(days=1)
    if actual.weekday() == 6:
        return actual + dt.timedelta(days=1)
    return actual


def nyse_holidays_for_year(year: int) -> dict[dt.date, str]:
    holidays = {
        observed_fixed(year, 1, 1): "New Year's Day",
        nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        easter_sunday(year) - dt.timedelta(days=2): "Good Friday",
        last_weekday(year, 5, 0): "Memorial Day",
        observed_fixed(year, 7, 4): "Independence Day",
        nth_weekday(year, 9, 0, 1): "Labor Day",
        nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        observed_fixed(year, 12, 25): "Christmas Day",
    }
    if year >= 2022:
        holidays[observed_fixed(year, 6, 19)] = "Juneteenth National Independence Day"
    return holidays


def nyse_holidays(date: dt.date) -> dict[dt.date, str]:
    holidays: dict[dt.date, str] = {}
    for year in range(date.year - 1, date.year + 2):
        holidays.update(nyse_holidays_for_year(year))
    return holidays


def hkex_holidays(date: dt.date) -> dict[dt.date, str]:
    if date.year not in HKEX_HOLIDAYS:
        raise UnsupportedCalendarYear(
            f"HKEX holiday calendar for {date.year} is not bundled; update market_calendar.py"
        )
    return HKEX_HOLIDAYS[date.year]


def market_status(market: str, date: dt.date) -> MarketStatus:
    normalized = market.upper()
    if normalized in {"HK", "HKEX", "XHKG"}:
        label = "HK"
        holidays = hkex_holidays(date)
    elif normalized in {"US", "NYSE", "NASDAQ", "XNYS", "XNAS"}:
        label = "US"
        holidays = nyse_holidays(date)
    else:
        raise ValueError(f"Unsupported market '{market}'. Use HK or US.")

    if date.weekday() >= 5:
        return MarketStatus(label, date, False, "Weekend")
    if date in holidays:
        return MarketStatus(label, date, False, holidays[date])
    return MarketStatus(label, date, True, "Regular trading day")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check bundled Folio Scribe market open days.")
    parser.add_argument("command", choices=["is-open"])
    parser.add_argument("--market", required=True, help="HK or US")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args(argv)

    try:
        status = market_status(args.market, parse_date(args.date))
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2
    state = "open" if status.open else "closed"
    print(f"{status.market} market is {state} on {status.date}: {status.reason}")
    return 0 if status.open else 1


if __name__ == "__main__":
    raise SystemExit(main())
