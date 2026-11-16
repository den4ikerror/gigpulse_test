"""Expand the order category taxonomy

Revision ID: a4f29c8d6e71
Revises: 2c6e8f91a4d2
Create Date: 2026-11-16 17:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f29c8d6e71"
down_revision: Union[str, None] = "2c6e8f91a4d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORY_PARENT = {
    "graphic_design": "design",
    "web_uiux_design": "design",
    "other_design": "design",
    "copywriting": "video_text",
    "smm_social": "marketing",
    "video_editing": "video_text",
    "frontend_backend": "web_dev",
    "chatbots": "dev_bots",
    "3d_visualization": "design",
    "logo_branding": "design",
    "pr_influencers": "marketing",
    "mobile_apps": "web_dev",
    "wordpress_cms": "web_dev",
    "qa_testing": "web_dev",
    "ai_data_automation": "web_dev",
    "seo": "marketing",
    "targeted_ads": "marketing",
    "translation": "video_text",
    "photo_editing": "video_text",
    "audio_voiceover": "video_text",
    "virtual_assistance": None,
}
ORDER_CATEGORY_MIGRATION = {
    "dev_bots": "chatbots",
    "web_dev": "frontend_backend",
    "design": "other_design",
    "marketing": "smm_social",
    "video_text": "copywriting",
}


def upgrade() -> None:
    connection = op.get_bind()
    user_filters = sa.table(
        "user_filters",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("category", sa.String(50)),
        sa.column("min_budget", sa.Float),
        sa.column("enabled", sa.Boolean),
        sa.column("keywords", sa.Text),
    )
    existing_filters = connection.execute(
        sa.select(
            user_filters.c.user_id,
            user_filters.c.category,
            user_filters.c.min_budget,
            user_filters.c.enabled,
            user_filters.c.keywords,
        )
    ).mappings().all()
    by_user: dict[int, dict[str, dict]] = {}
    for row in existing_filters:
        by_user.setdefault(row["user_id"], {})[row["category"]] = dict(row)

    users = sa.table("users", sa.column("id", sa.Integer))
    user_ids = connection.execute(sa.select(users.c.id)).scalars().all()
    connection.execute(sa.delete(user_filters))
    new_filters = []
    for user_id in user_ids:
        old_filters = by_user.get(user_id, {})
        for category, parent in CATEGORY_PARENT.items():
            old_filter = old_filters.get(parent) if parent else None
            new_filters.append({
                "user_id": user_id,
                "category": category,
                "min_budget": old_filter["min_budget"] if old_filter else 0,
                "enabled": old_filter["enabled"] if old_filter else True,
                "keywords": old_filter["keywords"] if old_filter else None,
            })
    if new_filters:
        op.bulk_insert(user_filters, new_filters)

    orders = sa.table("orders", sa.column("category", sa.String(50)))
    for old_category, new_category in ORDER_CATEGORY_MIGRATION.items():
        connection.execute(
            sa.update(orders)
            .where(orders.c.category == old_category)
            .values(category=new_category)
        )


def downgrade() -> None:
    connection = op.get_bind()
    user_filters = sa.table(
        "user_filters",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("category", sa.String(50)),
        sa.column("min_budget", sa.Float),
        sa.column("enabled", sa.Boolean),
        sa.column("keywords", sa.Text),
    )
    rows = connection.execute(
        sa.select(
            user_filters.c.user_id,
            user_filters.c.category,
            user_filters.c.min_budget,
            user_filters.c.enabled,
            user_filters.c.keywords,
        )
    ).mappings().all()
    legacy_filters: dict[int, dict[str, list[dict]]] = {}
    for row in rows:
        parent = CATEGORY_PARENT.get(row["category"])
        if parent:
            legacy_filters.setdefault(row["user_id"], {}).setdefault(parent, []).append(dict(row))

    users = sa.table("users", sa.column("id", sa.Integer))
    user_ids = connection.execute(sa.select(users.c.id)).scalars().all()
    connection.execute(sa.delete(user_filters))
    old_filters = []
    for user_id in user_ids:
        for category in ("dev_bots", "web_dev", "design", "marketing", "video_text"):
            children = legacy_filters.get(user_id, {}).get(category, [])
            if not children:
                continue
            old_filters.append({
                "user_id": user_id,
                "category": category,
                "min_budget": max(item["min_budget"] for item in children),
                "enabled": any(item["enabled"] for item in children),
                "keywords": next((item["keywords"] for item in children if item["keywords"]), None),
            })
    if old_filters:
        op.bulk_insert(user_filters, old_filters)

    orders = sa.table("orders", sa.column("category", sa.String(50)))
    for old_category, new_category in ORDER_CATEGORY_MIGRATION.items():
        connection.execute(
            sa.update(orders)
            .where(orders.c.category == new_category)
            .values(category=old_category)
        )
