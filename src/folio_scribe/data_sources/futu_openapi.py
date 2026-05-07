from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from folio_scribe.data_sources.base import ReadOnlyDataSourceError
from folio_scribe.models import AccountSnapshot, BrokerSnapshot, Position, Quote


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


class FutuOpenAPIDataSource:
    """Read-only Futu OpenAPI data source scaffold.

    The adapter intentionally exposes no order-entry, order-update, or
    unlock-trade helpers. Keep it read-only.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 11111) -> None:
        self.host = host
        self.port = port

    def read_snapshot(self, symbols: Sequence[str] = ()) -> BrokerSnapshot:
        futu = self._load_futu()
        quotes = self._read_quotes(futu, symbols) if symbols else {}

        # Account/position reads are left conservative until account market,
        # firm, and permissions are provided by config. The shape is ready for
        # the next milestone.
        return BrokerSnapshot(
            captured_at=datetime.now(timezone.utc),
            account=AccountSnapshot(raw={"source": "futu_openapi", "status": "quote_only"}),
            positions=[],
            quotes=quotes,
            raw={"host": self.host, "port": self.port},
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
                quantity=_decimal(row.get("qty") or row.get("quantity")),
                cost=_decimal(row.get("cost_price") or row.get("cost")),
                market_value=_decimal(row.get("market_val") or row.get("market_value")),
                unrealized_pnl=_decimal(row.get("pl_val") or row.get("unrealized_pnl")),
                currency=row.get("currency"),
                raw=dict(row),
            )
        )
    return positions
