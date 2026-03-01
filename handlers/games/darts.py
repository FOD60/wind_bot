"""
🎯 Дартс — попади в центр.
"""
from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.game_service import play_game
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount, mention_user

router = Router()

DARTS_MULTIPLIERS = {
    1: 0.0,     # Промах
    2: 1.0,     # Внешнее кольцо
    3: 1.0,     # Внешнее кольцо
    4: 1.3,     # Среднее кольцо
    5: 1.3,     # Среднее кольцо
    6: 1.5,    # 🎯 Яблочко!
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
    chat_id = message.chat.id if message.chat.type in ("group", "supergroup") else None
    is_group = chat_id is not None

    if is_group:
        player = mention_user(tg_id, message.from_user.first_name)
    else:
        player = ""

    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "🎯 <b>Дартс</b>\n\n"
            "Кидай дротик!\n"
            "• Внешнее кольцо → x1.0\n"
            "• Среднее кольцо → x1.3\n"
            "• Яблочко → x1.5 🎯\n"
            "• Промах → проигрыш\n\n"
            "Использование: <code>/дартс 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма. Пример: <code>/дартс 1к</code>")

    # Сначала отправляем дротик от лица бота, ЧТОБЫ ИСКЛЮЧИТЬ ПОДМЕНУ!
    dice_msg = await message.answer_dice(emoji="🎯")
    value = dice_msg.dice.value

    # Ждём анимацию
    await asyncio.sleep(2.5)

    multiplier = DARTS_MULTIPLIERS.get(value, 0.0)
    hit_name = DARTS_NAMES.get(value, "Неизвестно")
    won = multiplier > 0

    # Обрабатываем ставку и результат ПОСЛЕ броска
    result = await play_game(tg_id, "darts", amount, multiplier, won, chat_id)

    if not result["ok"]:
        # Если ставка не прошла (например, нет денег), мы просто удаляем дротик (если бот админ) или пишем ошибку
        try:
            await dice_msg.delete()
        except:
            pass
        return await message.answer(f"❌ {result['error']}")

    header = f"{player} " if is_group else ""

    if result["won"]:
        text = (
            f"{header}🎯 Результат: <b>{hit_name}</b>\n\n"
            f"🎉 <b>Выигрыш! x{multiplier}</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"{header}🎯 Результат: <b>{hit_name}</b>\n\n"
            f"😔 <b>Промазал!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.reply(text) # Отвечаем на исходное сообщение пользователя
