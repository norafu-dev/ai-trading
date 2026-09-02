import json
import logging
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

import discord

from backend.ingestion.collectors import BaseCollector, MessageHandler
from backend.ingestion.schemas import RawMessageCreate


logger = logging.getLogger(__name__)


def _snowflake(value: Any) -> str | None:
    return None if value is None else str(value)


def normalize_discord_message(
    message: discord.Message,
    raw_payload: dict[str, Any] | None = None,
) -> RawMessageCreate:
    """Convert a discord.py message into the ingestion boundary schema."""
    guild = getattr(message, "guild", None)
    reference = getattr(message, "reference", None)
    return RawMessageCreate(
        platform="discord",
        guild_id=_snowflake(getattr(guild, "id", None)),
        channel_id=str(message.channel.id),
        message_id=str(message.id),
        author_id=str(message.author.id),
        author_name=str(message.author),
        content=message.content,
        reply_to_message_id=_snowflake(
            getattr(reference, "message_id", None) if reference else None
        ),
        attachments=[attachment.to_dict() for attachment in message.attachments],
        embeds=[embed.to_dict() for embed in message.embeds],
        created_at=message.created_at,
        edited_at=message.edited_at,
        raw_payload=raw_payload or _fallback_raw_payload(message),
    )


def _fallback_raw_payload(message: discord.Message) -> dict[str, Any]:
    """Preserve the observable message when the raw gateway frame is unavailable."""
    return {
        "id": str(message.id),
        "guild_id": _snowflake(getattr(getattr(message, "guild", None), "id", None)),
        "channel_id": str(message.channel.id),
        "author": {"id": str(message.author.id), "name": str(message.author)},
        "content": message.content,
        "timestamp": message.created_at.astimezone(UTC).isoformat(),
        "edited_timestamp": (
            message.edited_at.astimezone(UTC).isoformat()
            if message.edited_at is not None
            else None
        ),
        "attachments": [attachment.to_dict() for attachment in message.attachments],
        "embeds": [embed.to_dict() for embed in message.embeds],
    }


class DiscordGatewayCollector(BaseCollector):
    """Official-bot Discord Gateway adapter with channel/author allowlists."""

    def __init__(
        self,
        token: str,
        channel_ids: frozenset[int],
        author_ids: frozenset[int] = frozenset(),
        *,
        raw_payload_cache_size: int = 1000,
    ) -> None:
        if not channel_ids:
            raise ValueError("at least one Discord channel ID is required")
        self._token = token
        self._channel_ids = channel_ids
        self._author_ids = author_ids
        self._raw_payload_cache_size = raw_payload_cache_size
        self._raw_payloads: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._handler: MessageHandler | None = None

        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        # discord.py only dispatches raw socket events when debug events are
        # enabled. MESSAGE_CREATE frames are cached so raw_payload remains an
        # actual source fact instead of a reconstruction whenever possible.
        self._client = discord.Client(intents=intents, enable_debug_events=True)
        self._client.event(self.on_ready)
        self._client.event(self.on_message)
        self._client.event(self.on_socket_raw_receive)

    async def run(self, handle_message: MessageHandler) -> None:
        self._handler = handle_message
        await self._client.start(self._token, reconnect=True)

    async def close(self) -> None:
        await self._client.close()

    async def on_ready(self) -> None:
        logger.info("Discord collector connected as %s", self._client.user)

    async def on_socket_raw_receive(self, payload: str | bytes) -> None:
        try:
            envelope = json.loads(payload)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if envelope.get("t") != "MESSAGE_CREATE" or not isinstance(envelope.get("d"), dict):
            return
        message_payload = envelope["d"]
        message_id = message_payload.get("id")
        if message_id is None:
            return
        self._raw_payloads[str(message_id)] = message_payload
        self._raw_payloads.move_to_end(str(message_id))
        while len(self._raw_payloads) > self._raw_payload_cache_size:
            self._raw_payloads.popitem(last=False)

    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id not in self._channel_ids:
            return
        if self._author_ids and message.author.id not in self._author_ids:
            return
        if self._handler is None:
            raise RuntimeError("collector received a message before run() initialized")

        raw_payload = self._raw_payloads.pop(str(message.id), None)
        normalized = normalize_discord_message(message, raw_payload)
        try:
            await self._handler(normalized)
        except Exception:
            logger.exception("Failed to persist Discord message %s", message.id)
