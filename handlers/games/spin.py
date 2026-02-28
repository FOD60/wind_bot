"""
🎡 Спин — колесо фортуны.

Механика:
  Колесо с секторами разной ценности.
  • x0 (проигрыш) — 35%
  • x1.5 — 25%
  • x2 — 20%
  • x3 — 12%
  • x5 — 5%
  • x10 — 2.5%
  • x50 — 0.5%

Команда: /спин <ставка> | /spin <ставка>
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

SPIN_TABLE = [
    (35.0, "💨 Пусто", 0.0),
    (25.0, "🟢 x1.5", 1.5),
    (20.0, "🔵 x2", 2.0),
    (12.0, "🟣 x3", 3.0),
    (5.0,  "🟠 x5", 5.0),
    (2.5,  "🔴 x10", 10.0),
    (0.5,  "💎 x50 ДЖЕКПОТ!", 50.0),
]


def spin_wheel() -> tuple[str, float]:
    roll = random.uniform(0, 100)
    cumulative = 0.0
    for chance, name, mult in SPIN_TABLE:
        cumulative += chance
        if roll <= cumulative:
            return name, mult
    return SPIN_TABLE[0][1], SPIN_TABLE[0][2]


@router.message(Command("спин", "spin"))
async def cmd_spin(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎡 <b>Спин — Колесо Фортуны</b>\n\n"
            "• 🟢 x1.5 (25%)\n"
            "• 🔵 x2 (20%)\n"
            "• 🟣 x3 (12%)\n"
            "• 🟠 x5 (5%)\n"
            "• 🔴 x10 (2.5%)\n"
            "• 💎 x50 (0.5%)\n"
            "• 💨 Пусто (35%)\n\n"
            "Использование: <code>/спин 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    name, multiplier = spin_wheel()
    won = multiplier > 0

    result = await play_game(tg_id, "spin", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    if result["won"]:
        text = (
            f"🎡 Колесо остановилось на: <b>{name}</b>\n\n"
            f"🎉 <b>Выигрыш!</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"🎡 Колесо остановилось на: <b>{name}</b>\n\n"
            f"😔 <b>Пусто!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)