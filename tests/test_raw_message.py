from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.app.database import Base
from backend.ingestion.models import RawMessage
from backend.ingestion.repository import RawMessageRepository
from backend.ingestion.schemas import RawMessageCreate, RawMessageRead


def make_raw_message(
    *,
    platform: str = "discord",
    message_id: str = "123456789",
) -> RawMessageCreate:
    return RawMessageCreate(
        platform=platform,
        guild_id="guild-1",
        channel_id="channel-1",
        message_id=message_id,
        author_id="author-1",
        author_name="Trader",
        content="BTC looks interesting here",
        reply_to_message_id="123456788",
        attachments=[{"id": "attachment-1", "url": "https://example.test/chart.png"}],
        embeds=[{"title": "Chart"}],
        created_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        raw_payload={"id": message_id, "type": 0, "extra": {"preserved": True}},
    )


@pytest.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as database_session:
        yield database_session

    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_persists_and_reads_complete_raw_message(session) -> None:
    repository = RawMessageRepository(session)
    data = make_raw_message()

    created = await repository.create(data)
    await session.commit()
    stored = await repository.get_by_platform_message_id(
        data.platform,
        data.message_id,
    )

    assert stored is not None
    assert stored.id == created.id
    assert stored.attachments == data.attachments
    assert stored.embeds == data.embeds
    assert stored.raw_payload == data.raw_payload
    assert stored.ingested_at is not None
    assert RawMessageRead.model_validate(stored).message_id == data.message_id


@pytest.mark.asyncio
async def test_create_if_absent_is_idempotent(session) -> None:
    repository = RawMessageRepository(session)
    first, first_created = await repository.create_if_absent(make_raw_message())
    duplicate, duplicate_created = await repository.create_if_absent(make_raw_message())

    assert first_created is True
    assert duplicate_created is False
    assert duplicate.id == first.id


@pytest.mark.asyncio
async def test_platform_message_id_unique_constraint_rejects_duplicates(session) -> None:
    repository = RawMessageRepository(session)
    await repository.create(make_raw_message())

    with pytest.raises(IntegrityError):
        await repository.create(make_raw_message())


@pytest.mark.asyncio
async def test_same_message_id_from_different_platforms_can_be_saved_and_queried(
    session,
) -> None:
    repository = RawMessageRepository(session)
    discord = await repository.create(make_raw_message(platform="discord"))
    telegram = await repository.create(make_raw_message(platform="telegram"))
    await session.commit()

    stored_discord = await repository.get_by_platform_message_id(
        "discord",
        discord.message_id,
    )
    stored_telegram = await repository.get_by_platform_message_id(
        "telegram",
        telegram.message_id,
    )

    assert stored_discord is not None
    assert stored_discord.id == discord.id
    assert stored_telegram is not None
    assert stored_telegram.id == telegram.id


def test_schema_rejects_blank_source_identifiers() -> None:
    with pytest.raises(ValidationError):
        make_raw_message(message_id="")


def test_unique_constraint_has_stable_name() -> None:
    assert any(
        constraint.name == "uq_raw_messages_platform_message_id"
        and tuple(column.name for column in constraint.columns)
        == ("platform", "message_id")
        for constraint in RawMessage.__table__.constraints
    )


def test_postgresql_uses_jsonb_for_raw_json_documents() -> None:
    for column_name in ("attachments", "embeds", "raw_payload"):
        column_type = RawMessage.__table__.c[column_name].type
        assert isinstance(column_type.dialect_impl(postgresql.dialect()), JSONB)
