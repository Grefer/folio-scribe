#!/usr/bin/env python3
"""Insert or update a daily trading plan/review section in an Obsidian note."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


SECTION_MARKERS = {
    "plan": ("## 09:45 Trading Plan", "## 16:45 Trading Review"),
    "review": ("## 16:45 Trading Review", None),
    "hk_plan": ("## 09:45 HK Trading Plan", "## 16:45 HK Trading Review"),
    "hk_review": ("## 16:45 HK Trading Review", "## 21:45 US Trading Plan"),
    "us_plan": ("## 21:45 US Trading Plan", "## 06:45 US Trading Review"),
    "us_review": ("## 06:45 US Trading Review", None),
    "计划": ("## 09:45 交易计划", "## 16:45 交易总结"),
    "总结": ("## 16:45 交易总结", None),
    "港股计划": ("## 09:45 港股交易计划", "## 16:45 港股交易总结"),
    "港股总结": ("## 16:45 港股交易总结", "## 21:45 美股交易计划"),
    "美股计划": ("## 21:45 美股交易计划", "## 06:45 美股交易总结"),
    "美股总结": ("## 06:45 美股交易总结", None),
}


def default_note(date: str, chinese: bool) -> str:
    if chinese:
        title = f"# {date} 交易日志"
        plan = "## 09:45 港股交易计划"
        review = "## 16:45 港股交易总结"
        us_plan = "## 21:45 美股交易计划"
        us_review = "## 06:45 美股交易总结"
        tags = "[trading, broker-journal]"
    else:
        title = f"# {date} Trading Journal"
        plan = "## 09:45 HK Trading Plan"
        review = "## 16:45 HK Trading Review"
        us_plan = "## 21:45 US Trading Plan"
        us_review = "## 06:45 US Trading Review"
        tags = "[trading, broker-journal]"
    return (
        "---\n"
        f"date: {date}\n"
        "type: trading-daily\n"
        f"tags: {tags}\n"
        "total_assets:\n"
        "daily_pnl:\n"
        "leverage:\n"
        "plan_score:\n"
        "discipline_score:\n"
        "---\n\n"
        f"{title}\n\n"
        f"{plan}\n\n"
        "待更新。\n\n"
        "---\n\n"
        f"{review}\n\n"
        "待更新。\n\n"
        "---\n\n"
        f"{us_plan}\n\n"
        "待更新。\n\n"
        "---\n\n"
        f"{us_review}\n\n"
        "待更新。\n"
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, help="Obsidian vault root")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--section", required=True, choices=sorted(SECTION_MARKERS))
    parser.add_argument("--content", required=True, help="Path to Markdown content")
    parser.add_argument("--daily-dir", default="Daily")
    parser.add_argument("--chinese", action="store_true", help="Create Chinese headings for new notes")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    note_path = vault / args.daily_dir / f"{args.date}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)

    content = Path(args.content).read_text(encoding="utf-8")
    if note_path.exists():
        note = note_path.read_text(encoding="utf-8")
    else:
        note = default_note(
            args.date,
            args.chinese or args.section in {"计划", "总结", "港股计划", "港股总结", "美股计划", "美股总结"},
        )

    start_marker, end_marker = SECTION_MARKERS[args.section]
    note = replace_section(note, start_marker, end_marker, content)
    note_path.write_text(note, encoding="utf-8")
    print(note_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
