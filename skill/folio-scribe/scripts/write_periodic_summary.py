#!/usr/bin/env python3
"""Generate weekly or monthly trading review notes from Daily journals.

The script is bundled and self-contained so it can run from a copied
folio-scribe skill folder. It reads Daily notes, asks the configured AI CLI to
write a higher-level review, writes Weekly/ or Monthly/ Markdown, then
optionally refreshes the TradingWeb dashboard.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_build_web_journal_module() -> Any:
    import importlib.util

    script = SCRIPT_DIR / "build_web_journal.py"
    spec = importlib.util.spec_from_file_location("build_web_journal", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_web_journal"] = module
    spec.loader.exec_module(module)
    return module


build_web_journal = load_build_web_journal_module()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def previous_month(today: dt.date) -> tuple[int, int]:
    year = today.year
    month = today.month - 1
    if month == 0:
        year -= 1
        month = 12
    return year, month


def month_range(year: int, month: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def last_trading_day_of_month(year: int, month: int) -> dt.date:
    day = month_range(year, month)[1]
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def resolve_period(
    period: str,
    date: dt.date,
    week: str | None = None,
    month: str | None = None,
) -> tuple[str, dt.date, dt.date]:
    if period == "weekly":
        if week:
            match = re.fullmatch(r"(\d{4})-W(\d{2})", week)
            if not match:
                raise ValueError("--week must be in YYYY-Www format, e.g. 2026-W21")
            iso_year = int(match.group(1))
            iso_week = int(match.group(2))
            start = dt.date.fromisocalendar(iso_year, iso_week, 1)
        else:
            iso_year, iso_week, _ = date.isocalendar()
            start = dt.date.fromisocalendar(iso_year, iso_week, 1)
        end = start + dt.timedelta(days=6)
        return f"{start.isocalendar().year}-W{start.isocalendar().week:02d}", start, end

    if period == "monthly":
        if month:
            match = re.fullmatch(r"(\d{4})-(\d{2})", month)
            if not match:
                raise ValueError("--month must be in YYYY-MM format, e.g. 2026-05")
            year = int(match.group(1))
            month_number = int(match.group(2))
        elif date.day == 1:
            year, month_number = previous_month(date)
        else:
            year, month_number = date.year, date.month
        start, end = month_range(year, month_number)
        return f"{year:04d}-{month_number:02d}", start, end

    raise ValueError("period must be weekly or monthly")


def read_rules_context(vault: Path, limit: int = 24000) -> str:
    rules_dir = vault / "Rules"
    if not rules_dir.exists():
        return "(No standing rules directory found.)"

    chunks: list[str] = []
    used = 0
    for path in sorted(rules_dir.glob("*.md")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        if len(text) > 6000:
            text = text[:6000] + "\n[Rule file truncated by periodic summary runner.]"
        chunk = f"\n--- Rules/{path.name} ---\n{text}\n"
        if used + len(chunk) > limit:
            chunks.append("\n[Additional rule files omitted by periodic summary runner.]\n")
            break
        chunks.append(chunk)
        used += len(chunk)

    return "".join(chunks).strip() if chunks else "(No standing rule files found.)"


def gather_daily_notes(vault: Path, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    daily_dir = vault / "Daily"
    if not daily_dir.exists():
        raise FileNotFoundError(f"Daily notes directory not found: {daily_dir}")

    notes: list[dict[str, Any]] = []
    for path in sorted(daily_dir.glob("*.md")):
        try:
            note = build_web_journal.parse_daily_note(path)
            note_date = parse_date(str(note["date"]))
        except Exception as exc:
            print(f"WARNING: Could not parse {path}: {exc}", file=sys.stderr)
            continue
        if start <= note_date <= end:
            notes.append(note)
    notes.sort(key=lambda item: item["date"])
    return notes


def truncate_text(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[Content truncated by periodic summary runner.]"


def compact_note(note: dict[str, Any]) -> str:
    section_limit = int(os.environ.get("FOLIO_SCRIBE_PERIODIC_SECTION_LIMIT", "2600"))
    lines = [
        f"## Daily {note['date']} | {note.get('title', '')}",
        f"- model: {note.get('model') or '-'}",
        f"- completion: {note.get('completedSectionCount', 0)}/{note.get('sectionCount', 0)}",
    ]
    if note.get("planScore"):
        lines.append(f"- plan_score: {note['planScore']}")
    if note.get("disciplineScore"):
        lines.append(f"- discipline_score: {note['disciplineScore']}")

    for section in note.get("sections", []):
        status = "pending" if section.get("pending") else "completed"
        lines.append("")
        time = f"{section.get('time')} " if section.get("time") else ""
        lines.append(f"### {time}{section.get('label', section.get('title', 'Section'))} ({status})")
        if section.get("pending"):
            lines.append("待更新。")
        else:
            lines.append(truncate_text(str(section.get("content") or ""), section_limit))
    return "\n".join(lines).strip()


def build_daily_context(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return "(No Daily notes found for this period.)"
    chunks = [compact_note(note) for note in notes]
    context = "\n\n---\n\n".join(chunks)
    return truncate_text(context, int(os.environ.get("FOLIO_SCRIBE_PERIODIC_CONTEXT_LIMIT", "64000")))


def completion_summary(notes: list[dict[str, Any]]) -> tuple[int, int]:
    completed = sum(int(note.get("completedSectionCount") or 0) for note in notes)
    total = sum(int(note.get("sectionCount") or 0) for note in notes)
    return completed, total


def note_date_bounds(notes: list[dict[str, Any]], fallback_start: dt.date, fallback_end: dt.date) -> tuple[dt.date, dt.date]:
    dates: list[dt.date] = []
    for note in notes:
        try:
            dates.append(parse_date(str(note["date"])))
        except Exception:
            continue
    if not dates:
        return fallback_start, fallback_end
    return min(dates), max(dates)


def summary_template(period: str) -> str:
    if period == "weekly":
        return """# PERIOD_ID 交易周总结

