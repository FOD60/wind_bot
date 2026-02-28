"""
💎 Джекпот — все ставят, один забирает.

Механика:
  Любой может добавить виндов в банк.
  Через 60 секунд после последней ставки (или по команде) — розыгрыш.
  Шанс победы пропорционален вложенной сумме.
  Победитель забирает всё (минус 5% комиссия).

Команда: /джекпот <ставка>
"""
from __future__ import annotations

import asyncio
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
from services.user_service import get_or_create_user
from utils.helpers import format_winds, parse_amount, safe_name

router = Router()

MSK = pytz.timezone("Europe/Moscow")

COMMISSION = 0.05
MIN_PLAYERS = 2
COUNTDOWN_SECONDS = 60

# chat_id → state
_jackpots: dict[int, dict] = {}
_jackpot_tasks: dict[int, asyncio.Task] = {}


def _format_jackpot(state: dict) -> str:
    total = state["total_pot"]
    lines = []
    for p in state["players"]:
        pct = round(p["amount"] / total * 100, 1) if total > 0 else 0
        lines.append(f"  {p['name']} — {format_winds(p['amount'])} ({pct}%)")
    return "\n".join(lines)


def _jackpot_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎰 Крутить сейчас!",
            callback_data=f"jackpot_spin:{chat_id}",
        )],
    ])


async def _auto_spin(chat_id: int, bot) -> None:
    """Автоматический розыгрыш через COUNTDOWN_SECONDS."""
    await asyncio.sleep(COUNTDOWN_SECONDS)
    state = _jackpots.get(chat_id)
    if not state or state["status"] != "active":
        return

    if len(state["players"]) < MIN_PLAYERS:
        return

    await _do_spin(chat_id, bot)


async def _do_spin(chat_id: int, bot) -> None:
    state = _jackpots.get(chat_id)
    if not state:
        return

    state["status"] = "finished"
    total = state["total_pot"]
    commission = int(total * COMMISSION)
    prize = total - commission

    # Взвешенный выбор
    weights = [p["amount"] for p in state["players"]]
    winner = random.choices(state["players"], weights=weights, k=1)[0]
    winner_tg_id = winner["tg_id"]

    await credit_winnings(winner_tg_id, prize)

    # История для всех
    for p in state["players"]:
        if p["tg_id"] == winner_tg_id:
            await record_game(p["tg_id"], "jackpot", p["amount"], prize)
        else:
            await record_game(p["tg_id"], "jackpot", p["amount"], 0)

    player_list = _format_jackpot(state)
    pct = round(winner["amount"] / total * 100, 1)

    del _jackpots[chat_id]
    if chat_id in _jackpot_tasks:
        del _jackpot_tasks[chat_id]

    await bot.send_message(
        chat_id,
        f"💎 <b>ДЖЕКПОТ — РОЗЫГРЫШ!</b> 🎉\n\n"
        f"👥 Участники:\n{player_list}\n\n"
        f"💰 Банк: {format_winds(total)}\n"
        f"🏆 Победитель: <b>{winner['name']}</b> (шанс {pct}%)\n"
        f"💰 Приз: {format_winds(prize)} (комиссия {int(COMMISSION * 100)}%)",
    )


@router.message(Command("джекпот", "jackpot"))
async def cmd_jackpot(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    chat_id = message.chat.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "💎 <b>Джекпот</b>\n\n"
            "Все ставят в общий банк.\n"
            "Чем больше ставка — тем выше шанс!\n"
            f"Розыгрыш через {COUNTDOWN_SECONDS} сек или по кнопке.\n"
            f"Минимум {MIN_PLAYERS} игрока.\n"
            f"Комиссия {int(COMMISSION * 100)}%.\n\n"
            "Использование: <code>/джекпот 1000</code>"
        )

    amount = parse_amount(command.args.strip())
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    name = safe_name(message.from_user.first_name)

    if chat_id not in _jackpots:
        _jackpots[chat_id] = {
            "players": [],
            "total_pot": 0,
            "status": "active",
        }

    state = _jackpots[chat_id]

    if state["status"] != "active":
        # Старый завершён, создаём новый
        _jackpots[chat_id] = {
            "players": [],
            "total_pot": 0,
            "status": "active",
        }
        state = _jackpots[chat_id]

    # Ищем игрока — может добавить ещё
    existing = None
    for p in state["players"]:
        if p["tg_id"] == tg_id:
            existing = p
            break

    if existing:
        existing["amount"] += amount
    else:
        state["players"].append({
            "tg_id": tg_id,
            "name": name,
            "amount": amount,
        })

    state["total_pot"] += amount

    # Перезапускаем таймер
    if chat_id in _jackpot_tasks:
        _jackpot_tasks[chat_id].cancel()

    if len(state["players"]) >= MIN_PLAYERS:
        task = asyncio.create_task(_auto_spin(chat_id, message.bot))
        _jackpot_tasks[chat_id] = task

    player_list = _format_jackpot(state)
    count = len(state["players"])

    kb = _jackpot_keyboard(chat_id) if count >= MIN_PLAYERS else None

    timer_text = f"⏳ Розыгрыш через {COUNTDOWN_SECONDS} сек" if count >= MIN_PLAYERS else f"⏳ Нужно минимум {MIN_PLAYERS} игрока"

    await message.answer(
        f"💎 <b>Джекпот</b>\n\n"
        f"👥 Участники ({count}):\n{player_list}\n\n"
        f"💰 Банк: {format_winds(state['total_pot'])}\n"
        f"{timer_text}",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("jackpot_spin:"))
async def cb_jackpot_spin(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[1])
    state = _jackpots.get(chat_id)

    if not state or state["status"] != "active":
        return await callback.answer("❌ Джекпот не найден.", show_alert=True)

    if len(state["players"]) < MIN_PLAYERS:
        return await callback.answer(
            f"❌ Нужно минимум {MIN_PLAYERS} игрока!", show_alert=True
        )

    # Проверяем, что нажавший — участник
    tg_id = callback.from_user.id
    is_player = any(p["tg_id"] == tg_id for p in state["players"])
    if not is_player:
        return await callback.answer("❌ Ты не участник!", show_alert=True)

    # Отменяем автотаймер
    if chat_id in _jackpot_tasks:
        _jackpot_tasks[chat_id].cancel()

    await _do_spin(chat_id, callback.bot)
    await callback.answer("🎰 Крутим!", show_alert=True)