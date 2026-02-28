"""
Wind Bot — игровой Telegram-бот.
Работает и в личных сообщениях, и в группах.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from database.firebase_init import init_firebase
from handlers import register_all_routers
from middlewares import UserMiddleware, ChatMiddleware
from scheduler.jobs import setup_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)



async def main() -> None:
    # 1. Firebase
    logger.info("Подключение к Firebase...")
    init_firebase()

    # 2. Бот
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # 3. Middleware (важен порядок!)
    dp.message.middleware(UserMiddleware())
    dp.message.middleware(ChatMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # 4. Роутеры
    register_all_routers(dp)

    # 5. Планировщик
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Планировщик запущен (%d задач).", len(scheduler.get_jobs()))

    # 6. Поллинг
    logger.info("Бот запускается...")
    try:
        # Разрешаем получать все обновления из групп
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member"],
        )
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())