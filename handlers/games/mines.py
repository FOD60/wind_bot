"""
💣 Мины — поле 5x5, ищи алмазы.

Механика:
  Поле 5x5 = 25 ячеек. Игрок выбирает количество мин (1-24).
  Каждый открытый безопасный алмаз → множитель x1.25.
  Множители умножаются: 2 алмаза = 1.25 * 1.25 = x1.5625.
  Можно забрать в любой момент.
  Наступил на мину → потеря.

Команда: /мины <ставка> <кол-во мин>
Далее inline-кнопки для открытия ячеек.
"""
from __future__ import annotations

import json
import random
from typing import Optional

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
from utils.constants import MINES_GRID_SIZE, MINES_DIAMOND_MULTIPLIER
from utils.helpers import format_winds, parse_amount

router = Router()

# Хранение активных сессий мин в памяти (telegram_id → state)
# В проде можно перенести в Redis/Firestore
_active_mines: dict[int, dict] = {}

GRID_TOTAL = MINES_GRID_SIZE * MINES_GRID_SIZE  # 25


def generate_field(num_mines: int) -> list[bool]:
    """True = мина, False = алмаз. Длина 25."""
    field = [True] * num_mines + [False] * (GRID_TOTAL - num_mines)
    random.shuffle(field)
    return field


def build_keyboard(
    tg_id: int, revealed: set[int], game_over: bool = False, exploded: int = -1
) -> InlineKeyboardMarkup:
    """Строим сетку 5x5 из inline-кнопок."""
    state = _active_mines.get(tg_id, {})
    field = state.get("field", [])

    rows = []
    for row in range(MINES_GRID_SIZE):
        buttons = []
        for col in range(MINES_GRID_SIZE):
            idx = row * MINES_GRID_SIZE + col

            if game_over:
                if idx == exploded:
                    text = "💥"
                elif idx in revealed:
                    text = "💎"
                elif field and field[idx]:
                    text = "💣"
                else:
                    text = "💎"
                buttons.append(InlineKeyboardButton(
                    text=text, callback_data="mines_noop"
                ))
            elif idx in revealed:
                buttons.append(InlineKeyboardButton(
                    text="💎", callback_data="mines_noop"
                ))
            else:
                buttons.append(InlineKeyboardButton(
                    text="⬜", callback_data=f"mines_open:{idx}"
                ))
        rows.append(buttons)

    if not game_over and state:
        # Кнопка забрать
        diamonds = len(revealed)
        mult = round(MINES_DIAMOND_MULTIPLIER ** diamonds, 2)
        win = int(state["bet"] * mult)
        rows.append([
            InlineKeyboardButton(
                text=f"💰 Забрать {format_winds(win)} (x{mult})",
                callback_data="mines_cashout",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("мины", "mines"))
async def cmd_mines(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if tg_id in _active_mines:
        return await message.answer("❌ У тебя уже есть активная игра в мины!")

    if not command.args:
        return await message.answer(
            "💣 <b>Мины</b>\n\n"
            "Поле 5×5. Открывай ячейки — ищи 💎!\n"
            "Каждый алмаз → x1.25 (множители перемножаются).\n"
            "Наступил на 💣 → потеря ставки.\n"
            "Можно забрать выигрыш в любой момент.\n\n"
            "Использование: <code>/мины 500 3</code>\n"
            "(500 виндов, 3 мины на поле)"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и кол-во мин.\n"
            "Пример: <code>/мины 500 3</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    try:
        num_mines = int(parts[1])
    except ValueError:
        return await message.answer("❌ Кол-во мин — число от 1 до 24.")

    if num_mines < 1 or num_mines > 24:
        return await message.answer("❌ Кол-во мин: от 1 до 24.")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    field = generate_field(num_mines)

    _active_mines[tg_id] = {
        "field": field,
        "bet": amount,
        "num_mines": num_mines,
        "revealed": set(),
    }

    kb = build_keyboard(tg_id, set())

    await message.answer(
        f"💣 <b>Мины</b> ({num_mines} мин)\n"
        f"💰 Ставка: {format_winds(amount)}\n"
        f"Открывай ячейки! 💎 = x{MINES_DIAMOND_MULTIPLIER}",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("mines_open:"))
async def cb_mines_open(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    state = _active_mines.get(tg_id)

    if not state:
        return await callback.answer("❌ Нет активной игры.", show_alert=True)

    idx = int(callback.data.split(":")[1])

    if idx in state["revealed"]:
        return await callback.answer("Уже открыто!")

    field = state["field"]

    if field[idx]:
        # БАБАХ! Мина!
        del _active_mines[tg_id]
        kb = build_keyboard(tg_id, state["revealed"], game_over=True, exploded=idx)

        # Восстанавливаем state для отрисовки
        _active_mines[tg_id] = state
        kb = build_keyboard(tg_id, state["revealed"], game_over=True, exploded=idx)
        del _active_mines[tg_id]

        await record_game(tg_id, "mines", state["bet"], 0)

        await callback.message.edit_text(
            f"💥 <b>БАБАХ! Мина!</b>\n\n"
            f"💸 -{format_winds(state['bet'])}\n"
            f"📊 Открыто алмазов: {len(state['revealed'])}",
            reply_markup=kb,
        )
        return await callback.answer("💥 Мина!", show_alert=True)

    # Алмаз!
    state["revealed"].add(idx)
    diamonds = len(state["revealed"])
    mult = round(MINES_DIAMOND_MULTIPLIER ** diamonds, 2)
    max_diamonds = GRID_TOTAL - state["num_mines"]

    if diamonds >= max_diamonds:
        # Все алмазы найдены — авто-кэшаут
        win_amount = int(state["bet"] * mult)
        del _active_mines[tg_id]

        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "mines", state["bet"], win_amount)

        await callback.message.edit_text(
            f"💎 <b>ВСЕ АЛМАЗЫ НАЙДЕНЫ!</b>\n\n"
            f"🎉 Множитель: x{mult}\n"
            f"💰 +{format_winds(win_amount - state['bet'])}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
        return await callback.answer("💎 Все найдены!", show_alert=True)

    kb = build_keyboard(tg_id, state["revealed"])
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(f"💎 Алмаз! x{mult}")


@router.callback_query(F.data == "mines_cashout")
async def cb_mines_cashout(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    state = _active_mines.get(tg_id)

    if not state:
        return await callback.answer("❌ Нет активной игры.", show_alert=True)

    diamonds = len(state["revealed"])
    if diamonds == 0:
        return await callback.answer("❌ Открой хотя бы одну ячейку!", show_alert=True)

    mult = round(MINES_DIAMOND_MULTIPLIER ** diamonds, 2)
    win_amount = int(state["bet"] * mult)

    del _active_mines[tg_id]

    new_balance = await credit_winnings(tg_id, win_amount)
    await record_game(tg_id, "mines", state["bet"], win_amount)
    profit = win_amount - state["bet"]

    await callback.message.edit_text(
        f"💰 <b>Забрал выигрыш!</b>\n\n"
        f"💎 Алмазов: {diamonds}\n"
        f"📈 Множитель: x{mult}\n"
        f"💰 +{format_winds(profit)}\n"
        f"📊 Баланс: {format_winds(new_balance)}"
    )
    await callback.answer("💰 Выигрыш забран!")


@router.callback_query(F.data == "mines_noop")
async def cb_mines_noop(callback: CallbackQuery) -> None:
    await callback.answer()