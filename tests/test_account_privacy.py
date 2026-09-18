from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skill" / "folio-scribe"
SCRIPTS = SKILL_DIR / "scripts"
RAW_ID = re.compile(r"U\d{7,}")

# Fake ids only. U87654321 holds more assets, so it must become 主.
IBKR_SNAPSHOT = {
    "captured_at": "2026-09-17T12:00:00+00:00",
    "account": {"account_id": "U12345678", "total_assets": "100000", "cash": "5000", "currency": "USD"},
    "accounts": {
        "U12345678": {
            "account_id": "U12345678", "total_assets": "100000", "cash": "5000",
            "buying_power": "20000", "leverage": "1.2", "currency": "USD",
        },
        "U87654321": {
            "account_id": "U87654321", "total_assets": "250000", "cash": "7000",
            "buying_power": "50000", "leverage": "1.0", "currency": "USD",
        },
    },
    "positions": [{
        "symbol": "US.AAPL", "name": "AAPL", "quantity": "5", "cost": "200",
        "market_value": "1100", "unrealized_pnl": "100", "currency": "USD",
        "raw": {"account": "U87654321"},
    }],
    "orders": [{
        "symbol": "US.AAPL", "side": "BUY", "quantity": "1", "price": "190",
        "status": "Submitted", "raw": {"account": "U12345678", "order_type": "LMT"},
    }],
    "fills": [],
    "quotes": {},
    "raw": {"trading_status": "ok", "managed_accounts": ["U12345678", "U87654321"]},
}

FUTU_SNAPSHOT = {
    "captured_at": "2026-09-17T12:00:00+00:00",
    "account": {"total_assets": "500000", "cash": "20000", "buying_power": "40000", "currency": "HKD"},
    "positions": [{
        "symbol": "US.NVDA", "name": "NVIDIA", "quantity": "10", "cost": "150",
        "market_value": "1800", "unrealized_pnl": "300", "currency": "USD",
    }],
    "orders": [],
    "fills": [],
    "quotes": {"US.NVDA": {"symbol": "US.NVDA", "name": "NVIDIA", "price": "180"}},
    "raw": {"trading_status": "ok"},
}


