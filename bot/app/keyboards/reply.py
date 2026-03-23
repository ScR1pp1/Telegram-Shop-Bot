from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def request_contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться контактом / Share contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку, чтобы поделиться телефоном",
    )

