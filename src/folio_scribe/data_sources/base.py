from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from folio_scribe.models import BrokerSnapshot


class ReadOnlyDataSourceError(RuntimeError):
    """Raised when a broker data source cannot return read-only data."""


class BrokerDataSource(Protocol):
    """Read-only broker data source."""

    def read_snapshot(self, symbols: Sequence[str] = ()) -> BrokerSnapshot:
        """Return normalized broker state without mutating the account."""
