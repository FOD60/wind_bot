"""
Все игровые константы Wind Bot.
Основная валюта: «винды» (1 винда, 2 винды, 5 виндов).
Донатная валюта: G-коин.
"""
from __future__ import annotations

# ────────────────────────── УРОВНИ ──────────────────────────
# transfer_limit == -1 → безлимит
LEVEL_CONFIG: dict[int, dict[str, int]] = {
    1:  {"cost": 0,           "transfer_limit": 50_000},
    2:  {"cost": 250_000,     "transfer_limit": 75_000},
    3:  {"cost": 500_000,     "transfer_limit": 100_000},
    4:  {"cost": 800_000,     "transfer_limit": 300_000},
    5:  {"cost": 1_500_000,   "transfer_limit": 500_000},
    6:  {"cost": 2_000_000,   "transfer_limit": 750_000},
    7:  {"cost": 3_000_000,   "transfer_limit": 1_000_000},
    8:  {"cost": 4_000_000,   "transfer_limit": 1_500_000},
    9:  {"cost": 5_000_000,   "transfer_limit": 2_250_000},
    10: {"cost": 25_000_000,  "transfer_limit": -1},
}

MAX_LEVEL = 10

# ────────────────────────── СТРАНЫ ──────────────────────────
COUNTRY_CREATION_COST = 249_999          # виндов
ARMY_VEHICLE_COST   = 1_249              # за 1 ед. техники
ARMY_EQUIPMENT_COST = 749                # за 1 ед. снаряжения
ARMY_MISSILE_COST   = 1_749              # за 1 ракету

# ────────────────────────── VIP ──────────────────────────────
VIP_COST_GCOINS = 250                    # G-коинов

# ────────────────────────── МИНИ-ИГРЫ ────────────────────────
MIN_BET = 100                            # виндов

# Лотерея
LOTTERY_TICKET_PRICE  = 10_000
LOTTERY_MAX_PLAYERS   = 5
LOTTERY_WINNER_PRIZE  = 47_500

# Рулетка
ROULETTE_NUMBER_MULTIPLIER  = 35
ROULETTE_COLOR_MULTIPLIER   = 2
ROULETTE_GREEN_MULTIPLIER   = 35

# Дартс
DARTS_BULLSEYE_MULTIPLIER = 3.35

# Мины
MINES_GRID_SIZE = 5
MINES_DIAMOND_MULTIPLIER = 1.25

# Башня
TOWER_LEVELS = 10
TOWER_CELLS  = 5
TOWER_MIN_BOMBS = 1
TOWER_MAX_BOMBS = 4

# ────────────────────────── ЛИДЕРБОРД ────────────────────────
LEADERBOARD_REWARDS: list[int] = [
    200_000,   # 1-е место
    150_000,   # 2-е место
    90_000,    # 3-е место
    60_000,    # 4-е место
    25_000,    # 5-е место
]

LEADERBOARD_EXCLUDED_GAMES: set[str] = {"duel", "russian_roulette"}

# ────────────────────────── СТРАНЫ (дополнительно) ───────────
COUNTRY_MAX_NAME_LENGTH = 32
COUNTRY_MIN_NAME_LENGTH = 2

# Стоимость содержания армии (ежедневно с бюджета)
ARMY_DAILY_VEHICLE_UPKEEP   = 50    # виндов/ед. техники/день
ARMY_DAILY_EQUIPMENT_UPKEEP = 30    # виндов/ед. снаряжения/день
ARMY_DAILY_MISSILE_UPKEEP   = 100   # виндов/ракету/день

# Готовность армии: за каждую единицу техники/снаряжения/ракет
ARMY_READINESS_PER_VEHICLE   = 2.0
ARMY_READINESS_PER_EQUIPMENT = 1.0
ARMY_READINESS_PER_MISSILE   = 5.0
ARMY_READINESS_MAX = 100.0

# Война: минимальная готовность для объявления
WAR_MIN_READINESS = 20.0

# Депозит в бюджет: минимум
COUNTRY_MIN_DEPOSIT = 100

# ────────────────────────── БРАКИ ────────────────────────────
MARRIAGE_CREATION_COST = 5_000           # виндов за регистрацию брака
MARRIAGE_DIVORCE_COST = 10_000           # виндов за развод
MARRIAGE_ADOPT_COST = 2_500              # виндов за усыновление
MARRIAGE_MAX_CHILDREN = 3                # максимум детей

# Уровни брака и награды
# {уровень: {"cost": стоимость_апгрейда, "daily_reward": ежедневная_награда}}
MARRIAGE_LEVELS: dict[int, dict[str, int]] = {
    1:  {"cost": 0,        "daily_reward": 500},
    2:  {"cost": 10_000,   "daily_reward": 1_000},
    3:  {"cost": 25_000,   "daily_reward": 2_000},
    4:  {"cost": 50_000,   "daily_reward": 3_500},
    5:  {"cost": 100_000,  "daily_reward": 5_000},
    6:  {"cost": 200_000,  "daily_reward": 7_500},
    7:  {"cost": 400_000,  "daily_reward": 10_000},
    8:  {"cost": 750_000,  "daily_reward": 15_000},
    9:  {"cost": 1_500_000, "daily_reward": 25_000},
    10: {"cost": 3_000_000, "daily_reward": 50_000},
}
MARRIAGE_MAX_LEVEL = 10

# ────────────────────────── АУКЦИОН ──────────────────────────
AUCTION_MIN_GCOINS = 1                   # минимум G-коинов в ордере
AUCTION_MAX_GCOINS = 10_000              # максимум G-коинов в ордере
AUCTION_MIN_PRICE = 100                  # минимальная цена за 1 G-коин (виндов)
AUCTION_MAX_PRICE = 1_000_000            # максимальная цена за 1 G-коин
AUCTION_FEE_PERCENT = 3                  # комиссия 3%