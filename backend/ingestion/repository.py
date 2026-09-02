from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ingestion.models import RawMessage
from backend.ingestion.schemas import RawMessageCreate


class RawMessageRepository:
    """Persistence operations for raw ingestion facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: RawMessageCreate) -> RawMessage:
        raw_message = RawMessage(**data.model_dump())
        self._session.add(raw_message)
        await self._session.flush()
        await self._session.refresh(raw_message)
        return raw_message

    async def get_by_platform_message_id(
        self,
        platform: str,
        message_id: str,
    ) -> RawMessage | None:
        statement = select(RawMessage).where(
            RawMessage.platform == platform,
            RawMessage.message_id == message_id,
        )
        return await self._session.scalar(statement)
