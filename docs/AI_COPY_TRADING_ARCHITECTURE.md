# AI Copy Trading System --- 项目架构基线

> 状态：Architecture Baseline v0.1\
> 用途：作为后续 Multica / Codex / Cursor
> 开发时的长期上下文与架构约束。\
> 当前阶段：**M1 --- Discord Message Ingestion（只做信息采集）**

## 1. 项目目标

从 Discord 中采集指定博主/交易员的消息，后续通过规则解析 + LLM
理解自然语言及结构化信号，将其转换为标准化
`TradingIntent`，经过交易状态管理、风险控制和交易执行后，下单到加密交易所，并持续跟踪订单、成交和仓位状态。

核心原则：

> **LLM
> 负责理解"人说了什么"；确定性的程序负责决定"系统应该做什么、能不能做、实际发生了什么"。**

系统必须保留完整事实链，支持人工确认、模拟交易、自动交易、异常恢复和审计。

------------------------------------------------------------------------

## 2. 六大功能域

### 2.1 Ingestion --- 信息采集

职责： - 监听 Discord 指定频道/用户消息。 -
原样保存文本、回复关系、附件、Embed、作者、频道和时间等信息。 - 标准化为
`RawMessage` / `NormalizedMessage`。 - 消息去重、断线重连、heartbeat。 -
**不负责判断消息是不是交易信号。**

数据流：

`Discord → Collector → NormalizedMessage → RawMessage → PostgreSQL`

说明： - 当前 Discord 场景无法邀请官方 Bot，因此数据入口需要做成可替换的
`Collector Adapter`，不能让后续系统绑定某一种采集实现。 -
普通用户账号自动化/self-bot 存在 Discord ToS
与账号风控风险，因此架构必须允许未来替换采集方式。

建议字段：

``` text
RawMessage
- id
- platform
- guild_id
- channel_id
- message_id          # 唯一约束
- author_id
- author_name
- content
- reply_to_message_id
- attachments
- embeds
- created_at
- edited_at
- raw_payload
- ingested_at
```

------------------------------------------------------------------------

### 2.2 Intelligence --- 智能理解

职责： - 判断消息是否与交易相关。 - 结构化消息优先走 Rule Parser。 -
非结构化自然语言走 LLM Parser。 - 使用历史消息、回复关系、当前交易等
Context。 - 使用每个博主自己的 `TraderProfile` 理解其表达习惯。 -
最终只输出标准 `TradingIntent`，**不直接调用交易所。**

核心动作建议：

``` text
OPEN
ADD
REDUCE
CLOSE
MOVE_STOP
SET_STOP
SET_TP
CANCEL_ORDER
COMMENT
IGNORE
NEED_CONFIRMATION
```

示例：

Discord： \> BTC这里可以接一点，跌破88000我走。

输出：

``` json
{
  "action": "OPEN",
  "symbol": "BTC",
  "side": "LONG",
  "entry_type": "MARKET",
  "stop_loss": 88000,
  "confidence": 0.94
}
```

后续消息： \> 再加一点。

系统不能孤立理解，必须结合该博主当前 Active Trade，转换为对应 BTC Trade
的 `ADD`。

------------------------------------------------------------------------

### 2.3 Trade Domain --- 交易领域

系统的核心领域对象不是 Order，而是 **Trade**。

一笔 Trade 可以包含多个 Order：

``` text
Trade: BTC LONG
├── Entry Order
├── Add Order
├── Reduce Order
├── Stop Order
└── Close Order
```

Trade State 建议：

``` text
PENDING
OPENING
OPEN
ADDING
REDUCING
CLOSING
CLOSED
CANCELLED
ERROR
```

Order State 必须与 Trade State 分开：

``` text
CREATED
SUBMITTING
SUBMITTED
OPEN
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
REJECTED
FAILED
UNKNOWN
```

`UNKNOWN`
很重要：例如下单请求超时，不能直接认为失败，因为交易所可能已经收到订单；此时必须通过
Reconciliation 查询真实状态。

核心对象：

``` text
TradingIntent
Trade
Order
Fill
Position
TradeEvent
```

------------------------------------------------------------------------

### 2.4 Risk --- 风险控制

任何 AI 产生的 TradingIntent 都不能直接进入交易所：

`TradingIntent → Risk Engine → Approved/Rejected → Execution`

第一版风险项建议：

