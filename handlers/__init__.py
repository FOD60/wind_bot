"""Регистрация всех роутеров."""
from aiogram import Dispatcher

from handlers.admin import router as admin_router
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.economy import router as economy_router
from handlers.leaderboard import router as leaderboard_router
from handlers.country import router as country_router
from handlers.marriage import router as marriage_router
from handlers.vip import router as vip_router
from handlers.auction import router as auction_router
from handlers.chat_admin import router as chat_admin_router

# 👇 НОВЫЕ РОУТЕРЫ
from handlers.promo_quests import router as pq_router
from handlers.payments import router as pay_router 
# 👆

from handlers.games import game_routers

def register_all_routers(dp: Dispatcher) -> None:
    dp.include_router(admin_router)
    dp.include_router(chat_admin_router)
    dp.include_router(start_router)
    
    # Подключаем новые роутеры
    dp.include_router(pq_router)
    dp.include_router(pay_router)
    
    dp.include_router(profile_router)
    dp.include_router(economy_router)
    dp.include_router(leaderboard_router)
    dp.include_router(country_router)
    dp.include_router(marriage_router)
    dp.include_router(vip_router)
    dp.include_router(auction_router)

    for game_router in game_routers:
        dp.include_router(game_router)