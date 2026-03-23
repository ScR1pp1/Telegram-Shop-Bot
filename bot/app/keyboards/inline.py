from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def check_subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Проверить подписку / Check", callback_data="check_subscription")]]
    )

