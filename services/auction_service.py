"""
Сервис P2P-биржи (Аукцион).
Ордера на покупку/продажу G-коинов за винды.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from database.collections import AUCTION_ORDERS, AUCTION_TRADES, USERS
from database.firestore_client import db_client
from utils.constants import (
    AUCTION_FEE_PERCENT,
    AUCTION_MAX_GCOINS,
    AUCTION_MAX_PRICE,
    AUCTION_MIN_GCOINS,
    AUCTION_MIN_PRICE,
)
from utils.helpers import format_gcoins, format_winds

MSK = pytz.timezone("Europe/Moscow")


# ═══════════════════ Создание ордеров ═════════════════════════


async def create_sell_order(
    telegram_id: int,
    gcoins_amount: int,
    price_per_gcoin: int,
) -> dict:
    """
    Создать ордер на ПРОДАЖУ G-коинов.
    Продавец замораживает G-коины, получит винды при исполнении.
    """
    if gcoins_amount < AUCTION_MIN_GCOINS:
        return {"ok": False, "error": f"Минимум {AUCTION_MIN_GCOINS} G-коин."}
    if gcoins_amount > AUCTION_MAX_GCOINS:
        return {"ok": False, "error": f"Максимум {AUCTION_MAX_GCOINS} G-коинов."}
    if price_per_gcoin < AUCTION_MIN_PRICE:
        return {"ok": False, "error": f"Минимальная цена: {format_winds(AUCTION_MIN_PRICE)}/G-коин."}
    if price_per_gcoin > AUCTION_MAX_PRICE:
        return {"ok": False, "error": f"Максимальная цена: {format_winds(AUCTION_MAX_PRICE)}/G-коин."}

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        gcoins = user.get("gcoins_balance", 0)

        if gcoins < gcoins_amount:
            return {"ok": False, "error": f"Недостаточно G-коинов. У тебя: {format_gcoins(gcoins)}"}

        # Замораживаем G-коины
        transaction.update(user_ref, {
            "gcoins_balance": gcoins - gcoins_amount,
        })

        # Создаём ордер
        order_ref = db.collection(AUCTION_ORDERS).document()
        now = datetime.now(MSK).isoformat()
        transaction.set(order_ref, {
            "user_telegram_id": telegram_id,
            "order_type": "sell",
            "gcoins_amount": gcoins_amount,
            "gcoins_filled": 0,
            "price_per_gcoin": price_per_gcoin,
            "is_active": True,
            "created_at": now,
        })

        total_winds = gcoins_amount * price_per_gcoin

        return {
            "ok": True,
            "order_id": order_ref.id,
            "gcoins": gcoins_amount,
            "price": price_per_gcoin,
            "total": total_winds,
        }

    return await db_client.run_transaction(_execute)


async def create_buy_order(
    telegram_id: int,
    gcoins_amount: int,
    price_per_gcoin: int,
) -> dict:
    """
    Создать ордер на ПОКУПКУ G-коинов.
    Покупатель замораживает винды, получит G-коины при исполнении.
    """
    if gcoins_amount < AUCTION_MIN_GCOINS:
        return {"ok": False, "error": f"Минимум {AUCTION_MIN_GCOINS} G-коин."}
    if gcoins_amount > AUCTION_MAX_GCOINS:
        return {"ok": False, "error": f"Максимум {AUCTION_MAX_GCOINS} G-коинов."}
    if price_per_gcoin < AUCTION_MIN_PRICE:
        return {"ok": False, "error": f"Минимальная цена: {format_winds(AUCTION_MIN_PRICE)}/G-коин."}
    if price_per_gcoin > AUCTION_MAX_PRICE:
        return {"ok": False, "error": f"Максимальная цена: {format_winds(AUCTION_MAX_PRICE)}/G-коин."}

    total_winds = gcoins_amount * price_per_gcoin

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        user_snap = user_ref.get(transaction=transaction)

        if not user_snap.exists:
            return {"ok": False, "error": "Не зарегистрирован."}

        user = user_snap.to_dict()
        winds = user.get("winds_balance", 0)

        if winds < total_winds:
            return {"ok": False, "error": f"Недостаточно виндов. Нужно: {format_winds(total_winds)}"}

        # Замораживаем винды
        transaction.update(user_ref, {
            "winds_balance": winds - total_winds,
        })

        # Создаём ордер
        order_ref = db.collection(AUCTION_ORDERS).document()
        now = datetime.now(MSK).isoformat()
        transaction.set(order_ref, {
            "user_telegram_id": telegram_id,
            "order_type": "buy",
            "gcoins_amount": gcoins_amount,
            "gcoins_filled": 0,
            "price_per_gcoin": price_per_gcoin,
            "is_active": True,
            "created_at": now,
        })

        return {
            "ok": True,
            "order_id": order_ref.id,
            "gcoins": gcoins_amount,
            "price": price_per_gcoin,
            "total": total_winds,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Отмена ордера ════════════════════════════


async def cancel_order(telegram_id: int, order_id: str) -> dict:
    """Отменить свой ордер и вернуть замороженные средства."""
    order = await db_client.get_doc(AUCTION_ORDERS, order_id)
    if not order:
        return {"ok": False, "error": "Ордер не найден."}

    if order.get("user_telegram_id") != telegram_id:
        return {"ok": False, "error": "Это не твой ордер!"}

    if not order.get("is_active"):
        return {"ok": False, "error": "Ордер уже неактивен."}

    remaining = order.get("gcoins_amount", 0) - order.get("gcoins_filled", 0)
    if remaining <= 0:
        return {"ok": False, "error": "Ордер уже полностью исполнен."}

    order_type = order.get("order_type")
    price = order.get("price_per_gcoin", 0)

    def _execute(transaction, db):
        user_ref = db.collection(USERS).document(str(telegram_id))
        order_ref = db.collection(AUCTION_ORDERS).document(order_id)

        user_snap = user_ref.get(transaction=transaction)
        if not user_snap.exists:
            return {"ok": False, "error": "Не найден."}

        user = user_snap.to_dict()

        if order_type == "sell":
            # Возвращаем G-коины
            new_gcoins = user.get("gcoins_balance", 0) + remaining
            transaction.update(user_ref, {"gcoins_balance": new_gcoins})
            refund = f"{remaining} G-коин(ов)"
        else:
            # Возвращаем винды
            refund_winds = remaining * price
            new_winds = user.get("winds_balance", 0) + refund_winds
            transaction.update(user_ref, {"winds_balance": new_winds})
            refund = format_winds(refund_winds)

        transaction.update(order_ref, {"is_active": False})

        return {"ok": True, "refund": refund}

    return await db_client.run_transaction(_execute)


# ═══════════════════ Исполнение ордера ════════════════════════


async def execute_order(
    buyer_tg_id: int,
    order_id: str,
    gcoins_to_buy: int,
) -> dict:
    """
    Исполнить (полностью или частично) ордер.
    buyer_tg_id покупает G-коины из sell-ордера
    или продаёт G-коины в buy-ордер.
    """
    order = await db_client.get_doc(AUCTION_ORDERS, order_id)
    if not order:
        return {"ok": False, "error": "Ордер не найден."}

    if not order.get("is_active"):
        return {"ok": False, "error": "Ордер неактивен."}

    if order.get("user_telegram_id") == buyer_tg_id:
        return {"ok": False, "error": "Нельзя исполнять свой ордер!"}

    remaining = order.get("gcoins_amount", 0) - order.get("gcoins_filled", 0)
    if remaining <= 0:
        return {"ok": False, "error": "Ордер уже исполнен."}

    if gcoins_to_buy > remaining:
        gcoins_to_buy = remaining

    if gcoins_to_buy <= 0:
        return {"ok": False, "error": "Неверное количество."}

    order_type = order.get("order_type")
    price = order.get("price_per_gcoin", 0)
    owner_tg_id = order.get("user_telegram_id")
    winds_total = gcoins_to_buy * price

    # Комиссия
    fee = int(winds_total * AUCTION_FEE_PERCENT / 100)

    def _execute(transaction, db):
        buyer_ref = db.collection(USERS).document(str(buyer_tg_id))
        owner_ref = db.collection(USERS).document(str(owner_tg_id))
        order_ref = db.collection(AUCTION_ORDERS).document(order_id)

        buyer_snap = buyer_ref.get(transaction=transaction)
        owner_snap = owner_ref.get(transaction=transaction)

        if not buyer_snap.exists or not owner_snap.exists:
            return {"ok": False, "error": "Пользователь не найден."}

        buyer = buyer_snap.to_dict()
        owner = owner_snap.to_dict()

        if order_type == "sell":
            # Покупатель платит виндами, получает G-коины
            if buyer.get("winds_balance", 0) < winds_total:
                return {"ok": False, "error": f"Недостаточно виндов. Нужно: {format_winds(winds_total)}"}

            # Покупатель: -винды, +G-коины
            transaction.update(buyer_ref, {
                "winds_balance": buyer["winds_balance"] - winds_total,
                "gcoins_balance": buyer.get("gcoins_balance", 0) + gcoins_to_buy,
            })

            # Продавец (owner): +винды (минус комиссия)
            transaction.update(owner_ref, {
                "winds_balance": owner.get("winds_balance", 0) + winds_total - fee,
            })

            seller_id = owner_tg_id
            buyer_id_final = buyer_tg_id

        else:  # buy order
            # Исполнитель продаёт G-коины владельцу ордера
            if buyer.get("gcoins_balance", 0) < gcoins_to_buy:
                return {"ok": False, "error": f"Недостаточно G-коинов."}

            # Исполнитель (buyer): -G-коины, +винды (минус комиссия)
            transaction.update(buyer_ref, {
                "gcoins_balance": buyer["gcoins_balance"] - gcoins_to_buy,
                "winds_balance": buyer.get("winds_balance", 0) + winds_total - fee,
            })

            # Владелец ордера: +G-коины (винды уже заморожены)
            transaction.update(owner_ref, {
                "gcoins_balance": owner.get("gcoins_balance", 0) + gcoins_to_buy,
            })

            seller_id = buyer_tg_id
            buyer_id_final = owner_tg_id

        # Обновляем ордер
        new_filled = order.get("gcoins_filled", 0) + gcoins_to_buy
        is_complete = new_filled >= order.get("gcoins_amount", 0)

        transaction.update(order_ref, {
            "gcoins_filled": new_filled,
            "is_active": not is_complete,
        })

        # Записываем сделку
        trade_ref = db.collection(AUCTION_TRADES).document()
        now = datetime.now(MSK).isoformat()
        transaction.set(trade_ref, {
            "order_id": order_id,
            "buyer_telegram_id": buyer_id_final,
            "seller_telegram_id": seller_id,
            "gcoins_amount": gcoins_to_buy,
            "winds_amount": winds_total,
            "fee": fee,
            "traded_at": now,
        })

        return {
            "ok": True,
            "gcoins": gcoins_to_buy,
            "winds": winds_total,
            "fee": fee,
            "complete": is_complete,
        }

    return await db_client.run_transaction(_execute)


# ═══════════════════ Списки ордеров ═══════════════════════════


async def get_sell_orders(limit: int = 20) -> list[tuple[str, dict]]:
    """Список активных ордеров на продажу (сортировка по цене ASC)."""
    return await db_client.query(
        AUCTION_ORDERS,
        filters=[
            ("order_type", "==", "sell"),
            ("is_active", "==", True),
        ],
        order_by="price_per_gcoin",
        direction="ASCENDING",
        limit=limit,
    )


async def get_buy_orders(limit: int = 20) -> list[tuple[str, dict]]:
    """Список активных ордеров на покупку (сортировка по цене DESC)."""
    return await db_client.query(
        AUCTION_ORDERS,
        filters=[
            ("order_type", "==", "buy"),
            ("is_active", "==", True),
        ],
        order_by="price_per_gcoin",
        direction="DESCENDING",
        limit=limit,
    )


async def get_my_orders(telegram_id: int) -> list[tuple[str, dict]]:
    """Мои активные ордера."""
    return await db_client.query(
        AUCTION_ORDERS,
        filters=[
            ("user_telegram_id", "==", telegram_id),
            ("is_active", "==", True),
        ],
    )