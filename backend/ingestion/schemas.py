from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RawMessageCreate(BaseModel):
    """Validated input for persisting an external source message."""

    platform: str = Field(min_length=1, max_length=32)
    guild_id: str | None = Field(default=None, max_length=64)
    channel_id: str = Field(min_length=1, max_length=64)
    message_id: str = Field(min_length=1, max_length=64)
    author_id: str = Field(min_length=1, max_length=64)
    author_name: str = Field(min_length=1, max_length=255)
    content: str
    reply_to_message_id: str | None = Field(default=None, max_length=64)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    embeds: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    edited_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class RawMessageRead(RawMessageCreate):
    """Raw message representation returned from the persistence boundary."""

    id: UUID
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)
