"""
✊ КНБ — Камень, Ножницы, Бумага (мультиплеер).

Механика:
  Игрок создаёт игру с указанной ставкой.
  Второй игрок принимает.
  Оба выбирают ход через inline-кнопки (скрыто).
  Когда оба выбрали — результат.
  Победитель получает x2 ставки (минус 5% комиссия).
  Ничья — возврат.

Команда: /кнб <ставка>
"""
from __future__ import annotations

import asyncio
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
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount, safe_name

router = Router()

MSK = pytz.timezone("Europe/Moscow")

# Активные сессии КНБ: session_id → state
_knb_sessions: dict[str, dict] = {}

MOVES = {
    "rock": "✊ Камень",
    "scissors": "✂️ Ножницы",
    "paper": "📄 Бумага",
}

# rock > scissors, scissors > paper, paper > rock
WINS_OVER = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock",
}

COMMISSION = 0.05  # 5% комиссия


def _session_id(creator_tg_id: int) -> str:
    return f"knb_{creator_tg_id}_{int(datetime.now(MSK).timestamp())}"


def _join_keyboard(session_id: str, bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⚔️ Принять вызов ({format_winds(bet)})",
            callback_data=f"knb_join:{session_id}",
        )],
        [InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"knb_cancel:{session_id}",
        )],
    ])


def _move_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✊", callback_data=f"knb_move:{session_id}:rock"),
            InlineKeyboardButton(text="✂️", callback_data=f"knb_move:{session_id}:scissors"),
            InlineKeyboardButton(text="📄", callback_data=f"knb_move:{session_id}:paper"),
        ]
    ])


