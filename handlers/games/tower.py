"""
🗼 Башня — 10 уровней по 5 ячеек.

Механика:
  Игрок выбирает кол-во бомб (1-4) на каждом уровне.
  На каждом уровне 5 ячеек, из них N бомб.
  Угадал безопасную → поднимается выше.
  Множитель за уровень = 5 / (5 - бомбы).
  Множители перемножаются.
  Можно забрать на любом уровне.

Команда: /башня <ставка> <кол-во бомб>
"""
from __future__ import annotations

import random

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
from utils.constants import TOWER_CELLS, TOWER_LEVELS, TOWER_MIN_BOMBS, TOWER_MAX_BOMBS
from utils.helpers import format_winds, parse_amount

router = Router()

_active_towers: dict[int, dict] = {}


def generate_tower_level(num_bombs: int) -> list[bool]:
    """True = бомба. 5 ячеек."""
    cells = [True] * num_bombs + [False] * (TOWER_CELLS - num_bombs)
    random.shuffle(cells)
    return cells


def level_multiplier(bombs: int) -> float:
    """Множитель за один уровень."""
    safe = TOWER_CELLS - bombs
    return round(TOWER_CELLS / safe, 2)


def total_multiplier(bombs: int, levels_passed: int) -> float:
    lm = level_multiplier(bombs)
    return round(lm ** levels_passed, 2)


