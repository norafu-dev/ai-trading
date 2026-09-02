from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from apps.api.app.config import get_settings


class Base(DeclarativeBase):
    """Shared metadata registry for future domain models."""


def build_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or str(get_settings().database_url)
    return create_async_engine(url, pool_pre_ping=True)


engine = build_engine()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
