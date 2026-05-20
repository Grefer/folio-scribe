#!/usr/bin/env python3
"""Read a Futu OpenD snapshot as JSON.

This bundled script is self-contained so the skill folder can be copied into
another AI client without also installing the repository package. It remains
read-only: it exposes quote/account/position/order/fill reads only.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


class ReadOnlyDataSourceError(RuntimeError):
    """Raised when the broker data source cannot return read-only data."""


Money = Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    total_assets: Money | None = None
    daily_pnl: Money | None = None
    cash: Money | None = None
    buying_power: Money | None = None
    leverage: Decimal | None = None
    currency: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str | None = None
    quantity: Decimal | None = None
    cost: Money | None = None
    market_value: Money | None = None
    unrealized_pnl: Money | None = None
    realized_pnl: Money | None = None
    portfolio_weight: Decimal | None = None
    currency: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str | None = None
    quantity: Decimal | None = None
    price: Money | None = None
    status: str | None = None
    submitted_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str | None = None
    quantity: Decimal | None = None
    price: Money | None = None
    filled_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str | None = None
    price: Money | None = None
    quote_time: str | None = None
    open: Money | None = None
    high: Money | None = None
    low: Money | None = None
    previous_close: Money | None = None
    pre_price: Money | None = None
    pre_high_price: Money | None = None
    pre_low_price: Money | None = None
    pre_volume: Decimal | None = None
    after_price: Money | None = None
    overnight_price: Money | None = None
    volume: Decimal | None = None
    turnover: Money | None = None
    bid: Money | None = None
    ask: Money | None = None
    currency: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerSnapshot:
    captured_at: datetime
    account: AccountSnapshot | None = None
    positions: list[Position] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    quotes: dict[str, Quote] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return list(frame)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "" or value == "N/A":
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def account_from_rows(rows: Sequence[dict[str, Any]]) -> AccountSnapshot:
    if not rows:
        return AccountSnapshot(raw={"source": "futu_openapi", "status": "empty"})
    row = dict(rows[0])
    return AccountSnapshot(
        total_assets=_decimal(row.get("total_assets")),
        daily_pnl=_decimal(_first_present(row, "today_pl_val", "daily_pnl")),
        cash=_decimal(row.get("cash")),
        buying_power=_decimal(_first_present(row, "power", "buying_power")),
        leverage=_decimal(row.get("leverage")),
        currency=row.get("currency"),
        raw=row,
    )


def positions_from_rows(rows: Sequence[dict[str, Any]]) -> list[Position]:
    positions: list[Position] = []
    for row in rows:
        symbol = str(row.get("code") or row.get("symbol") or "")
        if not symbol:
            continue
        positions.append(
            Position(
                symbol=symbol,
                name=row.get("stock_name") or row.get("name"),
                quantity=_decimal(_first_present(row, "qty", "quantity")),
                cost=_decimal(_first_present(row, "cost_price", "cost")),
                market_value=_decimal(_first_present(row, "market_val", "market_value")),
                unrealized_pnl=_decimal(_first_present(row, "unrealized_pl", "pl_val", "unrealized_pnl")),
                realized_pnl=_decimal(_first_present(row, "realized_pl", "realized_pnl")),
                portfolio_weight=_decimal(row.get("portfolio_weight")),
                currency=row.get("currency"),
                raw=dict(row),
            )
        )
    return positions


def orders_from_rows(rows: Sequence[dict[str, Any]]) -> list[Order]:
    orders: list[Order] = []
    for row in rows:
        symbol = str(row.get("code") or row.get("symbol") or "")
        if not symbol:
            continue
        orders.append(
            Order(
                symbol=symbol,
                side=row.get("trd_side") or row.get("side"),
                quantity=_decimal(_first_present(row, "qty", "quantity")),
                price=_decimal(row.get("price")),
                status=row.get("order_status") or row.get("status"),
                submitted_at=_parse_datetime(row.get("create_time") or row.get("submitted_at")),
                raw=dict(row),
            )
        )
    return orders


def fills_from_rows(rows: Sequence[dict[str, Any]]) -> list[Fill]:
    fills: list[Fill] = []
    for row in rows:
        symbol = str(row.get("code") or row.get("symbol") or "")
        if not symbol:
            continue
        fills.append(
            Fill(
                symbol=symbol,
                side=row.get("trd_side") or row.get("side"),
                quantity=_decimal(_first_present(row, "qty", "quantity")),
                price=_decimal(row.get("price")),
                filled_at=_parse_datetime(row.get("create_time") or row.get("filled_at")),
                raw=dict(row),
            )
        )
    return fills


class FutuOpenAPIDataSource:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11111,
        trd_market: str = "US",
        trd_env: str = "REAL",
        security_firm: str = "N/A",
        acc_id: int = 0,
        acc_index: int = 0,
        currency: str = "USD",
        include_trading: bool = True,
        strict_trading_errors: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.trd_market = trd_market
        self.trd_env = trd_env
        self.security_firm = security_firm
        self.acc_id = acc_id
        self.acc_index = acc_index
        self.currency = currency
        self.include_trading = include_trading
        self.strict_trading_errors = strict_trading_errors

    def read_snapshot(self, symbols: Sequence[str] = ()) -> BrokerSnapshot:
        futu = self._load_futu()
        quotes = self._read_quotes(futu, symbols) if symbols else {}
        raw: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "trd_market": self.trd_market,
            "trd_env": self.trd_env,
            "acc_id": self.acc_id,
            "acc_index": self.acc_index,
        }
        account = AccountSnapshot(raw={"source": "futu_openapi", "status": "quote_only"})
        positions: list[Position] = []
        orders: list[Order] = []
        fills: list[Fill] = []

        if self.include_trading:
            try:
                account, positions, orders, fills = self._read_trading(futu)
                raw["trading_status"] = "ok"
            except ReadOnlyDataSourceError as exc:
                if self.strict_trading_errors:
                    raise
                raw["trading_status"] = "error"
                raw["trading_error"] = str(exc)
                account = AccountSnapshot(raw={"source": "futu_openapi", "status": "trading_error"})

        return BrokerSnapshot(
            captured_at=datetime.now(timezone.utc),
            account=account,
            positions=positions,
            orders=orders,
            fills=fills,
            quotes=quotes,
            raw=raw,
        )

    def _load_futu(self) -> Any:
        try:
            import futu as futu_module  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ReadOnlyDataSourceError(
                "futu-api is not installed. Install with `pip install futu-api`."
            ) from exc
        except Exception as exc:
            raise ReadOnlyDataSourceError(f"futu-api failed to initialize: {exc}") from exc
        return futu_module

    def _read_quotes(self, futu: Any, symbols: Sequence[str]) -> dict[str, Quote]:
        ctx = futu.OpenQuoteContext(host=self.host, port=self.port)
        try:
            ret, data = ctx.get_market_snapshot(list(symbols))
            if ret != futu.RET_OK:
                raise ReadOnlyDataSourceError(f"Futu quote snapshot failed: {data}")
            return self._quotes_from_frame(data)
        finally:
            ctx.close()

    def _quotes_from_frame(self, frame: Any) -> dict[str, Quote]:
        quotes: dict[str, Quote] = {}
        for _, row in frame.iterrows():
            symbol = str(row.get("code") or row.get("symbol") or "")
            if not symbol:
                continue
            quotes[symbol] = Quote(
                symbol=symbol,
                name=row.get("stock_name") or row.get("name"),
                price=_decimal(row.get("last_price")),
                quote_time=str(_first_present(row, "update_time", "data_time") or ""),
                open=_decimal(row.get("open_price")),
                high=_decimal(row.get("high_price")),
                low=_decimal(row.get("low_price")),
                previous_close=_decimal(row.get("prev_close_price")),
                pre_price=_decimal(row.get("pre_price")),
                pre_high_price=_decimal(row.get("pre_high_price")),
                pre_low_price=_decimal(row.get("pre_low_price")),
                pre_volume=_decimal(row.get("pre_volume")),
                after_price=_decimal(row.get("after_price")),
                overnight_price=_decimal(row.get("overnight_price")),
                volume=_decimal(row.get("volume")),
                turnover=_decimal(row.get("turnover")),
                raw=dict(row),
            )
        return quotes

    def _read_trading(self, futu: Any) -> tuple[AccountSnapshot, list[Position], list[Order], list[Fill]]:
        ctx = futu.OpenSecTradeContext(
            filter_trdmarket=self.trd_market,
            host=self.host,
            port=self.port,
            security_firm=self.security_firm,
        )
        try:
            account = self._read_account(ctx, futu)
            positions = self._read_positions(ctx, futu)
            orders = self._read_orders(ctx, futu)
            fills = self._read_fills(ctx, futu)
            return account, positions, orders, fills
        finally:
            ctx.close()

    def _read_account(self, ctx: Any, futu: Any) -> AccountSnapshot:
        ret, data = ctx.accinfo_query(
            trd_env=self.trd_env,
            acc_id=self.acc_id,
            acc_index=self.acc_index,
            currency=self.currency,
        )
        if ret != futu.RET_OK:
            raise ReadOnlyDataSourceError(f"Futu account query failed: {data}")
        return account_from_rows(_frame_to_rows(data))

    def _read_positions(self, ctx: Any, futu: Any) -> list[Position]:
        ret, data = ctx.position_list_query(
            trd_env=self.trd_env,
            acc_id=self.acc_id,
            acc_index=self.acc_index,
        )
        if ret != futu.RET_OK:
            raise ReadOnlyDataSourceError(f"Futu positions query failed: {data}")
        return positions_from_rows(_frame_to_rows(data))

    def _read_orders(self, ctx: Any, futu: Any) -> list[Order]:
        ret, data = ctx.order_list_query(
            trd_env=self.trd_env,
            acc_id=self.acc_id,
            acc_index=self.acc_index,
        )
        if ret != futu.RET_OK:
            raise ReadOnlyDataSourceError(f"Futu orders query failed: {data}")
        return orders_from_rows(_frame_to_rows(data))

    def _read_fills(self, ctx: Any, futu: Any) -> list[Fill]:
        ret, data = ctx.deal_list_query(
            trd_env=self.trd_env,
            acc_id=self.acc_id,
            acc_index=self.acc_index,
        )
        if ret != futu.RET_OK:
            raise ReadOnlyDataSourceError(f"Futu fills query failed: {data}")
        return fills_from_rows(_frame_to_rows(data))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value, include_raw=True)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except Exception:
            pass
    return str(value)


def _dataclass_to_dict(value: Any, include_raw: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_info in dataclasses.fields(value):
        if field_info.name == "raw" and not include_raw:
            continue
        payload[field_info.name] = _jsonable(getattr(value, field_info.name))
    return payload


def snapshot_to_dict(
    snapshot: BrokerSnapshot,
    *,
    include_raw: bool = False,
    counts_only: bool = False,
) -> dict[str, Any]:
    if counts_only:
        return {
            "captured_at": snapshot.captured_at.isoformat(),
            "counts": {
                "quotes": len(snapshot.quotes),
                "positions": len(snapshot.positions),
                "orders": len(snapshot.orders),
                "fills": len(snapshot.fills),
            },
            "trading_status": snapshot.raw.get("trading_status"),
            "has_trading_error": bool(snapshot.raw.get("trading_error")),
        }

    return {
        "captured_at": snapshot.captured_at.isoformat(),
        "account": _dataclass_to_dict(snapshot.account, include_raw) if snapshot.account else None,
        "positions": [_dataclass_to_dict(position, include_raw) for position in snapshot.positions],
        "orders": [_dataclass_to_dict(order, include_raw) for order in snapshot.orders],
        "fills": [_dataclass_to_dict(fill, include_raw) for fill in snapshot.fills],
        "quotes": {symbol: _dataclass_to_dict(quote, include_raw) for symbol, quote in snapshot.quotes.items()},
        "raw": _jsonable(snapshot.raw) if include_raw else {"trading_status": snapshot.raw.get("trading_status")},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read a Futu OpenD snapshot as JSON. Read-only.")
    parser.add_argument("symbols", nargs="*", help="Optional Futu symbols, for example US.AAPL HK.00700.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--trd-market", default="US")
    parser.add_argument("--trd-env", default="REAL")
    parser.add_argument("--security-firm", default="N/A")
    parser.add_argument("--acc-id", type=int, default=0)
    parser.add_argument("--acc-index", type=int, default=0)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--quotes-only", action="store_true", help="Skip account, positions, orders, and fills.")
    parser.add_argument("--strict-trading-errors", action="store_true")
    parser.add_argument("--include-raw", action="store_true", help="Include raw SDK rows in JSON output.")
    parser.add_argument("--counts-only", action="store_true", help="Only print counts and connection status.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source = FutuOpenAPIDataSource(
        host=args.host,
        port=args.port,
        trd_market=args.trd_market,
        trd_env=args.trd_env,
        security_firm=args.security_firm,
        acc_id=args.acc_id,
        acc_index=args.acc_index,
        currency=args.currency,
        include_trading=not args.quotes_only,
        strict_trading_errors=args.strict_trading_errors,
    )
    try:
        snapshot = source.read_snapshot(args.symbols)
    except ReadOnlyDataSourceError as exc:
        parser.exit(2, f"folio-scribe-futu-snapshot: {exc}\n")
    print(json.dumps(snapshot_to_dict(snapshot, include_raw=args.include_raw, counts_only=args.counts_only), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
