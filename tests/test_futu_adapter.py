from __future__ import annotations

import unittest
from decimal import Decimal

from folio_scribe.data_sources.futu_openapi import (
    account_from_rows,
    fills_from_rows,
    orders_from_rows,
    positions_from_rows,
)


class FutuAdapterTests(unittest.TestCase):
    def test_positions_from_rows(self) -> None:
        positions = positions_from_rows(
            [
                {
                    "code": "US.QS",
                    "stock_name": "QuantumScape",
                    "qty": "100",
                    "cost_price": "14.598",
                    "market_val": "800",
                    "pl_val": "-659.81",
                    "currency": "USD",
                }
            ]
        )

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "US.QS")
        self.assertEqual(positions[0].quantity, Decimal("100"))
        self.assertEqual(positions[0].cost, Decimal("14.598"))

    def test_account_from_rows(self) -> None:
        account = account_from_rows(
            [
                {
                    "total_assets": "100000.50",
                    "cash": "12000",
                    "power": "35000",
                    "currency": "USD",
                }
            ]
        )

        self.assertEqual(account.total_assets, Decimal("100000.50"))
        self.assertEqual(account.cash, Decimal("12000"))
        self.assertEqual(account.buying_power, Decimal("35000"))
        self.assertEqual(account.currency, "USD")

    def test_orders_from_rows(self) -> None:
        orders = orders_from_rows(
            [
                {
                    "code": "US.AAPL",
                    "trd_side": "BUY",
                    "qty": "10",
                    "price": "280.5",
                    "order_status": "SUBMITTED",
                    "create_time": "2026-05-07 21:35:00",
                }
            ]
        )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].symbol, "US.AAPL")
        self.assertEqual(orders[0].side, "BUY")
        self.assertEqual(orders[0].quantity, Decimal("10"))
        self.assertEqual(orders[0].status, "SUBMITTED")
        self.assertIsNotNone(orders[0].submitted_at)

    def test_fills_from_rows(self) -> None:
        fills = fills_from_rows(
            [
                {
                    "code": "US.AAPL",
                    "trd_side": "SELL",
                    "qty": "5",
                    "price": "287.51",
                    "create_time": "2026-05-07 22:01:00",
                }
            ]
        )

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].symbol, "US.AAPL")
        self.assertEqual(fills[0].side, "SELL")
        self.assertEqual(fills[0].quantity, Decimal("5"))
        self.assertEqual(fills[0].price, Decimal("287.51"))
        self.assertIsNotNone(fills[0].filled_at)

    def test_zero_numeric_values_are_preserved(self) -> None:
        account = account_from_rows(
            [
                {
                    "total_assets": 0,
                    "cash": 0,
                    "power": 0,
                    "today_pl_val": 0,
                }
            ]
        )
        positions = positions_from_rows(
            [
                {
                    "code": "US.ZERO",
                    "qty": 0,
                    "cost_price": 0,
                    "market_val": 0,
                    "pl_val": 0,
                    "realized_pl": 0,
                }
            ]
        )
        orders = orders_from_rows([{"code": "US.ZERO", "qty": 0, "price": 0}])
        fills = fills_from_rows([{"code": "US.ZERO", "qty": 0, "price": 0}])

        self.assertEqual(account.daily_pnl, Decimal("0"))
        self.assertEqual(account.buying_power, Decimal("0"))
        self.assertEqual(positions[0].quantity, Decimal("0"))
        self.assertEqual(positions[0].cost, Decimal("0"))
        self.assertEqual(positions[0].market_value, Decimal("0"))
        self.assertEqual(positions[0].unrealized_pnl, Decimal("0"))
        self.assertEqual(positions[0].realized_pnl, Decimal("0"))
        self.assertEqual(orders[0].quantity, Decimal("0"))
        self.assertEqual(orders[0].price, Decimal("0"))
        self.assertEqual(fills[0].quantity, Decimal("0"))
        self.assertEqual(fills[0].price, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
