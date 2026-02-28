"""Inline-клавиатуры Wind Bot."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def confirm_keyboard(action_id: str) -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да", callback_data=f"confirm:{action_id}"
            ),
            InlineKeyboardButton(
                text="❌ Нет", callback_data=f"cancel:{action_id}"
            ),
        ]
    ])
