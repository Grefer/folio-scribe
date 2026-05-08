<![CDATA[<div align="center">

# 📒 Folio Scribe

**Broker data → Trading plans · Session reviews · Obsidian journals**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.3-blue.svg)](CHANGELOG.md)
[![Skill](https://img.shields.io/badge/AI%20Skill-Claude%20%7C%20Codex%20%7C%20Cursor-blueviolet)](#-quick-start)

*A read-only AI skill that turns live broker data into structured trading plans,
post-session reviews, and Obsidian/Markdown journals — without ever placing an order.*

[中文](#-中文说明) · [English](#-what-it-does) · [Quick Start](#-quick-start) · [Example Output](#-example-output)

</div>

---

## ✨ What It Does

| Capability | Description |
|:--|:--|
| 📊 **Read broker data** | Connects to broker APIs (Futu OpenD), desktop apps, exports, screenshots, or manual snapshots |
| 📝 **Trading plans** | Session-aware plans for HK, US, or other markets with trigger prices and risk boundaries |
| 🔍 **Session reviews** | Post-close reviews that check discipline, risk drift, chasing, overtrading, and missed setups |
| 📓 **Obsidian sync** | Auto-writes plans and reviews into structured daily notes with YAML frontmatter |
| ⏰ **Scheduled automation** | macOS launchd tasks that generate journals at the right time for each market session |
| 🔒 **Read-only by design** | Never places, modifies, or cancels orders — decision support, not financial advice |

## 🎯 Who This Is For

Folio Scribe is for traders who want an AI assistant to help with:

- 📋 Daily pre-market **trading plans**
- 📈 Post-close **session reviews**
- 👀 **Watchlist** maintenance and tracking
- 🛡️ **Portfolio and risk** summaries
- ✍️ Obsidian **trading journals**

> [!CAUTION]
> This is **not** an automated trading bot. All output should be treated as decision support, not financial advice.

## 🚀 Quick Start

### Claude Code

```bash
# Install the skill (symlink)
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe
```

Then use it in any Claude Code session:

```
/folio-scribe 生成今天的港股交易计划，写入 Obsidian vault
/folio-scribe Review today's HK session against the plan
/folio-scribe 读取当前持仓，生成美股交易计划
```

<details>
<summary>Non-interactive / script usage</summary>

```bash
claude -p "/folio-scribe Create today's HK trading plan" \
  --permission-mode acceptEdits \
  --allowed-tools "Read,Write,Bash(python3 *read_futu_snapshot.py*),Bash(python3 *write_daily_note.py*)"
```

</details>

### Codex

Install `skill/folio-scribe/` into your Codex skills directory, then:

```
Use Folio Scribe to create today's HK trading plan from my broker data.
Use Folio Scribe to review tonight's US session and update my Obsidian journal.
```

### Other AI Clients

| Client | Method |
|:--|:--|
| **Cursor / Cline / Roo** | Copy `skill/folio-scribe/` folder into the client's skill directory |
| **JetBrains AI** | Paste `SKILL.md` content into global custom instructions |
| **Others** | Keep `SKILL.md` as instructions + `scripts/` and `references/` as resources |

## 🏗️ Architecture

```
folio-scribe/
├── skill/folio-scribe/           ← AI skill bundle (copy this to use)
│   ├── SKILL.md                     Core instructions for AI clients
│   ├── scripts/
│   │   ├── run_folio_task.sh        Scheduled / manual task runner
│   │   ├── install_schedule.sh      macOS launchd installer
│   │   ├── check_setup.sh           Health-check utility
│   │   ├── write_daily_note.py      Obsidian note section writer
│   │   ├── read_futu_snapshot.py    Futu OpenD snapshot reader
│   │   └── launchd/                 Plist templates
│   └── references/                  Reference docs loaded on demand
│
├── src/folio_scribe/             ← Reusable Python package
│   ├── models.py                    BrokerSnapshot dataclasses
│   ├── data_sources/                Broker adapters (Futu, ...)
│   ├── journal/                     Obsidian writer module
│   └── futu_snapshot.py             CLI entry point
│
├── tests/                        ← Unit tests
├── docs/                         ← Project context & roadmap
└── pyproject.toml
```

> [!TIP]
> The `skill/folio-scribe/` bundle is **self-contained** — copy it without installing the Python package. Only `futu-api` is needed for broker reads.

## 📡 Data Sources

Folio Scribe prefers **live, structured broker data** over stale web quotes:

| Priority | Source | Status |
|:--:|:--|:--:|
| 1️⃣ | Broker APIs (Futu OpenD / OpenAPI) | ✅ Beta |
| 2️⃣ | Broker desktop app (visible data) | ✅ |
| 3️⃣ | Exported broker reports | ✅ |
| 4️⃣ | Screenshots | ✅ |
| 5️⃣ | Manual position / order snapshots | ✅ |

### Futu OpenD

Ensure OpenD is **installed, running, logged in**, and reachable on port `11111` (default).

```bash
# Connectivity check
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only

# Full JSON snapshot
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL HK.00700
```

<details>
<summary>Current Futu adapter capabilities</summary>

| Feature | Status |
|:--|:--:|
| Account summary, positions, orders, fills | ✅ |
| Quote snapshots | ✅ |
| Option chain, order book, ticks, K-line | 🗓️ Roadmap |
| News, sentiment, capital-flow anomalies | 🗓️ Roadmap |

</details>

## 📓 Obsidian Sync

### Daily Note Structure

```
<vault>/Daily/YYYY-MM-DD.md
├── 港股交易计划  /  HK Trading Plan
├── 港股交易总结  /  HK Trading Review
├── 美股交易计划  /  US Trading Plan
└── 美股交易总结  /  US Trading Review
```

### Write a Section

```bash
python3 skill/folio-scribe/scripts/write_daily_note.py \
  --vault /path/to/your/vault \
  --date 2026-05-07 \
  --section hk_plan \
  --content /tmp/plan.md \
  --chinese
```

Supported section names:

```
plan, review, hk_plan, hk_review, us_plan, us_review
计划, 总结, 港股计划, 港股总结, 美股计划, 美股总结
```

> [!NOTE]
> For US markets viewed from Asia, the post-close review happens the next local morning. Folio Scribe writes it back to the **US session date** by default.

## ⏰ Scheduled Tasks

Automate journal generation via macOS launchd:

```bash
# Install (default vault ~/Documents/Trading)
skill/folio-scribe/scripts/install_schedule.sh install

# Custom vault
skill/folio-scribe/scripts/install_schedule.sh install --vault ~/Documents/MyVault
```

### Schedule

| Time (HKT) | Task | Description |
|:--:|:--|:--|
| `06:45` | 🌙 US Trading Review | Writes to previous session's note |
| `08:45` | 🇭🇰 HK Trading Plan | Before HK market open |
| `16:15` | 🇭🇰 HK Trading Review | After HK market close |
| `20:45` | 🇺🇸 US Trading Plan | Before US market open |

### Auto-Detection Rules

When running without arguments, the task type is inferred from the current time:

| Local Time | Task |
|:--|:--|
| 05:00 – 08:29 | `us_review` |
| 08:30 – 12:59 | `hk_plan` |
| 13:00 – 19:59 | `hk_review` |
| 20:00 – 04:59 | `us_plan` |

```bash
# Auto-detect
skill/folio-scribe/scripts/run_folio_task.sh

# Explicit
skill/folio-scribe/scripts/run_folio_task.sh hk_plan
```

<details>
<summary>Management & Logs</summary>

```bash
# Status
skill/folio-scribe/scripts/install_schedule.sh status

# Uninstall
skill/folio-scribe/scripts/install_schedule.sh uninstall

# View logs
cat ~/Documents/Trading/.logs/folio-$(date +%Y%m%d)-hk_plan.log
cat ~/Documents/Trading/.logs/launchd-hk-plan.out
```

</details>

<details>
<summary>Important notes</summary>

- 💻 Mac must be **awake** at trigger time
- 📅 US Friday review can run on local Saturday morning
- 🔑 Futu OpenD auto-launches but must have been **logged in at least once**
- 🤖 Uses Claude Code global model setting; auto-falls back to Sonnet when overloaded
- 🔒 Uses a narrow tool allowlist — does **not** enable `--dangerously-skip-permissions`

</details>

## 📋 Example Output

Below is an auto-generated daily trading journal with dummy data.
See the full example at [`docs/example-daily-note.md`](docs/example-daily-note.md).

<details>
<summary><b>🇭🇰 港股交易计划 (08:45 auto-generated)</b></summary>

```markdown
## 08:45 港股交易计划

数据源：Futu OpenD 实时快照 | 生成时间：2026-01-15 08:45 HKT

### 账户快照与风险敞口

| 项目 | 数值 | 备注 |
|------|------|------|
| 总资产 | USD 25,380.50 | 较昨收 +1.2% |
| 现金余额 | USD 8,125.30 | 充足 |
| 港股集中度 | ~62% | 分散合理 |

### 当前持仓

| 标的 | 名称 | 数量 | 成本 | 现价 | 浮动盈亏 |
|------|------|------|------|------|----------|
| HK.00700 | 腾讯控股 | 200 股 | HK$368.50 | HK$392.40 | +HK$4,780 (+6.5%) |
| HK.09888 | 百度集团-W | 500 股 | HK$102.30 | HK$108.60 | +HK$3,150 (+6.2%) |
| US.NVDA | NVIDIA | 15 股 | USD 142.80 | USD 148.50 | +USD 85.50 (+4.0%) |

### 港股操作计划 — 腾讯（HK.00700）

| 情景 | 触发条件 | 操作 | 备注 |
|------|----------|------|------|
| 多头确认 | 站稳 $395 上方 ≥15 分钟 | 持仓不动，上看 $400 | 不追高 |
| 箱体震荡 | $388 – $395 间反复 | 按兵不动 | |
| 跌破支撑 | 跌破 $385 | 减仓 100 股 | 保护利润 |

### 风险边界与今日红线

1. **不加仓腾讯**：集中度已达 62%
2. **不新开港股仓位**
3. **不在开盘 15 分钟内交易**
4. **不使用市价单**
5. **最大新增敞口：0**；**最大减仓：腾讯 100 股 + 百度 200 股**
```

</details>

<details>
<summary><b>🇭🇰 港股交易总结 (16:15 auto-generated)</b></summary>

```markdown
## 16:15 港股交易总结

收盘时间：2026-01-15 16:00 HKT

### 账户变动

| 项目 | 开盘 | 收盘 | 变动 |
|------|------|------|------|
| 总资产 | USD 25,380.50 | USD 25,612.80 | +USD 232.30 (+0.92%) |

### 计划执行评估

| 计划项 | 执行情况 | 评分 |
|--------|----------|------|
| 不加仓腾讯 | ✅ 严格执行 | 10/10 |
| 不在开盘15分钟内交易 | ✅ 执行 | 10/10 |
| 跌破 $385 减仓 | 未触发 | — |

**纪律评分：9/10** — 全程按计划执行，未做冲动交易。

### 改进建议

- 腾讯突破 $395 后未及时设置移动止盈，下次应提前规划
- 百度走势平淡，考虑是否继续持有
```

</details>

<details>
<summary><b>📄 Obsidian Frontmatter (auto-populated)</b></summary>

```yaml
---
date: 2026-01-15
type: trading-daily
tags: [trading, broker-journal]
model: claude-opus-4-0-20250514
plan_score: 8
discipline_score: 9
---
```

</details>

## 💡 Example Workflow

```
1. 📊 Read broker data    →  AI reads live positions, orders, quotes via Futu/broker
2. 📝 Generate plan       →  "Create a US trading plan with risk boundaries"
3. 💹 Trade manually      →  You execute trades in your broker app
4. 🔍 Generate review     →  "Review the US session against the plan"
5. 📓 Journal saved       →  Daily note in Obsidian for weekly/monthly reviews
```

## 🛠️ Setup

### New Machine

```bash
# 1. Install Futu SDK (for OpenD reads)
python3 -m pip install futu-api

# 2. Install Claude Code skill (symlink)
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe

# 3. (Optional) Install scheduled tasks
skill/folio-scribe/scripts/install_schedule.sh install

# 4. (Optional) Verify setup
skill/folio-scribe/scripts/check_setup.sh
```

### Python Development

```bash
# Install locally (editable)
python3 -m pip install -e .

# With Futu support
python3 -m pip install -e ".[futu]"

# Run tests
PYTHONPATH=src python3 -m unittest discover -s tests
```

### Environment Variables

| Variable | Default | Description |
|:--|:--|:--|
| `FOLIO_SCRIBE_VAULT` | `~/Documents/Trading` | Obsidian vault path |
| `FOLIO_SCRIBE_OPEND_APP` | `~/Applications/Futu_OpenD/FutuOpenD.app` | Futu OpenD app path |
| `FOLIO_SCRIBE_OPEND_PORT` | `11111` | Futu OpenD port |
| `FOLIO_SCRIBE_CLAUDE` | Auto-detected | Claude Code CLI path |
| `FOLIO_SCRIBE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Claude Code permission mode |
| `FOLIO_SCRIBE_ALLOWED_TOOLS` | Limited allowlist | Claude Code tool allowlist |
| `FOLIO_SCRIBE_LANG` | `zh` | Output language (`en` / `zh`) |

## 🔒 Safety Boundaries

| Principle | Detail |
|:--|:--|
| 🔐 Read-only | No automated order entry, modification, or cancellation |
| 📊 Data-first | Live broker data always wins over stale context |
| 🚫 No guarantees | All output is decision support, not financial advice |
| ⚠️ Risk transparency | Leverage and options risk must be called out plainly |
| 🔏 Privacy | Personal account data stays outside the public repo |

## 📚 Documentation

| Document | Description |
|:--|:--|
| [`SKILL.md`](skill/folio-scribe/SKILL.md) | Core AI skill definition |
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | Product decisions and design principles |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestone tracking |
| [`docs/example-daily-note.md`](docs/example-daily-note.md) | Full example output |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |

---

## 🇨🇳 中文说明

Folio Scribe 是一个**只读**交易工作流 AI Skill，附带一组可复用的 Python 工具。

它可以把券商数据整理成：**交易计划** · **盘后复盘** · **关注标的追踪** · **Obsidian 交易日志**。

定位是「辅助计划和复盘」，默认**不会下单、改单或撤单**。

### 适合做什么

- 🔌 读取券商 API（Futu OpenD）、桌面端、导出文件、截图或手动快照
- 📊 汇总账户风险、持仓、委托、成交、报价、期权、新闻和观察信号
- 📝 按港股/美股交易时段生成计划
- 🔍 对照原计划做盘后复盘，检查纪律、风险漂移、追高和过度交易
- 📓 同步到 Obsidian 每日笔记
- 🔄 支持 Codex、Claude Code、Cursor、Cline/Roo、JetBrains AI 等客户端

### 快速使用

**Claude Code：**

```bash
# 安装 skill（符号链接）
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe
```

```
/folio-scribe 生成今天的港股交易计划，写入 Obsidian vault
/folio-scribe 对照今天的计划做港股收盘总结
/folio-scribe 读取当前持仓，生成美股交易计划
```

**Codex：**

```
使用 Folio Scribe 根据我的券商数据生成今天的港股交易计划。
使用 Folio Scribe 复盘今晚的美股交易，并更新我的 Obsidian 交易日志。
```

### 新机器部署

```bash
# 1. 安装 Futu SDK
python3 -m pip install futu-api

# 2. 安装 Claude Code skill
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe

# 3. 安装定时任务（可选）
skill/folio-scribe/scripts/install_schedule.sh install

# 4. 验证安装（可选）
skill/folio-scribe/scripts/check_setup.sh
```

### 定时任务

| 时间 (HKT) | 任务 | 说明 |
|:--:|:--|:--|
| `06:45` | 🌙 美股交易总结 | 写入前一交易日笔记 |
| `08:45` | 🇭🇰 港股交易计划 | 开盘前 |
| `16:15` | 🇭🇰 港股交易总结 | 收盘后 |
| `20:45` | 🇺🇸 美股交易计划 | 美股开盘前 |

<details>
<summary>定时任务管理</summary>

```bash
# 安装（自定义 vault 路径）
skill/folio-scribe/scripts/install_schedule.sh install --vault ~/Documents/MyVault

# 查看状态
skill/folio-scribe/scripts/install_schedule.sh status

# 卸载
skill/folio-scribe/scripts/install_schedule.sh uninstall
```

注意事项：
- 电脑需处于开机且未休眠状态
- 美股周五复盘可在本地周六早上运行
- Futu OpenD 自动启动，但需已登录过一次
- 使用 Claude Code 全局模型，Opus 过载时降级到 Sonnet

</details>

### 安全边界

- 🔐 默认只读，不自动下单
- 📊 实时券商数据优先于旧上下文
- 🚫 不承诺收益，不提供金融建议
- ⚠️ 杠杆和期权风险必须清楚说明

---

<div align="center">

**MIT License** · [Changelog](CHANGELOG.md) · [Roadmap](docs/ROADMAP.md)

</div>
]]>
