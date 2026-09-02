from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.ingestion.repository import RawMessageRepository
from backend.ingestion.schemas import RawMessageCreate


@dataclass(frozen=True)
class IngestionResult:
    raw_message_id: str
    created: bool


class MessageIngestionService:
    """Transaction boundary from normalized collector output to RawMessage."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ingest(self, message: RawMessageCreate) -> IngestionResult:
        async with self._session_factory() as session:
            repository = RawMessageRepository(session)
            stored, created = await repository.create_if_absent(message)
            await session.commit()
            return IngestionResult(raw_message_id=str(stored.id), created=created)
