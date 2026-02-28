"""
🔫 Русская рулетка — один патрон, шесть камер.

Механика:
  Шанс проиграть: 1/6 (16.7%).
  Выжил → x1.2 (получаешь 120% ставки).
  Не выжил → потеря ставки.
  ⚠️ НЕ учитывается в лидерборде.

Команда: /рр <ставка> | /rr <ставка>
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


@router.message(Command("рр", "rr", "русскаярулетка"))
async def cmd_russian_roulette(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🔫 <b>Русская рулетка</b>\n\n"
            "Один патрон — шесть камер.\n"
            "• Выжил → x1.2\n"
            "• 💀 → потеря ставки\n\n"
            "⚠️ Не учитывается в лидерборде!\n\n"
            "Использование: <code>/рр 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    # 1 из 6 — патрон
    chamber = random.randint(1, 6)
    won = chamber != 1  # Выжил если не 1

    result = await play_game(tg_id, "russian_roulette", amount, 1.2, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    chambers = ""
    for i in range(1, 7):
        if i == chamber:
            chambers += "💥"
        elif i < chamber:
            chambers += "⬜"
        else:
            chambers += "⬜"

    if result["won"]:
        text = (
            f"🔫 {chambers}\n\n"
            f"😮‍💨 <b>Щёлк... Пусто! Ты выжил!</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"🔫 {chambers}\n\n"
            f"💀 <b>БАХ! Не повезло...</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)