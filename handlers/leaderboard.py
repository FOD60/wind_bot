"""
Хендлер лидерборда: /top (/топ).
Показывает топ-10 игроков по выигрышам за сегодня.
"""
from __future__ import annotations

from datetime import datetime

import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.leaderboard_service import get_daily_top, get_user_position
from services.user_service import get_or_create_user
from utils.constants import LEADERBOARD_REWARDS
from utils.helpers import display_name, format_number, format_winds

router = Router()

MSK = pytz.timezone("Europe/Moscow")

RANK_EMOJI = {
    1: "🥇",
    2: "🥈",
    3: "🥉",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}


@router.message(Command("top", "топ", "leaderboard"))
async def cmd_top(message: Message) -> None:
    """Ежедневный лидерборд по выигрышам."""
    tg_id = message.from_user.id
    await get_or_create_user(
        tg_id, message.from_user.username, message.from_user.first_name
    )

    today = datetime.now(MSK)
    date_str = today.strftime("%d.%m.%Y")

    top = await get_daily_top(limit=10)

    text = f"🏆 <b>Лидерборд дня</b>\n📅 {date_str}\n\n"

    if not top:
        text += "<i>Пока нет выигрышей сегодня.</i>\n"
    else:
        for rank, entry in enumerate(top, start=1):
            emoji = RANK_EMOJI.get(rank, f"{rank}.")
            name = display_name(entry)
            winnings = format_winds(entry["total_winnings"])

            # Подсветка наградных мест
            if rank <= len(LEADERBOARD_REWARDS):
                reward = format_winds(LEADERBOARD_REWARDS[rank - 1])
                line = f"{emoji} {name} — <b>{winnings}</b>  💰{reward}\n"
            else:
                line = f"{emoji} {name} — {winnings}\n"

            text += line

    # Позиция текущего игрока
    user_pos = await get_user_position(tg_id)
    text += "\n"

    if user_pos is None:
        text += "📊 Ты ещё не выигрывал(а) сегодня.\n"
    elif user_pos["rank"] is not None:
        text += (
            f"📊 Твоя позиция: <b>#{user_pos['rank']}</b> "
            f"({format_winds(user_pos['total_winnings'])})\n"
        )
    else:
        text += (
            f"📊 Ты: за пределами топ-100 "
            f"({format_winds(user_pos['total_winnings'])})\n"
        )

    # Призовые
    text += (
        f"\n💰 <b>Награды в 00:00 МСК:</b>\n"
    )
    for i, reward in enumerate(LEADERBOARD_REWARDS):
        emoji = RANK_EMOJI.get(i + 1, f"{i + 1}.")
        text += f"  {emoji} {format_winds(reward)}\n"

    text += "\n<i>Дуэль и Русская рулетка не учитываются.</i>"

    await message.answer(text)