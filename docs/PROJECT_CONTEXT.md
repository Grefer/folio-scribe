# Project Context

This document captures the product decisions behind Folio Scribe in a
GitHub-safe, non-account-specific form.

## Origin

Folio Scribe began as a workflow for turning broker desktop data into daily
trading plans, close-of-day reviews, watchlists, and Obsidian journal entries.
The first implementation used the desktop broker client as the source of truth,
then evolved toward a reusable skill and Python package.

## Product Goal

Create a read-only assistant workflow that can:

- Read live broker state from an available source.
- Summarize positions, orders, fills, account risk, quotes, options, and news.
- Generate market-session-aware trading plans and reviews.
- Maintain an Obsidian/Markdown trading journal.
- Support daily, weekly, and monthly reflection.

## Core Principles

- **Read-only by default**: no order entry, order modification, or cancellation.
- **Broker data first**: prefer broker UI/API data over stale web quotes.
- **Dynamic positions**: never hard-code positions, costs, orders, or holdings.
- **Session-aware**: handle markets with different exchange hours and time zones.
- **Journal-friendly**: preserve daily plans and reviews in one note per session date.
- **Privacy by design**: keep personal account data outside the public repository.

## Data Source Strategy

The project supports multiple data sources:

1. Structured broker APIs such as Futu OpenAPI.
2. Desktop broker inspection as a visual fallback.
3. Manual snapshots or exported reports when automation is unavailable.

The Futu OpenAPI adapter should remain read-only. It may read account state,
positions, orders, fills, quotes, option chains, and financial/news summaries,
but it should not expose order-entry methods.

## Market Session Model

Folio Scribe treats each market session separately:

- HK market plan and review.
- US market plan and review.
- Weekly and monthly reviews based on accumulated daily notes.

For US markets viewed from Asia time zones, the close review may happen the
next local morning but should normally update the note for the US session date.

## Obsidian Model

Recommended vault structure:

```text
Daily/
Weekly/
Monthly/
Watchlist/
Rules/
Templates/
```

Daily notes can contain:

- HK trading plan.
- HK trading review.
- US trading plan.
- US trading review.

Weekly/monthly notes summarize account change, plan adherence, major trades,
watchlist changes, mistakes, and next-period plans.

## Open Source Scope

Good public examples:

- Normalized sample snapshots with fake symbols and values.
- Example Obsidian notes with synthetic data.
- Read-only API adapters.
- Report templates and tests.

Keep private:

- Real account numbers.
- Exact personal holdings, cost basis, orders, fills, or account assets.
- Personal Obsidian vault paths.
- Local automation IDs and schedules tied to a user.