## 本周概览

| 项目 | 数值 | 备注 |
|------|------|------|
| 覆盖日期 |  |  |
| 交易日志完成度 |  |  |
| 主要市场 | 港股 / 美股 |  |
| 本周主线 |  |  |

## 执行完成度

- 已完成的计划/总结：
- 缺失或待补的部分：
- 对复盘质量的影响：

## 账户与风险变化

- 现金/融资：
- 集中度：
- 期权保护：
- 需要警惕的风险漂移：

## 港股复盘

| 主题 | 观察 | 结论 |
|------|------|------|

## 美股复盘

| 主题 | 观察 | 结论 |
|------|------|------|

## 交易行为与纪律

- 做对的行为：
- 重复问题：
- 最大偏离：
- 本周纪律评分：

## 关注清单与机会质量

- 有效观察：
- 噪音/应移除：
- 下周继续观察：

## 下周行动框架

1. 
2. 
3. 

## 需要更新到规则的改进

- 
"""

    return """# PERIOD_ID 月度交易总结

## 本月概览

| 项目 | 数值 | 备注 |
|------|------|------|
| 覆盖日期 |  |  |
| 交易日志完成度 |  |  |
| 核心持仓/主线 |  |  |
| 本月关键结论 |  |  |

## 策略有效性

- 核心仓：
- T 仓/短线：
- 期权保护：
- 候选池/关注清单：

## 账户结构与风险

- 现金/融资趋势：
- 集中度变化：
- 最大风险暴露：
- 风险边界是否被突破：

## 主要正确决策

| 决策 | 为什么正确 | 可复制条件 |
|------|------------|------------|

## 主要错误与代价

| 问题 | 发生原因 | 下月修正 |
|------|----------|----------|

## 行为模式复盘

- 最稳定的好习惯：
- 最容易重复的坏习惯：
- 需要系统化的提醒：

## 下月交易原则

1. 
2. 
3. 
4. 
5. 

## 需要更新到规则的改进

- 
"""


def build_prompt(
    period: str,
    period_id: str,
    start: dt.date,
    end: dt.date,
    notes: list[dict[str, Any]],
    rules_context: str,
) -> str:
    completed, total = completion_summary(notes)
    trading_start, trading_end = note_date_bounds(notes, start, end)
    note_dates = ", ".join(str(note["date"]) for note in notes) or "-"
    period_name = "周" if period == "weekly" else "月"
    template = summary_template(period).replace("PERIOD_ID", period_id)
    daily_context = build_daily_context(notes)

    return f"""Folio Scribe 定时任务：生成交易{period_name}总结。

