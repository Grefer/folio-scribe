#!/usr/bin/env python3
"""Select dynamic watchlist candidates from Futu OpenD.

The output is intentionally plain: one Futu symbol per line. The runner then
reads fresh snapshots for these symbols and lets the AI choose what to mention.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


class CandidateSelectionError(RuntimeError):
    """Raised when Futu cannot provide a dynamic candidate list."""


@dataclass(frozen=True)
class MarketConfig:
    market: str
    price_min: float
    price_max: float
    market_val_min: float
    turnover_min: float
    momentum_turnover_min: float


MARKETS = {
    "HK": MarketConfig(
        market="HK",
        price_min=1,
        price_max=1000,
        market_val_min=5_000_000_000,
        turnover_min=20_000_000,
        momentum_turnover_min=10_000_000,
    ),
    "US": MarketConfig(
        market="US",
        price_min=5,
        price_max=1000,
        market_val_min=2_000_000_000,
        turnover_min=20_000_000,
        momentum_turnover_min=10_000_000,
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select dynamic non-position watchlist candidates from Futu OpenD."
    )
    parser.add_argument("--market", choices=sorted(MARKETS), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--limit", type=int, default=24)
    return parser


def _load_futu() -> Any:
    try:
        import futu as futu_module  # type: ignore[import-not-found]
        from futu.common.ft_logger import logger as futu_logger  # type: ignore[import-not-found]

        futu_logger.enable_console_log(False)
    except ImportError as exc:
        raise CandidateSelectionError("futu-api is not installed.") from exc
    except Exception as exc:
        raise CandidateSelectionError(f"futu-api failed to initialize: {exc}") from exc
    return futu_module


def _simple_filter(
    futu: Any,
    field: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    sort: Any | None = None,
) -> Any:
    item = futu.SimpleFilter()
    item.stock_field = field
    item.filter_min = minimum
    item.filter_max = maximum
    item.sort = sort
    item.is_no_filter = False
    return item


def _accumulate_filter(
    futu: Any,
    field: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    sort: Any | None = None,
    days: int = 1,
) -> Any:
    item = futu.AccumulateFilter()
    item.stock_field = field
    item.filter_min = minimum
    item.filter_max = maximum
    item.sort = sort
    item.days = days
    item.is_no_filter = False
    return item


def _base_filters(futu: Any, config: MarketConfig) -> list[Any]:
    return [
        _simple_filter(
            futu,
            futu.StockField.CUR_PRICE,
            minimum=config.price_min,
            maximum=config.price_max,
        ),
        _simple_filter(
            futu,
            futu.StockField.MARKET_VAL,
            minimum=config.market_val_min,
        ),
    ]


def _strategy_filters(futu: Any, config: MarketConfig) -> list[list[Any]]:
    return [
        [
            *_base_filters(futu, config),
            _accumulate_filter(
                futu,
                futu.StockField.TURNOVER,
                minimum=config.turnover_min,
                sort=futu.SortDir.DESCEND,
            ),
        ],
        [
            *_base_filters(futu, config),
            _accumulate_filter(
                futu,
                futu.StockField.TURNOVER,
                minimum=config.momentum_turnover_min,
            ),
            _accumulate_filter(
                futu,
                futu.StockField.CHANGE_RATE,
                minimum=-30,
                maximum=80,
                sort=futu.SortDir.DESCEND,
            ),
        ],
        [
            *_base_filters(futu, config),
            _accumulate_filter(
                futu,
                futu.StockField.TURNOVER,
                minimum=config.momentum_turnover_min,
            ),
            _accumulate_filter(
                futu,
                futu.StockField.CHANGE_RATE,
                minimum=-30,
                maximum=80,
                sort=futu.SortDir.ASCEND,
            ),
        ],
        [
            *_base_filters(futu, config),
            _simple_filter(
                futu,
                futu.StockField.VOLUME_RATIO,
                minimum=1.2,
                maximum=50,
                sort=futu.SortDir.DESCEND,
            ),
        ],
    ]


def _extract_items(data: Any) -> Iterable[Any]:
    if isinstance(data, tuple) and len(data) >= 3:
        return data[2]
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    return data or []


def _symbol_from_item(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("stock_code") or item.get("code") or item.get("symbol") or "")
    return str(getattr(item, "stock_code", "") or getattr(item, "code", "") or "")


def _looks_like_common_equity(symbol: str, market: str) -> bool:
    symbol = symbol.upper()
    if not symbol.startswith(f"{market}."):
        return False
    if market == "US":
        ticker = symbol.split(".", 1)[1]
        return ticker.replace("-", "").replace(".", "").isalnum()
    if market == "HK":
        code = symbol.split(".", 1)[1]
        return len(code) == 5 and code.isdigit()
    return True


def select_candidates(host: str, port: int, market_code: str, limit: int) -> list[str]:
    futu = _load_futu()
    config = MARKETS[market_code]
    market = getattr(futu.Market, config.market)
    symbols: list[str] = []
    seen: set[str] = set()

    ctx = futu.OpenQuoteContext(host=host, port=port)
    try:
        for filters in _strategy_filters(futu, config):
            ret, data = ctx.get_stock_filter(
                market=market,
                filter_list=filters,
                begin=0,
                num=max(limit * 2, 20),
            )
            if ret != futu.RET_OK:
                print(f"stock filter failed: {data}", file=sys.stderr)
                continue
            for item in _extract_items(data):
                symbol = _symbol_from_item(item).upper()
                if not _looks_like_common_equity(symbol, market_code):
                    continue
                if symbol in seen:
                    continue
                seen.add(symbol)
                symbols.append(symbol)
                if len(symbols) >= limit:
                    return symbols
    finally:
        ctx.close()

    if not symbols:
        raise CandidateSelectionError(f"No {market_code} candidates returned by Futu stock filter.")
    return symbols


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        symbols = select_candidates(args.host, args.port, args.market, args.limit)
    except CandidateSelectionError as exc:
        parser.exit(2, f"folio-scribe-watchlist: {exc}\n")
    print("\n".join(symbols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
