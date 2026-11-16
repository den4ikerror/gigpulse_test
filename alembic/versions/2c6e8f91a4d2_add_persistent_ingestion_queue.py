"""Add persistent ingestion queue

Revision ID: 2c6e8f91a4d2
Revises: 987d0deb2fb4
Create Date: 2026-11-16 12:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2c6e8f91a4d2"
down_revision: Union[str, None] = "987d0deb2fb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingested_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hash_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("contact_url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("budget", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingested_posts_hash_id", "ingested_posts", ["hash_id"], unique=True)
    op.create_index("ix_ingested_posts_status", "ingested_posts", ["status"], unique=False)
    op.create_index(
        "ix_ingested_posts_status_next_attempt",
        "ingested_posts",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingested_posts_status_next_attempt", table_name="ingested_posts")
    op.drop_index("ix_ingested_posts_status", table_name="ingested_posts")
    op.drop_index("ix_ingested_posts_hash_id", table_name="ingested_posts")
    op.drop_table("ingested_posts")
