# Obsidian Trading Journal Format

Use one note per trading day:

```text
Daily/YYYY-MM-DD.md
```

Recommended frontmatter:

```yaml
---
date: YYYY-MM-DD
type: trading-daily
tags: [trading, broker-journal]
model:
plan_score:
discipline_score:
---
```

Recommended body:

```markdown
# YYYY-MM-DD Trading Journal

## 08:45 HK Trading Plan

### Account Snapshot

### Current Positions

### Orders and Fills

### Position-Specific Plan

### Options Plan

### Recommended Watchlist

### Do Not Do Today

---

## 16:15 HK Trading Review

### Account Changes

### Fills

### Plan Execution

### Position Performance

### Watchlist Review

### Mistakes and Improvements

### Next Session Plan

---

## 20:45 US Trading Plan

### US Account and Exposure

### US Positions and Orders

### US Watchlist

### Do Not Do This Session

---

## 06:45 US Trading Review

### US Session Account Changes

### US Fills

### US Plan Execution

### Next US Session Plan
```

If the user's language is not English, use their language for headings and content. Preserve the same section intent. For markets that cross local midnight, store the review in the note for the exchange session date unless the user explicitly wants local-date journaling.
