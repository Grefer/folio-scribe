---
name: folio-scribe
description: Use when the user wants a trading workflow that reads broker or trading-app data such as positions, orders, fills, quotes, option chains, news, analyst/financial summaries, then creates daily trading plans, close-of-day reviews, watchlists, or Obsidian/Markdown trading journal entries. Prefer real-time broker UI/app data over web quotes when available. Never place, modify, or cancel orders unless the user explicitly requests that separately.
---

# Folio Scribe

## Purpose

Turn broker/trading-app data into structured portfolio plans, session reviews, watchlists, and Obsidian journals. This skill is broker-agnostic: use whichever broker UI, app connector, exported report, screenshot, or local file is available. If a live broker app is available, read current positions, orders, fills, quotes, options, and account risk from that app first.

This skill is analytical and journaling-only by default. Do not submit, modify, cancel, or stage orders unless the user explicitly asks for that as a separate action.

## Workflow

1. **Read live account context**
   - Positions: symbol, quantity, cost, market value, P/L, portfolio weight, margin/initial margin when shown.
   - Orders and fills: working/cancelled/filled orders, quantities, prices, timestamps.
   - Account risk: total assets, cash, margin, leverage, buying power, withdrawals, currency exposures.
   - Quotes: price, day range, volume/turnover, bid/ask, order book, VWAP or moving average if visible.
   - Options: contract multiplier, expiry, strike, bid/ask/last, Greeks if visible, assignment/exercise probability if available.
   - Fundamentals/news: use broker-provided financials, analyst summaries, company news, and announcements when available.

2. **Respect dynamic data**
   - Never rely on stale conversation state for quantities, costs, orders, or fills.
   - If current broker data conflicts with prior chat, use the broker data and call out the change.
   - For lot-size markets, ensure recommended quantities match the instrument trading unit.

3. **Separate outputs**
   - **Trading plan**: actionable plan for the current/next market session.
   - **Trading review**: session or end-of-day review against the plan.
   - **Watchlist module**: candidates to watch but not necessarily buy.
   - **Journal sync**: optional Markdown/Obsidian file output.

4. **Avoid false precision**
   - Give price zones and trigger conditions, not unconditional predictions.
   - Label high-risk ideas and leverage/margin effects plainly.
   - For options, explain what the contract covers and what risk remains uncovered.

## Futu / OpenD Data Source

When Futu Desktop, Futu OpenD, or Futu OpenAPI tooling is available, prefer it as the primary structured data source before screenshots, web quotes, or manual snapshots.

Before relying on OpenD:

- Confirm OpenD is installed, running, logged in, and reachable.
- Use the default local port `11111` unless the user or local config says otherwise.
- Confirm the intended market/account context when multiple accounts, currencies, or trading environments are visible.
- Keep Futu-derived order entry, order modification, order cancellation, watchlist edits, and price-alert changes disabled unless the user separately and explicitly asks for that action.

