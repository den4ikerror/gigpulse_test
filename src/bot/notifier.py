import asyncio
from html import escape
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import (
    User,
    UserFilter,
    Order,
    EXCLUDED_ORDER_SOURCES,
    ORDER_CATEGORY_LABELS,
)
from src.services.order_filters import matches_order_filter

logger = logging.getLogger("gigpulse.notifier")

class Notifier:
    def __init__(self, bot):
        self.bot = bot

    async def notify_new_order(self, session: AsyncSession, order: Order) -> bool:
        """Push notification to all users who enabled this order's category."""
        if order.source_name.casefold() in EXCLUDED_ORDER_SOURCES:
            logger.info("Skipping notification from excluded source %s", order.source_name)
            return True
        try:
            stmt = (
                select(User.telegram_id, UserFilter.min_budget, UserFilter.keywords)
                .join(UserFilter, UserFilter.user_id == User.id)
                .where(UserFilter.category == order.category, UserFilter.enabled.is_(True))
                .distinct()
            )
            result = await session.execute(stmt)
            telegram_ids = [
                telegram_id
                for telegram_id, min_budget, keywords in result.all()
                if matches_order_filter(
                    order.title,
                    order.summary,
                    order.budget,
                    min_budget,
                    keywords,
                )
            ]
            await session.commit()

            text = (
                f"🔥 <b>Нове замовлення!</b>\n\n"
                f"📌 <b>{escape(order.title)}</b>\n\n"
                f"📁 Категорія: <code>{escape(ORDER_CATEGORY_LABELS.get(order.category, order.category))}</code>\n"
                f"🌐 Джерело: <code>{escape(order.source_name)}</code>\n\n"
                f"{escape(order.summary[:300])}...\n\n"
                "Відкрийте GigPulse Mini App, щоб переглянути замовлення."
            )

            semaphore = asyncio.Semaphore(10)

            async def send(telegram_id: int) -> bool:
                try:
                    async with semaphore:
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=text,
                            parse_mode="HTML",
                        )
                    return True
                except Exception:
                    logger.exception("Failed to send notification to user %s", telegram_id)
                    return False

            results = await asyncio.gather(*(send(telegram_id) for telegram_id in telegram_ids))
            return all(results)
        except Exception:
            logger.exception("Error in notify_new_order")
            return False