def build_tower_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    state = _active_towers.get(tg_id, {})
    current_level = state.get("current_level", 0)
    bombs = state.get("bombs", 1)
    bet = state.get("bet", 0)

    rows = []

    # Текущий уровень — кнопки выбора ячейки
    level_cells = state.get("levels", {}).get(current_level, [])
    cell_buttons = []
    for i in range(TOWER_CELLS):
        cell_buttons.append(InlineKeyboardButton(
            text=f"🔲",
            callback_data=f"tower_pick:{i}",
        ))
    rows.append(cell_buttons)

    # Кнопка забрать (если хотя бы 1 уровень пройден)
    if current_level > 0:
        mult = total_multiplier(bombs, current_level)
        win = int(bet * mult)
        rows.append([InlineKeyboardButton(
            text=f"💰 Забрать {format_winds(win)} (x{mult})",
            callback_data="tower_cashout",
        )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("башня", "tower"))
async def cmd_tower(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if tg_id in _active_towers:
        return await message.answer("❌ У тебя уже есть активная башня!")

    if not command.args:
        return await message.answer(
            "🗼 <b>Башня</b>\n\n"
            f"10 уровней, по {TOWER_CELLS} ячеек.\n"
            f"Выбери кол-во бомб (1-4) — чем больше, тем выше множитель!\n\n"
            f"Множитель за уровень:\n"
            f"• 1 бомба: x{level_multiplier(1)}\n"
            f"• 2 бомбы: x{level_multiplier(2)}\n"
            f"• 3 бомбы: x{level_multiplier(3)}\n"
            f"• 4 бомбы: x{level_multiplier(4)}\n\n"
            f"Использование: <code>/башня 500 2</code>"
        )

    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ Укажи ставку и кол-во бомб.\n"
            "Пример: <code>/башня 500 2</code>"
        )

    amount = parse_amount(parts[0])
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    try:
        bombs = int(parts[1])
    except ValueError:
        return await message.answer(f"❌ Кол-во бомб — число от {TOWER_MIN_BOMBS} до {TOWER_MAX_BOMBS}.")

    if bombs < TOWER_MIN_BOMBS or bombs > TOWER_MAX_BOMBS:
        return await message.answer(f"❌ Кол-во бомб: от {TOWER_MIN_BOMBS} до {TOWER_MAX_BOMBS}.")

    bet_result = await validate_and_deduct_bet(tg_id, amount)
    if not bet_result["ok"]:
        return await message.answer(f"❌ {bet_result['error']}")

    # Генерируем все 10 уровней заранее
    levels = {}
    for lvl in range(TOWER_LEVELS):
        levels[lvl] = generate_tower_level(bombs)

    _active_towers[tg_id] = {
        "bet": amount,
        "bombs": bombs,
        "levels": levels,
        "current_level": 0,
    }

    lm = level_multiplier(bombs)
    kb = build_tower_keyboard(tg_id)

    await message.answer(
        f"🗼 <b>Башня</b> ({bombs} бомб, x{lm}/уровень)\n"
        f"💰 Ставка: {format_winds(amount)}\n"
        f"📊 Уровень: 1 / {TOWER_LEVELS}\n\n"
        f"Выбери безопасную ячейку!",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("tower_pick:"))
async def cb_tower_pick(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    state = _active_towers.get(tg_id)

    if not state:
        return await callback.answer("❌ Нет активной игры.", show_alert=True)

    cell_idx = int(callback.data.split(":")[1])
    current_level = state["current_level"]
    level_data = state["levels"][current_level]
    bombs = state["bombs"]
    bet = state["bet"]

    if level_data[cell_idx]:
        # БОМБА!
        del _active_towers[tg_id]
        await record_game(tg_id, "tower", bet, 0)

        # Показать весь уровень
        reveal = ""
        for i in range(TOWER_CELLS):
            if i == cell_idx:
                reveal += "💥 "
            elif level_data[i]:
                reveal += "💣 "
            else:
                reveal += "✅ "

        await callback.message.edit_text(
            f"🗼 Уровень {current_level + 1}\n"
            f"{reveal}\n\n"
            f"💥 <b>БОМБА! Башня рухнула!</b>\n"
            f"💸 -{format_winds(bet)}"
        )
        return await callback.answer("💥 Бомба!", show_alert=True)

    # Безопасно!
    state["current_level"] = current_level + 1
    passed = state["current_level"]
    mult = total_multiplier(bombs, passed)

    if passed >= TOWER_LEVELS:
        # Прошёл все 10 уровней!
        win_amount = int(bet * mult)
        del _active_towers[tg_id]

        new_balance = await credit_winnings(tg_id, win_amount)
        await record_game(tg_id, "tower", bet, win_amount)

        await callback.message.edit_text(
            f"🗼 <b>ВСЕ 10 УРОВНЕЙ ПРОЙДЕНЫ!</b> 🏆\n\n"
            f"📈 Множитель: x{mult}\n"
            f"💰 +{format_winds(win_amount - bet)}\n"
            f"📊 Баланс: {format_winds(new_balance)}"
        )
        return await callback.answer("🏆 Вершина!", show_alert=True)

    kb = build_tower_keyboard(tg_id)
    await callback.message.edit_text(
        f"🗼 <b>Башня</b> ({bombs} бомб)\n"
        f"✅ Безопасно! Уровень {passed + 1} / {TOWER_LEVELS}\n"
        f"📈 Текущий множитель: x{mult}\n"
        f"💰 Возможный выигрыш: {format_winds(int(bet * mult))}\n\n"
        f"Выбери ячейку или забери!",
        reply_markup=kb,
    )
    await callback.answer(f"✅ x{mult}")


@router.callback_query(F.data == "tower_cashout")
async def cb_tower_cashout(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    state = _active_towers.get(tg_id)

    if not state:
        return await callback.answer("❌ Нет активной игры.", show_alert=True)

    passed = state["current_level"]
    if passed == 0:
        return await callback.answer("❌ Пройди хотя бы один уровень!", show_alert=True)

    bombs = state["bombs"]
    bet = state["bet"]
    mult = total_multiplier(bombs, passed)
    win_amount = int(bet * mult)

    del _active_towers[tg_id]

    new_balance = await credit_winnings(tg_id, win_amount)
    await record_game(tg_id, "tower", bet, win_amount)
    profit = win_amount - bet

    await callback.message.edit_text(
        f"🗼 <b>Забрал на уровне {passed}!</b>\n\n"
        f"📈 Множитель: x{mult}\n"
        f"💰 +{format_winds(profit)}\n"
        f"📊 Баланс: {format_winds(new_balance)}"
    )
    await callback.answer("💰 Забрал!")