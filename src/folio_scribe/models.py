from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


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
    price: Money | None = None
    open: Money | None = None
    high: Money | None = None
    low: Money | None = None
    previous_close: Money | None = None
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
