<div align="center">

# 📒 Folio Scribe

**Broker data → Trading plans · Session reviews · Obsidian journals**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.3-blue.svg)](CHANGELOG.md)
[![Skill](https://img.shields.io/badge/AI%20Skill-Claude%20%7C%20Codex%20%7C%20Cursor-blueviolet)](#quick-start)

*A read-only AI skill that turns live broker data into structured trading plans,
post-session reviews, and Obsidian/Markdown journals — without ever placing an order.*

[中文](#中文说明) · [English](#what-it-does) · [Quick Start](#quick-start) · [Example Output](#example-output)

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
│   │   ├── build_web_journal.py     Static private web dashboard exporter
│   │   └── launchd/                 Plist templates
│   ├── web-template/                Static dashboard HTML/CSS/JS
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

## 🌐 Private Web Dashboard

Export Daily notes into a static, mobile-friendly dashboard:

```bash
python3 skill/folio-scribe/scripts/build_web_journal.py \
  --vault ~/Documents/Trading \
  --out ~/Documents/TradingWeb \
  --title "Trading Journal"
```

Preview locally:

```bash
python3 -m http.server 8787 --directory ~/Documents/TradingWeb
```

Then open `http://127.0.0.1:8787`.

The output contains `index.html`, local assets, `data/journal.json`, and a `robots.txt` that disallows indexing. Deploy that output directory to Vercel, then protect access with Vercel Authentication. On Vercel Hobby, Standard Protection protects preview and deployment URLs, but production domains remain public; keep this journal on a protected preview URL unless your plan supports protecting all deployments.

Safe Vercel deploy, creating a protected preview URL instead of a public production alias:

```bash
FOLIO_SCRIBE_VERCEL_SCOPE=<your-team-slug> \
skill/folio-scribe/scripts/deploy_web_journal_vercel.sh \
  --out ~/Documents/TradingWeb \
  --project vercel-trading-journal
```

The deploy script links the output directory, enables Vercel SSO protection, and defaults to a preview deployment so the private journal is available only through the protected deployment URL it prints.

For a private custom domain, add Basic Auth environment variables in Vercel, point DNS at Vercel, and deploy production through the custom-domain path:

```bash
FOLIO_SCRIBE_VERCEL_SCOPE=<your-team-slug> \
FOLIO_SCRIBE_VERCEL_DOMAIN=folio.example.com \
skill/folio-scribe/scripts/deploy_web_journal_vercel.sh \
  --out ~/Documents/TradingWeb \
  --project vercel-trading-journal
```

With `FOLIO_SCRIBE_VERCEL_DOMAIN` set, the script deploys production, keeps the custom domain alias, and removes automatic `*.vercel.app` aliases.

To refresh the dashboard after every scheduled task, install launchd with:

```bash
FOLIO_SCRIBE_WEB_EXPORT_DIR=~/Documents/TradingWeb \
skill/folio-scribe/scripts/install_schedule.sh install
```

To also redeploy after each scheduled refresh, opt in explicitly:

```bash
FOLIO_SCRIBE_WEB_EXPORT_DIR=~/Documents/TradingWeb \
FOLIO_SCRIBE_WEB_DEPLOY=vercel \
FOLIO_SCRIBE_VERCEL_PROJECT=vercel-trading-journal \
FOLIO_SCRIBE_VERCEL_SCOPE=<your-team-slug> \
FOLIO_SCRIBE_VERCEL_DOMAIN=folio.example.com \
skill/folio-scribe/scripts/install_schedule.sh install
```

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
- 🤖 Uses `FOLIO_SCRIBE_AI_CLI=claude` by default; set `FOLIO_SCRIBE_AI_CLI=codex` to generate through Codex CLI
- 🔒 The scheduler reads Futu and writes notes itself; the AI CLI only generates text
- 🧾 Claude runs in JSON mode and records actual `modelUsage` key(s) in note frontmatter when available
- 🔁 Reinstall launchd with `FOLIO_SCRIBE_AI_CLI=codex skill/folio-scribe/scripts/install_schedule.sh install` to persist a Codex-backed schedule

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
| `FOLIO_SCRIBE_AI_CLI` | `claude` | Text-generation CLI (`claude` / `codex`) |
| `FOLIO_SCRIBE_AI_MODEL` | CLI default | Explicit model override for the selected CLI |
| `FOLIO_SCRIBE_CLAUDE` | Auto-detected | Claude Code CLI path |
| `FOLIO_SCRIBE_CLAUDE_SETTINGS` | `~/.claude/settings.json` | Claude Code settings file used for env/model |
| `FOLIO_SCRIBE_CLAUDE_MODEL` | Current Claude Code model | Claude-specific model override, kept for compatibility |
| `FOLIO_SCRIBE_CLAUDE_FALLBACK_MODEL` | unset | Optional fallback model |
| `FOLIO_SCRIBE_CODEX` | Auto-detected | Codex CLI path |
| `FOLIO_SCRIBE_CODEX_CONFIG` | `~/.codex/config.toml` | Codex config used to record the configured model |
| `FOLIO_SCRIBE_CODEX_MODEL` | Current Codex model | Codex-specific model override |
| `FOLIO_SCRIBE_CODEX_PROFILE` | unset | Optional Codex config profile |
| `FOLIO_SCRIBE_CODEX_SANDBOX` | `read-only` | Codex exec sandbox mode |
| `FOLIO_SCRIBE_CODEX_DISABLE_FEATURES` | `plugins apps` | Codex features disabled for lean text-only runs |
| `FOLIO_SCRIBE_WEB_EXPORT_DIR` | unset | Optional static web dashboard output directory |
| `FOLIO_SCRIBE_WEB_TITLE` | `Folio Scribe Journal` | Static web dashboard title |
| `FOLIO_SCRIBE_MAX_BUDGET_USD` | `0.80` | Claude Code print-mode budget cap |
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

<details>
<summary>非交互 / 脚本调用</summary>

```bash
claude -p "/folio-scribe 生成今天的港股交易计划" \
  --permission-mode acceptEdits \
  --allowed-tools "Read,Write,Bash(python3 *read_futu_snapshot.py*),Bash(python3 *write_daily_note.py*)"
```

</details>

**Codex：**

```
使用 Folio Scribe 根据我的券商数据生成今天的港股交易计划。
使用 Folio Scribe 复盘今晚的美股交易，并更新我的 Obsidian 交易日志。
```

**其他 AI 客户端：**

| 客户端 | 方式 |
|:--|:--|
| **Cursor / Cline / Roo** | 复制 `skill/folio-scribe/` 文件夹到客户端的 skill 目录 |
| **JetBrains AI** | 将 `SKILL.md` 内容粘贴到全局自定义指令 |
| **其他** | `SKILL.md` 作为指令 + `scripts/` 和 `references/` 作为外部资源 |

### 目录结构

```
folio-scribe/
├── skill/folio-scribe/           ← AI skill 包（复制即用）
│   ├── SKILL.md                     各客户端加载的核心指令
│   ├── scripts/
│   │   ├── run_folio_task.sh        定时 / 手动执行入口
│   │   ├── install_schedule.sh      macOS launchd 安装器
│   │   ├── check_setup.sh           环境健康检查
│   │   ├── write_daily_note.py      Obsidian 笔记 section 写入
│   │   ├── read_futu_snapshot.py    Futu OpenD 快照读取
│   │   ├── build_web_journal.py     私有静态 Web 看板导出
│   │   └── launchd/                 Plist 模板
│   ├── web-template/                静态看板 HTML/CSS/JS
│   └── references/                  按需加载的参考文档
│
├── src/folio_scribe/             ← 可复用 Python 包
│   ├── models.py                    BrokerSnapshot 数据类
│   ├── data_sources/                券商适配器（Futu 等）
│   ├── journal/                     Obsidian 写入模块
│   └── futu_snapshot.py             CLI 入口
│
├── tests/                        ← 单元测试
├── docs/                         ← 项目背景与路线图
└── pyproject.toml
```

> [!TIP]
> `skill/folio-scribe/` 是**自包含**的——直接复制即可使用，无需安装 Python 包。券商读取仅需 `futu-api`。

### 数据来源

Folio Scribe 优先使用**实时、结构化的券商数据**，而非过期网页报价：

| 优先级 | 来源 | 状态 |
|:--:|:--|:--:|
| 1️⃣ | 券商 API（Futu OpenD / OpenAPI） | ✅ Beta |
| 2️⃣ | 券商桌面端可见数据 | ✅ |
| 3️⃣ | 券商导出报表 | ✅ |
| 4️⃣ | 截图 | ✅ |
| 5️⃣ | 手动整理的持仓/委托快照 | ✅ |

**Futu OpenD：** 确认 OpenD 已**安装、运行、登录**，且本地端口 `11111`（默认）可连接。

```bash
# 连通性检查
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only

# 完整 JSON 快照
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL HK.00700
```

<details>
<summary>当前 Futu 适配器能力</summary>

| 功能 | 状态 |
|:--|:--:|
| 账户摘要、持仓、委托、成交 | ✅ |
| 报价快照 | ✅ |
| 期权链、盘口、逐笔、K 线 | 🗓️ 路线图 |
| 新闻、舆情、资金流异常 | 🗓️ 路线图 |

</details>

### Obsidian 同步

**每日笔记结构：**

```
<vault>/Daily/YYYY-MM-DD.md
├── 港股交易计划
├── 港股交易总结
├── 美股交易计划
└── 美股交易总结
```

**写入 section：**

```bash
python3 skill/folio-scribe/scripts/write_daily_note.py \
  --vault /path/to/your/vault \
  --date 2026-05-07 \
  --section hk_plan \
  --content /tmp/plan.md \
  --chinese
```

支持的 section 名：

```
plan, review, hk_plan, hk_review, us_plan, us_review
计划, 总结, 港股计划, 港股总结, 美股计划, 美股总结
```

> [!NOTE]
> 美股收盘复盘通常发生在本地第二天早上。Folio Scribe 默认写回**美股交易所对应的交易日期**，而非本地日期。

### 私有 Web 看板

把 Daily notes 导出成静态、适配手机的交易日志看板：

```bash
python3 skill/folio-scribe/scripts/build_web_journal.py \
  --vault ~/Documents/Trading \
  --out ~/Documents/TradingWeb \
  --title "Trading Journal"
```

本地预览：

```bash
python3 -m http.server 8787 --directory ~/Documents/TradingWeb
```

然后打开 `http://127.0.0.1:8787`。

导出目录包含 `index.html`、本地前端资源、`data/journal.json` 和默认禁止索引的 `robots.txt`。把这个目录部署到 Vercel，并在托管平台侧启用 Vercel Authentication。Vercel Hobby 的 Standard Protection 可保护 preview/deployment URL，但 production domain 仍会公开；除非你的套餐支持保护所有部署，否则这类交易日志应先放在受保护的 preview URL 上。

如需每次定时任务完成后自动刷新看板，安装 launchd 时设置：

```bash
FOLIO_SCRIBE_WEB_EXPORT_DIR=~/Documents/TradingWeb \
skill/folio-scribe/scripts/install_schedule.sh install
```

### 示例输出

以下是自动生成的每日交易日志（虚拟数据）。完整示例见 [`docs/example-daily-note.md`](docs/example-daily-note.md)。

<details>
<summary><b>🇭🇰 港股交易计划（08:45 自动生成）</b></summary>

```markdown
## 08:45 港股交易计划

数据源：Futu OpenD 实时快照 | 生成时间：2026-01-15 08:45 HKT

### 账户快照与风险敞口

| 项目 | 数值 | 备注 |
|------|------|------|
| 总资产 | USD 25,380.50 | 较昨收 +1.2% |
| 现金余额 | USD 8,125.30 | 充足 |
| 港股集中度 | ~62% | 分散合理 |

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
```

</details>

<details>
<summary><b>🇭🇰 港股交易总结（16:15 自动生成）</b></summary>

```markdown
## 16:15 港股交易总结

### 计划执行评估

| 计划项 | 执行情况 | 评分 |
|--------|----------|------|
| 不加仓腾讯 | ✅ 严格执行 | 10/10 |
| 不在开盘15分钟内交易 | ✅ 执行 | 10/10 |
| 跌破 $385 减仓 | 未触发 | — |

**纪律评分：9/10** — 全程按计划执行，未做冲动交易。
```

</details>

### 工作流示例

```
1. 📊 读取券商数据    →  AI 通过 Futu / 券商读取持仓、委托、报价
2. 📝 生成交易计划    →  "为下一次美股交易时段生成计划，包含风险边界"
3. 💹 手动交易        →  你在券商软件中自行执行
4. 🔍 生成复盘        →  "对照美股交易计划做复盘"
5. 📓 日志保存        →  每日笔记存入 Obsidian，可用于周/月复盘
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

### Python 开发

```bash
# 本地安装（可编辑模式）
python3 -m pip install -e .

# 安装 Futu 支持
python3 -m pip install -e ".[futu]"

# 运行测试
PYTHONPATH=src python3 -m unittest discover -s tests
```

### 定时任务

| 时间 (HKT) | 任务 | 说明 |
|:--:|:--|:--|
| `06:45` | 🌙 美股交易总结 | 写入前一交易日笔记 |
| `08:45` | 🇭🇰 港股交易计划 | 开盘前 |
| `16:15` | 🇭🇰 港股交易总结 | 收盘后 |
| `20:45` | 🇺🇸 美股交易计划 | 美股开盘前 |

自动判断规则（无参数运行时）：

| 本地时间 | 任务 |
|:--|:--|
| 05:00 – 08:29 | `us_review` |
| 08:30 – 12:59 | `hk_plan` |
| 13:00 – 19:59 | `hk_review` |
| 20:00 – 04:59 | `us_plan` |

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
- 默认使用 `FOLIO_SCRIBE_AI_CLI=claude`；设置 `FOLIO_SCRIBE_AI_CLI=codex` 可切换为 Codex CLI 生成
- 调度器自行读取 Futu 并写入笔记；AI CLI 只负责生成文本
- Claude 模式会使用 JSON 输出，并在可用时把 `modelUsage` 里的实际模型 key 写入笔记 frontmatter；如果一次调用涉及多个内部模型，会全部记录
- 如需让 launchd 持久使用 Codex，执行 `FOLIO_SCRIBE_AI_CLI=codex skill/folio-scribe/scripts/install_schedule.sh install` 重装定时任务

</details>

### 环境变量

| 变量 | 默认值 | 说明 |
|:--|:--|:--|
| `FOLIO_SCRIBE_VAULT` | `~/Documents/Trading` | Obsidian vault 路径 |
| `FOLIO_SCRIBE_OPEND_APP` | `~/Applications/Futu_OpenD/FutuOpenD.app` | Futu OpenD 应用路径 |
| `FOLIO_SCRIBE_OPEND_PORT` | `11111` | Futu OpenD 端口 |
| `FOLIO_SCRIBE_AI_CLI` | `claude` | 文本生成 CLI（`claude` / `codex`） |
| `FOLIO_SCRIBE_AI_MODEL` | CLI 默认值 | 当前 CLI 的显式模型覆盖 |
| `FOLIO_SCRIBE_CLAUDE` | 自动检测 | Claude Code CLI 路径 |
| `FOLIO_SCRIBE_CLAUDE_SETTINGS` | `~/.claude/settings.json` | 用于读取 env/model 的 Claude Code 设置文件 |
| `FOLIO_SCRIBE_CLAUDE_MODEL` | 当前 Claude Code 模型 | Claude 专用模型覆盖，保留兼容 |
| `FOLIO_SCRIBE_CLAUDE_FALLBACK_MODEL` | 未设置 | 可选 fallback 模型 |
| `FOLIO_SCRIBE_CODEX` | 自动检测 | Codex CLI 路径 |
| `FOLIO_SCRIBE_CODEX_CONFIG` | `~/.codex/config.toml` | 用于记录当前模型的 Codex 配置文件 |
| `FOLIO_SCRIBE_CODEX_MODEL` | 当前 Codex 模型 | Codex 专用模型覆盖 |
| `FOLIO_SCRIBE_CODEX_PROFILE` | 未设置 | 可选 Codex config profile |
| `FOLIO_SCRIBE_CODEX_SANDBOX` | `read-only` | Codex exec 沙盒模式 |
| `FOLIO_SCRIBE_CODEX_DISABLE_FEATURES` | `plugins apps` | 为轻量 text-only 运行禁用的 Codex features |
| `FOLIO_SCRIBE_WEB_EXPORT_DIR` | 未设置 | 可选静态 Web 看板输出目录 |
| `FOLIO_SCRIBE_WEB_TITLE` | `Folio Scribe Journal` | 静态 Web 看板标题 |
| `FOLIO_SCRIBE_MAX_BUDGET_USD` | `0.80` | Claude Code print 模式预算上限 |
| `FOLIO_SCRIBE_LANG` | `zh` | 输出语言（`en` / `zh`） |

### 安全边界

| 原则 | 说明 |
|:--|:--|
| 🔐 只读 | 不自动下单、改单或撤单 |
| 📊 数据优先 | 实时券商数据始终优先于旧上下文 |
| 🚫 不承诺收益 | 所有输出均为决策辅助，非金融建议 |
| ⚠️ 风险透明 | 杠杆和期权风险必须清楚说明 |
| 🔏 隐私保护 | 个人账户数据不进入公开仓库 |

### 文档

| 文件 | 说明 |
|:--|:--|
| [`SKILL.md`](skill/folio-scribe/SKILL.md) | 核心 AI Skill 定义 |
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | 产品决策与设计原则 |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 里程碑追踪 |
| [`docs/example-daily-note.md`](docs/example-daily-note.md) | 完整示例输出 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本历史 |

---

<div align="center">

**MIT License** · [Changelog](CHANGELOG.md) · [Roadmap](docs/ROADMAP.md)

</div>
