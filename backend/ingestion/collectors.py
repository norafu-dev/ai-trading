from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from backend.ingestion.schemas import RawMessageCreate


MessageHandler = Callable[[RawMessageCreate], Awaitable[None]]


class BaseCollector(ABC):
    """Replaceable boundary for long-running external message collectors."""

    @abstractmethod
    async def run(self, handle_message: MessageHandler) -> None:
        """Run until stopped and send normalized messages to the handler."""

    @abstractmethod
    async def close(self) -> None:
        """Stop the collector and release its external connection."""
