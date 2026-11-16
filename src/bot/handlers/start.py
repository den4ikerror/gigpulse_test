import logging
from html import escape

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from src.database.session import async_session_maker
from src.database.models import ORDER_CATEGORIES, Order
from src.database.repository import Repository
from src.bot.keyboards.inline import get_categories_keyboard, get_order_action_keyboard

logger = logging.getLogger("gigpulse.bot.handlers.start")
router = Router()

def format_order(order: Order, favorite: bool = False) -> str:
    prefix = "⭐ <b>[Обране] " if favorite else "📌 <b>"
    return (
        f"{prefix}{escape(order.title)}</b>\n\n"
        f"📁 <code>{escape(order.category)}</code> | 💰 <code>{escape(order.budget or 'Не вказано')}</code>\n"
        f"🌐 Джерело: <code>{escape(order.source_name)}</code>\n\n"
        f"{escape(order.summary[:300])}..."
    )


async def send_orders(message: Message, orders: list[Order], empty_text: str, favorite: bool = False) -> None:
    if not orders:
        await message.answer(empty_text)
        return
    for order in orders:
        await message.answer(
            format_order(order, favorite),
            parse_mode="HTML",
            reply_markup=get_order_action_keyboard(order.id, order.contact_url)
        )


@router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        async with async_session_maker() as session:
            user = await Repository.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username
            )
            filters = await Repository.get_user_filters(session, user.id)

        welcome_text = (
            "👋 Вітаємо у <b>GigPulse</b> — вашому AI-агрегаторі фриланс-замовлень!\n\n"
            "🎁 Безкоштовний пробний період — 3 дні з першого запуску.\n"
            "Оберіть цікаві для вас категорії нижче, щоб отримувати сповіщення про нові замовлення:"
        )
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_categories_keyboard(filters))
    except Exception:
        logger.exception("Could not process /start for Telegram user %s", message.from_user.id)
        await message.answer("Не вдалося завантажити меню. Спробуйте ще раз за хвилину.")

@router.callback_query(F.data.startswith("toggle_cat:"))
async def callback_toggle_category(callback: CallbackQuery):
    cat = callback.data.split(":")[1]
    if cat not in ORDER_CATEGORIES:
        await callback.answer("Невідома категорія.", show_alert=True)
        return
    enabled = False
    async with async_session_maker() as session:
        user = await Repository.get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            enabled = await Repository.toggle_user_filter(session, user.id, cat)
            filters = await Repository.get_user_filters(session, user.id)
            await callback.message.edit_reply_markup(reply_markup=get_categories_keyboard(filters))
    await callback.answer("Категорію оновлено!")
    if enabled:
        async with async_session_maker() as session:
            orders = await Repository.get_recent_orders(session, categories=[cat], limit=5)
        await send_orders(
            callback.message,
            orders,
            "📭 У цій категорії за останню добу замовлень поки немає."
        )

@router.callback_query(F.data == "recent_orders")
async def callback_recent_orders(callback: CallbackQuery):
    async with async_session_maker() as session:
        user = await Repository.get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку натисніть /start", show_alert=True)
            return

        filters = await Repository.get_user_filters(session, user.id)
        enabled_cats = [f.category for f in filters if f.enabled]

        orders = await Repository.get_recent_orders(session, categories=enabled_cats, limit=5)

    await callback.answer()
    await send_orders(
        callback.message,
        orders,
        "📭 За останню добу замовлень у вибраних категоріях поки немає."
    )

@router.callback_query(F.data == "my_favorites")
async def callback_my_favorites(callback: CallbackQuery):
    async with async_session_maker() as session:
        user = await Repository.get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку натисніть /start", show_alert=True)
            return

        favorites = await Repository.get_user_favorites(session, user.id, limit=10)

    await callback.answer()
    await send_orders(callback.message, favorites, "⭐ У вас поки немає збереженого обраного.", favorite=True)

@router.callback_query(F.data.startswith("fav_add:"))
async def callback_add_favorite(callback: CallbackQuery):
    try:
        order_id = int(callback.data.split(":")[1])
        if order_id <= 0:
            raise ValueError
    except (ValueError, IndexError):
        await callback.answer("Некоректний номер замовлення.", show_alert=True)
        return
    async with async_session_maker() as session:
        user = await Repository.get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            added = await Repository.add_favorite(session, user.id, order_id)
            if added:
                await callback.answer("⭐ Додано в обране!")
            else:
                await callback.answer("Вже є в обраному.")
        else:
            await callback.answer("Користувача не знайдено.", show_alert=True)