When the local `folio_scribe` Python package is available, use the read-only
OpenD snapshot helper to gather structured data for any client that can run
local commands:

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only
python3 -m folio_scribe.futu_snapshot US.AAPL HK.00700
```

Use `--counts-only` for connectivity checks. For actual plans or reviews, read
the full JSON and summarize only the fields relevant to the user's requested
workflow. Do not print sensitive account details unless the user explicitly
needs them in the final output.

Use Futu capabilities as inputs to the Folio Scribe workflow:

- **Portfolio and account**: account assets, cash, buying power, margin, positions, P/L, working orders, fills.
- **Market data**: real-time quotes, snapshots, order book, ticks, K-line history, intraday trends.
- **Options and futures**: contract lookup, expirations, strikes, bid/ask, Greeks, implied volatility, unusual activity when available.
- **News and sentiment**: company news, announcements, research, platform comment sentiment, and discussion temperature.
- **Anomaly signals**: capital-flow anomalies, broker buy/sell activity, short selling, derivatives activity, technical indicators, and sector movement.

Treat anomaly, sentiment, and technical signals as watchlist and risk-context inputs, not as standalone buy/sell instructions.

## Market Sessions and Time Zones

Always identify which market session the output belongs to before writing a plan or review.

- Use the broker's exchange, symbol suffix, account currency, or visible market labels to classify holdings by market.
- For each market, use that market's trading hours, holidays, and session date when practical.
- If the user is in a different time zone from the exchange, show both the local trigger time and the exchange/session date when it matters.
- For US equities/options viewed from Asia, the regular session usually crosses the local calendar day. The post-close review should update the note for the US session date, not create a confusing separate next-day note unless the user asks for local-date logging.
- If a scheduled automation wakes outside a relevant market window, stay quiet or state that no action is needed.

Common Asia/Hong Kong examples:

```text
HK market plan: local 08:45, same local trading date
HK market review: local 16:15, same local trading date
US market plan during daylight saving time: local 20:45, same US session date
US market review during daylight saving time: local 06:45 next morning, write back to prior US session date
```

## Trading Plan Requirements

Include:

- Account snapshot and major risk exposures.
- Current positions and working orders.
- Instrument-specific plan with exact trigger prices and valid quantities.
- Option plan: hold, sell, roll, close, or avoid, with rationale.
- New watchlist module with 3-5 candidates when requested.
- Risk boundaries: stop/invalidations, maximum new exposure, and what not to do.

For position actions, prefer conditional language:

```text
If price holds above X for N minutes / closes above X, consider...
If price fails at X and returns below Y, reduce...
If price breaks support Z, stop adding and reassess...
```

## Trading Review Requirements

Include:

- Account and position changes.
- Fills versus the original plan.
- Whether each decision followed discipline.
- Missed opportunities, sell-flying/FOMO, chasing, overtrading, and risk drift.
- Updated next-session plan with concrete triggers.
- Watchlist continuation/removal notes.

## Obsidian / Markdown Sync

When asked to sync to Obsidian or a local journal, write one daily Markdown note:

```text
<vault>/Daily/YYYY-MM-DD.md
```

Use the helper script when useful:

```bash
python3 scripts/write_daily_note.py --vault /path/to/vault --date YYYY-MM-DD --section plan --content /tmp/plan.md
python3 scripts/write_daily_note.py --vault /path/to/vault --date YYYY-MM-DD --section review --content /tmp/review.md
python3 scripts/write_daily_note.py --vault /path/to/vault --date YYYY-MM-DD --section us_plan --content /tmp/us-plan.md --chinese
python3 scripts/write_daily_note.py --vault /path/to/vault --date YYYY-MM-DD --section us_review --content /tmp/us-review.md --chinese
```

Read `references/obsidian-format.md` for the recommended note structure and frontmatter.

## Client Portability

Keep the skill usable across Codex, Claude Code, Cursor, Cline/Roo, JetBrains assistants, and future AI clients.

- Keep core behavior in this `SKILL.md`; put deterministic repeated work in bundled scripts.
- Prefer relative paths inside the skill bundle such as `scripts/write_daily_note.py` and `references/obsidian-format.md`.
- Do not depend on a Codex-only connector when a local script, OpenD endpoint, exported file, or broker UI can provide the same data.
- When a client cannot run bundled scripts, provide the command the user or client should run and continue from the resulting file/output.
- If installing into another client, copy the whole `skill/folio-scribe/` folder when that client supports skill bundles. If it only supports global instructions, paste the essential `SKILL.md` content and keep script/reference paths documented separately.
- Never make client installation steps part of trading analysis output unless the user is explicitly setting up the skill.

## Safety

- This skill does not provide guaranteed returns.
- Treat all suggestions as decision support, not financial advice.
- Do not automate broker order entry.
- Do not recommend adding leverage unless the plan explicitly includes loss limits and margin consequences.
