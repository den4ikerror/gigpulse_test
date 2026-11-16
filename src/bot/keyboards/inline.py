from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from src.config import settings

def get_main_menu_keyboard() -> InlineKeyboardMarkup | None:
    if settings.WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🌐 Відкрити GigPulse",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        ]])
    return None
