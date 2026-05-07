from __future__ import annotations

import unittest
from decimal import Decimal

from folio_scribe.data_sources.futu_openapi import positions_from_rows


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


if __name__ == "__main__":
    unittest.main()
