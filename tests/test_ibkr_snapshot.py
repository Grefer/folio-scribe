from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "folio-scribe" / "scripts" / "read_ibkr_snapshot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("read_ibkr_snapshot", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class IBKRSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_decimal_rejects_non_finite_values(self) -> None:
        self.assertIsNone(self.module._decimal("NaN"))
        self.assertIsNone(self.module._decimal("nan"))
        self.assertIsNone(self.module._decimal("Infinity"))
        self.assertEqual(self.module._decimal("236.50"), Decimal("236.50"))

    def test_positions_are_enriched_from_quotes_when_portfolio_values_are_missing(self) -> None:
        position = self.module.Position(
            symbol="US.NVDA",
            quantity=Decimal("10"),
            cost=Decimal("202.5"),
            raw={"account": "U123"},
        )
        quote = self.module.Quote(symbol="US.NVDA", price=Decimal("236"), quote_time="2026-06-30T00:00:00Z")

        enriched = self.module._enrich_positions_with_quotes([position], {"US.NVDA": quote})[0]

        self.assertEqual(enriched.market_value, Decimal("2360"))
        self.assertEqual(enriched.unrealized_pnl, Decimal("335.0"))
        self.assertEqual(enriched.raw["valuation_source"], "ibkr_quote_estimate")
        self.assertEqual(enriched.raw["pnl_source"], "ibkr_quote_estimate")


if __name__ == "__main__":
    unittest.main()
