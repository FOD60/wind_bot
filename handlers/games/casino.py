"""
🎰 Казино — слот-машина.

Механика:
  Бот отправляет 🎰 (Telegram dice type = "slot_machine").
  Telegram сам генерирует результат (value 1-64).
  
  Значение value декодируется в 3 барабана.
  • 3 одинаковых: 777 → x10, другие тройки → x5
  • 2 одинаковых: x2
  • Все разные: проигрыш

Команда: /казино <ставка>  |  /casino <ставка>
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

# Декодирование slot_machine value → 3 символа
# Telegram slot machine: значения 1-64
# Барабаны: BAR, Grape, Lemon, Seven
# Формула: value-1, затем каждый барабан = (value // divisor) % 4
SLOT_SYMBOLS = ["BAR", "🍇", "🍋", "7️⃣"]


def decode_slot(value: int) -> tuple[str, str, str]:
    """Декодирует значение Telegram slot в 3 символа."""
    v = value - 1
    s1 = SLOT_SYMBOLS[v % 4]
    s2 = SLOT_SYMBOLS[(v // 4) % 4]
    s3 = SLOT_SYMBOLS[(v // 16) % 4]
    return s1, s2, s3


def get_slot_multiplier(value: int) -> float:
    """
    Определяет множитель по значению слота.
    value=64 → джекпот 777 → x10
    value=43 → BAR BAR BAR → x5
    value=22 → 🍇🍇🍇 → x5
    value=1  → 🍋🍋🍋 → x5
    Две одинаковых → x2
    """
    s1, s2, s3 = decode_slot(value)

    if s1 == s2 == s3:
        if s1 == "7️⃣":
            return 10.0  # 🎰 ДЖЕКПОТ
        return 5.0  # Тройка

    if s1 == s2 or s2 == s3 or s1 == s3:
        return 2.0  # Пара

    return 0.0  # Проигрыш


@router.message(Command("казино", "casino"))
async def cmd_casino(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎰 <b>Казино</b>\n\n"
            "Три барабана крутятся!\n"
            "• 7️⃣7️⃣7️⃣ — x10\n"
            "• Три одинаковых — x5\n"
            "• Два одинаковых — x2\n"
            "• Все разные — проигрыш\n\n"
            "Использование: <code>/казино 500</code>"
        )

    amount = parse_amount(command.args)
    if amount is None:
        return await message.answer("❌ Неверная сумма. Пример: <code>/казино 1к</code>")

    # Списываем ставку
    result = await validate_and_deduct_bet(tg_id, amount)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    # Отправляем dice (slot_machine)
    dice_msg = await message.answer_dice(emoji="🎰")
    value = dice_msg.dice.value

    # Ждём анимацию (Telegram slot animation ~2 сек)
    await asyncio.sleep(2.5)

    multiplier = get_slot_multiplier(value)
    s1, s2, s3 = decode_slot(value)

    if multiplier > 0:
        win_amount = int(amount * multiplier)
        new_balance = await credit_winnings(tg_id, win_amount)
        profit = win_amount - amount
        await record_game(tg_id, "casino", amount, win_amount)

        text = (
            f"🎰 [ {s1} | {s2} | {s3} ]\n\n"
            f"🎉 <b>Выигрыш! x{multiplier:.0f}</b>\n"
            f"💰 +{format_winds(profit)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
    else:
        await record_game(tg_id, "casino", amount, 0)
        new_balance = result["new_balance"]

        text = (
            f"🎰 [ {s1} | {s2} | {s3} ]\n\n"
            f"😔 <b>Мимо!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )

    await message.answer(text)