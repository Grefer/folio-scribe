"""Keep broker account ids out of journal notes, which are often published.

Mirrors the masking in the bundled skill's ``scripts/account_alias.py``. The
package cannot import from the skill folder, so keep the two patterns in sync.
"""

from __future__ import annotations

import re


ALIAS_PREFIX = "U****"

# IBKR live (U…) and paper (DU…) account ids. Boundaries are ASCII-only so an
# id glued to CJK text or an underscore ("账户U1234567", "acct_U1234567") still
# matches; a plain \b would miss both.
ACCOUNT_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])D?U\d{7,}(?!\d)")


def mask_account_ids(text: str) -> str:
    """Replace every IBKR-style account id in *text* with ``U****``."""
    return ACCOUNT_ID_PATTERN.sub(ALIAS_PREFIX, text)