``` text
max_position_size
max_account_risk
max_leverage
max_open_positions
max_daily_loss
symbol_blacklist
confidence_threshold
```

AI Confidence 可以配合运行模式：

``` text
高置信度 → 根据 Trader Mode 决定自动执行
中等置信度 → 人工确认
低置信度 → 拒绝/NEED_CONFIRMATION
```

系统级 Circuit Breaker 可在达到每日亏损阈值、行情异常、交易所异常、Risk
Engine 异常时暂停交易。

------------------------------------------------------------------------

### 2.5 Execution --- 执行交易

参考 QuantDinger 的成熟交易执行思想：

-   FastAPI Route 不直接承担长期交易生命周期。
-   独立 `Trading Worker` 负责 Intent、订单、Pending Order、仓位同步和
    Reconciliation。
-   使用 Exchange Adapter 隔离 Binance / Bitget / Bybit / OKX 等差异。
-   可用 CCXT 作为统一 API 基础，特殊能力使用交易所原生 API。
-   所有状态修改操作必须考虑幂等性。

建议接口：

``` text
ExecutionService
├── place_market_order()
├── place_limit_order()
├── cancel_order()
├── fetch_order()
├── fetch_positions()
└── reconcile()
```

### client_order_id

第一版实盘执行时就应该支持 `client_order_id`。

例如：

``` text
TradingIntent: intent_123
Order: order_789
client_order_id: acopy-intent123-01
```

用途： - 网络超时后确认订单是否已经创建。 - 防止 Retry 导致重复下单。 -
建立内部 Intent/Order 与交易所订单之间的追踪关系。

------------------------------------------------------------------------

### 2.6 Operations --- 系统运营

参考量化课程《实盘作战与 CEO 控制台》的思想：

-   7×24 heartbeat。
-   分级告警。
-   Event Log。
-   Circuit Breaker。
-   自动恢复。
-   Next.js Control Center。
-   一键暂停 / 恢复；高风险操作需要二次确认。

建议健康监控：

``` text
Discord Collector
LLM Parser
Trading Worker
Market Data
PostgreSQL
Redis
Binance
Bitget
...
```

告警等级可采用：

``` text
INFO
WARN
CRITICAL
FATAL
```

关键原则：

> **交易主循环写"事实"，Web/API 写"意图"。**

例如前端点击"平掉 BTC"：

`Next.js → CLOSE Command → Trading Worker → Exchange → Fill → Reconciliation → Trade=CLOSED`

前端不能直接把数据库里的 Position/Trade 改成 CLOSED。

------------------------------------------------------------------------

## 3. 整体数据流

``` text
Discord
   ↓
Collector
   ↓
RawMessage
   ↓
PostgreSQL
   ↓
Rule Parser / LLM Parser
   ↓
Context Engine + Trader Profile
   ↓
TradingIntent
   ↓
Trade State Machine
   ↓
Risk Engine
   ↓
Trading Worker
   ↓
Execution Service
   ↓
Exchange Adapter
   ↓
Binance / Bitget / Bybit / OKX
   ↓
Order / Fill / Position
   ↓
Reconciliation
   ↓
TradeEvent + PostgreSQL
   ↓
Next.js Control Center
```

------------------------------------------------------------------------

## 4. QuantDinger 借鉴点

QuantDinger 作为交易执行架构参考项目，主要借鉴：

1.  **HTTP API 与 Trading Worker 分离**\
    HTTP 层负责请求/响应，长期交易循环由独立 Worker 负责。

2.  **模块边界**\
    Route → Service → Domain/Execution，不把交易所逻辑散落在 API Route
    中。

3.  **Exchange Adapter**\
    上层使用统一接口，下层适配不同交易所。

4.  **Order 生命周期**\
    下单不是 success/failed 二元状态，要跟踪 submitted/open/partial
    fill/fill/cancel/unknown 等状态。

5.  **client_order_id + 幂等性**\
    防止网络异常导致重复下单。

6.  **Pending Order Manager**\
    处理尚未成交的限价单、撤单、后续博主指令。

7.  **Reconciliation**\
    交易所是实际订单/仓位状态的重要事实来源，系统需要定期对账。

8.  **Paper / Live 隔离**\
    模拟盘与实盘必须清晰区分。

不直接照搬： - 当前阶段不引入 QuantDinger 的完整 Celery / Redis Jobs /
Prometheus / Grafana 等复杂基础设施。 - 按实际需求逐阶段增加。

