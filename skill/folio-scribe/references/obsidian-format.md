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
cssclasses: [trading-journal]
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

## Callout Types

Use Obsidian callout blocks for visually distinct sections. The `trading-journal` CSS snippet styles these automatically.

```markdown
> [!红线] 风险边界与今日红线
> 1. **不加仓腾讯** — 集中度已达 62%
> 2. **不在开盘 15 分钟内交易**

> [!计划] 腾讯（HK.00700）—— 核心持仓
> | 情景 | 触发条件 | 操作 |
> |------|----------|------|
> | 多头确认 | 站稳 $395 | 持仓不动 |

> [!评分] 纪律评分 9/10 · 计划评分 8/10
> 全程按计划执行，未做冲动交易。

> [!改进] 改进建议
> 1. 腾讯突破 $395 后未及时设置移动止盈
> 2. 百度走势平淡，考虑是否继续持有

> [!观察] 港股观察清单
> | 标的 | 关注理由 |
> |------|----------|
> | HK.01810 小米 | 智能硬件龙头 |

> [!价位] 关键价位提示牌
> 腾讯：支撑 $385 / 压力 $400
```

Available callout types (Chinese and English aliases):

| Callout | Alias | Use |
|---------|-------|-----|
| `红线` | `redline` | Risk boundaries, do-not-do rules |
| `计划` | `plan` | Position-specific action plan |
| `评分` | `score` | Discipline and plan scores |
| `改进` | `improve` | Post-session improvement notes |
| `观察` | `watchlist` | Watch-only candidates |
| `价位` | `levels` | Key price levels, monospace |
