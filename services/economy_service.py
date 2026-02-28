"""
Сервис экономики.
Переводы виндов (атомарные транзакции), покупка уровней,
информация о балансе и лимитах.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from database.collections import USERS
from database.firestore_client import db_client
from utils.constants import LEVEL_CONFIG, MAX_LEVEL
from utils.helpers import format_limit, format_winds

MSK = pytz.timezone("Europe/Moscow")


def _today_msk() -> str:
    """Текущая дата в формате YYYY-MM-DD по МСК."""
    return datetime.now(MSK).strftime("%Y-%m-%d")


# ═══════════════════ Информация о балансе ═════════════════════


async def get_balance_info(telegram_id: int) -> dict | None:
    """
    Полная информация о балансе и лимитах.
    Возвращает None если пользователь не найден.
    """
    doc = await db_client.get_doc(USERS, str(telegram_id))
    if doc is None:
        return None

    today = _today_msk()
    level = doc.get("level", 1)
    limit = LEVEL_CONFIG[level]["transfer_limit"]

    # Lazy-reset: если дата сброса < сегодня, считаем использованное = 0
    used = doc.get("daily_transfer_used", 0)
    if doc.get("last_transfer_reset", "") < today:
        used = 0

    if limit == -1:
        remaining = -1
    else:
        remaining = max(0, limit - used)

    return {
        "winds_balance": doc.get("winds_balance", 0),
        "gcoins_balance": doc.get("gcoins_balance", 0),
        "level": level,
        "transfer_limit": limit,
        "transfer_used": used,
        "transfer_remaining": remaining,
        "is_vip": doc.get("is_vip", False),
        "vip_expires_at": doc.get("vip_expires_at"),
        "country_id": doc.get("country_id"),
    }


async def get_level_info(telegram_id: int) -> dict | None:
    """Информация о текущем и следующем уровне."""
    doc = await db_client.get_doc(USERS, str(telegram_id))
    if doc is None:
        return None

    today = _today_msk()
    level = doc.get("level", 1)
    limit = LEVEL_CONFIG[level]["transfer_limit"]

    used = doc.get("daily_transfer_used", 0)
    if doc.get("last_transfer_reset", "") < today:
        used = 0

    info = {
        "level": level,
        "limit": limit,
        "used": used,
        "balance": doc.get("winds_balance", 0),
        "is_max": level >= MAX_LEVEL,
    }

    if level < MAX_LEVEL:
        next_lvl = level + 1
        next_cfg = LEVEL_CONFIG[next_lvl]
        info["next_level"] = next_lvl
        info["next_cost"] = next_cfg["cost"]
        info["next_limit"] = next_cfg["transfer_limit"]
        info["can_afford"] = doc.get("winds_balance", 0) >= next_cfg["cost"]

    return info


# ═══════════════════ Перевод виндов ═══════════════════════════


async def transfer_winds(
    sender_tg_id: int,
    receiver_tg_id: int,
    amount: int,
) -> dict:
    """
    Атомарный перевод виндов через Firestore-транзакцию.

    Проверяет:
      • Существование обоих игроков
      • Достаточность баланса отправителя
      • Дневной лимит переводов (с lazy-reset)

    Возвращает:
      {"ok": True, "new_sender_balance": ..., "new_receiver_balance": ...}
      или
      {"ok": False, "error": "текст ошибки"}
    """
    if sender_tg_id == receiver_tg_id:
        return {"ok": False, "error": "Нельзя переводить самому себе."}

    if amount <= 0:
        return {"ok": False, "error": "Сумма должна быть больше 0."}

    today = _today_msk()

    def _execute(transaction, db):
        sender_ref = db.collection(USERS).document(str(sender_tg_id))
        receiver_ref = db.collection(USERS).document(str(receiver_tg_id))

        sender_snap = sender_ref.get(transaction=transaction)
        if not sender_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован. Напиши /start."}

        receiver_snap = receiver_ref.get(transaction=transaction)
        if not receiver_snap.exists:
            return {
                "ok": False,
                "error": "Получатель не найден. Он должен написать /start боту.",
            }

        sender = sender_snap.to_dict()
        receiver = receiver_snap.to_dict()

        # ── Баланс ──
        sender_balance = sender.get("winds_balance", 0)
        if sender_balance < amount:
            return {
                "ok": False,
                "error": (
                    f"Недостаточно виндов.\n"
                    f"Баланс: {format_winds(sender_balance)}"
                ),
            }

        # ── Лимит переводов (lazy reset) ──
        used = sender.get("daily_transfer_used", 0)
        if sender.get("last_transfer_reset", "") < today:
            used = 0  # Новый день — сбрасываем

        level = sender.get("level", 1)
        limit = LEVEL_CONFIG[level]["transfer_limit"]

        if limit != -1:
            remaining = limit - used
            if amount > remaining:
                return {
                    "ok": False,
                    "error": (
                        f"Превышен дневной лимит переводов.\n"
                        f"Осталось: {format_winds(max(0, remaining))} "
                        f"из {format_limit(limit)}\n"
                        f"Повысь уровень: /level"
                    ),
                }

        # ── Выполняем перевод ──
        new_sender_balance = sender_balance - amount
        new_receiver_balance = receiver.get("winds_balance", 0) + amount
        new_used = used + amount

        transaction.update(sender_ref, {
            "winds_balance": new_sender_balance,
            "daily_transfer_used": new_used,
            "last_transfer_reset": today,
        })
        transaction.update(receiver_ref, {
            "winds_balance": new_receiver_balance,
        })

        return {
            "ok": True,
            "new_sender_balance": new_sender_balance,
            "new_receiver_balance": new_receiver_balance,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Покупка уровня ═══════════════════════════


async def buy_next_level(telegram_id: int) -> dict:
    """
    Атомарная покупка следующего уровня.

    Возвращает:
      {"ok": True, "new_level": ..., "cost": ...,
       "new_balance": ..., "new_limit": ...}
      или
      {"ok": False, "error": "текст ошибки"}
    """

    def _execute(transaction, db):
        ref = db.collection(USERS).document(str(telegram_id))
        snap = ref.get(transaction=transaction)

        if not snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован. Напиши /start."}

        user = snap.to_dict()
        current_level = user.get("level", 1)

        if current_level >= MAX_LEVEL:
            return {"ok": False, "error": "У тебя уже максимальный уровень! 🏆"}

        next_level = current_level + 1
        cost = LEVEL_CONFIG[next_level]["cost"]
        balance = user.get("winds_balance", 0)

        if balance < cost:
            return {
                "ok": False,
                "error": (
                    f"Недостаточно виндов.\n"
                    f"Нужно: {format_winds(cost)}\n"
                    f"У тебя: {format_winds(balance)}"
                ),
            }

        new_balance = balance - cost
        new_limit = LEVEL_CONFIG[next_level]["transfer_limit"]

        transaction.update(ref, {
            "winds_balance": new_balance,
            "level": next_level,
        })

        return {
            "ok": True,
            "new_level": next_level,
            "cost": cost,
            "new_balance": new_balance,
            "new_limit": new_limit,
        }

    return await db_client.run_transaction(_execute)