from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


SECTION_MARKERS = {
    "hk_plan": ("## 09:45 HK Trading Plan", "## 16:45 HK Trading Review"),
    "hk_review": ("## 16:45 HK Trading Review", "## 21:45 US Trading Plan"),
    "us_plan": ("## 21:45 US Trading Plan", "## 06:45 US Trading Review"),
    "us_review": ("## 06:45 US Trading Review", None),
    "港股计划": ("## 09:45 港股交易计划", "## 16:45 港股交易总结"),
    "港股总结": ("## 16:45 港股交易总结", "## 21:45 美股交易计划"),
    "美股计划": ("## 21:45 美股交易计划", "## 06:45 美股交易总结"),
    "美股总结": ("## 06:45 美股交易总结", None),
}


def _default_note(date: str, chinese: bool) -> str:
    if chinese:
        title = f"# {date} 交易日志"
        headings = (
            "## 09:45 港股交易计划",
            "## 16:45 港股交易总结",
            "## 21:45 美股交易计划",
            "## 06:45 美股交易总结",
        )
    else:
        title = f"# {date} Trading Journal"
        headings = (
            "## 09:45 HK Trading Plan",
            "## 16:45 HK Trading Review",
            "## 21:45 US Trading Plan",
            "## 06:45 US Trading Review",
        )
    body = "\n\n---\n\n".join(f"{heading}\n\nPending." for heading in headings)
    return (
        "---\n"
        f"date: {date}\n"
        "type: trading-daily\n"
        "tags: [trading, folio-scribe]\n"
        "total_assets:\n"
        "daily_pnl:\n"
        "leverage:\n"
        "plan_score:\n"
        "discipline_score:\n"
        "---\n\n"
        f"{title}\n\n{body}\n"
    )


def _replace_section(note: str, start_marker: str, end_marker: str | None, content: str) -> str:
    start = note.find(start_marker)
    if start == -1:
        return note.rstrip() + f"\n\n{start_marker}\n\n{content.strip()}\n"

    content_start = note.find("\n", start)
    content_start = len(note) if content_start == -1 else content_start + 1
    end = note.find(end_marker, content_start) if end_marker else len(note)
    if end == -1:
        end = len(note)

    return note[:content_start] + "\n" + content.strip() + "\n\n" + note[end:].lstrip("\n")


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

    note = note_path.read_text(encoding="utf-8") if note_path.exists() else _default_note(date, chinese)
    start_marker, end_marker = SECTION_MARKERS[section]
    updated = _replace_section(note, start_marker, end_marker, content)
    note_path.write_text(updated, encoding="utf-8")
    return note_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--section", required=True, choices=sorted(SECTION_MARKERS))
    parser.add_argument("--content", required=True)
    parser.add_argument("--daily-dir", default="Daily")
    parser.add_argument("--chinese", action="store_true")
    args = parser.parse_args()

    content = Path(args.content).read_text(encoding="utf-8")
    path = write_daily_note(args.vault, args.date, args.section, content, args.daily_dir, args.chinese)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
