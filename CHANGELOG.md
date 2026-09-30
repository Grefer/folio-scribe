# Changelog

All notable changes to folio-scribe are documented here.

## [Unreleased]

### Added
- 2027 Hong Kong holiday coverage for the bundled market calendar.
- `FOLIO_SCRIBE_CLAUDE_EFFORT` (default `xhigh`) sets the Claude Code effort for scheduled runs and periodic summaries, independent of the interactive default. The runner passes a copy of the user settings with `env.CLAUDE_CODE_EFFORT_LEVEL` overridden, because that setting takes precedence over `--effort`.

### Changed
- The runner takes the note date from each market's own time zone (new `market_calendar.py session-date`): a plan belongs to the session that has not closed yet, a review to the latest closed one. The machine's time zone no longer shifts note dates, and auto-detection without a task argument reads the Hong Kong clock. The README lists launchd times for `America/Los_Angeles`, and the installer warns when the Mac is not on UTC+8 and no times are set.
- `FOLIO_SCRIBE_MAX_BUDGET_USD` is now unset by default, so no budget cap is passed. Claude Code checks the cap only after a single-turn reply is generated, so exceeding it spent the tokens and then discarded the output.
- `sync_tradingweb.sh` fails closed: it runs the vault secrets guard (`FOLIO_SCRIBE_SECRETS_GUARD`, default `<vault>/_tools/check_secrets.py`) before building and on the built output before deploying, and aborts with exit 1 if either scan fails or the guard is missing.

### Fixed
- AI output now has to contain every `###` heading of the section template and no tool-call text, or the run counts as failed and moves on to the fallback CLI or the data-only section. The runner used to check only for a non-empty result, so tool-call text was once written into a note as the review.
- Degradation notifications now include the reason when the Claude CLI times out; the timeout message went to stderr and the reason field was empty.
- IBKR account ids no longer reach AI prompts, deterministic-fallback tables, IBKR error lines, runner logs, or notes. The runner replaces them with `U****（主）`/`U****（次）` aliases (largest total assets = 主) right after reading the snapshot, and the Daily/Weekly/Monthly writers mask any remaining IBKR-style id as `U****`.
- The package writer `folio_scribe.journal.obsidian.write_daily_note` now masks IBKR-style account ids as `U****` too (new `folio_scribe.privacy.mask_account_ids`), matching the bundled skill writer.
- Scheduled runners now use a per-task lock, private temp directory cleanup, and AI CLI wall-clock timeouts.
- Scheduled runner logs no longer dump full prompts with account and position data, and default logs now live outside the vault.
- Periodic summaries now close temporary file descriptors and treat TradingWeb sync failures as warnings after the summary is written.
- TradingWeb template title replacement is HTML-escaped.
- Auto-detected task windows no longer overlap between US review and HK plan.

## [0.1.3] – 2026-05-08

### Added
- Standalone skill bundle support: bundled helper scripts can run after copying `skill/folio-scribe/` without installing the repository package.
- `agents/openai.yaml` skill UI metadata.
- `tests/test_skill_bundle.py` portability checks for copied bundles.
- `FOLIO_SCRIBE_LANG` env var for English prompts and note headings (`en`/`zh`).

### Fixed
- launchd templates now pass explicit task types, preventing scheduled jobs from being misclassified by time auto-detection.
- Session-aware skip logic allows US Friday reviews on local Saturday morning and skips local Monday US reviews.
- Futu row normalization now preserves legitimate numeric zero values.

### Changed
- Scheduled Claude runner no longer enables `--dangerously-skip-permissions` by default and uses a narrower tool allowlist.
- Setup checks treat the repository Python package as optional for skill-bundle use.
- Python package metadata now uses SPDX license syntax.

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
