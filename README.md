# Folio Scribe

Language: [中文](#中文) | [English](#english)

## 中文

Folio Scribe 是一个只读交易工作流 skill，也包含一组可复用的 Python
工具。它可以把券商数据整理成交易计划、盘后复盘、关注标的追踪，以及
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
- 关注标的行情追踪。
- 投资组合和风险摘要。
- 撰写交易日志。
- 只读券商数据工作流。

不要把它当成自动交易机器人。所有输出都应视为决策辅助，而不是金融建议。

### 目录结构

```text
skill/folio-scribe/        AI skill bundle
  SKILL.md                 兼容客户端加载的核心指令
  scripts/
    run_folio_task.sh      定时任务 / 手动执行入口
    install_schedule.sh    安装 / 卸载 / 查看 macOS 定时任务
    write_daily_note.py    Obsidian 笔记 section 写入
    read_futu_snapshot.py  Futu OpenD 快照读取
    launchd/               macOS launchd plist 模板
  references/              需要时加载的参考文档

src/folio_scribe/          可复用 Python 包
tests/                     单元测试
docs/                      项目背景和路线图
```

### 在 Claude Code 中快速使用

安装 skill（符号链接到本仓库）：

```bash
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe
```

之后在 Claude Code 交互会话中直接使用 `/folio-scribe`：

```text
/folio-scribe 生成今天的港股交易计划，写入 Obsidian vault
```

```text
/folio-scribe 对照今天的计划做港股收盘总结
```

```text
/folio-scribe 读取当前持仓，生成美股交易计划
```

也可以在脚本中非交互调用：

```bash
claude -p "/folio-scribe 生成今天的港股交易计划" \
  --permission-mode acceptEdits \
  --allowed-tools "Read,Write,Bash(python3 *read_futu_snapshot.py*),Bash(python3 *write_daily_note.py*)"
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

### 在其他 AI 客户端中使用

如果客户端支持 skill 文件夹（Cursor、Cline/Roo 等），复制整个目录即可：

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

当前实现状态：Bundled Futu helper 是只读 beta 实现。它可以通过 OpenD 读取
报价快照、账户摘要、持仓、当前委托和近期成交；期权链、订单簿、逐笔、K 线和
更丰富的市场上下文仍在路线图中。

`skill/folio-scribe/scripts/` 里的 helper 脚本可以随 skill bundle 单独复制使用；
读取 Futu 仍需要本机安装 `futu-api`，但不要求安装本仓库的 `folio_scribe` Python 包。

只读连通性检查：

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only
```

读取结构化 JSON：

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL HK.00700
```

如果已安装本仓库 Python 包，也可以使用 `python3 -m folio_scribe.futu_snapshot ...`。

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

### 定时任务

Folio Scribe 支持通过 macOS launchd 定时生成交易日志。脚本会自动启动 Futu
OpenD（如果未运行）、调用 Claude Code 的 `/folio-scribe` skill 生成内容、
写入 Obsidian vault。

**安装定时任务：**

```bash
# 首次安装（默认 vault 路径 ~/Documents/Trading）
skill/folio-scribe/scripts/install_schedule.sh install

# 指定自定义 vault 路径
skill/folio-scribe/scripts/install_schedule.sh install --vault ~/Documents/MyVault
```

安装后，任务按下面本地时间触发；脚本会根据交易时段决定是否跳过：

| 时间 (HKT) | 任务 | 说明 |
|---|---|---|
| 06:45 | 美股交易总结 | 写入前一交易日笔记 |
| 08:45 | 港股交易计划 | 开盘前 |
| 16:15 | 港股交易总结 | 收盘后 |
| 20:45 | 美股交易计划 | 美股开盘前 |

**手动运行：**

```bash
# 自动判断（按当前时间决定生成哪个 section）
skill/folio-scribe/scripts/run_folio_task.sh

# 指定任务类型
skill/folio-scribe/scripts/run_folio_task.sh hk_plan
skill/folio-scribe/scripts/run_folio_task.sh hk_review
skill/folio-scribe/scripts/run_folio_task.sh us_plan
skill/folio-scribe/scripts/run_folio_task.sh us_review
```

自动判断规则：

| 时间段 | 任务 |
|---|---|
| 05:00–08:29 | `us_review` |
| 08:30–12:59 | `hk_plan` |
| 13:00–19:59 | `hk_review` |
| 20:00–04:59 | `us_plan` |

**管理定时任务：**

```bash
# 查看状态
skill/folio-scribe/scripts/install_schedule.sh status

# 卸载所有定时任务
skill/folio-scribe/scripts/install_schedule.sh uninstall
```

**查看日志：**

```bash
# 今天某个任务的运行日志
cat ~/Documents/Trading/.logs/folio-$(date +%Y%m%d)-hk_plan.log

# launchd 输出（排查启动问题）
cat ~/Documents/Trading/.logs/launchd-hk-plan.out
cat ~/Documents/Trading/.logs/launchd-hk-plan.err
```

**注意事项：**

- 电脑需处于开机且未休眠状态，否则会错过触发时间。
- 脚本按交易时段做跳过判断；美股周五复盘允许在本地周六早上运行。
- Futu OpenD 会在脚本运行时自动启动，但需要已登录（首次需手动登录一次）。
- 默认使用 Claude Code 全局配置的模型（`~/.claude/settings.json` 中的 `model`），Opus 过载时自动降级到 Sonnet。
- 默认使用限定工具 allowlist，不启用 `--dangerously-skip-permissions`。

### 生成效果示例

以下是一篇由 Folio Scribe 自动生成的每日交易日志（虚拟数据）。完整示例见 [`docs/example-daily-note.md`](docs/example-daily-note.md)。

<details>
<summary><b>港股交易计划（08:45 自动生成）</b></summary>

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
<summary><b>港股交易总结（16:15 自动生成）</b></summary>

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
<summary><b>Obsidian frontmatter（自动填充）</b></summary>

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

### 新机器部署

```bash
# 1. 安装 Futu SDK（读取 OpenD 所需）
python3 -m pip install futu-api

# 2. 安装 Claude Code skill（符号链接）
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe

# 3. 安装定时任务
skill/folio-scribe/scripts/install_schedule.sh install
```

开发本仓库或使用 `python3 -m folio_scribe...` 入口时，再安装本地 Python 包。

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

### 环境变量

定时任务脚本 `run_folio_task.sh` 通过环境变量配置，均有默认值：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FOLIO_SCRIBE_VAULT` | `~/Documents/Trading` | Obsidian vault 路径 |
| `FOLIO_SCRIBE_OPEND_APP` | `~/Applications/Futu_OpenD/FutuOpenD.app` | Futu OpenD 应用路径 |
| `FOLIO_SCRIBE_OPEND_PORT` | `11111` | Futu OpenD 端口 |
| `FOLIO_SCRIBE_CLAUDE` | 自动检测 `claude` 命令路径 | Claude Code CLI 路径 |
| `FOLIO_SCRIBE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Claude Code 权限模式 |
| `FOLIO_SCRIBE_ALLOWED_TOOLS` | 限定 `Read`、`Write` 和两个 helper 脚本 | Claude Code 工具 allowlist |

示例：如果 vault 在非默认位置，可以在 shell profile 中设置：

```bash
export FOLIO_SCRIBE_VAULT="$HOME/Documents/MyTradingVault"
```

或者通过 `install_schedule.sh` 的 `--vault` 参数在安装时指定。

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
  scripts/
    run_folio_task.sh      Scheduled / manual task runner
    install_schedule.sh    Install / uninstall / status for macOS launchd
    write_daily_note.py    Obsidian note section writer
    read_futu_snapshot.py  Futu OpenD snapshot reader
    launchd/               macOS launchd plist templates
  references/              Optional references loaded when needed

src/folio_scribe/          Reusable Python package
tests/                     Unit tests
docs/                      Project context and roadmap
```

### Quick Start With Claude Code

Install the skill (symlink to this repo):

```bash
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe
```

Then use `/folio-scribe` directly in a Claude Code session:

```text
/folio-scribe Create today's HK trading plan and write it to Obsidian
```

```text
/folio-scribe Review today's HK session against the plan
```

```text
/folio-scribe Read current positions and create a US trading plan
```

Non-interactive usage from scripts:

```bash
claude -p "/folio-scribe Create today's HK trading plan" \
  --permission-mode acceptEdits \
  --allowed-tools "Read,Write,Bash(python3 *read_futu_snapshot.py*),Bash(python3 *write_daily_note.py*)"
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

### Other AI Clients

If your client supports skill folders (Cursor, Cline/Roo, etc.), copy the
whole directory:

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

Current implementation status: the bundled Futu helper is a read-only beta. It
can read quote snapshots, account summaries, positions, current orders, and
recent fills through OpenD. Option-chain, order-book, tick, K-line, and richer
market-context reads are still roadmap work.

The helper scripts under `skill/folio-scribe/scripts/` can be copied with the
skill bundle and used without installing this repository's `folio_scribe`
Python package. Futu reads still require `futu-api` on the local machine.

Read-only connectivity check:

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL --counts-only
```

Read structured JSON:

```bash
python3 skill/folio-scribe/scripts/read_futu_snapshot.py US.AAPL HK.00700
```

If the repository package is installed, `python3 -m folio_scribe.futu_snapshot ...`
is also available.

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

### Scheduled Tasks

Folio Scribe supports automated journal generation via macOS launchd. The runner
script auto-launches Futu OpenD if needed, invokes the `/folio-scribe` skill
through Claude Code, and writes the output to the Obsidian vault.

**Install scheduled tasks:**

```bash
# Install with default vault (~/Documents/Trading)
skill/folio-scribe/scripts/install_schedule.sh install

# Custom vault path
skill/folio-scribe/scripts/install_schedule.sh install --vault ~/Documents/MyVault
```

Once installed, tasks trigger at the local times below; the runner decides
whether to skip based on the mapped market session:

| Time (HKT) | Task | Description |
|---|---|---|
| 06:45 | US Trading Review | Writes to the previous session's note |
| 08:45 | HK Trading Plan | Before HK market open |
| 16:15 | HK Trading Review | After HK market close |
| 20:45 | US Trading Plan | Before US market open |

**Manual run:**

```bash
# Auto-detect task type from current time
skill/folio-scribe/scripts/run_folio_task.sh

# Specify task type
skill/folio-scribe/scripts/run_folio_task.sh hk_plan
skill/folio-scribe/scripts/run_folio_task.sh hk_review
skill/folio-scribe/scripts/run_folio_task.sh us_plan
skill/folio-scribe/scripts/run_folio_task.sh us_review
```

**Manage scheduled tasks:**

```bash
skill/folio-scribe/scripts/install_schedule.sh status     # check status
skill/folio-scribe/scripts/install_schedule.sh uninstall   # remove all tasks
```

**View logs:**

```bash
cat ~/Documents/Trading/.logs/folio-$(date +%Y%m%d)-hk_plan.log
```

**Notes:**

- The Mac must be awake (not sleeping) at trigger time.
- The session guard skips non-trading local windows; US Friday review can run on
  local Saturday morning.
- Futu OpenD is auto-launched but must have been logged in at least once.
- Uses the model from Claude Code global settings (`~/.claude/settings.json`),
  with automatic Sonnet fallback when the primary model is overloaded.
- Uses a narrow tool allowlist by default and does not enable
  `--dangerously-skip-permissions`.

### Example Output

Below is an auto-generated daily trading journal (with dummy data). See the full example at [`docs/example-daily-note.md`](docs/example-daily-note.md).

<details>
<summary><b>HK Trading Plan (auto-generated at 08:45)</b></summary>

```markdown
## 08:45 HK Trading Plan

Data source: Futu OpenD live snapshot | Generated: 2026-01-15 08:45 HKT

### Account Snapshot

| Item | Value | Note |
|------|-------|------|
| Total Assets | USD 25,380.50 | +1.2% vs prev close |
| Cash Balance | USD 8,125.30 | Sufficient |
| HK Concentration | ~62% | Well diversified |

### Current Positions

| Ticker | Name | Qty | Cost | Price | Unrealized P&L |
|--------|------|-----|------|-------|-----------------|
| HK.00700 | Tencent | 200 | HK$368.50 | HK$392.40 | +HK$4,780 (+6.5%) |
| HK.09888 | Baidu | 500 | HK$102.30 | HK$108.60 | +HK$3,150 (+6.2%) |
| US.NVDA | NVIDIA | 15 | USD 142.80 | USD 148.50 | +USD 85.50 (+4.0%) |

### Scenario Plan — Tencent (HK.00700)

| Scenario | Trigger | Action | Note |
|----------|---------|--------|------|
| Bullish confirmed | Holds above $395 for ≥15 min | Hold, target $400 | No chasing |
| Range-bound | Oscillates $388–$395 | No action | |
| Support break | Breaks below $385 | Trim 100 shares | Protect profits |

### Risk Boundaries

1. **No adding to Tencent** — concentration already at 62%
2. **No new HK positions**
3. **No trading in the first 15 minutes**
4. **No market orders**
5. **Max new exposure: 0; Max trim: Tencent 100 + Baidu 200**
```

</details>

<details>
<summary><b>HK Trading Review (auto-generated at 16:15)</b></summary>

```markdown
## 16:15 HK Trading Review

Close time: 2026-01-15 16:00 HKT

### Account Changes

| Item | Open | Close | Change |
|------|------|-------|--------|
| Total Assets | USD 25,380.50 | USD 25,612.80 | +USD 232.30 (+0.92%) |

### Plan Execution

| Plan Item | Execution | Score |
|-----------|-----------|-------|
| No adding to Tencent | ✅ Strictly followed | 10/10 |
| No trading in first 15 min | ✅ Followed | 10/10 |
| Trim below $385 | Not triggered | — |

**Discipline score: 9/10** — Followed the plan throughout. No impulsive trades.

### Improvements

- Did not set trailing stop after Tencent broke $395; plan ahead next time
- Baidu lacked momentum; consider whether to keep holding
```

</details>

<details>
<summary><b>Obsidian frontmatter (auto-populated)</b></summary>

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

### Setup on a New Machine

```bash
# 1. Install the Futu SDK required for OpenD reads
python3 -m pip install futu-api

# 2. Install Claude Code skill (symlink)
ln -s "$(pwd)/skill/folio-scribe" ~/.claude/skills/folio-scribe

# 3. Install scheduled tasks
skill/folio-scribe/scripts/install_schedule.sh install
```

Install the local Python package only when developing this repository or using
the `python3 -m folio_scribe...` entry points.

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

### Environment Variables

The runner script `run_folio_task.sh` is configured via environment variables,
all with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `FOLIO_SCRIBE_VAULT` | `~/Documents/Trading` | Obsidian vault path |
| `FOLIO_SCRIBE_OPEND_APP` | `~/Applications/Futu_OpenD/FutuOpenD.app` | Futu OpenD app path |
| `FOLIO_SCRIBE_OPEND_PORT` | `11111` | Futu OpenD port |
| `FOLIO_SCRIBE_CLAUDE` | auto-detected `claude` path | Claude Code CLI path |
| `FOLIO_SCRIBE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Claude Code permission mode |
| `FOLIO_SCRIBE_ALLOWED_TOOLS` | limited to `Read`, `Write`, and the two helper scripts | Claude Code tool allowlist |

Example: if your vault is in a non-default location:

```bash
export FOLIO_SCRIBE_VAULT="$HOME/Documents/MyTradingVault"
```

Or use the `--vault` flag when installing scheduled tasks.

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
