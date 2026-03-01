"""Хендлеры для доната."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

@router.message(Command("donate", "донат", "купить"))
async def cmd_donate(message: Message) -> None:
    
    text = (
        "💎 <b>Магазин G-коинов и VIP</b>\n\n"
        "G-коины используются для:\n"
        "• Покупки VIP-статуса (/vip)\n"
        "• Торговли на бирже (/биржа)\n"
        "• Уникальных функций в будущем!\n\n"
        "🛒 <b>Прайс-лист:</b>\n"
        "• 50 G-коинов — <i>уточнять в ЛС</i>\n"
        "• 275 G-коинов — <i>уточнять в ЛС</i>\n"
        "• 600 G-коинов — <i>уточнять в ЛС</i>\n"
        "• 1300 G-коинов — <i>уточнять в ЛС</i>\n\n"
        "💬 <b>Для покупки и по всем вопросам пишите напрямую создателю:</b>\n"
        "👉 @GTR56775"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать администратору", url="https://t.me/GTR56775")]
    ])
    
    await message.answer(text, reply_markup=kb)
