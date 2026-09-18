#!/usr/bin/env python3
"""Read an IBKR TWS / IB Gateway snapshot as JSON.

This bundled script is self-contained so the skill folder can be copied into
another AI client without also installing the repository package. It remains
read-only: it connects with readonly=True and exposes account, position, open
order, fill, and optional quote reads only.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


class ReadOnlyDataSourceError(RuntimeError):
    """Raised when the broker data source cannot return read-only data."""


Money = Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str | None = None
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
    order_id: str | None = None
    side: str | None = None
    quantity: Decimal | None = None
    price: Money | None = None
    status: str | None = None
    filled_quantity: Decimal | None = None
    filled_avg_price: Money | None = None
    submitted_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Fill:
    symbol: str
    deal_id: str | None = None
    order_id: str | None = None
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
    accounts: dict[str, AccountSnapshot] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    quotes: dict[str, Quote] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
        return None
    try:
        number = Decimal(text)
    except Exception:
        return None
    return number if number.is_finite() else None


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
    return str(value)


def _dataclass_to_dict(value: Any, include_raw: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_info in dataclasses.fields(value):
        if field_info.name == "raw" and not include_raw:
            continue
        payload[field_info.name] = _jsonable(getattr(value, field_info.name))
    return payload


def _contract_symbol(contract: Any) -> str:
    currency = getattr(contract, "currency", None)
    exchange = getattr(contract, "primaryExchange", None) or getattr(contract, "exchange", None)
    symbol = getattr(contract, "symbol", None) or getattr(contract, "localSymbol", None) or ""
    if exchange in {"SEHK", "HKSE"} or currency == "HKD":
        return f"HK.{symbol}"
    if currency == "USD":
        return f"US.{symbol}"
    return str(symbol)


def _contract_name(contract: Any) -> str | None:
    local_symbol = getattr(contract, "localSymbol", None)
    trading_class = getattr(contract, "tradingClass", None)
    if local_symbol and trading_class and local_symbol != trading_class:
        return f"{local_symbol} {trading_class}"
    return local_symbol or trading_class or getattr(contract, "symbol", None)


def _account_values_by_account(values: list[Any]) -> dict[str, dict[str, dict[str, str]]]:
    accounts: dict[str, dict[str, dict[str, str]]] = {}
    for value in values:
        account = str(getattr(value, "account", "") or "")
        tag = str(getattr(value, "tag", "") or "")
        if not account or not tag:
            continue
        accounts.setdefault(account, {})[tag] = {
            "value": str(getattr(value, "value", "") or ""),
            "currency": str(getattr(value, "currency", "") or ""),
        }
    return accounts


def _account_from_tags(account_id: str, tags: dict[str, dict[str, str]]) -> AccountSnapshot:
    def tag_value(*names: str) -> str | None:
        for name in names:
            value = tags.get(name, {}).get("value")
            if value not in (None, ""):
                return value
        return None

    def tag_currency(*names: str) -> str | None:
        for name in names:
            currency = tags.get(name, {}).get("currency")
            if currency not in (None, ""):
                return currency
        return None

    net_liq = _decimal(tag_value("NetLiquidation"))
    gross = _decimal(tag_value("GrossPositionValue"))
    equity = _decimal(tag_value("EquityWithLoanValue"))
    leverage = None
    if gross is not None and equity not in (None, Decimal("0")):
        leverage = gross / equity

    return AccountSnapshot(
        account_id=account_id,
        total_assets=net_liq,
        daily_pnl=_decimal(tag_value("RealizedPnL", "UnrealizedPnL")),
        cash=_decimal(tag_value("TotalCashValue", "CashBalance")),
        buying_power=_decimal(tag_value("BuyingPower", "AvailableFunds")),
        leverage=leverage,
        currency=tag_currency("NetLiquidation", "TotalCashValue", "BuyingPower"),
        raw=tags,
    )


def _positions_from_portfolio(portfolio_items: list[Any], position_items: list[Any]) -> list[Position]:
    by_key: dict[tuple[str, str], Position] = {}

    for item in portfolio_items:
        contract = getattr(item, "contract", None)
        if contract is None:
            continue
        account = str(getattr(item, "account", "") or "")
        symbol = _contract_symbol(contract)
        key = (account, symbol)
        by_key[key] = Position(
            symbol=symbol,
            name=_contract_name(contract),
            quantity=_decimal(getattr(item, "position", None)),
            cost=_decimal(getattr(item, "averageCost", None)),
            market_value=_decimal(getattr(item, "marketValue", None)),
            unrealized_pnl=_decimal(getattr(item, "unrealizedPNL", None)),
            realized_pnl=_decimal(getattr(item, "realizedPNL", None)),
            currency=getattr(contract, "currency", None),
            raw={
                "account": account,
                "con_id": getattr(contract, "conId", None),
                "exchange": getattr(contract, "exchange", None),
                "primary_exchange": getattr(contract, "primaryExchange", None),
                "security_type": getattr(contract, "secType", None),
                "market_price": str(getattr(item, "marketPrice", "")),
            },
        )

    for item in position_items:
        contract = getattr(item, "contract", None)
        if contract is None:
            continue
        account = str(getattr(item, "account", "") or "")
        symbol = _contract_symbol(contract)
        key = (account, symbol)
        if key in by_key:
            continue
        by_key[key] = Position(
            symbol=symbol,
            name=_contract_name(contract),
            quantity=_decimal(getattr(item, "position", None)),
            cost=_decimal(getattr(item, "avgCost", None)),
            currency=getattr(contract, "currency", None),
            raw={
                "account": account,
                "con_id": getattr(contract, "conId", None),
                "exchange": getattr(contract, "exchange", None),
                "primary_exchange": getattr(contract, "primaryExchange", None),
                "security_type": getattr(contract, "secType", None),
            },
        )

    return list(by_key.values())


def _orders_from_trades(trades: list[Any]) -> list[Order]:
    orders: list[Order] = []
    for trade in trades:
        contract = getattr(trade, "contract", None)
        order = getattr(trade, "order", None)
        status = getattr(trade, "orderStatus", None)
        if contract is None or order is None:
            continue
        orders.append(
            Order(
                symbol=_contract_symbol(contract),
                order_id=str(getattr(order, "orderId", "") or "") or None,
                side=getattr(order, "action", None),
                quantity=_decimal(getattr(order, "totalQuantity", None)),
                price=_decimal(getattr(order, "lmtPrice", None)),
                status=getattr(status, "status", None),
                filled_quantity=_decimal(getattr(status, "filled", None)),
                filled_avg_price=_decimal(getattr(status, "avgFillPrice", None)),
                raw={
                    "account": getattr(order, "account", None),
                    "perm_id": getattr(order, "permId", None),
                    "order_type": getattr(order, "orderType", None),
                    "time_in_force": getattr(order, "tif", None),
                    "remaining": str(getattr(status, "remaining", "")),
                },
            )
        )
    return orders


def _fills_from_fills(fills: list[Any]) -> list[Fill]:
    output: list[Fill] = []
    for fill in fills:
        contract = getattr(fill, "contract", None)
        execution = getattr(fill, "execution", None)
        if contract is None or execution is None:
            continue
        output.append(
            Fill(
                symbol=_contract_symbol(contract),
                deal_id=str(getattr(execution, "execId", "") or "") or None,
                order_id=str(getattr(execution, "orderId", "") or "") or None,
                side=getattr(execution, "side", None),
                quantity=_decimal(getattr(execution, "shares", None)),
                price=_decimal(getattr(execution, "price", None)),
                filled_at=getattr(execution, "time", None),
                raw={
                    "account": getattr(execution, "acctNumber", None),
                    "exchange": getattr(execution, "exchange", None),
                    "commission_report": _jsonable(getattr(fill, "commissionReport", None)),
                },
            )
        )
    return output


def _contract_for_symbol(symbol: str) -> Any:
    from ib_insync import Stock  # type: ignore[import-not-found]

    if symbol.startswith("US."):
        return Stock(symbol[3:], "SMART", "USD")
    if symbol.startswith("HK."):
        raw = symbol[3:].lstrip("0") or symbol[3:]
        return Stock(raw, "SEHK", "HKD")
    return Stock(symbol, "SMART", "USD")


def _unique_symbols(symbols: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = str(symbol or "").strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _position_symbols(positions: list[Position]) -> list[str]:
    return _unique_symbols([position.symbol for position in positions])


def _best_quote_price(ticker: Any) -> tuple[Decimal | None, str | None]:
    last = _decimal(getattr(ticker, "last", None))
    if last is not None:
        return last, "last"

    market_price = None
    if hasattr(ticker, "marketPrice"):
        try:
            market_price = _decimal(ticker.marketPrice())
        except Exception:
            market_price = None
    if market_price is not None:
        return market_price, "market_price"

    bid = _decimal(getattr(ticker, "bid", None))
    ask = _decimal(getattr(ticker, "ask", None))
    if bid is not None and ask is not None and ask >= bid:
        return (bid + ask) / Decimal("2"), "bid_ask_mid"

    close = _decimal(getattr(ticker, "close", None))
    if close is not None:
        return close, "close"
    if bid is not None:
        return bid, "bid"
    if ask is not None:
        return ask, "ask"
    return None, None


def _quote_from_ticker(requested_symbol: str, ticker: Any, market_data_type: str) -> Quote:
    contract = getattr(ticker, "contract", None)
    symbol = requested_symbol if requested_symbol else _contract_symbol(contract)
    bid = _decimal(getattr(ticker, "bid", None))
    ask = _decimal(getattr(ticker, "ask", None))
    close = _decimal(getattr(ticker, "close", None))
    price, price_source = _best_quote_price(ticker)
    return Quote(
        symbol=symbol,
        name=_contract_name(contract) if contract else None,
        price=price,
        quote_time=datetime.now(timezone.utc).isoformat(),
        previous_close=close,
        bid=bid,
        ask=ask,
        volume=_decimal(getattr(ticker, "volume", None)),
        currency=getattr(contract, "currency", None) if contract else None,
        raw={
            "market_data_type": market_data_type,
            "market_price": str(ticker.marketPrice()) if hasattr(ticker, "marketPrice") else None,
            "price_source": price_source,
            "halted": str(getattr(ticker, "halted", "")),
        },
    )


def _quotes_from_pairs(ib: Any, qualified_pairs: list[tuple[str, Any]], market_data_type: str) -> dict[str, Quote]:
    if not qualified_pairs:
        return {}
    tickers = ib.reqTickers(*(contract for _, contract in qualified_pairs))
    return {
        requested_symbol: _quote_from_ticker(requested_symbol, ticker, market_data_type)
        for (requested_symbol, _contract), ticker in zip(qualified_pairs, tickers, strict=False)
    }


def _quotes_from_symbols(ib: Any, symbols: list[str]) -> dict[str, Quote]:
    requested_symbols = _unique_symbols(symbols)
    if not requested_symbols:
        return {}

    qualified_pairs: list[tuple[str, Any]] = []
    for symbol in requested_symbols:
        contract = _contract_for_symbol(symbol)
        try:
            qualified = ib.qualifyContracts(contract)
        except Exception:
            continue
        if qualified:
            qualified_pairs.append((symbol, qualified[0]))

    if not qualified_pairs:
        return {}

    quotes = _quotes_from_pairs(ib, qualified_pairs, "default")
    missing_pairs = [
        pair for pair in qualified_pairs
        if quotes.get(pair[0]) is None or quotes[pair[0]].price is None
    ]
    if missing_pairs:
        for market_data_type, code in (("delayed", 3), ("delayed_frozen", 4)):
            try:
                ib.reqMarketDataType(code)
            except Exception:
                continue
            retry_quotes = _quotes_from_pairs(ib, missing_pairs, market_data_type)
            for symbol, quote in retry_quotes.items():
                if quote.price is not None or symbol not in quotes:
                    quotes[symbol] = quote
            missing_pairs = [
                pair for pair in missing_pairs
                if quotes.get(pair[0]) is None or quotes[pair[0]].price is None
            ]
            if not missing_pairs:
                break
    return quotes


def _enrich_positions_with_quotes(positions: list[Position], quotes: dict[str, Quote]) -> list[Position]:
    enriched: list[Position] = []
    for position in positions:
        quote = quotes.get(position.symbol.upper()) or quotes.get(position.symbol)
        price = quote.price if quote else None
        market_value = position.market_value
        unrealized_pnl = position.unrealized_pnl
        raw = dict(position.raw)

        if price is not None and position.quantity is not None:
            if market_value is None:
                market_value = price * position.quantity
                raw["valuation_source"] = "ibkr_quote_estimate"
                raw["valuation_price"] = str(price)
                raw["valuation_time"] = quote.quote_time if quote else None
            if unrealized_pnl is None and position.cost is not None:
                unrealized_pnl = (price - position.cost) * position.quantity
                raw["pnl_source"] = "ibkr_quote_estimate"

        enriched.append(
            dataclasses.replace(
                position,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                raw=raw,
            )
        )
    return enriched


class IBKRDataSource:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4001,
        client_id: int = 91,
        timeout: float = 45,
        account: str = "",
        readonly: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.account = account
        self.readonly = readonly

    def read_snapshot(self, symbols: list[str] | None = None) -> BrokerSnapshot:
        ib_module = self._load_ib_insync()
        ib = ib_module.IB()
        try:
            ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                timeout=self.timeout,
                readonly=self.readonly,
                account=self.account,
            )
            account_values = ib.accountSummary(account=self.account)
            account_tags = _account_values_by_account(account_values)
            accounts = {
                account_id: _account_from_tags(account_id, tags)
                for account_id, tags in account_tags.items()
            }
            selected_account = self.account or (next(iter(accounts)) if accounts else None)
            positions = _positions_from_portfolio(ib.portfolio(), ib.positions())
            orders = _orders_from_trades(ib.openTrades())
            fills = _fills_from_fills(ib.fills())
            quote_symbols = _unique_symbols([*(symbols or []), *_position_symbols(positions)])
            quotes = _quotes_from_symbols(ib, quote_symbols)
            positions = _enrich_positions_with_quotes(positions, quotes)
            return BrokerSnapshot(
                captured_at=datetime.now(timezone.utc),
                account=accounts.get(selected_account) if selected_account else None,
                accounts=accounts,
                positions=positions,
                orders=orders,
                fills=fills,
                quotes=quotes,
                raw={
                    "source": "ibkr_tws_gateway",
                    "host": self.host,
                    "port": self.port,
                    "client_id": self.client_id,
                    "readonly": self.readonly,
                    "server_version": ib.client.serverVersion(),
                    "managed_accounts": ib.managedAccounts(),
                    "trading_status": "ok",
                },
            )
        except Exception as exc:
            raise ReadOnlyDataSourceError(f"IBKR snapshot failed: {exc}") from exc
        finally:
            if ib.isConnected():
                ib.disconnect()

    def _load_ib_insync(self) -> Any:
        try:
            import ib_insync  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ReadOnlyDataSourceError(
                "ib_insync is not installed. Install with `python3 -m pip install --user ib_insync`."
            ) from exc
        except Exception as exc:
            raise ReadOnlyDataSourceError(f"ib_insync failed to initialize: {exc}") from exc
        return ib_insync


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
                "accounts": len(snapshot.accounts),
                "quotes": len(snapshot.quotes),
                "positions": len(snapshot.positions),
                "orders": len(snapshot.orders),
                "fills": len(snapshot.fills),
            },
            "trading_status": snapshot.raw.get("trading_status"),
            "managed_accounts": snapshot.raw.get("managed_accounts"),
        }

    return {
        "captured_at": snapshot.captured_at.isoformat(),
        "account": _dataclass_to_dict(snapshot.account, include_raw) if snapshot.account else None,
        "accounts": {
            account_id: _dataclass_to_dict(account, include_raw)
            for account_id, account in snapshot.accounts.items()
        },
        "positions": [_dataclass_to_dict(position, include_raw) for position in snapshot.positions],
        "orders": [_dataclass_to_dict(order, include_raw) for order in snapshot.orders],
        "fills": [_dataclass_to_dict(fill, include_raw) for fill in snapshot.fills],
        "quotes": {symbol: _dataclass_to_dict(quote, include_raw) for symbol, quote in snapshot.quotes.items()},
        "raw": _jsonable(snapshot.raw) if include_raw else {"trading_status": snapshot.raw.get("trading_status")},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read an IBKR TWS / IB Gateway snapshot as JSON. Read-only.")
    parser.add_argument("symbols", nargs="*", help="Optional symbols for quote snapshots, e.g. US.NVDA US.GOOGL.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=91)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--account", default="", help="Optional IBKR account id. Empty means first managed account.")
    parser.add_argument("--include-raw", action="store_true", help="Include raw SDK-derived fields in JSON output.")
    parser.add_argument("--counts-only", action="store_true", help="Only print counts and connection status.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source = IBKRDataSource(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        timeout=args.timeout,
        account=args.account,
        readonly=True,
    )
    try:
        snapshot = source.read_snapshot(args.symbols)
    except ReadOnlyDataSourceError as exc:
        parser.exit(2, f"folio-scribe-ibkr-snapshot: {exc}\n")
    print(json.dumps(snapshot_to_dict(snapshot, include_raw=args.include_raw, counts_only=args.counts_only), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
