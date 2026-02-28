"""
Ежедневные задачи (00:00 МСК):
  1. Сброс лимитов переводов у всех пользователей
  2. Выдача наград топ-5 лидерборда за прошедший день
  3. Сброс ежедневных наград браков
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database.firebase_init import get_db
from database.collections import (
    USERS,
    DAILY_WINNINGS,
    LEADERBOARD_REWARDS as LB_REWARDS_COL,
    MARRIAGES,
)
from utils.constants import LEADERBOARD_REWARDS

logger = logging.getLogger(__name__)

MSK = pytz.timezone("Europe/Moscow")


# ═══════════════ 1. Сброс лимитов переводов ══════════════════

async def reset_daily_transfer_limits() -> None:
    db = get_db()
    today = datetime.now(MSK).strftime("%Y-%m-%d")

    def _reset():
        docs = list(
            db.collection(USERS)
            .where("last_transfer_reset", "<", today)
            .stream()
        )
        if not docs:
            return 0

        batch = db.batch()
        total = 0
        for i, doc in enumerate(docs):
            batch.update(doc.reference, {
                "daily_transfer_used": 0,
                "last_transfer_reset": today,
            })
            total += 1
            if (i + 1) % 500 == 0:
                batch.commit()
                batch = db.batch()
        if total % 500 != 0:
            batch.commit()
        return total

    count = await asyncio.to_thread(_reset)
    logger.info("[CRON] Сброс лимитов переводов: %d пользователей", count)


# ═══════════════ 2. Награды лидерборда ════════════════════════

async def distribute_leaderboard_rewards() -> None:
    """
    Топ-5 по сумме выигрышей за ВЧЕРА получают:
      1 → 200к, 2 → 150к, 3 → 90к, 4 → 60к, 5 → 25к виндов.

    ВАЖНО: Для этого запроса нужен СОСТАВНОЙ ИНДЕКС в Firestore:
      Коллекция: daily_winnings
      Поля: date ASC, total_winnings DESC
    Создайте его в Firebase Console → Firestore → Indexes,
    либо перейдите по ссылке из ошибки при первом запуске.
    """
    db = get_db()
    yesterday = (datetime.now(MSK) - timedelta(seconds=1)).strftime("%Y-%m-%d")

    def _distribute():
        from google.cloud.firestore_v1 import Query

        docs = list(
            db.collection(DAILY_WINNINGS)
            .where("date", "==", yesterday)
            .where("total_winnings", ">", 0)
            .order_by("total_winnings", direction=Query.DESCENDING)
            .limit(len(LEADERBOARD_REWARDS))
            .stream()
        )

        if not docs:
            logger.info("[CRON] Лидерборд за %s: нет участников", yesterday)
            return

        batch = db.batch()
        now_iso = datetime.now(MSK).isoformat()

        for rank, doc in enumerate(docs):
            data = doc.to_dict()
            tg_id = data["user_telegram_id"]
            reward = LEADERBOARD_REWARDS[rank]

            # Атомарный инкремент баланса
            from google.cloud.firestore_v1 import Increment

            user_ref = db.collection(USERS).document(str(tg_id))
            batch.update(user_ref, {"winds_balance": Increment(reward)})

            # Аудит-запись
            reward_ref = db.collection(LB_REWARDS_COL).document()
            batch.set(reward_ref, {
                "user_telegram_id": tg_id,
                "date": yesterday,
                "rank": rank + 1,
                "reward_amount": reward,
                "created_at": now_iso,
            })

            logger.info(
                "[CRON] Лидерборд %s: #%d → tg=%d, выигрыш=%d, награда=%d виндов",
                yesterday, rank + 1, tg_id, data["total_winnings"], reward,
            )

        batch.commit()

    await asyncio.to_thread(_distribute)


# ═══════════════ 3. Сброс наград браков ═══════════════════════

async def reset_marriage_daily_rewards() -> None:
    db = get_db()
    today = datetime.now(MSK).strftime("%Y-%m-%d")

    def _reset():
        docs = list(
            db.collection(MARRIAGES)
            .where("is_active", "==", True)
            .where("last_reward_reset", "<", today)
            .stream()
        )
        if not docs:
            return 0

        batch = db.batch()
        total = 0
        for i, doc in enumerate(docs):
            batch.update(doc.reference, {
                "daily_reward_claimed": False,
                "last_reward_reset": today,
            })
            total += 1
            if (i + 1) % 500 == 0:
                batch.commit()
                batch = db.batch()
        if total % 500 != 0:
            batch.commit()
        return total

    count = await asyncio.to_thread(_reset)
    logger.info("[CRON] Сброс наград браков: %d пар", count)


# ═══════════════ Настройка планировщика ═══════════════════════

def setup_scheduler() -> AsyncIOScheduler:
    """Создаёт планировщик с 3 задачами на 00:00 МСК."""
    scheduler = AsyncIOScheduler(timezone=MSK)

    trigger = CronTrigger(hour=0, minute=0, second=0, timezone=MSK)

    scheduler.add_job(
        reset_daily_transfer_limits,
        trigger=trigger,
        id="reset_transfers",
        name="Сброс лимитов переводов (00:00 МСК)",
        replace_existing=True,
    )
    scheduler.add_job(
        distribute_leaderboard_rewards,
        trigger=trigger,
        id="leaderboard_rewards",
        name="Награды лидерборда (00:00 МСК)",
        replace_existing=True,
    )
    scheduler.add_job(
        reset_marriage_daily_rewards,
        trigger=trigger,
        id="marriage_rewards",
        name="Сброс наград браков (00:00 МСК)",
        replace_existing=True,
    )

    logger.info("[SCHEDULER] Настроено %d задач", len(scheduler.get_jobs()))
    return scheduler
