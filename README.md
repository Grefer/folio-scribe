# Folio Scribe

Folio Scribe is a Codex skill and Python toolkit for turning broker data into
trading plans, session reviews, watchlists, and Obsidian journals.

It is designed to be broker-agnostic:

- Read live broker data when available.
- Prefer structured APIs over screenshots or desktop UI scraping.
- Fall back to desktop inspection or manual snapshots when APIs are unavailable.
- Write daily, weekly, and monthly Markdown journals.

Folio Scribe is analytical by default. It does not place, modify, or cancel
orders.

## Skill Design

The skill is designed to stay portable across AI coding assistants and desktop
agents:

- Codex can use the full bundle in `skill/folio-scribe/`.
- Claude Code and other clients that support skill folders should receive the
  whole `skill/folio-scribe/` directory, including `scripts/` and `references/`.
- Clients that only support global custom instructions can use the core
  `SKILL.md` text, with bundled scripts run manually or by the surrounding
  project.
- Broker integrations should use structured APIs such as Futu OpenD/OpenAPI
  when available, with desktop inspection and manual snapshots as fallbacks.

The skill should remain broker-agnostic even when Futu is the first supported
structured connector.

## Repository Layout

```text
skill/folio-scribe/        Codex skill bundle
src/folio_scribe/          Reusable Python package
tests/                     Unit tests
docs/                      Project notes and roadmap
```

Useful project notes:

- `docs/PROJECT_CONTEXT.md`
- `docs/ROADMAP.md`

## Current Status

This project is currently a beta read-only workflow. The Futu connector is
quote-only today: it can connect to a local OpenD gateway and read quote
snapshots, but account, position, order, fill, and option-chain reads are still
roadmap work.

The initial project contains:

- A Codex skill bundle at `skill/folio-scribe`.
- An Obsidian daily-note writer.
- Shared data models for account snapshots, positions, orders, and quotes.
- A read-only data-source interface.
- A Futu OpenAPI adapter scaffold that intentionally excludes trading actions.

## Futu OpenAPI Direction

The next milestone is a read-only Futu OpenAPI connector:

1. Confirm OpenD is installed, running, logged in, and reachable on the expected
   local port, usually `11111`.
2. Read account, positions, orders, fills, and buying power.
3. Read quotes, snapshots, order books, ticks, K-lines, option chains, and
   financial summaries.
4. Incorporate news, comment sentiment, capital-flow anomalies, derivatives
   anomalies, technical signals, and sector context when available.
5. Convert everything into a normalized `BrokerSnapshot`.
6. Keep the desktop Futu client as visual verification and fallback.

No order-entry methods should be implemented in this project unless a separate
safety design is reviewed first.

## Obsidian Journal

Daily notes use this shape:

```text
Daily/YYYY-MM-DD.md
```

Each note can contain separate market sessions:

- HK trading plan
- HK trading review
- US trading plan
- US trading review

Example:

```bash
python -m folio_scribe.journal.obsidian \
  --vault /path/to/vault \
  --date 2026-05-07 \
  --section hk_plan \
  --content /tmp/plan.md \
  --chinese
```

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Disclaimer

This project is decision-support tooling. It does not provide financial advice,
guaranteed returns, or automated trade execution.
