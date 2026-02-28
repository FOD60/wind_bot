"""
🎲 Кубик — угадай больше/меньше.

Механика:
  Игрок выбирает «больше 3» или «меньше 4» (числа 1-6).
  Бот бросает Telegram dice 🎲.
  
  • Больше (4, 5, 6): x2
  • Меньше (1, 2, 3): x2
  • Точное число: x5

Команда: /кубик <ставка> <б|м|число>
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

BIG_ALIASES = {"б", "больше", "big", "б3", ">", "+"}
SMALL_ALIASES = {"м", "меньше", "small", "м4", "<", "-"}


def parse_choice(text: str) -> tuple[str, int | None]:
    """
    Возвращает:
      ("big", None)   — больше 3
      ("small", None) — меньше 4
      ("exact", 5)    — точное число
      ("error", None) — ошибка
    """
    t = text.strip().lower()
    if t in BIG_ALIASES:
        return "big", None
    if t in SMALL_ALIASES:
        return "small", None
    try:
        n = int(t)
        if 1 <= n <= 6:
            return "exact", n
    except ValueError:
        pass
    return "error", None


@router.message(Command("кубик", "dice", "куб"))
async def cmd_dice(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎲 <b>Кубик</b>\n\n"
            "Угадай результат броска!\n"
            "• <b>б</b> (больше 3) → x2\n"
            "• <b>м</b> (меньше 4) → x2\n"
            "• <b>Точное число</b> (1-6) → x5\n\n"
            "Примеры:\n"
            "<code>/кубик 500 б</code>\n"
            "<code>/кубик 1к 4</code>"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и выбор.\n"
            "Пример: <code>/кубик 500 б</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    choice, exact_num = parse_choice(parts[1])
    if choice == "error":
        return await message.answer(
            "❌ Неверный выбор.\n"
            "Используй: <b>б</b> (больше), <b>м</b> (меньше), или число 1-6."
        )

    # Списываем ставку
    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    # Бросаем кубик через Telegram
    dice_msg = await message.answer_dice(emoji="🎲")
    value = dice_msg.dice.value  # 1-6

    await asyncio.sleep(2.0)

    # Определяем результат
    won = False
    multiplier = 0.0

    if choice == "big":
        choice_text = "Больше 3"
        if value >= 4:
            won = True
            multiplier = 2.0
    elif choice == "small":
        choice_text = "Меньше 4"
        if value <= 3:
            won = True
            multiplier = 2.0
    else:  # exact
        choice_text = f"Число {exact_num}"
        if value == exact_num:
            won = True
            multiplier = 5.0

    if won:
        win_amount = int(amount * multiplier)
        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "dice", amount, win_amount)
        profit = win_amount - amount

        text = (
            f"🎲 Выпало: <b>{value}</b>\n"
            f"Твой выбор: <b>{choice_text}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier:.0f}</b>\n"
            f"💰 +{format_winds(profit)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        await record_game(tg_id, "dice", amount, 0)
        text = (
            f"🎲 Выпало: <b>{value}</b>\n"
            f"Твой выбор: <b>{choice_text}</b>\n\n"
            f"😔 <b>Мимо!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(bet_result['new_balance'])}"
        )

    await message.answer(text)