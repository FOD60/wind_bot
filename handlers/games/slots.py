"""
🍒 Слоты — фруктовый автомат.

Механика:
  3 барабана с 6 символами.
  • Три 💎 → x20
  • Три 7️⃣ → x10
  • Три одинаковых → x5
  • Два одинаковых → x1.5
  • Все разные → проигрыш

Команда: /слоты <ставка> | /slots <ставка>
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

SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "7️⃣", "💎"]


def spin_reels() -> tuple[str, str, str]:
    return random.choice(SYMBOLS), random.choice(SYMBOLS), random.choice(SYMBOLS)


def get_multiplier(s1: str, s2: str, s3: str) -> float:
    if s1 == s2 == s3:
        if s1 == "💎":
            return 20.0
        if s1 == "7️⃣":
            return 10.0
        return 5.0
    if s1 == s2 or s2 == s3 or s1 == s3:
        return 1.5
    return 0.0


@router.message(Command("слоты", "slots"))
async def cmd_slots(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🍒 <b>Слоты</b>\n\n"
            "Три барабана крутятся!\n"
            "• 💎💎💎 → x20\n"
            "• 7️⃣7️⃣7️⃣ → x10\n"
            "• Три одинаковых → x5\n"
            "• Два одинаковых → x1.5\n"
            "• Все разные → проигрыш\n\n"
            "Использование: <code>/слоты 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    s1, s2, s3 = spin_reels()
    multiplier = get_multiplier(s1, s2, s3)
    won = multiplier > 0

    result = await play_game(tg_id, "slots", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    line = f"[ {s1} | {s2} | {s3} ]"

    if result["won"]:
        text = (
            f"🍒 {line}\n\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"🍒 {line}\n\n"
            f"😔 <b>Мимо!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)