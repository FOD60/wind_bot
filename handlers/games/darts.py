"""
🎯 Дартс — попади в центр.

Механика:
  Бот отправляет 🎯 (Telegram dice type = "darts").
  Значения:
    1 — промах
    2, 3 — внешнее кольцо (x1.5)
    4, 5 — среднее кольцо (x2)
    6 — яблочко / bullseye (x3.35)

Команда: /дартс <ставка>  |  /darts <ставка>
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

# Множители по значению Telegram darts dice (1-6)
DARTS_MULTIPLIERS = {
    1: 0.0,     # Промах
    2: 1.5,     # Внешнее кольцо
    3: 1.5,     # Внешнее кольцо
    4: 2.0,     # Среднее кольцо
    5: 2.0,     # Среднее кольцо
    6: 3.35,    # 🎯 Яблочко!
}

DARTS_NAMES = {
    1: "Промах 💨",
    2: "Внешнее кольцо",
    3: "Внешнее кольцо",
    4: "Среднее кольцо",
    5: "Среднее кольцо",
    6: "🎯 ЯБЛОЧКО!",
}


@router.message(Command("дартс", "darts"))
async def cmd_darts(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎯 <b>Дартс</b>\n\n"
            "Кидай дротик!\n"
            "• Внешнее кольцо → x1.5\n"
            "• Среднее кольцо → x2\n"
            "• Яблочко → x3.35 🎯\n"
            "• Промах → проигрыш\n\n"
            "Использование: <code>/дартс 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма. Пример: <code>/дартс 1к</code>")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    dice_msg = await message.answer_dice(emoji="🎯")
    value = dice_msg.dice.value

    await asyncio.sleep(2.5)

    multiplier = DARTS_MULTIPLIERS[value]
    hit_name = DARTS_NAMES[value]

    if multiplier > 0:
        win_amount = int(amount * multiplier)
        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "darts", amount, win_amount)
        profit = win_amount - amount

        text = (
            f"🎯 Результат: <b>{hit_name}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(profit)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        await record_game(tg_id, "darts", amount, 0)
        text = (
            f"🎯 Результат: <b>{hit_name}</b>\n\n"
            f"😔 <b>Промазал!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(bet_result['new_balance'])}"
        )

    await message.answer(text)