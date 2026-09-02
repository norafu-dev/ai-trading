from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database import Base


JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class RawMessage(Base):
    """An immutable source message captured by the ingestion domain."""

    __tablename__ = "raw_messages"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "message_id",
            name="uq_raw_messages_platform_message_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    guild_id: Mapped[str | None] = mapped_column(String(64))
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_message_id: Mapped[str | None] = mapped_column(String(64))
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT,
        nullable=False,
        default=list,
    )
    embeds: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT,
        nullable=False,
        default=dict,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
