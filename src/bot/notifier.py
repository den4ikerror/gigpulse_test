import asyncio
from html import escape
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, UserFilter, Order
from src.bot.keyboards.inline import get_order_action_keyboard
from src.services.order_filters import matches_order_filter

logger = logging.getLogger("gigpulse.notifier")

class Notifier:
    def __init__(self, bot):
        self.bot = bot

    async def notify_new_order(self, session: AsyncSession, order: Order) -> bool:
        """Push notification to all users who enabled this order's category."""
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
                f"📁 Категорія: <code>{escape(order.category)}</code>\n"
                f"💰 Бюджет: <code>{escape(order.budget or 'Не вказано')}</code>\n"
                f"🌐 Джерело: <code>{escape(order.source_name)}</code>\n\n"
                f"{escape(order.summary[:300])}..."
            )

            keyboard = get_order_action_keyboard(order.id, order.contact_url)

            semaphore = asyncio.Semaphore(10)

            async def send(telegram_id: int) -> bool:
                try:
                    async with semaphore:
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=text,
                            parse_mode="HTML",
                            reply_markup=keyboard
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
