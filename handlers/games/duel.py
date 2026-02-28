"""
⚔️ Дуэль — 1 на 1, всё или ничего.

Механика:
  Игрок вызывает другого на дуэль (ответом на сообщение или по @username).
  Оба ставят одинаковую сумму.
  Победитель определяется случайно (50/50).
  Победитель забирает всё (комиссия 5%).
  ⚠️ НЕ учитывается в лидерборде.

Команда: /дуэль <ставка> (ответом на сообщение)
         /дуэль <ставка> @username
"""
from __future__ import annotations

import random
from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.game_service import validate_and_deduct_bet, credit_winnings, record_game
from services.user_service import find_by_username, get_or_create_user, get_user
from utils.helpers import format_winds, parse_amount, safe_name

router = Router()

MSK = pytz.timezone("Europe/Moscow")

COMMISSION = 0.05

# session_id → state
_duels: dict[str, dict] = {}


def _duel_id(creator_tg_id: int) -> str:
    return f"duel_{creator_tg_id}_{int(datetime.now(MSK).timestamp())}"


def _duel_keyboard(session_id: str, bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⚔️ Принять дуэль ({format_winds(bet)})",
            callback_data=f"duel_accept:{session_id}",
        )],
        [InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"duel_decline:{session_id}",
        )],
    ])


@router.message(Command("дуэль", "duel"))
async def cmd_duel(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "⚔️ <b>Дуэль</b>\n\n"
            "Вызови соперника! 50/50, победитель забирает всё.\n"
            "Комиссия 5%.\n"
            "⚠️ Не учитывается в лидерборде.\n\n"
            "Использование:\n"
            "• Ответь на сообщение: <code>/дуэль 1000</code>\n"
            "• По юзернейму: <code>/дуэль 1000 @username</code>"
        )

    args = command.args.strip()
    parts = args.split(maxsplit=1)

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    # Определяем соперника
    target_tg_id = None
    target_name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return await message.answer("❌ Нельзя вызвать бота.")
        if target.id == tg_id:
            return await message.answer("❌ Нельзя вызвать себя.")
        target_tg_id = target.id
        target_name = safe_name(target.first_name)

    elif len(parts) > 1 and parts[1].startswith("@"):
        username = parts[1][1:]
        user_data = await find_by_username(username)
        if not user_data:
            return await message.answer(f"❌ @{safe_name(username)} не найден.")
        target_tg_id = user_data["telegram_id"]
        if target_tg_id == tg_id:
            return await message.answer("❌ Нельзя вызвать себя.")
        target_name = safe_name(user_data.get("first_name", username))

    else:
        return await message.answer(
            "❌ Укажи соперника.\n"
            "Ответь на сообщение или укажи @username.\n"
            "Пример: <code>/дуэль 1000 @player</code>"
        )

    # Проверяем нет ли активной дуэли
    for sid, s in _duels.items():
        if s["creator_id"] == tg_id and s["status"] == "waiting":
            return await message.answer("❌ У тебя уже есть активная дуэль!")

    # Списываем ставку у создателя
    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    session_id = _duel_id(tg_id)
    _duels[session_id] = {
        "creator_id": tg_id,
        "creator_name": safe_name(message.from_user.first_name),
        "target_id": target_tg_id,
        "target_name": target_name,
        "bet": amount,
        "status": "waiting",
    }

    kb = _duel_keyboard(session_id, amount)
    await message.answer(
        f"⚔️ <b>Дуэль!</b>\n\n"
        f"👤 {safe_name(message.from_user.first_name)} вызывает {target_name}!\n"
        f"💰 Ставка: {format_winds(amount)}\n\n"
        f"{target_name}, примешь вызов?",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("duel_accept:"))
async def cb_duel_accept(callback: CallbackQuery) -> None:
    session_id = callback.data.split(":", 1)[1]
    state = _duels.get(session_id)

    if not state or state["status"] != "waiting":
        return await callback.answer("❌ Дуэль не найдена.", show_alert=True)

    tg_id = callback.from_user.id

    if tg_id != state["target_id"]:
        return await callback.answer("❌ Эта дуэль не для тебя!", show_alert=True)

    await get_or_create_user(tg_id, callback.from_user.username, callback.from_user.first_name)

    # Списываем ставку у принимающего
    bet_result = await validate_and_deduct_bet(tg_id, state["bet"])
    if not bet_result["ok"]:
        return await callback.answer(f"❌ {bet_result['error']}", show_alert=True)

    state["status"] = "finished"
    bet = state["bet"]
    total = bet * 2
    commission = int(total * COMMISSION)
    prize = total - commission

    # 50/50
    winner_is_creator = random.choice([True, False])

    if winner_is_creator:
        winner_id = state["creator_id"]
        winner_name = state["creator_name"]
        loser_id = state["target_id"]
        loser_name = state["target_name"]
    else:
        winner_id = state["target_id"]
        winner_name = state["target_name"]
        loser_id = state["creator_id"]
        loser_name = state["creator_name"]

    await credit_winnings(winner_id, prize)
    await record_game(winner_id, "duel", bet, prize)
    await record_game(loser_id, "duel", bet, 0)

    del _duels[session_id]

    await callback.message.edit_text(
        f"⚔️ <b>Дуэль — Результат!</b>\n\n"
        f"👤 {state['creator_name']} vs {state['target_name']}\n"
        f"💰 Банк: {format_winds(total)}\n\n"
        f"🏆 Победитель: <b>{winner_name}</b>!\n"
        f"💰 Приз: {format_winds(prize)} (комиссия {int(COMMISSION * 100)}%)\n"
        f"😔 {loser_name} проиграл."
    )
    await callback.answer("⚔️ Дуэль завершена!", show_alert=True)


@router.callback_query(F.data.startswith("duel_decline:"))
async def cb_duel_decline(callback: CallbackQuery) -> None:
    session_id = callback.data.split(":", 1)[1]
    state = _duels.get(session_id)

    if not state:
        return await callback.answer("❌ Дуэль не найдена.", show_alert=True)

    tg_id = callback.from_user.id

    if tg_id != state["target_id"] and tg_id != state["creator_id"]:
        return await callback.answer("❌ Ты не участник!", show_alert=True)

    if state["status"] != "waiting":
        return await callback.answer("❌ Дуэль уже завершена.", show_alert=True)

    # Возврат ставки создателю
    await credit_winnings(state["creator_id"], state["bet"])
    del _duels[session_id]

    if tg_id == state["target_id"]:
        text = f"❌ {state['target_name']} отклонил(а) дуэль. Ставка возвращена."
    else:
        text = f"❌ {state['creator_name']} отменил(а) дуэль. Ставка возвращена."

    await callback.message.edit_text(text)
    await callback.answer("Отменено.")