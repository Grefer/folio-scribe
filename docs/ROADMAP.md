# Roadmap

## Milestone 1: Project Foundation

- [x] Codex skill bundle.
- [x] Obsidian daily note writer.
- [x] Shared broker snapshot models.
- [x] Read-only data source interface.
- [x] Futu OpenAPI scaffold.

## Milestone 2: Futu Read-Only Connector

- [ ] Connect to local OpenD.
- [ ] Add OpenD readiness checks for login state, host, port, and account context.
- [ ] Read account summary.
- [ ] Read positions.
- [ ] Read working orders and fills.
- [ ] Read quote snapshots for configured symbols.
- [ ] Read order book, ticks, and K-line snapshots when requested.
- [ ] Read option-chain snapshots.
- [ ] Ingest Futu news, comment sentiment, capital-flow anomalies, derivatives anomalies, technical signals, and sector context as optional risk/watchlist inputs.
- [ ] Normalize all data into `BrokerSnapshot`.

## Milestone 3: Report Generation

- [ ] Generate HK trading plan.
- [ ] Generate HK close review.
- [ ] Generate US trading plan with Asia time-zone handling.
- [ ] Generate US close review and write back to the session date.
- [ ] Generate weekly and monthly reviews from daily notes.

## Milestone 4: Safety and Privacy

- [ ] Redact account numbers by default.
- [ ] Add config validation.
- [ ] Add "read-only mode" assertions.
- [ ] Add sample data without private information.

## Milestone 5: Multi-Client Skill Support

- [ ] Keep `skill/folio-scribe/SKILL.md` portable across Codex, Claude Code, Cursor, Cline/Roo, and JetBrains assistants.
- [ ] Add a release/install workflow that can copy the full skill bundle into client-specific global skill directories.
- [ ] Ensure bundled scripts work when run from the skill directory or from the repository root.
- [ ] Document fallback behavior for clients that only support pasted custom instructions.

## Explicit Non-Goals

- Automated order placement.
- Trade modification/cancellation.
- Claims of guaranteed profitability.
