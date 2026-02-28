"""
🎡 Рулетка — ставки на число, цвет, диапазон.

Механика:
  Числа 0-36. Зелёный (0), красные, чёрные.
  
  Ставки:
    • Число (0-36): x35
    • Цвет (к/ч):  x2
    • Зелёный (0):  x35
    • Чёт/Нечёт:   x2
    • Диапазон 1-18 / 19-36: x2

Команда:
  /рулетка <ставка> <число|цвет|чёт|нечёт|1-18|19-36>
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

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

RED_ALIASES = {"к", "кр", "красный", "красное", "red", "r"}
BLACK_ALIASES = {"ч", "чёрный", "черный", "чёрное", "черное", "black", "b"}
GREEN_ALIASES = {"з", "зелёный", "зеленый", "зелёное", "зеленое", "green", "g", "0"}
EVEN_ALIASES = {"чёт", "чет", "четное", "чётное", "even", "e"}
ODD_ALIASES = {"нечёт", "нечет", "нечетное", "нечётное", "odd", "o"}
LOW_ALIASES = {"1-18", "мин", "low", "l"}
HIGH_ALIASES = {"19-36", "макс", "high", "h"}


def parse_bet_type(text: str) -> tuple[str, int | None]:
    """
    Возвращает:
      ("number", 17)     — конкретное число
      ("red", None)      — красный
      ("black", None)    — чёрный
      ("green", None)    — зелёный (0)
      ("even", None)     — чётное
      ("odd", None)      — нечётное
      ("low", None)      — 1-18
      ("high", None)     — 19-36
      ("error", None)    — ошибка
    """
    t = text.strip().lower()

    if t in RED_ALIASES:
        return "red", None
    if t in BLACK_ALIASES:
        return "black", None
    if t in GREEN_ALIASES:
        return "green", None
    if t in EVEN_ALIASES:
        return "even", None
    if t in ODD_ALIASES:
        return "odd", None
    if t in LOW_ALIASES:
        return "low", None
    if t in HIGH_ALIASES:
        return "high", None

    try:
        n = int(t)
        if 0 <= n <= 36:
            if n == 0:
                return "green", None
            return "number", n
    except ValueError:
        pass

    return "error", None


def get_color_emoji(num: int) -> str:
    if num == 0:
        return "🟢"
    if num in RED_NUMBERS:
        return "🔴"
    return "⚫"


def get_color_name(num: int) -> str:
    if num == 0:
        return "зелёный"
    if num in RED_NUMBERS:
        return "красный"
    return "чёрный"


@router.message(Command("рулетка", "roulette"))
async def cmd_roulette(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎡 <b>Рулетка</b>\n\n"
            "Сделай ставку!\n"
            "• Число (0-36) → x35\n"
            "• Цвет (<b>к</b>расный/<b>ч</b>ёрный) → x2\n"
            "• <b>з</b>елёный (0) → x35\n"
            "• <b>чёт</b>/<b>нечёт</b> → x2\n"
            "• <b>1-18</b> / <b>19-36</b> → x2\n\n"
            "Примеры:\n"
            "<code>/рулетка 500 17</code>\n"
            "<code>/рулетка 1к к</code>\n"
            "<code>/рулетка 500 чёт</code>"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и тип.\n"
            "Пример: <code>/рулетка 500 к</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    bet_type, bet_number = parse_bet_type(parts[1])
    if bet_type == "error":
        return await message.answer(
            "❌ Неверный тип ставки.\n"
            "Доступно: число (0-36), к, ч, з, чёт, нечёт, 1-18, 19-36"
        )

    # Крутим рулетку
    result_num = random.randint(0, 36)
    color_emoji = get_color_emoji(result_num)
    color_name = get_color_name(result_num)

    # Проверяем выигрыш
    won = False
    multiplier = 0.0

    if bet_type == "number":
        bet_display = f"Число {bet_number}"
        if result_num == bet_number:
            won = True
            multiplier = 35.0
    elif bet_type == "red":
        bet_display = "🔴 Красный"
        if result_num in RED_NUMBERS:
            won = True
            multiplier = 2.0
    elif bet_type == "black":
        bet_display = "⚫ Чёрный"
        if result_num in BLACK_NUMBERS:
            won = True
            multiplier = 2.0
    elif bet_type == "green":
        bet_display = "🟢 Зелёный (0)"
        if result_num == 0:
            won = True
            multiplier = 35.0
    elif bet_type == "even":
        bet_display = "Чётное"
        if result_num != 0 and result_num % 2 == 0:
            won = True
            multiplier = 2.0
    elif bet_type == "odd":
        bet_display = "Нечётное"
        if result_num != 0 and result_num % 2 == 1:
            won = True
            multiplier = 2.0
    elif bet_type == "low":
        bet_display = "1-18"
        if 1 <= result_num <= 18:
            won = True
            multiplier = 2.0
    elif bet_type == "high":
        bet_display = "19-36"
        if 19 <= result_num <= 36:
            won = True
            multiplier = 2.0

    result = await play_game(tg_id, "roulette", amount, multiplier, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    header = f"🎡 Выпало: {color_emoji} <b>{result_num}</b> ({color_name})\n📌 Ставка: {bet_display}\n"

    if result["won"]:
        text = (
            f"{header}\n"
            f"🎉 <b>Выигрыш! x{multiplier:.0f}</b>\n"
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