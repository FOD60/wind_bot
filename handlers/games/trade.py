"""
📉📈 Трейд — угадай направление рынка.

Механика:
  Виртуальный актив. Цена меняется случайно.
  Игрок выбирает ЛОНГ (рост) или ШОРТ (падение).
  Изменение от -30% до +30%.
  
  • Угадал направление: выигрыш = ставка * |изменение%| / 100 * 5
  • Не угадал: проигрыш

Команда: /трейд <ставка> <лонг|шорт>
"""
from __future__ import annotations

import random

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.game_service import play_game
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount

router = Router()

LONG_ALIASES = {"лонг", "long", "л", "l", "вверх", "рост"}
SHORT_ALIASES = {"шорт", "short", "ш", "s", "вниз", "падение"}


@router.message(Command("трейд", "trade"))
async def cmd_trade(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "📈 <b>Трейд</b>\n\n"
            "Угадай направление рынка!\n"
            "• ЛОНГ — ставка на рост\n"
            "• ШОРТ — ставка на падение\n\n"
            "Множитель зависит от силы движения.\n\n"
            "Примеры:\n"
            "<code>/трейд 500 лонг</code>\n"
            "<code>/трейд 1к шорт</code>"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и направление.\n"
            "Пример: <code>/трейд 500 лонг</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    direction_text = parts[1].strip().lower()
    if direction_text in LONG_ALIASES:
        direction = "long"
        dir_display = "📈 ЛОНГ"
    elif direction_text in SHORT_ALIASES:
        direction = "short"
        dir_display = "📉 ШОРТ"
    else:
        return await message.answer(
            "❌ Укажи <b>лонг</b> или <b>шорт</b>.\n"
            "Пример: <code>/трейд 500 лонг</code>"
        )

    # Генерируем изменение цены (-30% до +30%), исключая 0
    change = 0
    while change == 0:
        change = random.randint(-30, 30)

    abs_change = abs(change)
    multiplier = round(1 + (abs_change / 100 * 5), 2)

    won = (direction == "long" and change > 0) or (direction == "short" and change < 0)

    result = await play_game(tg_id, "trade", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    change_emoji = "📈" if change > 0 else "📉"
    change_sign = "+" if change > 0 else ""

    if result["won"]:
        text = (
            f"💹 Рынок: {change_emoji} <b>{change_sign}{change}%</b>\n"
            f"📌 Позиция: {dir_display}\n\n"
            f"🎉 <b>Профит! x{multiplier}</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"💹 Рынок: {change_emoji} <b>{change_sign}{change}%</b>\n"
            f"📌 Позиция: {dir_display}\n\n"
            f"😔 <b>Ликвидация!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)