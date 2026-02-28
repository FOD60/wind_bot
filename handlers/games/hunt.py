"""
🏹 Охота — выследи добычу.

Механика:
  Рандом определяет кого встретил:
  • 40% — Промах (потеря ставки)
  • 25% — Заяц (x1.5)
  • 15% — Олень (x2.5)
  • 10% — Медведь (x4)
  • 7%  — Легендарный зверь (x7)
  • 3%  — Дракон (x15)

Команда: /охота <ставка> | /hunt <ставка>
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

HUNT_TABLE = [
    (40, "Промах… 💨 Добыча ускользнула!", 0.0),
    (25, "🐇 Заяц!", 1.5),
    (15, "🦌 Олень!", 2.5),
    (10, "🐻 Медведь!", 4.0),
    (7,  "🦄 Легендарный зверь!", 7.0),
    (3,  "🐉 ДРАКОН!!!", 15.0),
]


def roll_hunt() -> tuple[str, float]:
    roll = random.randint(1, 100)
    cumulative = 0
    for chance, name, mult in HUNT_TABLE:
        cumulative += chance
        if roll <= cumulative:
            return name, mult
    return HUNT_TABLE[0][1], HUNT_TABLE[0][2]


@router.message(Command("охота", "hunt"))
async def cmd_hunt(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🏹 <b>Охота</b>\n\n"
            "Выслеживай добычу!\n"
            "• 🐇 Заяц → x1.5\n"
            "• 🦌 Олень → x2.5\n"
            "• 🐻 Медведь → x4\n"
            "• 🦄 Легендарный → x7\n"
            "• 🐉 Дракон → x15\n"
            "• 💨 Промах — проигрыш\n\n"
            "Использование: <code>/охота 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    name, multiplier = roll_hunt()
    won = multiplier > 0

    result = await play_game(tg_id, "hunt", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    if result["won"]:
        text = (
            f"🏹 <b>{name}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"🏹 <b>{name}</b>\n\n"
            f"😔 <b>Ничего не поймал!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)