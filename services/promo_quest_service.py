"""Сервис промокодов и заданий."""
from __future__ import annotations
from datetime import datetime
import pytz
from database.collections import PROMO_CODES, PROMO_USES, QUESTS, USER_QUESTS, USERS
from database.firestore_client import db_client

MSK = pytz.timezone("Europe/Moscow")

def _now_iso(): return datetime.now(MSK).isoformat()

# ══════════════ ПРОМОКОДЫ ══════════════

async def create_promo(code: str, winds: int, gcoins: int, uses: int) -> dict:
    code = code.upper().strip()
    if await db_client.get_doc(PROMO_CODES, code):
        return {"ok": False, "error": "Промокод уже существует."}
    
    await db_client.set_doc(PROMO_CODES, code, {
        "winds": winds, "gcoins": gcoins, "max_uses": uses, "uses": 0, "is_active": True
    })
    return {"ok": True}

async def activate_promo(tg_id: int, code: str) -> dict:
    code = code.upper().strip()
    use_id = f"{tg_id}_{code}"
    
    if await db_client.get_doc(PROMO_USES, use_id):
        return {"ok": False, "error": "Ты уже использовал этот код!"}

    def _execute(transaction, db):
        promo_ref = db.collection(PROMO_CODES).document(code)
        promo_snap = promo_ref.get(transaction=transaction)
        if not promo_snap.exists or not promo_snap.to_dict().get("is_active"):
            return {"ok": False, "error": "Промокод не найден или неактивен."}
            
        promo = promo_snap.to_dict()
        if promo["uses"] >= promo["max_uses"]:
            return {"ok": False, "error": "Лимит использований исчерпан."}

        user_ref = db.collection(USERS).document(str(tg_id))
        user = user_ref.get(transaction=transaction).to_dict()

        w = promo.get("winds", 0)
        g = promo.get("gcoins", 0)

        transaction.update(user_ref, {
            "winds_balance": user.get("winds_balance", 0) + w,
            "gcoins_balance": user.get("gcoins_balance", 0) + g
        })
        transaction.update(promo_ref, {"uses": promo["uses"] + 1})
        transaction.set(db.collection(PROMO_USES).document(use_id), {"used_at": _now_iso()})

        return {"ok": True, "winds": w, "gcoins": g}

    return await db_client.run_transaction(_execute)

# ══════════════ ЗАДАНИЯ ══════════════

async def add_quest(quest_id: str, title: str, url: str, winds: int) -> None:
    await db_client.set_doc(QUESTS, quest_id, {
        "title": title, "url": url, "reward_winds": winds, "is_active": True, "created_at": _now_iso()
    })

async def del_quest(quest_id: str) -> None:
    await db_client.delete_doc(QUESTS, quest_id)

async def get_active_quests(tg_id: int) -> list[dict]:
    all_quests = await db_client.query(QUESTS, filters=[("is_active", "==", True)])
    user_done = await db_client.query(USER_QUESTS, filters=[("tg_id", "==", tg_id)])
    done_ids = [d["quest_id"] for _, d in user_done]

    available = []
    for q_id, q_data in all_quests:
        if q_id not in done_ids:
            q_data["id"] = q_id
            available.append(q_data)
    return available

async def claim_quest_reward(tg_id: int, quest_id: str) -> dict:
    use_id = f"{tg_id}_{quest_id}"
    if await db_client.get_doc(USER_QUESTS, use_id):
        return {"ok": False, "error": "Задание уже выполнено!"}

    def _execute(transaction, db):
        q_ref = db.collection(QUESTS).document(quest_id)
        q_snap = q_ref.get(transaction=transaction)
        if not q_snap.exists: return {"ok": False, "error": "Задание не найдено."}
        
        reward = q_snap.to_dict().get("reward_winds", 0)
        
        u_ref = db.collection(USERS).document(str(tg_id))
        u_snap = u_ref.get(transaction=transaction)
        
        transaction.update(u_ref, {"winds_balance": u_snap.to_dict().get("winds_balance", 0) + reward})
        transaction.set(db.collection(USER_QUESTS).document(use_id), {"tg_id": tg_id, "quest_id": quest_id, "done_at": _now_iso()})
        
        return {"ok": True, "reward": reward}

    return await db_client.run_transaction(_execute)