任务：基于下面的 Daily 交易日志和长期规则，生成 {period_id} 的交易{period_name}总结，中文输出。

总结口径：
- 交易日范围：{trading_start.isoformat()} 至 {trading_end.isoformat()}
- 日历周期：{start.isoformat()} 至 {end.isoformat()}
- 覆盖 Daily：{note_dates}
- 完成度：{completed}/{total}
- 周/月总结不是 Daily 的流水账拼接；重点提炼行为模式、风险结构、策略有效性和下一周期可执行规则。
- 必须同时覆盖港股与美股；若某一市场没有数据，明确写“本周期无该市场有效数据”。
- 不提出自动下单、改单或撤单；只做复盘、风险约束和下周期计划框架。
- 不要臆造 Daily 中不存在的成交、价格或收益数字。
- 若 Daily 存在待更新段落，说明它对总结可靠性的影响。
- 若上下文中出现 "Content truncated" 或 "periodic summary runner" 等工具内部标记，不要在总结中提及这些字样；只在确实影响判断时概括为“需回读原始 Daily”。

固定输出模板：
必须严格使用下列 Markdown 结构、标题和表格列。模板里的空白要用实际总结填充。

{template}

交易规则与长期策略：
{rules_context}

Daily 交易日志上下文：
{daily_context}

