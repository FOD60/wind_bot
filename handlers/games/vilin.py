"""
🃏 Вилин — выше/ниже карта.

Механика:
  Открывается случайная карта (2-14, где 11=В, 12=Д, 13=К, 14=Т).
  Игрок угадывает — следующая карта будет ВЫШЕ или НИЖЕ.
  x2 при угадывании, при равных — ничья (возврат).

Команда: /вилин <ставка> <в|н>
"""
from __future__ import annotations

import random

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.game_service import validate_and_deduct_bet, credit_winnings, record_game
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount

router = Router()

CARD_NAMES = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8",
    9: "9", 10: "10", 11: "Валет", 12: "Дама", 13: "Король", 14: "Туз",
}
CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]

HIGH_ALIASES = {"в", "выше", "больше", "high", "h", "б"}
LOW_ALIASES = {"н", "ниже", "меньше", "low", "l", "м"}


def format_card(value: int) -> str:
    suit = random.choice(CARD_SUITS)
    return f"{CARD_NAMES[value]}{suit}"


@router.message(Command("вилин", "vilin"))
async def cmd_vilin(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🃏 <b>Вилин</b>\n\n"
            "Открывается карта. Угадай — следующая выше или ниже?\n"
            "• Угадал → x2\n"
            "• Равные → возврат ставки\n\n"
            "Использование:\n"
            "<code>/вилин 500 в</code> — выше\n"
            "<code>/вилин 500 н</code> — ниже"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и выбор (в/н).\n"
            "Пример: <code>/вилин 500 в</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    choice_text = parts[1].strip().lower()
    if choice_text in HIGH_ALIASES:
        choice = "high"
        choice_display = "Выше"
    elif choice_text in LOW_ALIASES:
        choice = "low"
        choice_display = "Ниже"
    else:
        return await message.answer(
            "❌ Укажи <b>в</b> (выше) или <b>н</b> (ниже).\n"
            "Пример: <code>/вилин 500 в</code>"
        )

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    card1 = random.randint(2, 14)
    card2 = random.randint(2, 14)

    c1_str = format_card(card1)
    c2_str = format_card(card2)

    if card1 == card2:
        # Ничья — возврат
        new_balance = await credit_winnings(tg_id, amount)
        await record_game(tg_id, "vilin", amount, amount)
        text = (
            f"🃏 Первая: <b>{c1_str}</b>\n"
            f"🃏 Вторая: <b>{c2_str}</b>\n"
            f"📌 Выбор: {choice_display}\n\n"
            f"🤝 <b>Ничья!</b> Ставка возвращена.\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        won = (choice == "high" and card2 > card1) or (choice == "low" and card2 < card1)

        if won:
            win_amount = int(amount * 2)
            new_balance = await credit_winnings(tg_id, win_amount)
            await record_game(tg_id, "vilin", amount, win_amount)
            profit = win_amount - amount
            text = (
                f"🃏 Первая: <b>{c1_str}</b>\n"
                f"🃏 Вторая: <b>{c2_str}</b>\n"
                f"📌 Выбор: {choice_display}\n\n"
                f"🎉 <b>Угадал! x2</b>\n"
                f"💰 +{format_winds(profit)}\n"
                f"📊 Баланс: {format_winds(new_balance)}"
            )
        else:
            await record_game(tg_id, "vilin", amount, 0)
            text = (
                f"🃏 Первая: <b>{c1_str}</b>\n"
                f"🃏 Вторая: <b>{c2_str}</b>\n"
                f"📌 Выбор: {choice_display}\n\n"
                f"😔 <b>Не угадал!</b>\n"
                f"💸 -{format_winds(amount)}\n"
                f"📊 Баланс: {format_winds(bet_result['new_balance'])}"
            )

    await message.answer(text)