from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from folio_scribe.futu_snapshot import snapshot_to_dict
from folio_scribe.models import AccountSnapshot, BrokerSnapshot, Fill, Order, Position, Quote


class FutuSnapshotCliTests(unittest.TestCase):
    def test_snapshot_to_dict_serializes_public_fields(self) -> None:
        snapshot = BrokerSnapshot(
            captured_at=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
            account=AccountSnapshot(total_assets=Decimal("1000.50"), raw={"secret": "hidden"}),
            positions=[Position(symbol="US.AAPL", quantity=Decimal("2"), raw={"source": "futu"})],
            orders=[Order(symbol="US.AAPL", quantity=Decimal("1"), raw={"source": "futu"})],
            fills=[Fill(symbol="US.AAPL", price=Decimal("180.25"), raw={"source": "futu"})],
            quotes={"US.AAPL": Quote(symbol="US.AAPL", price=Decimal("181.10"), raw={"source": "futu"})},
            raw={"trading_status": "ok", "host": "127.0.0.1"},
        )

        payload = snapshot_to_dict(snapshot)

        self.assertEqual(payload["account"]["total_assets"], "1000.50")
        self.assertEqual(payload["positions"][0]["symbol"], "US.AAPL")
        self.assertNotIn("raw", payload["account"])
        self.assertEqual(payload["raw"], {"trading_status": "ok"})

    def test_counts_only_snapshot(self) -> None:
        snapshot = BrokerSnapshot(
            captured_at=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
            positions=[Position(symbol="US.AAPL")],
            orders=[Order(symbol="US.AAPL")],
            fills=[Fill(symbol="US.AAPL")],
            quotes={"US.AAPL": Quote(symbol="US.AAPL")},
            raw={"trading_status": "error", "trading_error": "not unlocked"},
        )

        payload = snapshot_to_dict(snapshot, counts_only=True)

        self.assertEqual(payload["counts"], {"quotes": 1, "positions": 1, "orders": 1, "fills": 1})
        self.assertEqual(payload["trading_status"], "error")
        self.assertTrue(payload["has_trading_error"])


if __name__ == "__main__":
    unittest.main()