------------------------------------------------------------------------

## 5. 技术栈基线

### Frontend

-   Next.js
-   TypeScript

### Backend

-   Python 3.11+
-   FastAPI
-   Pydantic v2
-   SQLAlchemy 2.x
-   Alembic

### Database

-   PostgreSQL

### Queue / Realtime State

-   Redis：**M3 左右按需求引入**

### Trading

-   CCXT
-   Exchange-specific Adapter / Native API

### Testing

-   pytest

### Infrastructure

-   Docker Compose（开发环境）
-   Linux server / process supervisor（生产阶段）

### Celery

**当前不使用。**

未来出现以下需求再考虑： - 大量历史消息重新解析。 - 大规模回测。 - AI
Parser Benchmark 批处理。 - 定时报表。 - 大量可排队、可重试的后台 Job。

实时交易生命周期仍优先由独立 Trading Worker
管理，而不是把核心交易状态机交给 Celery Task。

------------------------------------------------------------------------

## 6. 运行模式

每个 Trader 可以独立配置：

``` text
OBSERVE
AI 只识别，不交易

PAPER
AI 识别 + 模拟交易

CONFIRM
AI 识别 + 人工确认 + 实盘

AUTO
AI 识别 + 风控通过后自动实盘
```

这样可以先积累识别准确率，再逐渐开放自动化。

------------------------------------------------------------------------

## 7. Trader Profile

未来每个博主建立独立 Profile，例如：

``` text
Trader: Wilson

Platform identity:
Discord author_id → internal trader_id

Typical language:
“接一点” → 通常 OPEN LONG
“加点” → ADD
“走一半” → REDUCE 50%
“保护” → MOVE_STOP TO ENTRY
“撤” → CLOSE/CANCEL，需要结合上下文

Default mode:
CONFIRM
```

注意： - Profile 是辅助 Context，不允许在信息不足时强行猜测。 -
不确定时输出 `NEED_CONFIRMATION`。

------------------------------------------------------------------------

## 8. 数据库规划

### M1 实现

``` text
raw_messages
collectors
```

### M2

``` text
traders
trader_identities
trading_intents
```

### M3

``` text
trades
orders
fills
positions
trade_events
exchange_accounts
risk_profiles
```

订单建议字段：

``` text
id
trade_id
exchange
exchange_order_id
client_order_id
symbol
side
order_type
requested_qty
filled_qty
avg_fill_price
status
reduce_only
submitted_at
filled_at
cancelled_at
raw_exchange_payload
```

------------------------------------------------------------------------

## 9. Worker 规划

``` text
Ingestion Worker
├── Discord Collector
├── normalization
├── deduplication
└── heartbeat

Intelligence Worker          # M2
├── Rule Parser
├── LLM Parser
├── Context Engine
└── TradingIntent

Trading Worker               # M3
├── Intent Processor
├── Trade State Machine
├── Risk
├── Order Manager
├── Pending Order Manager
└── Reconciliation
```

Web/API 与这些长期 Worker 生命周期分离。

------------------------------------------------------------------------

## 10. 当前里程碑：M1 --- Discord Message Ingestion

**M1 只做采集，不做 AI、不做下单、不做 Risk。**

目标：

``` text
Discord 目标频道出现消息
        ↓
Collector 收到
        ↓
NormalizedMessage
        ↓
RawMessage
        ↓
PostgreSQL
```

Definition of Done：

-   Discord 目标消息可被采集。
-   原始信息完整保存。
-   `message_id` 唯一，重复消息不重复入库。
-   断线可恢复。
-   有 heartbeat / health。
-   后端 API 能查询采集状态和 RawMessage。
-   从消息出现到入库目标 \< 5 秒。

建议 API：

``` text
GET /health
GET /api/collectors
GET /api/messages
```

------------------------------------------------------------------------

## 11. Multica 开发管理原则

Multica 只负责：

``` text
Epic / Issue
↓
任务拆分
↓
分配 Codex / Cursor / Agent
↓
开发
↓
Review
↓
合并
```

Multica **不属于生产运行时架构**。

开发原则： - 一个 Issue 只解决一个明确问题。 - Agent
不允许"顺手"实现后续里程碑。 - 每个 Issue 必须有 Acceptance Criteria。 -
架构修改需要同步更新本文件。 - 优先测试领域逻辑与边界条件。 - 不允许 API
Route 直接拥有长期交易循环。 - 不允许 LLM 直接调用交易所。 - 不允许 Web
直接修改订单/仓位事实状态。

