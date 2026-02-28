"""
Сервис браков.
Создание, развод, усыновление, изгнание,
бюджет, уровень, ежедневная награда.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pytz

from database.collections import MARRIAGES, MARRIAGE_CHILDREN, USERS
from database.firestore_client import db_client
from database.models import MarriageModel, MarriageChildModel
from utils.constants import (
    MARRIAGE_ADOPT_COST,
    MARRIAGE_CREATION_COST,
    MARRIAGE_DIVORCE_COST,
    MARRIAGE_LEVELS,
    MARRIAGE_MAX_CHILDREN,
    MARRIAGE_MAX_LEVEL,
)
from utils.helpers import format_winds

MSK = pytz.timezone("Europe/Moscow")


def _today_msk() -> str:
    return datetime.now(MSK).strftime("%Y-%m-%d")


# ═══════════════════ Получение информации ═════════════════════


async def get_user_marriage(telegram_id: int) -> Optional[tuple[str, dict]]:
    """Возвращает (doc_id, data) активного брака пользователя или None."""
    # Проверяем как partner1
    results = await db_client.query(
        MARRIAGES,
        filters=[
            ("partner1_telegram_id", "==", telegram_id),
            ("is_active", "==", True),
        ],
        limit=1,
    )
    if results:
        return results[0]

    # Проверяем как partner2
    results = await db_client.query(
        MARRIAGES,
        filters=[
            ("partner2_telegram_id", "==", telegram_id),
            ("is_active", "==", True),
        ],
        limit=1,
    )
    if results:
        return results[0]

    return None


async def get_marriage_children(marriage_id: str) -> list[dict]:
    """Список детей в браке."""
    results = await db_client.query(
        MARRIAGE_CHILDREN,
        filters=[("marriage_id", "==", marriage_id)],
    )
    children = []
    for doc_id, data in results:
        child_tg_id = data.get("child_telegram_id")
        child_user = await db_client.get_doc(USERS, str(child_tg_id))
        children.append({
            "doc_id": doc_id,
            "telegram_id": child_tg_id,
            "user": child_user,
            "adopted_at": data.get("adopted_at", ""),
        })
    return children


async def is_user_child(telegram_id: int) -> bool:
    """Проверяет, усыновлён ли пользователь."""
    results = await db_client.query(
        MARRIAGE_CHILDREN,
        filters=[("child_telegram_id", "==", telegram_id)],
        limit=1,
    )
    return len(results) > 0


async def get_marriage_info(telegram_id: int) -> Optional[dict]:
    """Полная информация о браке пользователя."""
    marriage_data = await get_user_marriage(telegram_id)
    if not marriage_data:
        return None

    doc_id, data = marriage_data

    p1_tg_id = data.get("partner1_telegram_id")
    p2_tg_id = data.get("partner2_telegram_id")

    partner1 = await db_client.get_doc(USERS, str(p1_tg_id))
    partner2 = await db_client.get_doc(USERS, str(p2_tg_id))

    children = await get_marriage_children(doc_id)

    level = data.get("level", 1)
    daily_reward = MARRIAGE_LEVELS[level]["daily_reward"]

    # Проверяем lazy reset награды
    today = _today_msk()
    can_claim = not data.get("daily_reward_claimed", False)
    if data.get("last_reward_reset", "") < today:
        can_claim = True

    return {
        "marriage_id": doc_id,
        "partner1": partner1,
        "partner2": partner2,
        "partner1_tg_id": p1_tg_id,
        "partner2_tg_id": p2_tg_id,
        "budget": data.get("budget_winds", 0),
        "level": level,
        "daily_reward": daily_reward,
        "can_claim_reward": can_claim,
        "children": children,
        "created_at": data.get("created_at", ""),
    }


# ═══════════════════ Создание брака ═══════════════════════════


async def propose_marriage(proposer_tg_id: int, target_tg_id: int) -> dict:
    """
    Предложение брака. Стоимость делится пополам.
    Оба должны быть свободны от брака.
    """
    if proposer_tg_id == target_tg_id:
        return {"ok": False, "error": "Нельзя жениться на себе! 😅"}

    cost_each = MARRIAGE_CREATION_COST // 2

    def _execute(transaction, db):
        p1_ref = db.collection(USERS).document(str(proposer_tg_id))
        p2_ref = db.collection(USERS).document(str(target_tg_id))

        p1_snap = p1_ref.get(transaction=transaction)
        p2_snap = p2_ref.get(transaction=transaction)

        if not p1_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован."}
        if not p2_snap.exists:
            return {"ok": False, "error": "Партнёр не зарегистрирован."}

        p1 = p1_snap.to_dict()
        p2 = p2_snap.to_dict()

        # Проверяем балансы
        if p1.get("winds_balance", 0) < cost_each:
            return {"ok": False, "error": f"Тебе не хватает {format_winds(cost_each)}."}
        if p2.get("winds_balance", 0) < cost_each:
            return {"ok": False, "error": f"Партнёру не хватает {format_winds(cost_each)}."}

        # Создаём брак
        marriage_ref = db.collection(MARRIAGES).document()
        marriage = MarriageModel.new(proposer_tg_id, target_tg_id)
        transaction.set(marriage_ref, marriage.to_dict())

        # Списываем с обоих
        transaction.update(p1_ref, {
            "winds_balance": p1["winds_balance"] - cost_each
        })
        transaction.update(p2_ref, {
            "winds_balance": p2["winds_balance"] - cost_each
        })

        return {
            "ok": True,
            "marriage_id": marriage_ref.id,
            "cost_each": cost_each,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Развод ═══════════════════════════════════


async def divorce(telegram_id: int) -> dict:
    """Развод. Бюджет делится пополам. Дети освобождаются."""
    marriage_data = await get_user_marriage(telegram_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, data = marriage_data
    p1_tg_id = data.get("partner1_telegram_id")
    p2_tg_id = data.get("partner2_telegram_id")
    budget = data.get("budget_winds", 0)

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        if user.get("winds_balance", 0) < MARRIAGE_DIVORCE_COST:
            return {"ok": False, "error": f"Нужно {format_winds(MARRIAGE_DIVORCE_COST)} на развод."}

        # Списываем стоимость развода
        transaction.update(user_ref, {
            "winds_balance": user["winds_balance"] - MARRIAGE_DIVORCE_COST
        })

        # Делим бюджет
        half = budget // 2
        if half > 0:
            p1_ref = db.collection(USERS).document(str(p1_tg_id))
            p2_ref = db.collection(USERS).document(str(p2_tg_id))

            p1_snap = p1_ref.get(transaction=transaction)
            p2_snap = p2_ref.get(transaction=transaction)

            if p1_snap.exists:
                transaction.update(p1_ref, {
                    "winds_balance": p1_snap.to_dict().get("winds_balance", 0) + half
                })
            if p2_snap.exists:
                transaction.update(p2_ref, {
                    "winds_balance": p2_snap.to_dict().get("winds_balance", 0) + half
                })

        # Деактивируем брак
        marriage_ref = db.collection(MARRIAGES).document(doc_id)
        transaction.update(marriage_ref, {"is_active": False})

        return {"ok": True, "budget_split": half}

    result = await db_client.run_transaction(_execute)

    if result.get("ok"):
        # Удаляем записи детей
        children = await get_marriage_children(doc_id)
        for child in children:
            await db_client.delete_doc(MARRIAGE_CHILDREN, child["doc_id"])

    return result


# ═══════════════════ Усыновление ══════════════════════════════


async def adopt_child(parent_tg_id: int, child_tg_id: int) -> dict:
    """Усыновить игрока в семью."""
    if parent_tg_id == child_tg_id:
        return {"ok": False, "error": "Нельзя усыновить себя!"}

    marriage_data = await get_user_marriage(parent_tg_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, data = marriage_data
    p1_tg_id = data.get("partner1_telegram_id")
    p2_tg_id = data.get("partner2_telegram_id")

    if child_tg_id in (p1_tg_id, p2_tg_id):
        return {"ok": False, "error": "Нельзя усыновить партнёра!"}

    # Проверяем, не усыновлён ли уже
    if await is_user_child(child_tg_id):
        return {"ok": False, "error": "Этот игрок уже усыновлён в другой семье."}

    # Проверяем лимит детей
    children = await get_marriage_children(doc_id)
    if len(children) >= MARRIAGE_MAX_CHILDREN:
        return {"ok": False, "error": f"Максимум {MARRIAGE_MAX_CHILDREN} детей в семье."}

    # Проверяем, что ребёнок не в браке
    child_marriage = await get_user_marriage(child_tg_id)
    if child_marriage:
        return {"ok": False, "error": "Нельзя усыновить человека в браке."}

    def _execute(transaction, db):
        parent_ref = db.collection(USERS).document(str(parent_tg_id))
        child_ref = db.collection(USERS).document(str(child_tg_id))

        parent_snap = parent_ref.get(transaction=transaction)
        child_snap = child_ref.get(transaction=transaction)

        if not parent_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован."}
        if not child_snap.exists:
            return {"ok": False, "error": "Ребёнок не зарегистрирован."}

        parent = parent_snap.to_dict()
        if parent.get("winds_balance", 0) < MARRIAGE_ADOPT_COST:
            return {"ok": False, "error": f"Нужно {format_winds(MARRIAGE_ADOPT_COST)}."}

        # Списываем
        transaction.update(parent_ref, {
            "winds_balance": parent["winds_balance"] - MARRIAGE_ADOPT_COST
        })

        # Создаём запись ребёнка
        child_doc_ref = db.collection(MARRIAGE_CHILDREN).document()
        transaction.set(child_doc_ref, {
            "marriage_id": doc_id,
            "child_telegram_id": child_tg_id,
            "adopted_at": datetime.now(MSK).isoformat(),
        })

        return {"ok": True}

    return await db_client.run_transaction(_execute)


async def kick_child(parent_tg_id: int, child_tg_id: int) -> dict:
    """Изгнать ребёнка из семьи."""
    marriage_data = await get_user_marriage(parent_tg_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, _ = marriage_data

    children = await get_marriage_children(doc_id)
    target_child = None
    for c in children:
        if c["telegram_id"] == child_tg_id:
            target_child = c
            break

    if not target_child:
        return {"ok": False, "error": "Этот игрок не ваш ребёнок."}

    await db_client.delete_doc(MARRIAGE_CHILDREN, target_child["doc_id"])
    return {"ok": True}


# ═══════════════════ Бюджет семьи ═════════════════════════════


async def deposit_to_family(telegram_id: int, amount: int) -> dict:
    """Внести в семейный бюджет."""
    if amount <= 0:
        return {"ok": False, "error": "Сумма должна быть > 0."}

    marriage_data = await get_user_marriage(telegram_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, data = marriage_data

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        marriage_ref = db.collection(MARRIAGES).document(doc_id)

        user_snap = user_ref.get(transaction=transaction)
        marriage_snap = marriage_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        marriage = marriage_snap.to_dict()

        if user.get("winds_balance", 0) < amount:
            return {"ok": False, "error": f"Недостаточно виндов."}

        new_balance = user["winds_balance"] - amount
        new_budget = marriage.get("budget_winds", 0) + amount

        transaction.update(user_ref, {"winds_balance": new_balance})
        transaction.update(marriage_ref, {"budget_winds": new_budget})

        return {"ok": True, "new_balance": new_balance, "new_budget": new_budget}

    return await db_client.run_transaction(_execute)


# ═══════════════════ Уровень брака ════════════════════════════


async def upgrade_marriage(telegram_id: int) -> dict:
    """Повысить уровень брака (из семейного бюджета)."""
    marriage_data = await get_user_marriage(telegram_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, data = marriage_data
    current_level = data.get("level", 1)

    if current_level >= MARRIAGE_MAX_LEVEL:
        return {"ok": False, "error": "Уже максимальный уровень! 💍"}

    next_level = current_level + 1
    cost = MARRIAGE_LEVELS[next_level]["cost"]
    budget = data.get("budget_winds", 0)

    if budget < cost:
        return {"ok": False, "error": f"В семейном бюджете не хватает.\nНужно: {format_winds(cost)}\nБюджет: {format_winds(budget)}"}

    new_budget = budget - cost
    new_reward = MARRIAGE_LEVELS[next_level]["daily_reward"]

    await db_client.update_doc(MARRIAGES, doc_id, {
        "level": next_level,
        "budget_winds": new_budget,
    })

    return {
        "ok": True,
        "new_level": next_level,
        "cost": cost,
        "new_budget": new_budget,
        "new_reward": new_reward,
    }


# ═══════════════════ Ежедневная награда ═══════════════════════


async def claim_daily_reward(telegram_id: int) -> dict:
    """Забрать ежедневную награду (делится поровну между партнёрами)."""
    marriage_data = await get_user_marriage(telegram_id)
    if not marriage_data:
        return {"ok": False, "error": "Ты не в браке."}

    doc_id, data = marriage_data
    today = _today_msk()

    # Lazy reset
    if data.get("last_reward_reset", "") < today:
        await db_client.update_doc(MARRIAGES, doc_id, {
            "daily_reward_claimed": False,
            "last_reward_reset": today,
        })
        data["daily_reward_claimed"] = False

    if data.get("daily_reward_claimed", False):
        return {"ok": False, "error": "Награда уже получена сегодня!"}

    level = data.get("level", 1)
    total_reward = MARRIAGE_LEVELS[level]["daily_reward"]
    half = total_reward // 2

    p1_tg_id = data.get("partner1_telegram_id")
    p2_tg_id = data.get("partner2_telegram_id")

    # Начисляем обоим
    await db_client.increment_field(USERS, str(p1_tg_id), "winds_balance", half)
    await db_client.increment_field(USERS, str(p2_tg_id), "winds_balance", half)

    # Отмечаем как полученную
    await db_client.update_doc(MARRIAGES, doc_id, {
        "daily_reward_claimed": True,
        "last_reward_reset": today,
    })

    return {
        "ok": True,
        "total_reward": total_reward,
        "each_received": half,
    }