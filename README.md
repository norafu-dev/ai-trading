# AI Copy Trading

AI 跟单交易系统的基础项目脚手架。本里程碑只包含可运行的 FastAPI、PostgreSQL、Alembic、pytest 与 Next.js 环境，不包含采集、AI 理解或交易业务逻辑。

## Architecture

项目的完整架构基线、领域边界、里程碑规划和开发约束见 [`docs/AI_COPY_TRADING_ARCHITECTURE.md`](docs/AI_COPY_TRADING_ARCHITECTURE.md)。该文档是当前项目的 Architecture Source of Truth；当前阶段为 `M1 — Discord Message Ingestion`。

## 环境要求

- Python 3.11+
- Node.js 20+
- pnpm 9+
- Docker 与 Docker Compose

## 首次配置

```bash
cp .env.example .env
```

`.env.example` 中只有本地占位值。使用前请在 `.env` 中设置自己的 PostgreSQL 密码；不要提交 `.env`。

## PostgreSQL

```bash
docker compose up -d
docker compose ps
```

停止数据库：

```bash
docker compose down
```

## 后端

创建虚拟环境并安装开发依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

启动 FastAPI：

```bash
uvicorn apps.api.app.main:app --reload
```

健康检查位于 `http://localhost:8000/health`。

## Alembic

执行已有迁移：

```bash
alembic upgrade head
```

创建后续迁移：

```bash
alembic revision --autogenerate -m "describe change"
```

查看当前版本：

```bash
alembic current
```

## 测试

单元测试不依赖正在运行的 PostgreSQL：

```bash
pytest
```

验证真实 PostgreSQL 连接（先启动数据库并执行迁移）：

```bash
RUN_DB_TESTS=1 pytest -m integration
```

## 前端

```bash
cd apps/web
pnpm install
pnpm dev
```

最小页面位于 `http://localhost:3000`。生产构建可使用 `pnpm build`。

## 当前边界

`backend/` 下的六个领域目前只有占位包。本里程碑有意不实现 Discord Collector、selfbot、RawMessage、Redis、Celery、LLM、TradingIntent、交易/订单状态机、风控、Trading Worker、CCXT、交易所适配器和业务 Dashboard。
