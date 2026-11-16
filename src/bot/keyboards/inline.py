from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from src.config import settings
from src.database.models import ORDER_CATEGORY_LABELS

def get_categories_keyboard(user_filters: list) -> InlineKeyboardMarkup:
    buttons = []
    for f in user_filters:
        status_icon = "✅" if f.enabled else "⬜"
        label = f"{status_icon} {ORDER_CATEGORY_LABELS.get(f.category, f.category)}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"toggle_cat:{f.category}")])

    buttons.append([InlineKeyboardButton(text="🚀 Свіжі замовлення", callback_data="recent_orders")])
    buttons.append([InlineKeyboardButton(text="⭐ Моє обране", callback_data="my_favorites")])
    if settings.WEBAPP_URL:
        buttons.append([
            InlineKeyboardButton(
                text="🌐 Відкрити GigPulse",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_order_action_keyboard(order_id: int, contact_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔗 Відгукнутися", url=contact_url),
            InlineKeyboardButton(text="⭐ В обране", callback_data=f"fav_add:{order_id}")
        ]
    ])
