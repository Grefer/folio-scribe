#!/usr/bin/env python3
"""Insert or update a daily trading plan/review section in an Obsidian note.

This is a thin wrapper that delegates to the canonical implementation in
``folio_scribe.journal.obsidian``.  Keep all logic there so we have a
single source of truth for section markers, default templates, and the
replace-section algorithm.
"""

from folio_scribe.journal.obsidian import main

if __name__ == "__main__":
    raise SystemExit(main())
