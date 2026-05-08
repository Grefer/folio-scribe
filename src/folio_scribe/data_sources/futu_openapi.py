from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from folio_scribe.data_sources.base import ReadOnlyDataSourceError
from folio_scribe.models import AccountSnapshot, BrokerSnapshot, Fill, Order, Position, Quote


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


class FutuOpenAPIDataSource:
    """Read-only Futu OpenAPI data source scaffold.

    The adapter intentionally exposes no order-entry, order-update, or
    unlock-trade helpers. Keep it read-only.
    """

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
                "futu-api is not installed. Install with `pip install 'folio-scribe[futu]'` "
                "or `pip install futu-api`."
            ) from exc
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
                price=_decimal(row.get("last_price")),
                open=_decimal(row.get("open_price")),
                high=_decimal(row.get("high_price")),
                low=_decimal(row.get("low_price")),
                previous_close=_decimal(row.get("prev_close_price")),
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
    """Convert dict rows to positions.

    This helper is used by tests and future Futu account adapters without
    requiring the Futu SDK at import time.
    """

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
