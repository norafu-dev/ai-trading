from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

    async def create_if_absent(
        self,
        data: RawMessageCreate,
    ) -> tuple[RawMessage, bool]:
        """Persist one external fact and return the existing row on duplicates."""
        existing = await self.get_by_platform_message_id(data.platform, data.message_id)
        if existing is not None:
            return existing, False

        try:
            async with self._session.begin_nested():
                created = await self.create(data)
        except IntegrityError:
            # A concurrent worker may win after the initial read. The savepoint
            # keeps the outer transaction usable so the winning row can be read.
            existing = await self.get_by_platform_message_id(
                data.platform,
                data.message_id,
            )
            if existing is None:
                raise
            return existing, False

        return created, True
