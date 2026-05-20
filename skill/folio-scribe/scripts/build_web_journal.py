#!/usr/bin/env python3
"""Build a private static web dashboard from Folio Scribe journal notes."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "web-template"


SECTION_ORDER = ["hk_plan", "hk_review", "us_plan", "us_review", "other"]
SECTION_LABELS = {
    "hk_plan": "港股计划",
    "hk_review": "港股总结",
    "us_plan": "美股计划",
    "us_review": "美股总结",
    "other": "其他",
}


@dataclass
class ParsedSection:
    key: str
    title: str
    time: str
    content: str
    pending: bool


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the simple YAML frontmatter produced by write_daily_note.py."""
    if not text.startswith("---\n"):
        return {}, text

    lines = text.splitlines()
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text

    frontmatter: dict[str, Any] = {}
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            frontmatter[key] = [item.strip() for item in inner.split(",") if item.strip()]
        else:
            frontmatter[key] = value

    body = "\n".join(lines[end_index + 1 :]).strip()
    return frontmatter, body


def classify_section(title: str) -> str:
    normalized = title.lower()
    if ("港股" in title or "hk" in normalized) and ("计划" in title or "plan" in normalized):
        return "hk_plan"
    if ("港股" in title or "hk" in normalized) and (
        "总结" in title or "review" in normalized or "summary" in normalized
    ):
        return "hk_review"
    if ("美股" in title or "us" in normalized) and ("计划" in title or "plan" in normalized):
        return "us_plan"
    if ("美股" in title or "us" in normalized) and (
        "总结" in title or "review" in normalized or "summary" in normalized
    ):
        return "us_review"
    return "other"


def is_pending_section(content: str) -> bool:
    normalized = re.sub(r"\s+", "", content.strip().lower())
    return normalized in {"", "待更新。", "待更新", "pending.", "pending"}


def clean_section_content(content: str) -> str:
    lines = content.strip().splitlines()
    while lines and lines[-1].strip() in {"---", "***"}:
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines).strip()


