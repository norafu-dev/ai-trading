"""Add the raw_messages ingestion fact table.

Revision ID: 20260903_0002
Revises: 20260902_0001
"""

import sqlalchemy as sa
from alembic import op


revision: str = "20260903_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("guild_id", sa.String(length=64), nullable=True),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("author_id", sa.String(length=64), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reply_to_message_id", sa.String(length=64), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("embeds", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_raw_messages_message_id"),
    )


def downgrade() -> None:
    op.drop_table("raw_messages")