@router.message(Command("кнб", "knb"))
async def cmd_knb(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "✊✂️📄 <b>Камень-Ножницы-Бумага</b>\n\n"
            "Создай игру — другой игрок примет вызов.\n"
            "Победитель забирает x2 (комиссия 5%).\n"
            "Ничья — возврат.\n\n"
            "Использование: <code>/кнб 500</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    # Проверяем нет ли уже активной сессии от этого игрока
    for sid, s in _knb_sessions.items():
        if s["creator_id"] == tg_id and s["status"] == "waiting":
            return await message.answer("❌ У тебя уже есть активная игра КНБ!")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    session_id = _session_id(tg_id)
    _knb_sessions[session_id] = {
        "creator_id": tg_id,
        "creator_name": safe_name(message.from_user.first_name),
        "opponent_id": None,
        "opponent_name": None,
        "bet": amount,
        "status": "waiting",
        "moves": {},
        "message_id": None,
        "chat_id": message.chat.id,
    }

    kb = _join_keyboard(session_id, amount)
    sent = await message.answer(
        f"✊✂️📄 <b>КНБ — Вызов!</b>\n\n"
        f"👤 {safe_name(message.from_user.first_name)} ставит {format_winds(amount)}\n"
        f"Кто примет вызов?",
        reply_markup=kb,
    )
    _knb_sessions[session_id]["message_id"] = sent.message_id


@router.callback_query(F.data.startswith("knb_join:"))
async def cb_knb_join(callback: CallbackQuery) -> None:
    session_id = callback.data.split(":", 1)[1]
    state = _knb_sessions.get(session_id)

    if not state or state["status"] != "waiting":
        return await callback.answer("❌ Игра не найдена или уже началась.", show_alert=True)

    tg_id = callback.from_user.id

    if tg_id == state["creator_id"]:
        return await callback.answer("❌ Нельзя играть с самим собой!", show_alert=True)

    await get_or_create_user(tg_id, callback.from_user.username, callback.from_user.first_name)

    bet_result = await validate_and_deduct_bet(tg_id, state["bet"])
    if not bet_result["ok"]:
        return await callback.answer(f"❌ {bet_result['error']}", show_alert=True)

    state["opponent_id"] = tg_id
    state["opponent_name"] = safe_name(callback.from_user.first_name)
    state["status"] = "choosing"

    kb = _move_keyboard(session_id)
    await callback.message.edit_text(
        f"✊✂️📄 <b>КНБ — Выбирайте ход!</b>\n\n"
        f"👤 {state['creator_name']} vs 👤 {state['opponent_name']}\n"
        f"💰 Банк: {format_winds(state['bet'] * 2)}\n\n"
        f"Оба игрока — нажмите свой ход ниже!",
        reply_markup=kb,
    )
    await callback.answer("✅ Ты принял вызов! Выбери ход.")


@router.callback_query(F.data.startswith("knb_move:"))
async def cb_knb_move(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    session_id = parts[1]
    move = parts[2]

    state = _knb_sessions.get(session_id)
    if not state or state["status"] != "choosing":
        return await callback.answer("❌ Игра не найдена.", show_alert=True)

    tg_id = callback.from_user.id

    if tg_id != state["creator_id"] and tg_id != state["opponent_id"]:
        return await callback.answer("❌ Ты не участник этой игры!", show_alert=True)

    if tg_id in state["moves"]:
        return await callback.answer("✅ Ты уже выбрал ход. Жди соперника.", show_alert=True)

    if move not in MOVES:
        return await callback.answer("❌ Неверный ход.", show_alert=True)

    state["moves"][tg_id] = move
    await callback.answer(f"✅ Ты выбрал: {MOVES[move]}")

    # Ждём оба хода
    if len(state["moves"]) < 2:
        await callback.message.edit_text(
            f"✊✂️📄 <b>КНБ</b>\n\n"
            f"👤 {state['creator_name']} — {'✅ готов' if state['creator_id'] in state['moves'] else '⏳ думает'}\n"
            f"👤 {state['opponent_name']} — {'✅ готов' if state['opponent_id'] in state['moves'] else '⏳ думает'}\n"
            f"💰 Банк: {format_winds(state['bet'] * 2)}",
            reply_markup=_move_keyboard(session_id),
        )
        return

    # Оба выбрали — определяем результат
    state["status"] = "finished"
    creator_move = state["moves"][state["creator_id"]]
    opponent_move = state["moves"][state["opponent_id"]]
    bet = state["bet"]
    total_pot = bet * 2

    c_name = state["creator_name"]
    o_name = state["opponent_name"]

    if creator_move == opponent_move:
        # Ничья — возврат
        await credit_winnings(state["creator_id"], bet)
        await credit_winnings(state["opponent_id"], bet)
        await record_game(state["creator_id"], "knb", bet, bet)
        await record_game(state["opponent_id"], "knb", bet, bet)

        text = (
            f"✊✂️📄 <b>КНБ — Ничья!</b>\n\n"
            f"👤 {c_name}: {MOVES[creator_move]}\n"
            f"👤 {o_name}: {MOVES[opponent_move]}\n\n"
            f"🤝 Ставки возвращены!"
        )
    else:
        # Определяем победителя
        if WINS_OVER[creator_move] == opponent_move:
            winner_id = state["creator_id"]
            winner_name = c_name
            loser_name = o_name
        else:
            winner_id = state["opponent_id"]
            winner_name = o_name
            loser_name = c_name

        loser_id = state["creator_id"] if winner_id == state["opponent_id"] else state["opponent_id"]

        commission = int(total_pot * COMMISSION)
        prize = total_pot - commission

        await credit_winnings(winner_id, prize)
        await record_game(winner_id, "knb", bet, prize)
        await record_game(loser_id, "knb", bet, 0)

        text = (
            f"✊✂️📄 <b>КНБ — Результат!</b>\n\n"
            f"👤 {c_name}: {MOVES[creator_move]}\n"
            f"👤 {o_name}: {MOVES[opponent_move]}\n\n"
            f"🏆 Победитель: <b>{winner_name}</b>\n"
            f"💰 Приз: {format_winds(prize)} (комиссия {int(COMMISSION * 100)}%)"
        )

    del _knb_sessions[session_id]
    await callback.message.edit_text(text)


@router.callback_query(F.data.startswith("knb_cancel:"))
async def cb_knb_cancel(callback: CallbackQuery) -> None:
    session_id = callback.data.split(":", 1)[1]
    state = _knb_sessions.get(session_id)

    if not state:
        return await callback.answer("❌ Игра не найдена.", show_alert=True)

    if callback.from_user.id != state["creator_id"]:
        return await callback.answer("❌ Только создатель может отменить.", show_alert=True)

    if state["status"] != "waiting":
        return await callback.answer("❌ Игра уже началась!", show_alert=True)

    # Возврат ставки создателю
    await credit_winnings(state["creator_id"], state["bet"])
    del _knb_sessions[session_id]

    await callback.message.edit_text("❌ Игра КНБ отменена. Ставка возвращена.")
    await callback.answer("Отменено.")