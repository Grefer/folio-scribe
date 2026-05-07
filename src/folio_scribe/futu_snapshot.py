from __future__ import annotations

import argparse
import dataclasses
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from folio_scribe.data_sources.base import ReadOnlyDataSourceError
from folio_scribe.data_sources.futu_openapi import FutuOpenAPIDataSource
from folio_scribe.models import BrokerSnapshot


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
    for field in dataclasses.fields(value):
        if field.name == "raw" and not include_raw:
            continue
        payload[field.name] = _jsonable(getattr(value, field.name))
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
