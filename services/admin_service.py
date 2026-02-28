"""
Сервис админ-панели.
Выдача валюты, баны, статистика.
"""
from __future__ import annotations

from database.collections import USERS
from database.firestore_client import db_client
from utils.helpers import format_gcoins, format_winds


async def change_balance(telegram_id: int, amount: int, currency: str = "winds") -> dict:
    """Изменить баланс пользователя (amount может быть отрицательным)."""
    field = "winds_balance" if currency == "winds" else "gcoins_balance"
    
    def _execute(transaction, db):
        ref = db.collection(USERS).document(str(telegram_id))
        snap = ref.get(transaction=transaction)
        
        if not snap.exists:
            return {"ok": False, "error": "Пользователь не найден."}
        
        user = snap.to_dict()
        current = user.get(field, 0)
        new_val = max(0, current + amount)  # Баланс не может быть меньше 0
        
        transaction.update(ref, {field: new_val})
        return {"ok": True, "new_balance": new_val}
        
    return await db_client.run_transaction(_execute)


async def set_ban_status(telegram_id: int, is_banned: bool) -> bool:
    """Забанить / разбанить пользователя."""
    doc = await db_client.get_doc(USERS, str(telegram_id))
    if not doc:
        return False
        
    await db_client.update_doc(USERS, str(telegram_id), {"is_banned": is_banned})
    return True


async def get_bot_stats() -> dict:
    """Глобальная статистика бота (кол-во пользователей, всего денег)."""
    # Внимание: для очень больших баз (100к+ юзеров) этот запрос лучше
    # переписать на агрегацию или счетчики, но для начала отлично подойдёт.
    users = await db_client.query(USERS)
    
    total_users = len(users)
    total_winds = sum(data.get("winds_balance", 0) for doc_id, data in users)
    total_gcoins = sum(data.get("gcoins_balance", 0) for doc_id, data in users)
    banned_users = sum(1 for doc_id, data in users if data.get("is_banned"))
    
    return {
        "users": total_users,
        "winds": total_winds,
        "gcoins": total_gcoins,
        "banned": banned_users,
        "all_user_ids": [int(doc_id) for doc_id, data in users],
    }