def parse_sections(body: str) -> list[ParsedSection]:
    pattern = re.compile(r"^##\s+(?:(\d{2}:\d{2})\s+)?(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    sections: list[ParsedSection] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = clean_section_content(body[start:end])
        time = match.group(1) or ""
        title = match.group(2).strip()
        key = classify_section(title)
        sections.append(
            ParsedSection(
                key=key,
                title=title,
                time=time,
                content=content,
                pending=is_pending_section(content),
            )
        )

    return sorted(sections, key=lambda section: SECTION_ORDER.index(section.key))


def parse_daily_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(text)

    title = path.stem
    title_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    date = str(frontmatter.get("date") or path.stem)
    sections = parse_sections(body)
    completed_sections = [section for section in sections if not section.pending]

    return {
        "date": date,
        "title": title,
        "sourceFile": path.name,
        "model": str(frontmatter.get("model") or ""),
        "planScore": str(frontmatter.get("plan_score") or ""),
        "disciplineScore": str(frontmatter.get("discipline_score") or ""),
        "tags": frontmatter.get("tags") or [],
        "sectionCount": len(sections),
        "completedSectionCount": len(completed_sections),
        "rawMarkdown": body,
        "sections": [
            {
                "key": section.key,
                "label": SECTION_LABELS[section.key],
                "title": section.title,
                "time": section.time,
                "content": section.content,
                "pending": section.pending,
            }
            for section in sections
        ],
    }


def parse_periodic_note(path: Path, period: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(text)

    title = path.stem
    title_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    period_id = str(frontmatter.get("id") or path.stem)
    start_date = str(frontmatter.get("start_date") or "")
    end_date = str(frontmatter.get("end_date") or "")
    daily_count = str(frontmatter.get("daily_count") or "")
    completed_sections = str(frontmatter.get("completed_sections") or "")
    total_sections = str(frontmatter.get("total_sections") or "")

    return {
        "id": period_id,
        "period": period,
        "title": title,
        "sourceFile": path.name,
        "startDate": start_date,
        "endDate": end_date,
        "dailyCount": daily_count,
        "completedSectionCount": completed_sections,
        "sectionCount": total_sections,
        "model": str(frontmatter.get("model") or ""),
        "tags": frontmatter.get("tags") or [],
        "generatedAt": str(frontmatter.get("generated_at") or ""),
        "rawMarkdown": body,
    }


def parse_iso_date(value: Any) -> date | None:
    try:
        text = str(value or "")
        if not text:
            return None
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def display_range(start: str, end: str) -> str:
    if start and end:
        return f"{start} - {end}"
    return start or end or ""


def last_weekday_on_or_before(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def enrich_periodic_notes(notes: list[dict[str, Any]], daily_notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    daily_dates = sorted(str(note.get("date") or "") for note in daily_notes if note.get("date"))
    today = datetime.now(timezone.utc).date()
    enriched: list[dict[str, Any]] = []

    for note in notes:
        start = parse_iso_date(note.get("startDate"))
        end = parse_iso_date(note.get("endDate"))
        if not start or not end:
            enriched.append(note)
            continue

        trading_dates = [item for item in daily_dates if start.isoformat() <= item <= end.isoformat()]
        trading_start = trading_dates[0] if trading_dates else ""
        trading_end = trading_dates[-1] if trading_dates else ""

        if note.get("period") == "monthly":
            anchor = last_weekday_on_or_before(end)
            generated = parse_iso_date(note.get("generatedAt"))
            if anchor > today or (generated and generated < anchor):
                continue
            display_start = start.isoformat()
            display_end = anchor.isoformat()
        else:
            anchor = parse_iso_date(trading_end) or last_weekday_on_or_before(end)
            display_start = trading_start or start.isoformat()
            display_end = trading_end or anchor.isoformat()

        note = dict(note)
        note["tradingStartDate"] = trading_start
        note["tradingEndDate"] = trading_end
        note["anchorDate"] = anchor.isoformat()
        note["displayRange"] = display_range(display_start, display_end)
        enriched.append(note)

    return enriched


def build_periodic_notes(vault: Path, directory: str, period: str, limit: int | None = None) -> list[dict[str, Any]]:
    notes_dir = vault / directory
    if not notes_dir.exists():
        return []

    notes = [parse_periodic_note(path, period) for path in sorted(notes_dir.glob("*.md"))]
    notes.sort(key=lambda note: note["id"], reverse=True)
    if limit is not None:
        notes = notes[:limit]
    return notes


def build_journal_data(vault: Path, daily_dir: str = "Daily", limit: int | None = None) -> dict[str, Any]:
    daily_path = vault / daily_dir
    if not daily_path.exists():
        raise FileNotFoundError(f"Daily notes directory not found: {daily_path}")

    notes = [parse_daily_note(path) for path in sorted(daily_path.glob("*.md"))]
    notes.sort(key=lambda note: note["date"], reverse=True)
    if limit is not None:
        notes = notes[:limit]

    completed = sum(note["completedSectionCount"] for note in notes)
    total_sections = sum(note["sectionCount"] for note in notes)
    latest = notes[0] if notes else None
    weekly_notes = enrich_periodic_notes(build_periodic_notes(vault, "Weekly", "weekly", limit=limit), notes)
    monthly_notes = enrich_periodic_notes(build_periodic_notes(vault, "Monthly", "monthly", limit=limit), notes)

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dailyDir": daily_dir,
        "stats": {
            "noteCount": len(notes),
            "sectionCount": total_sections,
            "completedSectionCount": completed,
            "latestDate": latest["date"] if latest else "",
            "latestModel": latest["model"] if latest else "",
            "weeklyCount": len(weekly_notes),
            "monthlyCount": len(monthly_notes),
        },
        "sections": [{"key": key, "label": SECTION_LABELS[key]} for key in SECTION_ORDER[:-1]],
        "notes": notes,
        "summaries": {
            "weekly": weekly_notes,
            "monthly": monthly_notes,
        },
    }


def copy_template(out_dir: Path, title: str) -> None:
    if not TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"Web template directory not found: {TEMPLATE_DIR}")

    for source in TEMPLATE_DIR.rglob("*"):
        relative = source.relative_to(TEMPLATE_DIR)
        target = out_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in {".html", ".css", ".js"}:
            text = source.read_text(encoding="utf-8").replace("__SITE_TITLE__", title)
            target.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(source, target)


def write_site(data: dict[str, Any], out_dir: Path, title: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_template(out_dir, title)

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    (data_dir / "journal.json").write_text(payload + "\n", encoding="utf-8")

    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "journal-data.js").write_text(
        "window.FOLIO_JOURNAL_DATA = " + payload + ";\n",
        encoding="utf-8",
    )


def build_site(vault: Path, out_dir: Path, title: str, daily_dir: str = "Daily", limit: int | None = None) -> dict[str, Any]:
    data = build_journal_data(vault, daily_dir=daily_dir, limit=limit)
    data["title"] = title
    write_site(data, out_dir, title)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static private web dashboard from Folio Scribe journal notes.")
    parser.add_argument("--vault", required=True, help="Obsidian vault path")
    parser.add_argument("--out", required=True, help="Output directory for the static site")
    parser.add_argument("--daily-dir", default="Daily", help="Daily notes directory inside the vault")
    parser.add_argument("--title", default="Folio Scribe Journal", help="Dashboard title")
    parser.add_argument("--limit", type=int, help="Maximum number of recent notes to export")
    parser.add_argument("--quiet", action="store_true", help="Only print the output path")
    args = parser.parse_args(argv)

    data = build_site(
        vault=Path(args.vault).expanduser(),
        out_dir=Path(args.out).expanduser(),
        title=args.title,
        daily_dir=args.daily_dir,
        limit=args.limit,
    )

    if args.quiet:
        print(Path(args.out).expanduser())
    else:
        stats = data["stats"]
        print(f"Built {stats['noteCount']} notes / {stats['completedSectionCount']} completed sections")
        print(Path(args.out).expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
