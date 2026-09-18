from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from folio_scribe.privacy import ACCOUNT_ID_PATTERN, ALIAS_PREFIX, mask_account_ids


SKILL_ACCOUNT_ALIAS = Path(__file__).resolve().parents[1] / "skill" / "folio-scribe" / "scripts" / "account_alias.py"


class MaskAccountIdsTests(unittest.TestCase):
    # Fake ids only.

    def test_masks_id_adjacent_to_cjk_text(self) -> None:
        self.assertEqual(mask_account_ids("账户U12345678的净值"), "账户U****的净值")

    def test_masks_underscore_adjacent_id(self) -> None:
        self.assertEqual(mask_account_ids("acct_U12345678"), "acct_U****")

    def test_masks_paper_account_id(self) -> None:
        self.assertEqual(mask_account_ids("paper DU1234567 only"), "paper U**** only")

    def test_masks_id_in_table_cell(self) -> None:
        self.assertEqual(mask_account_ids("| IBKR:U12345678 | 100000 |"), "| IBKR:U**** | 100000 |")

    def test_leaves_option_codes_order_ids_and_aliases_untouched(self) -> None:
        for text in (
            "US.U260918C25000",
            "order_id=1234567890 | deal_id=9876543210",
            "U****（主） / U****（次）",
            "US.NVDA HK.00700",
        ):
            with self.subTest(text=text):
                self.assertEqual(mask_account_ids(text), text)


class SkillParityTests(unittest.TestCase):
    """The bundled skill keeps its own copy of the mask; the two must not drift."""

    def test_pattern_matches_bundled_skill(self) -> None:
        spec = importlib.util.spec_from_file_location("skill_account_alias", SKILL_ACCOUNT_ALIAS)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load {SKILL_ACCOUNT_ALIAS}")
        skill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill)

        self.assertEqual(ACCOUNT_ID_PATTERN.pattern, skill.ACCOUNT_ID_PATTERN.pattern)
        self.assertEqual(ALIAS_PREFIX, skill.ALIAS_PREFIX)


if __name__ == "__main__":
    unittest.main()
