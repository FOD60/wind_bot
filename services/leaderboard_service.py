"""
Сервис лидерборда.
Запись выигрышей, получение топа дня.
Выигрыши в Дуэли и Русской рулетке НЕ учитываются.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytz

from database.collections import DAILY_WINNINGS, USERS
from database.firestore_client import db_client
from database.firebase_init import get_db
from utils.constants import LEADERBOARD_EXCLUDED_GAMES

MSK = pytz.timezone("Europe/Moscow")


def _today_msk() -> str:
    return datetime.now(MSK).strftime("%Y-%m-%d")


async def record_winning(
    telegram_id: int,
    game_type: str,
    win_amount: int,
) -> None:
    """
    Записать выигрыш в ежедневный лидерборд.
    Вызывается из game_service после каждого выигрыша.

    Пропускает игры из LEADERBOARD_EXCLUDED_GAMES (дуэль, русская рулетка).
    """
    if game_type in LEADERBOARD_EXCLUDED_GAMES:
        return

    if win_amount <= 0:
        return

    today = _today_msk()
    doc_id = f"{telegram_id}_{today}"

    # Шаг 1: гарантируем существование документа (merge не перезапишет total_winnings)
    await db_client.set_doc(
        DAILY_WINNINGS,
        doc_id,
        {
            "user_telegram_id": telegram_id,
            "date": today,
        },
        merge=True,
    )

    # Шаг 2: атомарный инкремент
    await db_client.increment_field(
        DAILY_WINNINGS, doc_id, "total_winnings", win_amount
    )


async def get_daily_top(
    limit: int = 10,
) -> list[dict]:
    """
    Получить топ игроков за сегодня.

    Возвращает список словарей:
      [{"telegram_id": ..., "total_winnings": ...,
        "username": ..., "first_name": ...}, ...]

    ⚠️ Требуется СОСТАВНОЙ ИНДЕКС в Firestore:
       Коллекция: daily_winnings
       Поля: date ASC, total_winnings DESC
    """
    today = _today_msk()

    entries = await db_client.query(
        DAILY_WINNINGS,
        filters=[
            ("date", "==", today),
            ("total_winnings", ">", 0),
        ],
        order_by="total_winnings",
        direction="DESCENDING",
        limit=limit,
    )

    if not entries:
        return []

    # Подгружаем данные пользователей для отображения имён
    result = []
    for doc_id, data in entries:
        tg_id = data.get("user_telegram_id", 0)
        user = await db_client.get_doc(USERS, str(tg_id))

        result.append({
            "telegram_id": tg_id,
            "total_winnings": data.get("total_winnings", 0),
            "username": user.get("username") if user else None,
            "first_name": user.get("first_name") if user else None,
        })

    return result


async def get_user_position(telegram_id: int) -> dict | None:
    """
    Позиция пользователя в лидерборде сегодня.

    Возвращает {"rank": 7, "total_winnings": 98765} или None.
    Ранг считается среди топ-100. Если не попал — rank = None.
    """
    today = _today_msk()

    entries = await db_client.query(
        DAILY_WINNINGS,
        filters=[
            ("date", "==", today),
            ("total_winnings", ">", 0),
        ],
        order_by="total_winnings",
        direction="DESCENDING",
        limit=100,
    )

    for rank, (doc_id, data) in enumerate(entries, start=1):
        if data.get("user_telegram_id") == telegram_id:
            return {
                "rank": rank,
                "total_winnings": data.get("total_winnings", 0),
            }

    # Не в топ-100 — проверяем есть ли запись вообще
    doc_id = f"{telegram_id}_{today}"
    doc = await db_client.get_doc(DAILY_WINNINGS, doc_id)
    if doc and doc.get("total_winnings", 0) > 0:
        return {
            "rank": None,  # >100
            "total_winnings": doc["total_winnings"],
        }

    return None