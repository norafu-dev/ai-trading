# AI Copy Trading

当前仓库处于 M1 Discord 消息采集阶段。Collector 只保存原始消息事实，不解析交易信号，也不执行交易。

## 启动 Discord → PostgreSQL 最小闭环

该实现使用 Discord 官方 Bot Gateway，不使用用户 token 或 self-bot。Bot 必须已加入目标服务器，并拥有目标频道的 `View Channel`、`Read Message History` 权限；Developer Portal 中还需启用 `Message Content Intent`。

```bash
cp .env.example .env
# 编辑 .env，填写 PostgreSQL 密码、DISCORD_BOT_TOKEN 和 DISCORD_CHANNEL_IDS
docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/python -m apps.collector.main
```

在配置的频道发送一条消息后，日志会显示 `inserted`；重复 Gateway 事件会显示 `duplicate ignored`，数据库中的 `(platform, message_id)` 仍只有一行：

```sql
SELECT platform, channel_id, message_id, author_name, content, ingested_at
FROM raw_messages
ORDER BY ingested_at DESC
LIMIT 1;
```

如果当前目标服务器无法邀请官方 Bot，则此适配器不能绕过该权限限制。Collector 边界保持可替换，后续可在获得合规采集入口后替换适配器；本实现不会使用违反 Discord 条款的 self-bot 方案。
