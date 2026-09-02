import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from apps.api.app.database import Base, build_engine
from backend.ingestion.repository import RawMessageRepository
from backend.ingestion.schemas import RawMessageCreate


pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="set RUN_DB_TESTS=1 to test the configured PostgreSQL instance",
    ),
]


def make_raw_message(*, platform: str) -> RawMessageCreate:
    return RawMessageCreate(
        platform=platform,
        guild_id="guild-1",
        channel_id="channel-1",
        message_id="123456789",
        author_id="author-1",
        author_name="Trader",
        content="BTC looks interesting here",
        attachments=[{"id": "attachment-1"}],
        embeds=[{"title": "Chart"}],
        created_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        raw_payload={"id": "123456789", "type": 0},
    )


async def test_raw_message_postgresql_schema_and_unique_constraint() -> None:
    engine = build_engine(os.environ["DATABASE_URL"])
    schema_name = f"test_raw_message_{uuid4().hex}"
    schema_created = False
    schema_engine = engine.execution_options(
        schema_translate_map={None: schema_name},
    )

    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema_name))
            schema_created = True

        async with schema_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_columns(
                    "raw_messages",
                    schema=schema_name,
                )
            )
            unique_constraints = await connection.run_sync(
                lambda sync_connection: inspect(
                    sync_connection
                ).get_unique_constraints(
                    "raw_messages",
                    schema=schema_name,
                )
            )

        assert {
            column["name"]
            for column in columns
            if isinstance(column["type"], JSONB)
        } == {"attachments", "embeds", "raw_payload"}
        assert {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in unique_constraints
        }["uq_raw_messages_platform_message_id"] == (
            "platform",
            "message_id",
        )

        session_factory = async_sessionmaker(
            schema_engine,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repository = RawMessageRepository(session)
            discord = await repository.create(make_raw_message(platform="discord"))
            await session.commit()
            discord_id = discord.id
            message_id = discord.message_id

            with pytest.raises(IntegrityError):
                await repository.create(make_raw_message(platform="discord"))
            await session.rollback()

            telegram = await repository.create(
                make_raw_message(platform="telegram"),
            )
            await session.commit()

            stored_discord = await repository.get_by_platform_message_id(
                "discord",
                message_id,
            )
            stored_telegram = await repository.get_by_platform_message_id(
                "telegram",
                telegram.message_id,
            )
            assert stored_discord is not None
            assert stored_discord.id == discord_id
            assert stored_telegram is not None
            assert stored_telegram.id == telegram.id
    finally:
        if schema_created:
            async with engine.begin() as connection:
                await connection.execute(DropSchema(schema_name, cascade=True))
        await engine.dispose()
