"""
Сервис VIP.
Покупка VIP-статуса за G-коины.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from database.collections import USERS
from database.firestore_client import db_client
from utils.constants import VIP_COST_GCOINS
from utils.helpers import format_gcoins

MSK = pytz.timezone("Europe/Moscow")


async def buy_vip(telegram_id: int, days: int = 30) -> dict:
    """
    Покупка VIP на N дней.
    Стоимость: 250 G-коинов за 30 дней.
    """
    if days <= 0:
        return {"ok": False, "error": "Количество дней должно быть > 0."}

    cost = VIP_COST_GCOINS * (days // 30) if days >= 30 else VIP_COST_GCOINS
    if days < 30:
        days = 30  # Минимум 30 дней

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован."}

        user = user_snap.to_dict()
        gcoins = user.get("gcoins_balance", 0)

        if gcoins < cost:
            return {
                "ok": False,
                "error": f"Недостаточно G-коинов.\nНужно: {format_gcoins(cost)}\nУ тебя: {format_gcoins(gcoins)}",
            }

        now = datetime.now(MSK)

        # Если уже VIP — продлеваем
        current_expires = user.get("vip_expires_at")
        if current_expires and user.get("is_vip"):
            try:
                # Парсим ISO строку
                if isinstance(current_expires, str):
                    expires_dt = datetime.fromisoformat(current_expires.replace("Z", "+00:00"))
                else:
                    expires_dt = current_expires
                if expires_dt > now:
                    new_expires = expires_dt + timedelta(days=days)
                else:
                    new_expires = now + timedelta(days=days)
            except:
                new_expires = now + timedelta(days=days)
        else:
            new_expires = now + timedelta(days=days)

        transaction.update(user_ref, {
            "gcoins_balance": gcoins - cost,
            "is_vip": True,
            "vip_expires_at": new_expires.isoformat(),
        })

        return {
            "ok": True,
            "cost": cost,
            "days": days,
            "expires_at": new_expires.isoformat(),
            "new_gcoins": gcoins - cost,
        }

    return await db_client.run_transaction(_execute)


async def check_vip_status(telegram_id: int) -> dict:
    """Проверить VIP-статус пользователя."""
    user = await db_client.get_doc(USERS, str(telegram_id))
    if not user:
        return {"is_vip": False}

    if not user.get("is_vip"):
        return {"is_vip": False}

    expires_str = user.get("vip_expires_at")
    if not expires_str:
        return {"is_vip": True, "expires_at": None, "days_left": None}

    try:
        if isinstance(expires_str, str):
            expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        else:
            expires_dt = expires_str

        now = datetime.now(MSK)
        if expires_dt.tzinfo is None:
            expires_dt = MSK.localize(expires_dt)

        if expires_dt < now:
            # VIP истёк — снимаем статус
            await db_client.update_doc(USERS, str(telegram_id), {
                "is_vip": False,
            })
            return {"is_vip": False, "expired": True}

        days_left = (expires_dt - now).days
        return {
            "is_vip": True,
            "expires_at": expires_dt.strftime("%d.%m.%Y"),
            "days_left": days_left,
        }
    except:
        return {"is_vip": True, "expires_at": None, "days_left": None}