def _load_account_alias():
    spec = importlib.util.spec_from_file_location("account_alias", SCRIPTS / "account_alias.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load account_alias.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _clean_env(**overrides: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("FOLIO_SCRIBE_")}
    env.pop("PYTHONPATH", None)
    env.update(overrides)
    return env


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class AccountAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_account_alias()

    def test_largest_total_assets_is_primary(self) -> None:
        aliases = self.module.rank_aliases({"U12345678": 100000, "U87654321": 250000})
        self.assertEqual(aliases, {"U87654321": "U****（主）", "U12345678": "U****（次）"})

    def test_more_than_two_accounts_are_numbered(self) -> None:
        aliases = self.module.rank_aliases({"U1111111": 5, "U2222222": 9, "U3333333": None, "U4444444": 7})
        self.assertEqual(
            aliases,
            {
                "U2222222": "U****（主）",
                "U4444444": "U****（次1）",
                "U1111111": "U****（次2）",
                "U3333333": "U****（次3）",
            },
        )

    def test_single_account_is_primary(self) -> None:
        self.assertEqual(self.module.rank_aliases({"U1234567": 1}), {"U1234567": "U****（主）"})

    def test_mask_catches_ids_next_to_cjk_underscore_and_paper_prefix(self) -> None:
        text = "账户U23456789的净值；acct_U56789012；DU4567890；主账户 U34567890。"
        masked = self.module.mask_account_ids(text)
        self.assertEqual(masked, "账户U****的净值；acct_U****；U****；主账户 U****。")

    def test_mask_leaves_symbols_order_ids_and_aliases_alone(self) -> None:
        text = "US.U260918C25000 | order_id=1234567890 | U****（主） | US.NVDA"
        self.assertEqual(self.module.mask_account_ids(text), text)

    def test_sanitize_snapshot_aliases_every_id_and_orders_primary_first(self) -> None:
        sanitized = self.module.sanitize_snapshot(IBKR_SNAPSHOT)

        self.assertIsNone(RAW_ID.search(json.dumps(sanitized, ensure_ascii=False)))
        self.assertEqual(list(sanitized["accounts"]), ["U****（主）", "U****（次）"])
        self.assertEqual(sanitized["accounts"]["U****（主）"]["total_assets"], "250000")
        self.assertEqual(sanitized["account"]["account_id"], "U****（次）")
        self.assertEqual(sanitized["positions"][0]["raw"]["account"], "U****（主）")
        self.assertEqual(sanitized["raw"]["managed_accounts"], ["U****（次）", "U****（主）"])

    def test_sanitize_snapshot_masks_error_text(self) -> None:
        payload = {"raw": {"trading_error": "account updates for U12345678 request timed out"}}
        sanitized = self.module.sanitize_snapshot(payload)
        self.assertEqual(sanitized["raw"]["trading_error"], "account updates for U**** request timed out")

    def test_placeholder_account_keys_are_not_aliased(self) -> None:
        payload = {"accounts": {"All": {"total_assets": "1"}, "U12345678": {"total_assets": "2"}}}
        sanitized = self.module.sanitize_snapshot(payload)
        self.assertEqual(list(sanitized["accounts"]), ["U****（主）", "All"])


class WriterMaskingTests(unittest.TestCase):
    def test_daily_writer_masks_account_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = tmp_path / "plan.md"
            content.write_text("| IBKR:U12345678 | 100000 |\n账户U87654321已平仓。\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable, str(SCRIPTS / "write_daily_note.py"),
                    "--vault", str(tmp_path / "vault"), "--date", "2026-09-17",
                    "--section", "美股计划", "--content", str(content),
                ],
                cwd=tmp_path, env=_clean_env(), text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            note = (tmp_path / "vault" / "Daily" / "2026-09-17.md").read_text(encoding="utf-8")
            self.assertIn("| IBKR:U**** | 100000 |", note)
            self.assertIn("账户U****已平仓", note)
            self.assertIsNone(RAW_ID.search(note))

    def test_periodic_writer_masks_account_ids(self) -> None:
        spec = importlib.util.spec_from_file_location("write_periodic_summary", SCRIPTS / "write_periodic_summary.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = module.write_summary_note(
                Path(tmp), "weekly", "2026-W38", dt.date(2026, 9, 14), dt.date(2026, 9, 20),
                "# 2026-W38 交易周总结\n\n- 账户U12345678现金偏低。", "test", [],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("账户U****现金偏低", text)
        self.assertIsNone(RAW_ID.search(text))


class WebSyncSecretsGuardTests(unittest.TestCase):
    """sync_tradingweb.sh must refuse to build or deploy when the guard fails."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.skill = self.tmp / "folio-scribe"
        shutil.copytree(SKILL_DIR, self.skill)
        self.deploy_marker = self.tmp / "deployed"
        # Stub the deploy script so no test can reach Vercel.
        _write_executable(
            self.skill / "scripts" / "deploy_web_journal_vercel.sh",
            f"#!/bin/bash\ntouch '{self.deploy_marker}'\n",
        )
        self.vault = self.tmp / "vault"
        (self.vault / "Daily").mkdir(parents=True)
        (self.vault / "Daily" / "2026-09-17.md").write_text(
            "---\ndate: 2026-09-17\ntype: trading-daily\n---\n\n# 2026-09-17 交易日志\n\n## 08:45 港股交易计划\n\n计划。\n",
            encoding="utf-8",
        )
        self.guard_calls = self.tmp / "guard-calls.log"
        (self.vault / "_tools").mkdir()
        (self.vault / "_tools" / "check_secrets.py").write_text(
            "import os, sys\n"
            f"open({str(self.guard_calls)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
            "key = 'GUARD_PATH_EXIT' if '--path' in sys.argv else 'GUARD_EXIT'\n"
            "code = int(os.environ.get(key, '0'))\n"
            "print('!! 发现 1 处敏感信息: U********' if code else 'clean')\n"
            "sys.exit(code)\n",
            encoding="utf-8",
        )
        self.out = self.tmp / "web"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_sync(self, deploy: str = "none", **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.skill / "scripts" / "sync_tradingweb.sh"),
                "--vault", str(self.vault), "--out", str(self.out), "--deploy", deploy,
            ],
            cwd=self.tmp,
            env=_clean_env(FOLIO_SCRIBE_LOG_DIR=str(self.tmp / "logs"), **env),
            text=True, capture_output=True, check=False,
        )

    def test_guard_failure_aborts_before_build(self) -> None:
        result = self.run_sync(deploy="vercel", GUARD_EXIT="1")

        self.assertEqual(result.returncode, 1)
        self.assertIn("secrets guard failed (exit 1)", result.stderr)
        self.assertIn("U********", result.stderr)
        self.assertFalse((self.out / "index.html").exists())
        self.assertFalse(self.deploy_marker.exists())

    def test_missing_guard_fails_closed(self) -> None:
        (self.vault / "_tools" / "check_secrets.py").unlink()

        result = self.run_sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn("secrets guard not found", result.stderr)
        self.assertFalse((self.out / "index.html").exists())

    def test_built_output_is_scanned_before_deploy(self) -> None:
        result = self.run_sync(deploy="vercel", GUARD_PATH_EXIT="1")

        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.out / "index.html").exists())
        self.assertFalse(self.deploy_marker.exists())
        self.assertIn(f"--path {self.out}", self.guard_calls.read_text(encoding="utf-8"))

    def test_clean_guard_builds_and_deploys(self) -> None:
        result = self.run_sync(deploy="vercel")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.out / "index.html").exists())
        self.assertTrue(self.deploy_marker.exists())
        self.assertEqual(len(self.guard_calls.read_text(encoding="utf-8").splitlines()), 2)

    def test_guard_can_be_disabled_explicitly(self) -> None:
        (self.vault / "_tools" / "check_secrets.py").unlink()

        result = self.run_sync(FOLIO_SCRIBE_SECRETS_GUARD="none")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.out / "index.html").exists())


@unittest.skipUnless(sys.platform == "darwin", "run_folio_task.sh requires macOS")
class RunnerFallbackPrivacyTests(unittest.TestCase):
    """End-to-end: the real runner with fake brokers and a failing AI CLI."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.skill = self.tmp / "folio-scribe"
        shutil.copytree(SKILL_DIR, self.skill)
        scripts = self.skill / "scripts"
        _write_executable(
            scripts / "read_futu_snapshot.py",
            f"import json\nprint(json.dumps({FUTU_SNAPSHOT!r}))\n",
        )
        self.prompt_file = self.tmp / "prompt.txt"
        _write_executable(
            self.tmp / "fake-claude",
            "#!/bin/bash\n"
            "while [ $# -gt 0 ]; do\n"
            f"  if [ \"$1\" = -p ]; then printf '%s' \"$2\" > '{self.prompt_file}'; shift 2; continue; fi\n"
            "  shift\n"
            "done\n"
            "echo '{\"is_error\": true, \"result\": \"simulated outage\"}'\n"
            "exit 1\n",
        )
        self.vault = self.tmp / "vault"
        self.logs = self.tmp / "logs"
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()

    def tearDown(self) -> None:
        self.listener.close()
        self._tmp.cleanup()

    def run_us_plan(self, ibkr_script: str) -> subprocess.CompletedProcess[str]:
        _write_executable(self.skill / "scripts" / "read_ibkr_snapshot.py", ibkr_script)
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        return subprocess.run(
            [str(self.skill / "scripts" / "run_folio_task.sh"), "us_plan"],
            cwd=self.tmp,
            env=_clean_env(
                HOME=str(home),
                FOLIO_SCRIBE_VAULT=str(self.vault),
                FOLIO_SCRIBE_LOG_DIR=str(self.logs),
                FOLIO_SCRIBE_NOTE_DATE="2026-09-17",
                FOLIO_SCRIBE_PLAN_PHASE="final",
                FOLIO_SCRIBE_ALLOW_NON_TRADING_DAY="1",
                FOLIO_SCRIBE_OPEND_PORT=str(self.listener.getsockname()[1]),
                FOLIO_SCRIBE_WATCHLIST_MODE="off",
                FOLIO_SCRIBE_IBKR_SNAPSHOT_MODE="gateway",
                FOLIO_SCRIBE_AI_CLI="claude",
                FOLIO_SCRIBE_CLAUDE=str(self.tmp / "fake-claude"),
                FOLIO_SCRIBE_AI_FALLBACK_CLI="none",
                FOLIO_SCRIBE_NOTIFY="0",
            ),
            text=True, capture_output=True, check=False, timeout=120,
        )

    def read_note(self) -> str:
        return (self.vault / "Daily" / "2026-09-17.md").read_text(encoding="utf-8")

    def test_fallback_note_and_prompt_use_aliases(self) -> None:
        result = self.run_us_plan(f"import json\nprint(json.dumps({IBKR_SNAPSHOT!r}))\n")

        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        note = self.read_note()
        self.assertIn("model: runner:deterministic-fallback", note)
        self.assertIn("| IBKR:U****（主） | 250000 | 7000 | 50000 | 1.0 | USD |", note)
        self.assertIn("| IBKR:U****（次） | 100000 | 5000 | 20000 | 1.2 | USD |", note)
        self.assertIsNone(RAW_ID.search(note))

        prompt = self.prompt_file.read_text(encoding="utf-8")
        self.assertIn("- U****（主） | total_assets=250000 USD", prompt)
        self.assertIn("account=U****（主）", prompt)
        self.assertIsNone(RAW_ID.search(prompt))
        self.assertIsNone(RAW_ID.search(result.stdout))

    def test_ibkr_error_text_is_masked_in_note_and_log(self) -> None:
        result = self.run_us_plan(
            "import sys\n"
            "sys.stderr.write('positions request timed out\\n'"
            " 'account updates for U12345678 request timed out\\n')\n"
            "sys.exit(2)\n"
        )

        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        note = self.read_note()
        self.assertIn("account updates for U**** request timed out", note)
        self.assertIsNone(RAW_ID.search(note))
        self.assertIn("account updates for U**** request timed out", result.stdout)
        self.assertIsNone(RAW_ID.search(result.stdout))
        for log in self.logs.glob("*.log"):
            self.assertIsNone(RAW_ID.search(log.read_text(encoding="utf-8")), log.name)


if __name__ == "__main__":
    unittest.main()