只输出完整 Markdown 正文。不要包含 frontmatter、代码围栏、shell 命令或任何工具调用说明。"""


def read_json_model_setting(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("model") or "")
    except Exception:
        return ""


def read_toml_model_setting(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        import tomllib

        return str(tomllib.loads(path.read_text(encoding="utf-8")).get("model") or "")
    except Exception:
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"(?m)^model\s*=\s*[\"']?([^\"'#\n]+)", text)
        return match.group(1).strip() if match else ""


def resolve_initial_model_label(cli: str) -> tuple[str, str, bool]:
    explicit_model = os.environ.get("FOLIO_SCRIBE_AI_MODEL", "")
    model = explicit_model
    explicit = bool(model)

    home = Path.home()
    if cli == "claude":
        if not model:
            model = os.environ.get("FOLIO_SCRIBE_CLAUDE_MODEL", "")
            explicit = bool(model)
        if not model:
            settings = Path(os.environ.get("FOLIO_SCRIBE_CLAUDE_SETTINGS", home / ".claude/settings.json"))
            model = read_json_model_setting(settings)
        return (f"claude:{model}" if model else "claude", model, explicit)

    if cli == "codex":
        if not model:
            model = os.environ.get("FOLIO_SCRIBE_CODEX_MODEL", "")
            explicit = bool(model)
        if not model:
            config = Path(os.environ.get("FOLIO_SCRIBE_CODEX_CONFIG", home / ".codex/config.toml"))
            model = read_toml_model_setting(config)
        return (f"codex:{model}" if model else "codex", model, explicit)

    raise ValueError(f"Unsupported AI CLI: {cli}")


def run_claude(prompt: str, content_path: Path, fallback_label: str, model: str, explicit_model: bool) -> str:
    claude = os.environ.get("FOLIO_SCRIBE_CLAUDE") or shutil.which("claude") or "/opt/homebrew/bin/claude"
    settings = Path(os.environ.get("FOLIO_SCRIBE_CLAUDE_SETTINGS", Path.home() / ".claude/settings.json"))
    max_turns = os.environ.get("FOLIO_SCRIBE_MAX_TURNS", "20")
    max_budget = os.environ.get("FOLIO_SCRIBE_MAX_BUDGET_USD", "0.80")
    bare = os.environ.get("FOLIO_SCRIBE_CLAUDE_BARE", "0").lower() in {"1", "true", "yes", "on"}

    args = [
        claude,
        "-p",
        prompt,
        "--max-turns",
        max_turns,
        "--max-budget-usd",
        max_budget,
        "--no-session-persistence",
        "--output-format",
        "json",
        "--tools",
        "",
    ]
    if bare:
        args.append("--bare")
    if settings.exists():
        args.extend(["--settings", str(settings)])
    if model and explicit_model:
        args.extend(["--model", model])
    fallback_model = os.environ.get("FOLIO_SCRIBE_CLAUDE_FALLBACK_MODEL", "")
    if fallback_model:
        args.extend(["--fallback-model", fallback_model])

    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout[:3000], file=sys.stderr)
        if result.stderr:
            print(result.stderr[:3000], file=sys.stderr)
        raise RuntimeError(f"Claude CLI failed with exit {result.returncode}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Claude CLI did not return JSON: {exc}") from exc

    if payload.get("is_error") is True:
        raise RuntimeError(str(payload.get("result") or payload.get("error") or "Claude returned an error"))

    content = payload.get("result")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Claude JSON output did not contain a non-empty result")

    content_path.write_text(content.strip() + "\n", encoding="utf-8")

    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict):
        models = [str(item) for item in model_usage.keys() if str(item).strip()]
    else:
        models = []
    raw_label = "claude:" + ",".join(models) if models else fallback_label
    resolver = SCRIPT_DIR / "resolve_model_label.py"
    if resolver.exists():
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            claude_json = Path(handle.name)
        try:
            resolved = subprocess.run(
                [
                    sys.executable,
                    str(resolver),
                    "--cli",
                    "claude",
                    "--label",
                    raw_label,
                    "--claude-json",
                    str(claude_json),
                    "--cc-switch-db",
                    os.environ.get("FOLIO_SCRIBE_CC_SWITCH_DB", str(Path.home() / ".cc-switch/cc-switch.db")),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if resolved.returncode == 0 and resolved.stdout.strip():
                return resolved.stdout.strip()
        finally:
            claude_json.unlink(missing_ok=True)
    return raw_label


def run_codex(prompt: str, content_path: Path, vault: Path, model: str, explicit_model: bool) -> str:
    codex = os.environ.get("FOLIO_SCRIBE_CODEX") or shutil.which("codex") or "/opt/homebrew/bin/codex"
    sandbox = os.environ.get("FOLIO_SCRIBE_CODEX_SANDBOX", "read-only")
    disabled = os.environ.get("FOLIO_SCRIBE_CODEX_DISABLE_FEATURES", "plugins apps").split()
    profile = os.environ.get("FOLIO_SCRIBE_CODEX_PROFILE", "")

    args = [
        codex,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        sandbox,
        "--color",
        "never",
        "--output-last-message",
        str(content_path),
        "--cd",
        str(vault),
    ]
    for feature in disabled:
        args.extend(["--disable", feature])
    if profile:
        args.extend(["--profile", profile])
    if model and explicit_model:
        args.extend(["--model", model])
    args.append("-")

    result = subprocess.run(args, input=prompt, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout[:3000], file=sys.stderr)
        if result.stderr:
            print(result.stderr[:3000], file=sys.stderr)
        raise RuntimeError(f"Codex CLI failed with exit {result.returncode}")
    if not content_path.exists() or not content_path.read_text(encoding="utf-8", errors="replace").strip():
        raise RuntimeError("Codex CLI completed but did not produce a final message")
    return f"codex:{model}" if model else "codex"


def generate_with_ai(prompt: str, vault: Path) -> tuple[str, str]:
    primary = os.environ.get("FOLIO_SCRIBE_AI_CLI", "codex").lower()
    fallback = os.environ.get("FOLIO_SCRIBE_AI_FALLBACK_CLI", "codex").lower()
    if primary not in {"claude", "codex"}:
        raise ValueError("FOLIO_SCRIBE_AI_CLI must be claude or codex")
    if fallback not in {"", "none", "codex"}:
        raise ValueError("FOLIO_SCRIBE_AI_FALLBACK_CLI must be codex or none")

    content_path = Path(tempfile.mkstemp(prefix="folio-periodic-summary-", suffix=".md")[1])
    initial_label, model, explicit = resolve_initial_model_label(primary)

    try:
        if primary == "claude":
            try:
                label = run_claude(prompt, content_path, initial_label, model, explicit)
            except Exception as exc:
                if fallback == "codex":
                    print(f"WARNING: Claude failed; falling back to Codex: {exc}", file=sys.stderr)
                    _, codex_model, codex_explicit = resolve_initial_model_label("codex")
                    label = run_codex(prompt, content_path, vault, codex_model, codex_explicit)
                else:
                    raise
        else:
            label = run_codex(prompt, content_path, vault, model, explicit)

        content = content_path.read_text(encoding="utf-8", errors="replace").strip()
        return content, label
    finally:
        content_path.unlink(missing_ok=True)


def ensure_heading(content: str, period_id: str, period: str) -> str:
    content = content.strip()
    if content.startswith("# "):
        return content
    label = "交易周总结" if period == "weekly" else "月度交易总结"
    return f"# {period_id} {label}\n\n{content}"


def write_summary_note(
    vault: Path,
    period: str,
    period_id: str,
    start: dt.date,
    end: dt.date,
    content: str,
    model_label: str,
    notes: list[dict[str, Any]],
) -> Path:
    directory_name = "Weekly" if period == "weekly" else "Monthly"
    type_name = "trading-weekly" if period == "weekly" else "trading-monthly"
    tag = "weekly-review" if period == "weekly" else "monthly-review"
    out_dir = vault / directory_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{period_id}.md"

    completed, total = completion_summary(notes)
    trading_start, trading_end = note_date_bounds(notes, start, end)
    heading_body = ensure_heading(content, period_id, period)
    frontmatter = (
        "---\n"
        f"period: {period}\n"
        f"id: {period_id}\n"
        f"type: {type_name}\n"
        f"start_date: {trading_start.isoformat()}\n"
        f"end_date: {trading_end.isoformat()}\n"
        f"daily_count: {len(notes)}\n"
        f"completed_sections: {completed}\n"
        f"total_sections: {total}\n"
        "tags: [trading, broker-journal, periodic-review, "
        f"{tag}]\n"
        f"model: {model_label}\n"
        f"generated_at: {dt.datetime.now(dt.timezone.utc).isoformat()}\n"
        "---\n\n"
    )
    out_path.write_text(frontmatter + heading_body.rstrip() + "\n", encoding="utf-8")
    return out_path


def maybe_sync_web(vault: Path) -> None:
    out_dir = os.environ.get("FOLIO_SCRIBE_WEB_EXPORT_DIR", "")
    if not out_dir:
        return
    sync_script = SCRIPT_DIR / "sync_tradingweb.sh"
    if not sync_script.exists():
        raise FileNotFoundError(f"TradingWeb sync script not found: {sync_script}")
    args = [
        str(sync_script),
        "--vault",
        str(vault),
        "--out",
        out_dir,
        "--title",
        os.environ.get("FOLIO_SCRIBE_WEB_TITLE", "Folio Scribe Journal"),
        "--deploy",
        os.environ.get("FOLIO_SCRIBE_WEB_DEPLOY", "none") or "none",
        "--quiet",
    ]
    subprocess.run(args, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Weekly/Monthly Folio Scribe summary notes.")
    parser.add_argument("--vault", default=os.environ.get("FOLIO_SCRIBE_VAULT", str(Path.home() / "Documents/Trading")))
    parser.add_argument("--period", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Anchor date, default today")
    parser.add_argument("--week", help="Explicit ISO week, e.g. 2026-W21")
    parser.add_argument("--month", help="Explicit month, e.g. 2026-05")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt context only; do not call AI or write")
    parser.add_argument("--no-web-sync", action="store_true", help="Do not refresh TradingWeb after writing")
    args = parser.parse_args(argv)

    vault = Path(args.vault).expanduser().resolve()
    if not vault.exists():
        raise FileNotFoundError(f"Vault not found: {vault}")

    anchor = parse_date(args.date)
    period_id, start, end = resolve_period(args.period, anchor, week=args.week, month=args.month)
    if args.period == "monthly" and not args.month and anchor.day != 1:
        current_month_last_trading_day = last_trading_day_of_month(anchor.year, anchor.month)
        if anchor != current_month_last_trading_day:
            print(
                f"Monthly summary is scheduled for {current_month_last_trading_day}; "
                f"{anchor} is not the last trading day of the month, skipping."
            )
            return 0
    notes = gather_daily_notes(vault, start, end)
    if not notes:
        print(f"No Daily notes found for {period_id} ({start} to {end}); skipping.")
        return 0

    rules_context = read_rules_context(vault)
    prompt = build_prompt(args.period, period_id, start, end, notes, rules_context)
    if args.dry_run:
        print(prompt)
        return 0

    print(f"Generating {args.period} summary {period_id} from {len(notes)} Daily notes ...")
    content, model_label = generate_with_ai(prompt, vault)
    path = write_summary_note(vault, args.period, period_id, start, end, content, model_label, notes)
    print(path)

    if not args.no_web_sync:
        maybe_sync_web(vault)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
