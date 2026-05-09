#!/usr/bin/env python3
"""Insert or update a daily trading plan/review section in an Obsidian note.

This bundled script is intentionally self-contained so the skill folder can be
copied into another AI client without also installing the repository package.
Keep behavior mirrored with ``folio_scribe.journal.obsidian``.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


SECTION_MARKERS = {
    "plan": ("## 08:45 Trading Plan", "## 16:15 Trading Review"),
    "review": ("## 16:15 Trading Review", None),
    "hk_plan": ("## 08:45 HK Trading Plan", "## 16:15 HK Trading Review"),
    "hk_review": ("## 16:15 HK Trading Review", "## 20:45 US Trading Plan"),
    "us_plan": ("## 20:45 US Trading Plan", "## 06:45 US Trading Review"),
    "us_review": ("## 06:45 US Trading Review", None),
    "计划": ("## 08:45 交易计划", "## 16:15 交易总结"),
    "总结": ("## 16:15 交易总结", None),
    "港股计划": ("## 08:45 港股交易计划", "## 16:15 港股交易总结"),
    "港股总结": ("## 16:15 港股交易总结", "## 20:45 美股交易计划"),
    "美股计划": ("## 20:45 美股交易计划", "## 06:45 美股交易总结"),
    "美股总结": ("## 06:45 美股交易总结", None),
}


def default_note(date: str, chinese: bool) -> str:
    if chinese:
        title = f"# {date} 交易日志"
        plan = "## 08:45 港股交易计划"
        review = "## 16:15 港股交易总结"
        us_plan = "## 20:45 美股交易计划"
        us_review = "## 06:45 美股交易总结"
        placeholder = "待更新。"
    else:
        title = f"# {date} Trading Journal"
        plan = "## 08:45 HK Trading Plan"
        review = "## 16:15 HK Trading Review"
        us_plan = "## 20:45 US Trading Plan"
        us_review = "## 06:45 US Trading Review"
        placeholder = "Pending."

    return (
        "---\n"
        f"date: {date}\n"
        "type: trading-daily\n"
        "tags: [trading, broker-journal]\n"
        "cssclasses: [trading-journal]\n"
        "model:\n"
        "plan_score:\n"
        "discipline_score:\n"
        "---\n\n"
        f"{title}\n\n"
        f"{plan}\n\n"
        f"{placeholder}\n\n"
        "---\n\n"
        f"{review}\n\n"
        f"{placeholder}\n\n"
        "---\n\n"
        f"{us_plan}\n\n"
        f"{placeholder}\n\n"
        "---\n\n"
        f"{us_review}\n\n"
        f"{placeholder}\n"
    )


def replace_section(note: str, start_marker: str, end_marker: str | None, content: str) -> str:
    start = note.find(start_marker)
    if start == -1:
        suffix = f"\n\n{start_marker}\n\n{content.strip()}\n"
        return note.rstrip() + suffix

    content_start = note.find("\n", start)
    content_start = len(note) if content_start == -1 else content_start + 1

    if end_marker:
        end = note.find(end_marker, content_start)
        if end == -1:
            end = len(note)
    else:
        end = len(note)

    replacement = "\n" + content.strip() + "\n\n"
    return note[:content_start] + replacement + note[end:].lstrip("\n")


def write_daily_note(
    vault: str | Path,
    date: str,
    section: str,
    content: str,
    daily_dir: str = "Daily",
    chinese: bool = False,
) -> Path:
    if section not in SECTION_MARKERS:
        raise ValueError(f"Unknown section: {section}")

    vault_path = Path(vault).expanduser().resolve()
    note_path = vault_path / daily_dir / f"{date}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)

    if note_path.exists():
        note = note_path.read_text(encoding="utf-8")
    else:
        is_chinese = chinese or section in {
            "计划", "总结", "港股计划", "港股总结", "美股计划", "美股总结",
        }
        note = default_note(date, is_chinese)

    start_marker, end_marker = SECTION_MARKERS[section]
    updated = replace_section(note, start_marker, end_marker, content)
    note_path.write_text(updated, encoding="utf-8")
    return note_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Insert or update a daily trading plan/review section in an Obsidian note.",
    )
    parser.add_argument("--vault", required=True, help="Obsidian vault root")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--section", required=True, choices=sorted(SECTION_MARKERS))
    parser.add_argument("--content", required=True, help="Path to Markdown content")
    parser.add_argument("--daily-dir", default="Daily")
    parser.add_argument("--chinese", action="store_true", help="Create Chinese headings for new notes")
    args = parser.parse_args()

    content = Path(args.content).read_text(encoding="utf-8")
    path = write_daily_note(args.vault, args.date, args.section, content, args.daily_dir, args.chinese)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
