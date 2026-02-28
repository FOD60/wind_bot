"""
⚽ Футбол — забей гол!

Механика:
  Бот отправляет ⚽ (Telegram dice type = "football").
  Значения:
    1, 2 — мимо (промах)
    3     — штанга (возврат ставки)
    4, 5  — гол (x2)

Команда: /футбол <ставка>  |  /football <ставка>
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

FOOTBALL_RESULTS = {
    1: {"name": "Мимо ворот 💨", "multiplier": 0.0},
    2: {"name": "Мимо ворот 💨", "multiplier": 0.0},
    3: {"name": "Штанга! 😤", "multiplier": 1.0},      # возврат
    4: {"name": "⚽ ГОЛ!", "multiplier": 2.0},
    5: {"name": "⚽ ГОЛ!", "multiplier": 2.0},
}


@router.message(Command("футбол", "football"))
async def cmd_football(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "⚽ <b>Футбол</b>\n\n"
            "Бей по воротам!\n"
            "• Гол → x2\n"
            "• Штанга → возврат ставки\n"
            "• Мимо → проигрыш\n\n"
            "Использование: <code>/футбол 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    dice_msg = await message.answer_dice(emoji="⚽")
    value = dice_msg.dice.value

    await asyncio.sleep(2.5)

    info = FOOTBALL_RESULTS[value]
    multiplier = info["multiplier"]

    if multiplier > 1.0:
        # Гол
        win_amount = int(amount * multiplier)
        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "football", amount, win_amount)
        profit = win_amount - amount
        text = (
            f"⚽ <b>{info['name']}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier:.0f}</b>\n"
            f"💰 +{format_winds(profit)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    elif multiplier == 1.0:
        # Штанга — возврат ставки
        new_balance = await credit_winnings(tg_id, amount)
        await record_game(tg_id, "football", amount, amount)
        text = (
            f"⚽ <b>{info['name']}</b>\n\n"
            f"↩️ Ставка возвращена.\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        await record_game(tg_id, "football", amount, 0)
        text = (
            f"⚽ <b>{info['name']}</b>\n\n"
            f"😔 <b>Не забил!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(bet_result['new_balance'])}"
        )

    await message.answer(text)