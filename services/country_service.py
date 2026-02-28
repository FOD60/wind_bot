"""
Сервис стран.
Создание, вступление, выход, президентство,
бюджет, армия, дипломатия (союзы, войны).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from database.collections import COUNTRIES, COUNTRY_DIPLOMACY, USERS
from database.firestore_client import db_client
from database.firebase_init import get_db
from database.models import CountryModel, DiplomacyModel
from utils.constants import (
    ARMY_EQUIPMENT_COST,
    ARMY_MISSILE_COST,
    ARMY_READINESS_MAX,
    ARMY_READINESS_PER_EQUIPMENT,
    ARMY_READINESS_PER_MISSILE,
    ARMY_READINESS_PER_VEHICLE,
    ARMY_VEHICLE_COST,
    COUNTRY_CREATION_COST,
    COUNTRY_MAX_NAME_LENGTH,
    COUNTRY_MIN_DEPOSIT,
    COUNTRY_MIN_NAME_LENGTH,
    WAR_MIN_READINESS,
)
from utils.helpers import format_winds

MSK = pytz.timezone("Europe/Moscow")


def _calc_readiness(vehicles: int, equipment: int, missiles: int) -> float:
    r = (
        vehicles * ARMY_READINESS_PER_VEHICLE
        + equipment * ARMY_READINESS_PER_EQUIPMENT
        + missiles * ARMY_READINESS_PER_MISSILE
    )
    return min(r, ARMY_READINESS_MAX)


# ═══════════════════ Информация ═══════════════════════════════


async def get_user_country(telegram_id: int) -> Optional[dict]:
    """Возвращает данные страны пользователя или None."""
    user = await db_client.get_doc(USERS, str(telegram_id))
    if not user or not user.get("country_id"):
        return None
    country = await db_client.get_doc(COUNTRIES, user["country_id"])
    if country:
        country["_id"] = user["country_id"]
    return country


async def get_country_by_name(name: str) -> Optional[tuple[str, dict]]:
    """Ищет страну по имени. Возвращает (doc_id, data) или None."""
    results = await db_client.query(
        COUNTRIES,
        filters=[("name", "==", name)],
        limit=1,
    )
    if results:
        return results[0]
    return None


async def get_country_members(country_id: str) -> list[dict]:
    """Список участников страны."""
    results = await db_client.query(
        USERS,
        filters=[("country_id", "==", country_id)],
    )
    members = []
    for doc_id, data in results:
        data["_id"] = doc_id
        members.append(data)
    return members


async def get_country_info(country_id: str) -> Optional[dict]:
    """Полная информация о стране: данные + участники + дипломатия."""
    country = await db_client.get_doc(COUNTRIES, country_id)
    if not country:
        return None

    country["_id"] = country_id
    members = await get_country_members(country_id)
    diplomacy = await get_diplomacy(country_id)

    # Президент
    president_tg_id = country.get("president_telegram_id")
    president = await db_client.get_doc(USERS, str(president_tg_id)) if president_tg_id else None

    readiness = _calc_readiness(
        country.get("army_vehicles", 0),
        country.get("army_equipment", 0),
        country.get("army_missiles", 0),
    )

    return {
        "country": country,
        "members": members,
        "member_count": len(members),
        "president": president,
        "diplomacy": diplomacy,
        "readiness": readiness,
    }


# ═══════════════════ Создание страны ══════════════════════════


async def create_country(telegram_id: int, name: str) -> dict:
    """
    Создание страны (транзакция).
    Стоимость: 249 999 виндов.
    Создатель автоматически становится президентом.
    """
    name = name.strip()

    if len(name) < COUNTRY_MIN_NAME_LENGTH:
        return {"ok": False, "error": f"Название слишком короткое (мин. {COUNTRY_MIN_NAME_LENGTH} символа)."}
    if len(name) > COUNTRY_MAX_NAME_LENGTH:
        return {"ok": False, "error": f"Название слишком длинное (макс. {COUNTRY_MAX_NAME_LENGTH} символов)."}

    # Проверяем уникальность имени
    existing = await get_country_by_name(name)
    if existing:
        return {"ok": False, "error": f"Страна «{name}» уже существует!"}

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован. Напиши /start."}

        user = user_snap.to_dict()

        if user.get("country_id"):
            return {"ok": False, "error": "Ты уже состоишь в стране! Сначала выйди."}

        balance = user.get("winds_balance", 0)
        if balance < COUNTRY_CREATION_COST:
            return {
                "ok": False,
                "error": (
                    f"Недостаточно виндов.\n"
                    f"Нужно: {format_winds(COUNTRY_CREATION_COST)}\n"
                    f"У тебя: {format_winds(balance)}"
                ),
            }

        # Создаём страну
        country_ref = db.collection(COUNTRIES).document()
        country_data = CountryModel.new(name, telegram_id).to_dict()
        transaction.set(country_ref, country_data)

        # Обновляем пользователя
        transaction.update(user_ref, {
            "winds_balance": balance - COUNTRY_CREATION_COST,
            "country_id": country_ref.id,
            "is_president": True,
        })

        return {
            "ok": True,
            "country_id": country_ref.id,
            "name": name,
            "cost": COUNTRY_CREATION_COST,
            "new_balance": balance - COUNTRY_CREATION_COST,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Вступление / Выход ═══════════════════════


async def join_country(telegram_id: int, country_id: str) -> dict:
    """Вступить в страну."""

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован."}

        user = user_snap.to_dict()
        if user.get("country_id"):
            return {"ok": False, "error": "Ты уже в стране! Сначала выйди (/страна выйти)."}

        country_ref = db.collection(COUNTRIES).document(country_id)
        country_snap = country_ref.get(transaction=transaction)

        if not country_snap.exists:
            return {"ok": False, "error": "Страна не найдена."}

        transaction.update(user_ref, {
            "country_id": country_id,
            "is_president": False,
        })

        return {"ok": True, "country_name": country_snap.to_dict().get("name", "?")}

    return await db_client.run_transaction(_execute)


async def leave_country(telegram_id: int) -> dict:
    """Выйти из страны. Президент не может выйти."""

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован."}

        user = user_snap.to_dict()
        if not user.get("country_id"):
            return {"ok": False, "error": "Ты не состоишь в стране."}

        if user.get("is_president"):
            return {"ok": False, "error": "Президент не может покинуть страну!\nПередай пост или распусти страну."}

        transaction.update(user_ref, {
            "country_id": None,
            "is_president": False,
        })

        return {"ok": True}

    return await db_client.run_transaction(_execute)


# ═══════════════════ Президент ════════════════════════════════


async def transfer_presidency(
    president_tg_id: int, new_president_tg_id: int
) -> dict:
    """Передать пост президента другому участнику страны."""

    def _execute(transaction, db):
        pres_ref = db.collection(USERS).document(str(president_tg_id))
        new_ref = db.collection(USERS).document(str(new_president_tg_id))

        pres_snap = pres_ref.get(transaction=transaction)
        new_snap = new_ref.get(transaction=transaction)

        if not pres_snap.exists or not new_snap.exists:
            return {"ok": False, "error": "Пользователь не найден."}

        pres = pres_snap.to_dict()
        new = new_snap.to_dict()

        if not pres.get("is_president"):
            return {"ok": False, "error": "Ты не президент!"}

        if pres.get("country_id") != new.get("country_id"):
            return {"ok": False, "error": "Этот игрок не в твоей стране!"}

        country_id = pres["country_id"]
        country_ref = db.collection(COUNTRIES).document(country_id)

        transaction.update(pres_ref, {"is_president": False})
        transaction.update(new_ref, {"is_president": True})
        transaction.update(country_ref, {"president_telegram_id": new_president_tg_id})

        return {"ok": True}

    return await db_client.run_transaction(_execute)


async def disband_country(president_tg_id: int) -> dict:
    """Распустить страну (только президент). Все участники выходят."""
    user = await db_client.get_doc(USERS, str(president_tg_id))
    if not user or not user.get("is_president"):
        return {"ok": False, "error": "Ты не президент!"}

    country_id = user.get("country_id")
    if not country_id:
        return {"ok": False, "error": "Ты не в стране."}

    # Убираем всех из страны
    members = await get_country_members(country_id)
    updates = []
    for m in members:
        updates.append((
            str(m["telegram_id"]),
            {"country_id": None, "is_president": False},
        ))

    if updates:
        await db_client.batch_update(USERS, updates)

    # Удаляем страну
    await db_client.delete_doc(COUNTRIES, country_id)

    # Удаляем дипломатию
    diplo = await get_all_diplomacy_docs(country_id)
    for doc_id, _ in diplo:
        await db_client.delete_doc(COUNTRY_DIPLOMACY, doc_id)

    return {"ok": True}


# ═══════════════════ Бюджет ═══════════════════════════════════


async def deposit_to_budget(telegram_id: int, amount: int) -> dict:
    """Внести виндов в бюджет страны."""
    if amount < COUNTRY_MIN_DEPOSIT:
        return {"ok": False, "error": f"Минимум {format_winds(COUNTRY_MIN_DEPOSIT)}."}

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        country_id = user.get("country_id")
        if not country_id:
            return {"ok": False, "error": "Ты не в стране."}

        balance = user.get("winds_balance", 0)
        if balance < amount:
            return {"ok": False, "error": f"Недостаточно виндов. Баланс: {format_winds(balance)}"}

        country_ref = db.collection(COUNTRIES).document(country_id)
        country_snap = country_ref.get(transaction=transaction)

        if not country_snap.exists:
            return {"ok": False, "error": "Страна не найдена."}

        country = country_snap.to_dict()

        transaction.update(user_ref, {"winds_balance": balance - amount})
        transaction.update(country_ref, {"budget_winds": country.get("budget_winds", 0) + amount})

        return {
            "ok": True,
            "new_balance": balance - amount,
            "new_budget": country.get("budget_winds", 0) + amount,
        }

    return await db_client.run_transaction(_execute)


async def withdraw_from_budget(president_tg_id: int, amount: int) -> dict:
    """Снять виндов из бюджета (только президент)."""
    if amount <= 0:
        return {"ok": False, "error": "Сумма должна быть > 0."}

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(president_tg_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        if not user.get("is_president"):
            return {"ok": False, "error": "Только президент может снимать из бюджета!"}

        country_id = user.get("country_id")
        country_ref = db.collection(COUNTRIES).document(country_id)
        country_snap = country_ref.get(transaction=transaction)

        if not country_snap.exists:
            return {"ok": False, "error": "Страна не найдена."}

        country = country_snap.to_dict()
        budget = country.get("budget_winds", 0)

        if budget < amount:
            return {"ok": False, "error": f"В бюджете недостаточно. Бюджет: {format_winds(budget)}"}

        transaction.update(user_ref, {"winds_balance": user.get("winds_balance", 0) + amount})
        transaction.update(country_ref, {"budget_winds": budget - amount})

        return {
            "ok": True,
            "new_balance": user.get("winds_balance", 0) + amount,
            "new_budget": budget - amount,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Армия ════════════════════════════════════


async def buy_army(
    president_tg_id: int,
    unit_type: str,
    quantity: int,
) -> dict:
    """
    Покупка армейских единиц из бюджета страны.
    unit_type: "vehicles" | "equipment" | "missiles"
    """
    costs = {
        "vehicles": ARMY_VEHICLE_COST,
        "equipment": ARMY_EQUIPMENT_COST,
        "missiles": ARMY_MISSILE_COST,
    }
    fields = {
        "vehicles": "army_vehicles",
        "equipment": "army_equipment",
        "missiles": "army_missiles",
    }
    names = {
        "vehicles": "Техника",
        "equipment": "Снаряжение",
        "missiles": "Ракеты",
    }

    if unit_type not in costs:
        return {"ok": False, "error": "Неверный тип юнита."}
    if quantity <= 0:
        return {"ok": False, "error": "Количество должно быть > 0."}

    cost_per = costs[unit_type]
    total_cost = cost_per * quantity
    field = fields[unit_type]
    unit_name = names[unit_type]

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(president_tg_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        if not user.get("is_president"):
            return {"ok": False, "error": "Только президент может покупать армию!"}

        country_id = user.get("country_id")
        country_ref = db.collection(COUNTRIES).document(country_id)
        country_snap = country_ref.get(transaction=transaction)

        if not country_snap.exists:
            return {"ok": False, "error": "Страна не найдена."}

        country = country_snap.to_dict()
        budget = country.get("budget_winds", 0)

        if budget < total_cost:
            return {
                "ok": False,
                "error": (
                    f"Недостаточно в бюджете!\n"
                    f"Нужно: {format_winds(total_cost)}\n"
                    f"Бюджет: {format_winds(budget)}"
                ),
            }

        current = country.get(field, 0)
        new_count = current + quantity
        new_budget = budget - total_cost

        # Пересчитываем готовность
        v = country.get("army_vehicles", 0)
        e = country.get("army_equipment", 0)
        m = country.get("army_missiles", 0)
        if unit_type == "vehicles":
            v = new_count
        elif unit_type == "equipment":
            e = new_count
        else:
            m = new_count
        readiness = _calc_readiness(v, e, m)

        transaction.update(country_ref, {
            "budget_winds": new_budget,
            field: new_count,
            "army_readiness": readiness,
        })

        return {
            "ok": True,
            "unit_name": unit_name,
            "quantity": quantity,
            "total_cost": total_cost,
            "new_count": new_count,
            "new_budget": new_budget,
            "readiness": readiness,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Дипломатия ═══════════════════════════════


async def get_diplomacy(country_id: str) -> list[dict]:
    """Все дипломатические отношения страны."""
    results1 = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country1_id", "==", country_id)],
    )
    results2 = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country2_id", "==", country_id)],
    )

    diplomacy = []
    for doc_id, data in results1 + results2:
        other_id = data["country2_id"] if data["country1_id"] == country_id else data["country1_id"]
        other = await db_client.get_doc(COUNTRIES, other_id)
        other_name = other.get("name", "?") if other else "?"
        diplomacy.append({
            "doc_id": doc_id,
            "other_id": other_id,
            "other_name": other_name,
            "status": data["status"],
        })

    return diplomacy


async def get_all_diplomacy_docs(country_id: str) -> list[tuple[str, dict]]:
    """Все записи дипломатии (для удаления)."""
    r1 = await db_client.query(COUNTRY_DIPLOMACY, filters=[("country1_id", "==", country_id)])
    r2 = await db_client.query(COUNTRY_DIPLOMACY, filters=[("country2_id", "==", country_id)])
    return r1 + r2


async def propose_alliance(
    president_tg_id: int, target_country_name: str
) -> dict:
    """Предложить союз другой стране."""
    user = await db_client.get_doc(USERS, str(president_tg_id))
    if not user or not user.get("is_president"):
        return {"ok": False, "error": "Ты не президент!"}

    my_country_id = user.get("country_id")
    target = await get_country_by_name(target_country_name)
    if not target:
        return {"ok": False, "error": f"Страна «{target_country_name}» не найдена."}

    target_id, target_data = target

    if target_id == my_country_id:
        return {"ok": False, "error": "Нельзя заключить союз с собой!"}

    # Проверяем нет ли уже отношений
    c1, c2 = sorted([my_country_id, target_id])
    existing = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country1_id", "==", c1), ("country2_id", "==", c2)],
        limit=1,
    )
    if existing:
        status = existing[0][1].get("status")
        if status == "alliance":
            return {"ok": False, "error": "Союз уже заключён!"}
        if status == "war":
            return {"ok": False, "error": "Вы сейчас воюете! Сначала заключите мир."}

    now = datetime.now(MSK).isoformat()
    await db_client.add_doc(COUNTRY_DIPLOMACY, {
        "country1_id": c1,
        "country2_id": c2,
        "status": "alliance",
        "created_at": now,
    })

    my_country = await db_client.get_doc(COUNTRIES, my_country_id)
    my_name = my_country.get("name", "?") if my_country else "?"

    return {"ok": True, "my_name": my_name, "target_name": target_data.get("name", "?")}


async def declare_war(
    president_tg_id: int, target_country_name: str
) -> dict:
    """Объявить войну другой стране."""
    user = await db_client.get_doc(USERS, str(president_tg_id))
    if not user or not user.get("is_president"):
        return {"ok": False, "error": "Ты не президент!"}

    my_country_id = user.get("country_id")
    my_country = await db_client.get_doc(COUNTRIES, my_country_id)
    if not my_country:
        return {"ok": False, "error": "Страна не найдена."}

    readiness = _calc_readiness(
        my_country.get("army_vehicles", 0),
        my_country.get("army_equipment", 0),
        my_country.get("army_missiles", 0),
    )
    if readiness < WAR_MIN_READINESS:
        return {
            "ok": False,
            "error": f"Готовность армии слишком низкая ({readiness:.1f}%).\nМинимум для войны: {WAR_MIN_READINESS}%.",
        }

    target = await get_country_by_name(target_country_name)
    if not target:
        return {"ok": False, "error": f"Страна «{target_country_name}» не найдена."}

    target_id, target_data = target
    if target_id == my_country_id:
        return {"ok": False, "error": "Нельзя воевать с собой!"}

    c1, c2 = sorted([my_country_id, target_id])
    existing = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country1_id", "==", c1), ("country2_id", "==", c2)],
        limit=1,
    )

    now = datetime.now(MSK).isoformat()

    if existing:
        doc_id = existing[0][0]
        status = existing[0][1].get("status")
        if status == "war":
            return {"ok": False, "error": "Вы уже воюете!"}
        # Был союз → теперь война
        await db_client.update_doc(COUNTRY_DIPLOMACY, doc_id, {
            "status": "war",
            "created_at": now,
        })
    else:
        await db_client.add_doc(COUNTRY_DIPLOMACY, {
            "country1_id": c1,
            "country2_id": c2,
            "status": "war",
            "created_at": now,
        })

    return {"ok": True, "my_name": my_country.get("name", "?"), "target_name": target_data.get("name", "?")}


async def make_peace(
    president_tg_id: int, target_country_name: str
) -> dict:
    """Заключить мир (удалить запись войны)."""
    user = await db_client.get_doc(USERS, str(president_tg_id))
    if not user or not user.get("is_president"):
        return {"ok": False, "error": "Ты не президент!"}

    my_country_id = user.get("country_id")

    target = await get_country_by_name(target_country_name)
    if not target:
        return {"ok": False, "error": f"Страна «{target_country_name}» не найдена."}

    target_id, target_data = target
    c1, c2 = sorted([my_country_id, target_id])

    existing = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country1_id", "==", c1), ("country2_id", "==", c2)],
        limit=1,
    )

    if not existing:
        return {"ok": False, "error": "Нет дипломатических отношений."}

    doc_id = existing[0][0]
    status = existing[0][1].get("status")

    if status != "war":
        return {"ok": False, "error": "Вы не воюете!"}

    await db_client.delete_doc(COUNTRY_DIPLOMACY, doc_id)

    return {"ok": True, "target_name": target_data.get("name", "?")}


async def break_alliance(
    president_tg_id: int, target_country_name: str
) -> dict:
    """Разорвать союз."""
    user = await db_client.get_doc(USERS, str(president_tg_id))
    if not user or not user.get("is_president"):
        return {"ok": False, "error": "Ты не президент!"}

    my_country_id = user.get("country_id")

    target = await get_country_by_name(target_country_name)
    if not target:
        return {"ok": False, "error": f"Страна «{target_country_name}» не найдена."}

    target_id, target_data = target
    c1, c2 = sorted([my_country_id, target_id])

    existing = await db_client.query(
        COUNTRY_DIPLOMACY,
        filters=[("country1_id", "==", c1), ("country2_id", "==", c2)],
        limit=1,
    )

    if not existing or existing[0][1].get("status") != "alliance":
        return {"ok": False, "error": "Союз не найден."}

    await db_client.delete_doc(COUNTRY_DIPLOMACY, existing[0][0])

    return {"ok": True, "target_name": target_data.get("name", "?")}


async def list_countries(limit: int = 20) -> list[tuple[str, dict]]:
    """Список всех стран."""
    return await db_client.query(COUNTRIES, limit=limit)