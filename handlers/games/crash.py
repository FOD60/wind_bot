"""
📈 Краш — успей забрать до краша!

Механика:
  Множитель растёт от x1.00.
  Точка краша генерируется заранее по формуле.
  Игрок выбирает множитель, на котором забрать.
  Если выбранный множитель <= точки краша — выигрыш.

Команда: /краш <ставка> <множитель>
Пример: /краш 500 2.5
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


def generate_crash_point() -> float:
    """
    Генерирует точку краша.
    Распределение: house edge ~3%.
    Результат от 1.00 до 100.00.
    """
    r = random.random()
    if r < 0.03:
        return 1.0  # Мгновенный краш (3%)
    crash = 0.97 / (1.0 - r)
    return round(min(crash, 100.0), 2)


@router.message(Command("краш", "crash"))
async def cmd_crash(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "📈 <b>Краш</b>\n\n"
            "Множитель растёт... но может упасть!\n"
            "Выбери множитель для вывода (1.1 — 100.0).\n"
            "Если краш случится позже — ты выиграешь!\n\n"
            "Примеры:\n"
            "<code>/краш 500 2</code> — забрать на x2\n"
            "<code>/краш 1к 1.5</code> — забрать на x1.5"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и множитель.\n"
            "Пример: <code>/краш 500 2.5</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    try:
        target_mult = round(float(parts[1].replace(",", ".")), 2)
    except ValueError:
        return await message.answer("❌ Неверный множитель. Пример: 2.5")

    if target_mult < 1.1:
        return await message.answer("❌ Минимальный множитель — 1.1")
    if target_mult > 100.0:
        return await message.answer("❌ Максимальный множитель — 100.0")

    crash_point = generate_crash_point()
    won = target_mult <= crash_point

    result = await play_game(tg_id, "crash", amount, target_mult, won)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    if result["won"]:
        text = (
            f"📈 Краш на: <b>x{crash_point}</b>\n"
            f"📌 Ты забрал на: <b>x{target_mult}</b>\n\n"
            f"🎉 <b>Успел! Выигрыш!</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"📈 Краш на: <b>x{crash_point}</b> 💥\n"
            f"📌 Ты хотел забрать на: <b>x{target_mult}</b>\n\n"
            f"😔 <b>Не успел!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)