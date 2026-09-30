#!/usr/bin/env python3
"""Small bundled market-day calendar for Folio Scribe scheduled tasks.

The daily runner only needs a conservative open/closed decision before it
starts OpenD and AI generation, and the trading date a run belongs to in the
market's own time zone.  Keep this file dependency-free so copied skill
bundles work without installing exchange calendar packages.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo


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
    2027: {
        dt.date(2027, 1, 1): "The first day of January",
        dt.date(2027, 2, 8): "The third day of Lunar New Year",
        dt.date(2027, 2, 9): "The fourth day of Lunar New Year",
        dt.date(2027, 3, 26): "Good Friday",
        dt.date(2027, 3, 29): "Easter Monday",
        dt.date(2027, 4, 5): "Ching Ming Festival",
        dt.date(2027, 5, 13): "The Birthday of the Buddha",
        dt.date(2027, 6, 9): "Tuen Ng Festival",
        dt.date(2027, 7, 1): "Hong Kong Special Administrative Region Establishment Day",
        dt.date(2027, 9, 16): "The day following the Chinese Mid-Autumn Festival",
        dt.date(2027, 10, 1): "National Day",
        dt.date(2027, 10, 8): "Chung Yeung Festival",
        dt.date(2027, 12, 27): "The first weekday after Christmas Day",
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


MARKET_TIMEZONES = {"HK": "Asia/Hong_Kong", "US": "America/New_York"}
# HKEX and NYSE regular sessions both end at 16:00 local time.
SESSION_CLOSE = dt.time(16, 0)


def market_label(market: str) -> str:
    normalized = market.upper()
    if normalized in {"HK", "HKEX", "XHKG"}:
        return "HK"
    if normalized in {"US", "NYSE", "NASDAQ", "XNYS", "XNAS"}:
        return "US"
    raise ValueError(f"Unsupported market '{market}'. Use HK or US.")


def market_status(market: str, date: dt.date) -> MarketStatus:
    label = market_label(market)
    holidays = hkex_holidays(date) if label == "HK" else nyse_holidays(date)

    if date.weekday() >= 5:
        return MarketStatus(label, date, False, "Weekend")
    if date in holidays:
        return MarketStatus(label, date, False, holidays[date])
    return MarketStatus(label, date, True, "Regular trading day")


def session_date(market: str, task: str, now: dt.datetime | None = None) -> dt.date:
    """Trading date a plan or review run belongs to, in the market's own time zone.

    A plan targets the session that has not closed yet: today before the close,
    otherwise tomorrow.  A review targets the latest closed session: today after
    the close, otherwise yesterday.  Weekends and holidays are left to
    market_status(), so the result does not depend on the machine's time zone.
    """
    if task not in {"plan", "review"}:
        raise ValueError(f"Unsupported task '{task}'. Use plan or review.")
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include a UTC offset")
    local = now.astimezone(ZoneInfo(MARKET_TIMEZONES[market_label(market)]))
    after_close = local.time() >= SESSION_CLOSE
    if task == "plan":
        return local.date() + dt.timedelta(days=1 if after_close else 0)
    return local.date() - dt.timedelta(days=0 if after_close else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check bundled Folio Scribe market open days.")
    parser.add_argument("command", choices=["is-open", "session-date"])
    parser.add_argument("--market", required=True, help="HK or US")
    parser.add_argument("--date", help="YYYY-MM-DD (is-open)")
    parser.add_argument("--task", choices=["plan", "review"], help="session-date: which run the date is for")
    parser.add_argument("--now", help="session-date: ISO 8601 time with UTC offset (default: now)")
    args = parser.parse_args(argv)

    if args.command == "session-date":
        if not args.task:
            parser.error("session-date requires --task")
        try:
            now = dt.datetime.fromisoformat(args.now) if args.now else None
            print(session_date(args.market, args.task, now).isoformat())
        except Exception as exc:
            print(f"ERROR: {exc}")
            return 2
        return 0

    if not args.date:
        parser.error("is-open requires --date")
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
