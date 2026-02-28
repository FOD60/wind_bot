"""
🎳 Боулинг — собьй кегли!

Механика:
  Telegram dice 🎳 → значения 1-6.
  1 — промах
  2, 3 — частичный (x1.5)
  4, 5 — почти страйк (x2)
  6 — СТРАЙК! (x3)

Команда: /боулинг <ставка>
"""
from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.game_service import validate_and_deduct_bet, credit_winnings, record_game
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount

router = Router()

BOWLING_RESULTS = {
    1: {"name": "Промах 💨", "multiplier": 0.0},
    2: {"name": "Сбил пару кеглей", "multiplier": 1.5},
    3: {"name": "Неплохой бросок!", "multiplier": 1.5},
    4: {"name": "Почти страйк! 💪", "multiplier": 2.0},
    5: {"name": "Отличный бросок! 🔥", "multiplier": 2.0},
    6: {"name": "🎳 СТРАЙК!!!", "multiplier": 3.0},
}


@router.message(Command("боулинг", "bowling"))
async def cmd_bowling(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎳 <b>Боулинг</b>\n\n"
            "Кидай шар!\n"
            "• Пара кеглей → x1.5\n"
            "• Почти страйк → x2\n"
            "• СТРАЙК → x3 🎳\n"
            "• Промах → проигрыш\n\n"
            "Использование: <code>/боулинг 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма. Пример: <code>/боулинг 1к</code>")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    dice_msg = await message.answer_dice(emoji="🎳")
    value = dice_msg.dice.value

    await asyncio.sleep(2.5)

    info = BOWLING_RESULTS[value]
    multiplier = info["multiplier"]

    if multiplier > 0:
        win_amount = int(amount * multiplier)
        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "bowling", amount, win_amount)
        profit = win_amount - amount

        text = (
            f"🎳 <b>{info['name']}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(profit)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        await record_game(tg_id, "bowling", amount, 0)
        text = (
            f"🎳 <b>{info['name']}</b>\n\n"
            f"😔 <b>Мимо!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(bet_result['new_balance'])}"
        )

    await message.answer(text)