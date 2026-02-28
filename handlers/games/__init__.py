"""Все 22 игровых роутера."""
from handlers.games.casino import router as casino_router
from handlers.games.flip import router as flip_router
from handlers.games.dice import router as dice_router
from handlers.games.darts import router as darts_router
from handlers.games.football import router as football_router
from handlers.games.basketball import router as basketball_router
from handlers.games.bowling import router as bowling_router
from handlers.games.roulette import router as roulette_router
from handlers.games.slots import router as slots_router
from handlers.games.nvuti import router as nvuti_router
from handlers.games.vilin import router as vilin_router
from handlers.games.hunt import router as hunt_router
from handlers.games.crash import router as crash_router
from handlers.games.trade import router as trade_router
from handlers.games.russian_roulette import router as rr_router
from handlers.games.spin import router as spin_router
from handlers.games.mines import router as mines_router
from handlers.games.tower import router as tower_router
from handlers.games.knb import router as knb_router
from handlers.games.lottery import router as lottery_router
from handlers.games.jackpot import router as jackpot_router
from handlers.games.duel import router as duel_router

game_routers = [
    casino_router,
    flip_router,
    dice_router,
    darts_router,
    football_router,
    basketball_router,
    bowling_router,
    roulette_router,
    slots_router,
    nvuti_router,
    vilin_router,
    hunt_router,
    crash_router,
    trade_router,
    rr_router,
    spin_router,
    mines_router,
    tower_router,
    # Мультиплеерные
    knb_router,
    lottery_router,
    jackpot_router,
    duel_router,
]