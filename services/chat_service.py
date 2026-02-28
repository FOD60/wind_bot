"""
Сервис чатов.
Регистрация, настройки, статистика групп.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from database.collections import CHATS
from database.firestore_client import db_client
from database.models import ChatModel

MSK = pytz.timezone("Europe/Moscow")


async def get_chat(chat_id: int) -> Optional[dict]:
    """Получить данные чата."""
    return await db_client.get_doc(CHATS, str(chat_id))


async def get_or_create_chat(
    chat_id: int,
    title: str = None,
    chat_type: str = "group",
) -> dict:
    """Получить или создать чат."""
    doc = await db_client.get_doc(CHATS, str(chat_id))

    if doc is None:
        chat = ChatModel.new(chat_id, title, chat_type)
        data = chat.to_dict()
        await db_client.set_doc(CHATS, str(chat_id), data)
        return data

    # Обновляем title если изменился
    if title and doc.get("title") != title:
        await db_client.update_doc(CHATS, str(chat_id), {
            "title": title,
            "updated_at": datetime.now(MSK).isoformat(),
        })
        doc["title"] = title

    return doc


async def update_chat_settings(
    chat_id: int,
    games_enabled: bool = None,
    transfers_enabled: bool = None,
    min_bet: int = None,
) -> dict:
    """Обновить настройки чата."""
    updates = {"updated_at": datetime.now(MSK).isoformat()}

    if games_enabled is not None:
        updates["games_enabled"] = games_enabled
    if transfers_enabled is not None:
        updates["transfers_enabled"] = transfers_enabled
    if min_bet is not None:
        updates["min_bet"] = min_bet

    await db_client.update_doc(CHATS, str(chat_id), updates)
    return {"ok": True}


async def increment_chat_stats(chat_id: int, games: int = 0, volume: int = 0) -> None:
    """Увеличить статистику чата."""
    if games > 0:
        await db_client.increment_field(CHATS, str(chat_id), "total_games", games)
    if volume > 0:
        await db_client.increment_field(CHATS, str(chat_id), "total_volume", volume)


async def get_chat_stats(chat_id: int) -> dict:
    """Получить статистику чата."""
    doc = await db_client.get_doc(CHATS, str(chat_id))
    if not doc:
        return {"total_games": 0, "total_volume": 0}
    return {
        "total_games": doc.get("total_games", 0),
        "total_volume": doc.get("total_volume", 0),
    }