------------------------------------------------------------------------

## 12. M1 Issue 拆分

### INIT-001 --- Bootstrap Backend

-   FastAPI
-   PostgreSQL
-   SQLAlchemy async
-   Alembic
-   Docker Compose
-   `.env.example`
-   `/health`
-   pytest

### INGEST-001 --- RawMessage Domain

-   RawMessage schema/model
-   migration
-   repository
-   `message_id` unique constraint

### INGEST-002 --- Collector Abstraction

-   `BaseCollector`
-   `NormalizedMessage`
-   lifecycle
-   health

### INGEST-003 --- Discord Collector

-   监听目标频道
-   标准化消息
-   写入 RawMessage
-   第一版优先文本；附件能力按实际采集接口扩展

### INGEST-004 --- Reliability

-   reconnect
-   duplicate protection
-   heartbeat
-   logging
-   recovery

### INGEST-005 --- Monitoring API

-   `/api/collectors`
-   `/api/messages`
-   `/api/health`

------------------------------------------------------------------------

## 13. 后续里程碑

### M2 --- Signal Intelligence

`RawMessage → Rule/LLM → Context → TradingIntent`

重点： - Trader Profile - Context Association - Confidence -
NEED_CONFIRMATION - Signal Replay / Parser Benchmark

### M3 --- Trading & Execution

`TradingIntent → Trade → Risk → Order → Exchange`

重点： - Trading Worker - Trade/Order State Machine - Exchange Adapter -
client_order_id - Idempotency - Pending Orders - Reconciliation - Paper
/ Confirm / Auto

### M4 --- Production Operations

重点： - Redis（按需求） - Alerting - Circuit Breaker - Heartbeat -
Recovery - Next.js Control Center - Observability -
Celery（只有出现明确后台 Job 需求才引入）

------------------------------------------------------------------------

## 14. 一条完整示例

Discord 博主：

> BTC这里可以接一点，跌破88000我走。

### Step 1 --- Ingestion

保存 `RawMessage`，不做交易判断。

### Step 2 --- Intelligence

输出：

``` text
TradingIntent
symbol = BTC
side = LONG
action = OPEN
entry = MARKET
stop_loss = 88000
confidence = 0.94
```

### Step 3 --- Trade Domain

创建：

``` text
Trade BTC LONG
state = OPENING
```

### Step 4 --- Risk

例如系统规则： - 单笔最大风险 1% - 最大仓位 5% - 最大杠杆 3x

计算实际允许的下单数量。

### Step 5 --- Execution

创建内部 Order，并生成：

``` text
client_order_id = acopy-intent123-01
```

通过 Bitget Adapter / CCXT 提交。

### Step 6 --- Order Tracking

订单：

``` text
SUBMITTED
→ OPEN
→ FILLED
```

Trade：

``` text
OPENING
→ OPEN
```

### Step 7 --- 后续博主消息

> 再加一点。

Context Engine 找到 Wilson 当前 BTC LONG Trade：

``` text
TradingIntent = ADD
```

经过 Risk 后创建第二张 Order。

> 先走一半。

``` text
TradingIntent = REDUCE 50%
```

> 全走。

``` text
TradingIntent = CLOSE
Trade: CLOSING → CLOSED
```

整个过程中每个 Intent、Order、Fill、Position 变化和异常都写入
`TradeEvent`，并在 Next.js 控制台展示。

------------------------------------------------------------------------

## 15. 当前最重要的架构约束

1.  **RawMessage 永久保留原始事实。**
2.  **LLM 不直接下单。**
3.  **TradingIntent 是 AI 与交易系统之间的边界。**
4.  **Trade 与 Order 是两个不同状态机。**
5.  **FastAPI 不承担长期交易循环。**
6.  **Trading Worker 是实盘生命周期核心。**
7.  **Web 写意图，Worker 写事实。**
8.  **交易执行必须幂等。**
9.  **订单超时不等于失败；允许 UNKNOWN + Reconciliation。**
10. **交易所状态必须定期 Reconcile。**
11. **Collector / Exchange 都使用 Adapter，避免绑定供应商。**
12. **M1 不提前实现 M2/M3/M4。**
13. **Celery 目前不引入。**
14. **先 OBSERVE/PAPER/CONFIRM，再逐步 AUTO。**
15. **所有架构变更同步更新本文件。**
