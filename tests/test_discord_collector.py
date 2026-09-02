import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.app.database import Base
from apps.collector.config import CollectorSettings
from backend.ingestion.discord import DiscordGatewayCollector, normalize_discord_message
from backend.ingestion.models import RawMessage
from backend.ingestion.repository import RawMessageRepository
from backend.ingestion.service import MessageIngestionService


class Serializable:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return self.payload


class Author:
    def __init__(self, author_id: int, name: str = "Trader") -> None:
        self.id = author_id
        self.name = name

    def __str__(self) -> str:
        return self.name


def make_message(*, channel_id=123, author_id=456, message_id=789):
    return SimpleNamespace(
        id=message_id,
        guild=SimpleNamespace(id=111),
        channel=SimpleNamespace(id=channel_id),
        author=Author(author_id),
        content="BTC here",
        reference=SimpleNamespace(message_id=788),
        attachments=[Serializable({"id": "attachment-1", "url": "https://example.test/a"})],
        embeds=[Serializable({"title": "Chart"})],
        created_at=datetime(2026, 9, 3, 1, 2, tzinfo=UTC),
        edited_at=None,
    )


def test_normalize_discord_message_preserves_source_facts() -> None:
    message = make_message()
    raw_payload = {"id": "789", "content": "BTC here", "extra": {"raw": True}}

    normalized = normalize_discord_message(message, raw_payload)

    assert normalized.platform == "discord"
    assert normalized.guild_id == "111"
    assert normalized.channel_id == "123"
    assert normalized.author_name == "Trader"
    assert normalized.reply_to_message_id == "788"
    assert normalized.attachments[0]["id"] == "attachment-1"
    assert normalized.embeds == [{"title": "Chart"}]
    assert normalized.raw_payload == raw_payload


@pytest.mark.asyncio
async def test_normalized_discord_message_reaches_database() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    service = MessageIngestionService(session_factory)
    normalized = normalize_discord_message(make_message(), {"id": "789"})

    first = await service.ingest(normalized)
    duplicate = await service.ingest(normalized)
    async with session_factory() as session:
        stored = await RawMessageRepository(session).get_by_platform_message_id(
            "discord",
            "789",
        )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.raw_message_id == first.raw_message_id
    assert isinstance(stored, RawMessage)
    assert stored.content == "BTC here"
    await engine.dispose()


@pytest.mark.asyncio
async def test_collector_filters_and_forwards_allowed_raw_gateway_message() -> None:
    collector = DiscordGatewayCollector(
        token="secret",
        channel_ids=frozenset({123}),
        author_ids=frozenset({456}),
    )
    handler = AsyncMock()
    collector._handler = handler
    message = make_message()
    gateway_payload = {
        "t": "MESSAGE_CREATE",
        "d": {"id": "789", "content": "BTC here", "nonce": "preserved"},
    }

    await collector.on_socket_raw_receive(json.dumps(gateway_payload))
    await collector.on_message(message)
    await collector.on_message(make_message(channel_id=999))

    handler.assert_awaited_once()
    assert handler.await_args.args[0].raw_payload["nonce"] == "preserved"


def test_collector_settings_parse_allowlists(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "secret")
    monkeypatch.setenv("DISCORD_CHANNEL_IDS", "123, 456")
    monkeypatch.setenv("DISCORD_AUTHOR_IDS", "789")

    settings = CollectorSettings()

    assert settings.channel_ids == frozenset({123, 456})
    assert settings.author_ids == frozenset({789})
