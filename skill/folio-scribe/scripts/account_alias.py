#!/usr/bin/env python3
"""Replace broker account ids with stable aliases before they reach notes.

Daily/Weekly/Monthly notes are built into the published web journal, so a raw
account number must never be written there. Accounts are aliased by size: the
one with the largest total assets (net liquidation) is ``U****（主）``, the
other is ``U****（次）``, and with more than two accounts the rest become
``U****（次1）``, ``U****（次2）`` … in descending order. Ids that cannot be
ranked, such as one an AI read straight from a broker app, become ``U****``.

This bundled script is stdlib-only so the skill folder stays self-contained.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ALIAS_PREFIX = "U****"

# IBKR live (U…) and paper (DU…) account ids. Boundaries are ASCII-only so an
# id glued to CJK text or an underscore ("账户U1234567", "acct_U1234567") still
# matches; a plain \b would miss both.
ACCOUNT_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])D?U\d{7,}(?!\d)")

# Shape a snapshot value must have to be treated as an account id (U1234567,
# DU1234567, F1234567, …). Keeps placeholders such as "All" or bare numbers
# from being aliased and then replaced wherever they appear in prose.
_ACCOUNT_ID_SHAPE = re.compile(r"[A-Za-z]{1,3}\d{5,}")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def snapshot_account_totals(
    payload: Mapping[str, Any],
    extra_ids: Iterable[str] = (),
) -> dict[str, Decimal | None]:
    """Collect every account id a broker snapshot mentions, with total assets when known."""
    totals: dict[str, Decimal | None] = {}

    def add(account_id: Any, total: Any = None) -> None:
        key = str(account_id or "").strip()
        if not _ACCOUNT_ID_SHAPE.fullmatch(key):
            return
        if totals.get(key) is None:
            totals[key] = _to_decimal(total)

    accounts = payload.get("accounts")
    if isinstance(accounts, Mapping):
        for account_id, item in accounts.items():
            item = item if isinstance(item, Mapping) else {}
            add(account_id, item.get("total_assets"))
            add(item.get("account_id"), item.get("total_assets"))

    account = payload.get("account")
    if isinstance(account, Mapping):
        add(account.get("account_id"), account.get("total_assets"))

    raw = payload.get("raw")
    if isinstance(raw, Mapping):
        managed = raw.get("managed_accounts") or []
        if isinstance(managed, str):
            managed = managed.split(",")
        for account_id in managed:
            add(account_id)

    for key in ("positions", "orders", "fills"):
        for item in payload.get(key) or []:
            if isinstance(item, Mapping) and isinstance(item.get("raw"), Mapping):
                add(item["raw"].get("account"))

    for account_id in extra_ids:
        add(account_id)
    return totals


def rank_aliases(totals: Mapping[str, Decimal | None]) -> dict[str, str]:
    """Alias ids by total assets, largest first; ids without a total rank last."""
    ranked = sorted(
        totals,
        key=lambda account_id: (
            totals[account_id] is None,
            -(totals[account_id] or 0),
            account_id,
        ),
    )
    aliases: dict[str, str] = {}
    for rank, account_id in enumerate(ranked):
        if rank == 0:
            suffix = "主"
        elif len(ranked) == 2:
            suffix = "次"
        else:
            suffix = f"次{rank}"
        aliases[account_id] = f"{ALIAS_PREFIX}（{suffix}）"
    return aliases


def mask_account_ids(text: str, aliases: Mapping[str, str] | None = None) -> str:
    """Swap known ids for their aliases, then mask any other IBKR-style id as ``U****``."""
    if aliases:
        known = sorted(aliases, key=len, reverse=True)
        pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:" + "|".join(map(re.escape, known)) + r")(?![A-Za-z0-9])"
        )
        text = pattern.sub(lambda match: aliases[match.group(0)], text)
    return ACCOUNT_ID_PATTERN.sub(ALIAS_PREFIX, text)


def _mask_tree(value: Any, aliases: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mask_account_ids(value, aliases)
    if isinstance(value, Mapping):
        return {_mask_tree(key, aliases): _mask_tree(item, aliases) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_tree(item, aliases) for item in value]
    return value


def sanitize_snapshot(payload: Mapping[str, Any], extra_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Return a copy of a broker snapshot with every account id replaced by its alias.

    ``accounts`` is re-keyed by alias and ordered 主 first, so anything that
    formats the snapshot (prompts, fallback tables) only ever sees aliases.
    """
    aliases = rank_aliases(snapshot_account_totals(payload, extra_ids))
    rank = {account_id: index for index, account_id in enumerate(aliases)}
    sanitized = dict(payload)
    accounts = payload.get("accounts")
    if isinstance(accounts, Mapping):
        sanitized["accounts"] = dict(
            sorted(accounts.items(), key=lambda item: rank.get(str(item[0]).strip(), len(rank)))
        )
    return _mask_tree(sanitized, aliases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replace broker account ids with 主/次 aliases.")
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "sanitize-snapshot",
        help="Rewrite a broker snapshot JSON file in place with every account id aliased.",
    )
    snapshot.add_argument("path", type=Path)
    snapshot.add_argument(
        "--account-id",
        action="append",
        default=[],
        help="Extra known account id to alias, e.g. the one requested from the broker.",
    )
    commands.add_parser("mask", help="Mask account ids in stdin and write the result to stdout.")
    args = parser.parse_args(argv)

    if args.command == "mask":
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(mask_account_ids(text).encode("utf-8"))
        return 0

    payload = json.loads(args.path.read_text(encoding="utf-8", errors="replace"))
    sanitized = sanitize_snapshot(payload, args.account_id)
    args.path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
