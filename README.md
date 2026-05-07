# Folio Scribe

Language: [中文](#中文) | [English](#english)

## 中文

Folio Scribe 是一个只读交易工作流 skill，也包含一组可复用的 Python
工具。它可以把券商数据整理成交易计划、盘后复盘、观察列表，以及
Obsidian/Markdown 交易日志。

它的定位是“辅助计划和复盘”，默认不会下单、改单或撤单。

### 适合做什么

- 读取券商 API、券商桌面端、导出文件、截图或手动快照里的账户信息。
- 汇总账户风险、持仓、委托、成交、报价、期权、新闻和观察信号。
- 按港股、美股或其他市场的交易时段生成计划。
- 对照原计划做盘后复盘，检查纪律、风险漂移、追高、过度交易和错失机会。
- 把计划和复盘同步到一篇 Obsidian 每日笔记。
- 在 Codex、Claude Code、Cursor、Cline/Roo、JetBrains AI 助手等客户端中复用。

### 适合谁使用

如果你希望 AI 助手帮你做下面这些事，可以使用 Folio Scribe：

- 每日盘前交易计划。
- 收盘后交易复盘。
- 观察列表维护。
- 投资组合和风险摘要。
- Obsidian 交易日志。
- 只读券商数据工作流。

不要把它当成自动交易机器人。所有输出都应视为决策辅助，而不是金融建议。

### 目录结构

```text
skill/folio-scribe/        AI skill bundle
  SKILL.md                 兼容客户端加载的核心指令
  scripts/                 辅助脚本，例如 Obsidian 笔记同步
  references/              需要时加载的参考文档
  agents/openai.yaml       Codex 界面元数据

src/folio_scribe/          可复用 Python 包
tests/                     单元测试
docs/                      项目背景和路线图
```

### 在 Codex 中快速使用

把 `skill/folio-scribe/` 安装到 Codex skills 目录，或者在当前仓库中让
Codex 使用 `folio-scribe` skill。

常用提示词：

```text
使用 Folio Scribe 根据我的券商数据生成今天的港股交易计划。
```

```text
使用 Folio Scribe 复盘今晚的美股交易，并更新我的 Obsidian 交易日志。
```

```text
读取我当前的持仓和委托，然后为下一交易时段生成观察列表。不要下单。
```

如果你的 AI 客户端支持 skill 文件夹，复制整个目录即可：

```text
skill/folio-scribe/
```

如果客户端只支持全局自定义指令，可以把
`skill/folio-scribe/SKILL.md` 的核心内容粘贴进去，并保留 `scripts/`
和 `references/` 作为外部辅助资源。

### 数据来源优先级

Folio Scribe 优先使用实时、结构化的券商数据，而不是过期网页报价。

推荐优先级：

1. 券商 API，例如 Futu OpenD/OpenAPI。
2. 券商桌面端可见数据。
3. 券商导出报表。
4. 截图。
5. 手动整理的持仓、委托和成交快照。

使用 Futu 时，请先确认 Futu OpenD 已安装、正在运行、已登录，并且本地端口可连接。
默认端口通常是 `11111`。

当前实现状态：Python Futu adapter 是只读 beta 实现。它可以通过 OpenD 读取
报价快照、账户摘要、持仓、当前委托和近期成交；期权链、订单簿、逐笔、K 线和
更丰富的市场上下文仍在路线图中。

只读连通性检查：

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only
```

读取结构化 JSON：

```bash
python3 -m folio_scribe.futu_snapshot US.AAPL HK.00700
```

### 同步到 Obsidian

每日笔记路径：

```text
<vault>/Daily/YYYY-MM-DD.md
```

使用内置脚本插入或更新每日笔记中的某个章节：

```bash
python3 skill/folio-scribe/scripts/write_daily_note.py \
  --vault /path/to/your/vault \
  --date 2026-05-07 \
  --section hk_plan \
  --content /tmp/plan.md \
  --chinese
```

支持的章节名：

```text
plan, review, hk_plan, hk_review, us_plan, us_review
计划, 总结, 港股计划, 港股总结, 美股计划, 美股总结
```

推荐每日笔记结构：

```text
Daily/YYYY-MM-DD.md
├── 港股交易计划
├── 港股交易总结
├── 美股交易计划
└── 美股交易总结
```

如果你在亚洲时区查看美股，美股收盘复盘通常发生在本地第二天早上。Folio Scribe
默认会把复盘写回美股交易所对应的交易日期，而不是本地日期，除非你明确要求按本地
日期记录。

### 示例工作流

1. 先让 Codex 读取当前券商数据。
2. 生成交易计划：

   ```text
   使用 Folio Scribe 为下一次美股交易时段生成计划。包含当前持仓、未完成委托、
   风险边界和 3 个观察标的。
   ```

3. 你自己在券商软件中手动交易。
4. 交易结束后生成复盘：

   ```text
   使用 Folio Scribe 对照美股交易计划做复盘，并更新我的 Obsidian 每日笔记。
   ```

5. 保留每日记录，之后可用于周复盘和月复盘。

### Python 开发

本地安装：

```bash
python3 -m pip install -e .
```

安装 Futu 支持：

```bash
python3 -m pip install -e ".[futu]"
```

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

### 安全边界

- 默认只读。
- 不自动下单。
- 不自动改单或撤单，除非用户单独、明确提出。
- 不承诺收益。
- 不假设隐藏账户信息。
- 实时券商数据优先于旧对话上下文。
- 杠杆和期权风险必须清楚说明。

### 项目文档

- `docs/PROJECT_CONTEXT.md`
- `docs/ROADMAP.md`

许可证：MIT。

[Back to top](#folio-scribe)

## English

Folio Scribe is a read-only trading workflow skill with a small reusable Python
toolkit. It turns broker data into trading plans, session reviews, watchlists,
and Obsidian/Markdown trading journals.

It is designed for planning and review. By default, it does not place, modify,
or cancel orders.

### What It Can Do

- Read account context from broker APIs, broker desktop apps, exported files,
  screenshots, or manual snapshots.
- Summarize account risk, positions, orders, fills, quotes, options, news, and
  watchlist signals.
- Create market-session-aware plans for HK, US, or other markets.
- Review a session against the original plan and call out discipline, risk
  drift, chasing, overtrading, and missed setups.
- Sync plans and reviews into one Obsidian daily note.
- Stay portable across Codex, Claude Code, Cursor, Cline/Roo, JetBrains AI
  assistants, and similar clients.

### Who This Is For

Use Folio Scribe if you want an AI assistant to help with:

- Daily pre-market trading plans.
- Post-close trading reviews.
- Watchlist maintenance.
- Portfolio and risk summaries.
- Obsidian trading journals.
- Read-only broker-data workflows.

Do not use it as an automated trading bot. Treat all output as decision support,
not financial advice.

### Repository Layout

```text
skill/folio-scribe/        AI skill bundle
  SKILL.md                 Core instructions loaded by compatible clients
  scripts/                 Helper scripts, including Obsidian note sync
  references/              Optional references loaded when needed
  agents/openai.yaml       Codex UI metadata

src/folio_scribe/          Reusable Python package
tests/                     Unit tests
docs/                      Project context and roadmap
```

### Quick Start With Codex

Install `skill/folio-scribe/` into your Codex skills directory, or keep this
repo as your working project and ask Codex to use the `folio-scribe` skill.

Example prompts:

```text
Use Folio Scribe to create today's HK trading plan from my broker data.
```

```text
Use Folio Scribe to review tonight's US session and update my Obsidian journal.
```

```text
Read my current positions and orders, then create a watchlist for the next
session. Do not place any orders.
```

If your AI client supports skill folders, copy the whole directory:

```text
skill/folio-scribe/
```

If your client only supports global custom instructions, paste the essential
contents of `skill/folio-scribe/SKILL.md` into that client's instruction area
and keep `scripts/` and `references/` available as external resources.

### Data Source Priority

Folio Scribe prefers live, structured broker data over stale web quotes.

Recommended order:

1. Broker APIs, such as Futu OpenD/OpenAPI.
2. Broker desktop app data.
3. Exported broker reports.
4. Screenshots.
5. Manual position, order, and fill snapshots.

When using Futu, first confirm that Futu OpenD is installed, running, logged in,
and reachable on the local port. The default port is usually `11111`.

Current implementation status: the Python Futu adapter is a read-only beta. It
can read quote snapshots, account summaries, positions, current orders, and
recent fills through OpenD. Option-chain, order-book, tick, K-line, and richer
market-context reads are still roadmap work.

Read-only connectivity check:

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only
```

Read structured JSON:

```bash
python3 -m folio_scribe.futu_snapshot US.AAPL HK.00700
```

### Obsidian Sync

Daily note path:

```text
<vault>/Daily/YYYY-MM-DD.md
```

Use the bundled helper script to insert or update one section of a daily note:

```bash
python3 skill/folio-scribe/scripts/write_daily_note.py \
  --vault /path/to/your/vault \
  --date 2026-05-07 \
  --section hk_plan \
  --content /tmp/plan.md \
  --chinese
```

Supported section names:

```text
plan, review, hk_plan, hk_review, us_plan, us_review
计划, 总结, 港股计划, 港股总结, 美股计划, 美股总结
```

Recommended daily structure:

```text
Daily/YYYY-MM-DD.md
├── HK Trading Plan
├── HK Trading Review
├── US Trading Plan
└── US Trading Review
```

For US markets viewed from Asia time zones, the post-close review often happens
the next local morning. Folio Scribe normally writes that review back to the US
exchange session date unless you explicitly ask for local-date journaling.

### Example Workflow

1. Start by asking Codex to read current broker data.
2. Create a trading plan:

   ```text
   Use Folio Scribe to create a US trading plan for the next session. Include
   current positions, working orders, risk boundaries, and 3 watchlist names.
   ```

3. Trade manually in your broker app.
4. Create a review after the session:

   ```text
   Use Folio Scribe to review the US session against the plan and update my
   Obsidian daily note.
   ```

5. Keep the daily record for weekly and monthly reviews.

### Python Development

Install locally:

```bash
python3 -m pip install -e .
```

Install Futu support:

```bash
python3 -m pip install -e ".[futu]"
```

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

### Safety Boundaries

- Read-only by default.
- No automated order entry.
- No order modification or cancellation unless separately and explicitly
  requested.
- No guaranteed returns.
- No hidden account assumptions.
- Live broker data wins over stale conversation context.
- Leverage and options risk must be called out plainly.

### Project Docs

- `docs/PROJECT_CONTEXT.md`
- `docs/ROADMAP.md`

License: MIT.

[Back to top](#folio-scribe)
