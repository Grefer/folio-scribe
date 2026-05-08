# Changelog

All notable changes to folio-scribe are documented here.

## [Unreleased]

### Added
- `FOLIO_SCRIBE_LANG` env var for English prompts and note headings (`en`/`zh`).

## [0.1.2] – 2026-05-08

### Added
- `check_setup.sh` health-check script — verifies Python, Claude CLI, Futu OpenD, vault, launchd, and scripts in one command.
- Example output section in README with collapsible demo trading journal.
- Full demo daily note at `docs/example-daily-note.md`.
- 17 unit tests covering `default_note`, `replace_section`, `write_daily_note`, and section-marker consistency.

### Fixed
- `journal/obsidian.py` synced to correct session times (08:45/16:15/20:45/06:45) and frontmatter (`model`, `plan_score`, `discipline_score`).
- Added missing generic (`plan`/`review`) and single-market Chinese (`计划`/`总结`) section markers.
- `scripts/write_daily_note.py` deduplicated — now a thin wrapper importing from the package.

### Changed
- SKILL.md: documented required frontmatter fields and prohibited financial fields.

## [0.1.1] – 2026-05-08

### Added
- Scheduled task runner `run_folio_task.sh` with auto-detection of HK/US plan/review by time of day.
- launchd plist templates and `install_schedule.sh` installer/uninstaller.
- Claude Code quick-start section and environment variable reference in README.

### Changed
- Trading plan/review times updated to 08:45/16:15/20:45/06:45 across SKILL.md and scripts.

## [0.1.0] – 2026-05-07

### Added
- Initial beta release.
- Read-only Futu OpenD data source (`FutuOpenAPIDataSource`) with account, positions, orders, fills, and quotes.
- `BrokerSnapshot` data model with frozen dataclasses.
- Obsidian daily note writer with section-based content injection.
- SKILL.md: broker-agnostic trading journal skill definition.
- `read_futu_snapshot.py` CLI for quick connectivity checks and JSON snapshots.
