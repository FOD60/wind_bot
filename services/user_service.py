"""
Сервис пользователей.
Регистрация, поиск, обновление профиля.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from database.collections import USERS
from database.firestore_client import db_client
from database.models import UserModel


async def get_user(telegram_id: int) -> Optional[dict]:
    """Получить данные пользователя или None."""
    return await db_client.get_doc(USERS, str(telegram_id))


async def get_or_create_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> dict:
    """
    Получить пользователя. Если не существует — создать.
    Если существует — обновить username/first_name (они могут меняться).
    """
    doc = await db_client.get_doc(USERS, str(telegram_id))

    if doc is None:
        user = UserModel.new(telegram_id, username, first_name)
        data = user.to_dict()
        await db_client.set_doc(USERS, str(telegram_id), data)
        return data

    # Обновить username/first_name если изменились
    updates = {}
    if username and doc.get("username") != username:
        updates["username"] = username
    if first_name and doc.get("first_name") != first_name:
        updates["first_name"] = first_name
    if updates:
        updates["updated_at"] = datetime.utcnow().isoformat()
        await db_client.update_doc(USERS, str(telegram_id), updates)
        doc.update(updates)

    return doc


async def find_by_username(username: str) -> Optional[dict]:
    """Найти пользователя по Telegram username (без @)."""
    results = await db_client.query(
        USERS,
        filters=[("username", "==", username)],
        limit=1,
    )
    if results:
        doc_id, data = results[0]
        data["_id"] = doc_id
        return data
    return None