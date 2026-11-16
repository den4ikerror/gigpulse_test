import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from src.database.session import async_session_maker
from src.database.repository import Repository
from src.bot.keyboards.inline import get_main_menu_keyboard

logger = logging.getLogger("gigpulse.bot.handlers.start")
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        async with async_session_maker() as session:
            user = await Repository.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username
            )

        welcome_text = (
            "👋 Вітаємо у <b>GigPulse</b> — вашому AI-агрегаторі фриланс-замовлень!\n\n"
            "Усі фільтри та замовлення доступні в Mini App. "
            "У цьому чаті надходитимуть лише повідомлення про нові замовлення."
        )
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception:
        logger.exception("Could not process /start for Telegram user %s", message.from_user.id)
        await message.answer("Не вдалося завантажити меню. Спробуйте ще раз за хвилину.")
