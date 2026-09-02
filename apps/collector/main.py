import asyncio
import logging

from apps.api.app.database import async_session_factory
from apps.collector.config import get_collector_settings
from backend.ingestion.discord import DiscordGatewayCollector
from backend.ingestion.schemas import RawMessageCreate
from backend.ingestion.service import MessageIngestionService


logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_collector_settings()
    service = MessageIngestionService(async_session_factory)
    collector = DiscordGatewayCollector(
        token=settings.discord_bot_token,
        channel_ids=settings.channel_ids,
        author_ids=settings.author_ids,
    )

    async def persist(message: RawMessageCreate) -> None:
        result = await service.ingest(message)
        logger.info(
            "Discord message %s (%s)",
            message.message_id,
            "inserted" if result.created else "duplicate ignored",
        )

    try:
        await collector.run(persist)
    finally:
        await collector.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
