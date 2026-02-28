"""
🎫 Лотерея — 5 игроков, один победитель.

Механика:
  Билет стоит 10 000 виндов (фиксировано).
  Нужно 5 игроков.
  Банк = 5 * 10 000 = 50 000.
  Комиссия 5% → победитель получает 47 500 виндов.
  Победитель выбирается случайно.

Команда: /лотерея | /lottery
"""
from __future__ import annotations

import random
from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.game_service import validate_and_deduct_bet, credit_winnings, record_game
from services.user_service import get_or_create_user
from utils.constants import LOTTERY_MAX_PLAYERS, LOTTERY_TICKET_PRICE, LOTTERY_WINNER_PRIZE
from utils.helpers import format_winds, safe_name

router = Router()

MSK = pytz.timezone("Europe/Moscow")

# Одна глобальная лотерея на чат
# chat_id → state
_lotteries: dict[int, dict] = {}


def _lottery_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    state = _lotteries.get(chat_id, {})
    count = len(state.get("players", []))
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🎫 Купить билет ({format_winds(LOTTERY_TICKET_PRICE)}) [{count}/{LOTTERY_MAX_PLAYERS}]",
            callback_data="lottery_buy",
        )],
    ])


def _format_players(state: dict) -> str:
    lines = []
    for i, p in enumerate(state.get("players", []), 1):
        lines.append(f"  {i}. {p['name']}")
    return "\n".join(lines) if lines else "  Пока никого..."


@router.message(Command("лотерея", "lottery"))
async def cmd_lottery(message: Message) -> None:
    tg_id = message.from_user.id
    chat_id = message.chat.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if chat_id in _lotteries:
        state = _lotteries[chat_id]
        kb = _lottery_keyboard(chat_id)
        return await message.answer(
            f"🎫 <b>Лотерея уже запущена!</b>\n\n"
            f"💰 Билет: {format_winds(LOTTERY_TICKET_PRICE)}\n"
            f"🏆 Приз: {format_winds(LOTTERY_WINNER_PRIZE)}\n"
            f"👥 Игроки ({len(state['players'])}/{LOTTERY_MAX_PLAYERS}):\n"
            f"{_format_players(state)}\n\n"
            f"Купи билет!",
            reply_markup=kb,
        )

    _lotteries[chat_id] = {
        "players": [],
        "chat_id": chat_id,
    }

    kb = _lottery_keyboard(chat_id)
    await message.answer(
        f"🎫 <b>Лотерея открыта!</b>\n\n"
        f"💰 Билет: {format_winds(LOTTERY_TICKET_PRICE)}\n"
        f"🏆 Приз победителю: {format_winds(LOTTERY_WINNER_PRIZE)}\n"
        f"👥 Нужно {LOTTERY_MAX_PLAYERS} игроков.\n\n"
        f"Покупай билет!",
        reply_markup=kb,
    )


@router.callback_query(F.data == "lottery_buy")
async def cb_lottery_buy(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    chat_id = callback.message.chat.id

    state = _lotteries.get(chat_id)
    if not state:
        return await callback.answer("❌ Лотерея не запущена.", show_alert=True)

    # Проверка дубля
    for p in state["players"]:
        if p["tg_id"] == tg_id:
            return await callback.answer("❌ Ты уже купил билет!", show_alert=True)

    await get_or_create_user(tg_id, callback.from_user.username, callback.from_user.first_name)

    bet_result = await validate_and_deduct_bet(tg_id, LOTTERY_TICKET_PRICE)
    if not bet_result["ok"]:
        return await callback.answer(f"❌ {bet_result['error']}", show_alert=True)

    state["players"].append({
        "tg_id": tg_id,
        "name": safe_name(callback.from_user.first_name),
    })

    count = len(state["players"])

    if count < LOTTERY_MAX_PLAYERS:
        kb = _lottery_keyboard(chat_id)
        await callback.message.edit_text(
            f"🎫 <b>Лотерея</b>\n\n"
            f"💰 Билет: {format_winds(LOTTERY_TICKET_PRICE)}\n"
            f"🏆 Приз: {format_winds(LOTTERY_WINNER_PRIZE)}\n"
            f"👥 Игроки ({count}/{LOTTERY_MAX_PLAYERS}):\n"
            f"{_format_players(state)}\n\n"
            f"Ждём ещё {LOTTERY_MAX_PLAYERS - count} игроков!",
            reply_markup=kb,
        )
        return await callback.answer(f"🎫 Билет куплен! [{count}/{LOTTERY_MAX_PLAYERS}]")

    # Все собрались — розыгрыш!
    winner = random.choice(state["players"])
    winner_tg_id = winner["tg_id"]
    winner_name = winner["name"]

    # Начисляем приз
    new_balance = await credit_winnings(winner_tg_id, LOTTERY_WINNER_PRIZE)

    # Записываем историю для всех
    for p in state["players"]:
        if p["tg_id"] == winner_tg_id:
            await record_game(p["tg_id"], "lottery", LOTTERY_TICKET_PRICE, LOTTERY_WINNER_PRIZE)
        else:
            await record_game(p["tg_id"], "lottery", LOTTERY_TICKET_PRICE, 0)

    player_list = _format_players(state)
    del _lotteries[chat_id]

    await callback.message.edit_text(
        f"🎫 <b>ЛОТЕРЕЯ — РОЗЫГРЫШ!</b> 🎉\n\n"
        f"👥 Участники:\n{player_list}\n\n"
        f"🏆 Победитель: <b>{winner_name}</b>!\n"
        f"💰 Приз: {format_winds(LOTTERY_WINNER_PRIZE)}"
    )
    await callback.answer("🎉 Розыгрыш!", show_alert=True)