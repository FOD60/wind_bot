"""
📊 Нвути — угадай число выше/ниже порога.

Механика:
  Генерируется число 1-100.
  Игрок выбирает порог и направление.
  
  • /нвути 500 >50 — выиграть если число > 50
  • /нвути 500 <30 — выиграть если число < 30
  
  Множитель = 100 / шанс_победы.
  >50 → шанс 50% → x2.0
  >80 → шанс 20% → x5.0
  <10 → шанс 9%  → x11.1

Команда: /нвути <ставка> <направление><порог>
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


def parse_nvuti(text: str) -> tuple[str, int, float] | None:
    """
    Парсит '>50' или '<30'.
    Возвращает (direction, threshold, multiplier) или None.
    """
    t = text.strip()
    if not t:
        return None

    if t[0] == ">":
        direction = ">"
    elif t[0] == "<":
        direction = "<"
    elif t[0] == "б":
        direction = ">"
        t = ">" + t[1:]
    elif t[0] == "м":
        direction = "<"
        t = "<" + t[1:]
    else:
        return None

    try:
        threshold = int(t[1:])
    except (ValueError, IndexError):
        return None

    if threshold < 1 or threshold > 99:
        return None

    # Рассчитываем шанс и множитель
    if direction == ">":
        chance = 100 - threshold  # >50 → 50 чисел из 100
    else:
        chance = threshold - 1    # <30 → 29 чисел из 100

    if chance <= 0 or chance >= 100:
        return None

    # Множитель с комиссией 3%
    multiplier = round(97.0 / chance, 2)
    if multiplier < 1.01:
        return None

    return direction, threshold, multiplier


@router.message(Command("нвути", "nvuti"))
async def cmd_nvuti(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "📊 <b>Нвути</b>\n\n"
            "Генерируется число 1-100.\n"
            "Угадай — выше или ниже порога!\n\n"
            "Чем сложнее угадать, тем выше множитель:\n"
            "• <code>/нвути 500 >50</code> → x1.94 (шанс 50%)\n"
            "• <code>/нвути 500 >80</code> → x4.85 (шанс 20%)\n"
            "• <code>/нвути 500 <20</code> → x5.11 (шанс 19%)\n"
            "• <code>/нвути 500 >95</code> → x19.4 (шанс 5%)\n\n"
            "Порог: от 1 до 99."
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и порог.\n"
            "Пример: <code>/нвути 500 >50</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    parsed = parse_nvuti(parts[1])
    if parsed is None:
        return await message.answer(
            "❌ Неверный порог.\n"
            "Формат: >число или <число (1-99)\n"
            "Пример: <code>/нвути 500 >50</code>"
        )

    direction, threshold, multiplier = parsed
    chance = 100 - threshold if direction == ">" else threshold - 1

    # Бросаем
    roll = random.randint(1, 100)

    if direction == ">":
        won = roll > threshold
        bet_display = f"Больше {threshold}"
    else:
        won = roll < threshold
        bet_display = f"Меньше {threshold}"

    result = await play_game(tg_id, "nvuti", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    header = (
        f"📊 Число: <b>{roll}</b>\n"
        f"📌 Ставка: {bet_display} (шанс {chance}%, x{multiplier})\n"
    )

    if result["won"]:
        text = (
            f"{header}\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"{header}\n"
            f"😔 <b>Не угадал!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)