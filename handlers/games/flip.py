"""
🪙 Флип — орёл или решка.
Работает и в личке, и в группах.
"""
from __future__ import annotations

import random

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.game_service import play_game
from utils.helpers import format_winds, parse_amount, mention_user

router = Router()

HEADS_ALIASES = {"о", "орёл", "орел", "heads", "head", "h", "1"}
TAILS_ALIASES = {"р", "решка", "tails", "tail", "t", "2"}


def parse_side(text: str) -> str | None:
    t = text.strip().lower()
    if t in HEADS_ALIASES:
        return "heads"
    if t in TAILS_ALIASES:
        return "tails"
    return None


@router.message(Command("флип", "flip"))
async def cmd_flip(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    chat_id = message.chat.id if message.chat.type in ("group", "supergroup") else None
    is_group = chat_id is not None

    # Упоминание для групп
    if is_group:
        player = mention_user(tg_id, message.from_user.first_name)
    else:
        player = ""

    if not command.args:
        return await message.answer(
            "🪙 <b>Флип</b>\n\n"
            "Орёл или решка? Угадай — получи x2!\n\n"
            "Использование:\n"
            "<code>/флип 500 о</code> — ставка на орла\n"
            "<code>/флип 1к р</code> — ставка на решку"
        )

    parts = command.args.strip().split(maxsplit=1)

    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и сторону.\n"
            "Пример: <code>/флип 500 о</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    side = parse_side(parts[1])
    if side is None:
        return await message.answer(
            "❌ Укажи сторону: <b>о</b> (орёл) или <b>р</b> (решка)."
        )

    # Бросаем монетку
    coin = random.choice(["heads", "tails"])
    won = coin == side

    coin_emoji = "🦅" if coin == "heads" else "🪙"
    coin_name = "Орёл" if coin == "heads" else "Решка"
    side_name = "Орёл" if side == "heads" else "Решка"

    result = await play_game(tg_id, "flip", amount, 2.0, won, chat_id)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    # Формируем ответ
    header = f"{player} " if is_group else ""

    if result["won"]:
        text = (
            f"{header}{coin_emoji} <b>{coin_name}</b>\n"
            f"Ставка: {side_name}\n\n"
            f"🎉 <b>Выигрыш! x2</b>\n"
            f"💰 +{format_winds(result['profit'])}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )
    else:
        text = (
            f"{header}{coin_emoji} <b>{coin_name}</b>\n"
            f"Ставка: {side_name}\n\n"
            f"😔 <b>Не угадал!</b>\n"
            f"💸 -{format_winds(amount)}\n"
            f"📊 Баланс: {format_winds(result['new_balance'])}"
        )

    await message.answer(text)