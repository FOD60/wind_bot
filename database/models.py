"""
Модели данных Wind Bot (dataclasses).

Firestore — NoSQL, схем нет, но dataclass-ы дают:
  • Документацию полей
  • Типизацию и автодополнение
  • Методы to_dict() / from_dict()
  • Фабрики для создания новых документов

Валюта: винды (основная), G-коин (донатная).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields as dc_fields
from datetime import datetime, date
from typing import Any, Optional


# ══════════════════════════ BASE ══════════════════════════════


@dataclass
class BaseModel:
    """Базовый класс с общей логикой сериализации."""

    def to_dict(self) -> dict:
        """Конвертация в dict для Firestore (убирает None-поля)."""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: dict):
        """Создание из Firestore-документа (игнорирует лишние поля)."""
        valid = {f.name for f in dc_fields(cls)}
        cleaned = {}
        for k, v in data.items():
            if k not in valid:
                continue
            # Firestore DatetimeWithNanoseconds → ISO-строка
            if hasattr(v, "isoformat") and isinstance(v, datetime):
                cleaned[k] = v.isoformat()
            else:
                cleaned[k] = v
        return cls(**cleaned)


# ══════════════════════════ USER ══════════════════════════════


@dataclass
class UserModel(BaseModel):
    """
    Коллекция: users
    Документ ID: str(telegram_id)
    """

    telegram_id: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None

    # Балансы
    winds_balance: int = 2500
    gcoins_balance: int = 0

    # Уровень (1-10)
    level: int = 1

    # Дневной лимит переводов
    daily_transfer_used: int = 0
    last_transfer_reset: str = ""  # "YYYY-MM-DD"

    # VIP
    is_vip: bool = False
    vip_expires_at: Optional[str] = None  # ISO datetime

    # Принадлежность к стране
    country_id: Optional[str] = None  # doc ID страны
    is_president: bool = False

    # Таймстемпы
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def new(
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> UserModel:
        """Фабрика для нового игрока."""
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()
        return UserModel(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_transfer_reset=today,
            created_at=now,
            updated_at=now,
        )


# ══════════════════════════ COUNTRY ═══════════════════════════


@dataclass
class CountryModel(BaseModel):
    """
    Коллекция: countries
    Документ ID: auto
    """

    name: str = ""
    president_telegram_id: int = 0

    # Бюджет
    budget_winds: int = 0

    # Армия
    army_vehicles: int = 0   # техника (1 249 виндов/шт)
    army_equipment: int = 0  # снаряжение (749 виндов/шт)
    army_missiles: int = 0   # ракеты (1 749 виндов/шт)
    army_readiness: float = 0.0  # 0-100 %

    created_at: str = ""

    @staticmethod
    def new(name: str, president_tg_id: int) -> CountryModel:
        return CountryModel(
            name=name,
            president_telegram_id=president_tg_id,
            created_at=datetime.utcnow().isoformat(),
        )


# ══════════════════════════ DIPLOMACY ═════════════════════════


@dataclass
class DiplomacyModel(BaseModel):
    """
    Коллекция: country_diplomacy
    Документ ID: auto
    Пара стран уникальна (country1_id < country2_id).
    status: "alliance" | "war"
    """

    country1_id: str = ""
    country2_id: str = ""
    status: str = ""  # "alliance" | "war"
    created_at: str = ""


# ══════════════════════════ MARRIAGE ══════════════════════════


@dataclass
class MarriageModel(BaseModel):
    """
    Коллекция: marriages
    Документ ID: auto
    """

    partner1_telegram_id: int = 0
    partner2_telegram_id: int = 0
    budget_winds: int = 0
    level: int = 1
    daily_reward_claimed: bool = False
    last_reward_reset: str = ""  # "YYYY-MM-DD"
    is_active: bool = True
    created_at: str = ""

    @staticmethod
    def new(p1_tg_id: int, p2_tg_id: int) -> MarriageModel:
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()
        return MarriageModel(
            partner1_telegram_id=p1_tg_id,
            partner2_telegram_id=p2_tg_id,
            last_reward_reset=today,
            created_at=now,
        )


@dataclass
class MarriageChildModel(BaseModel):
    """
    Коллекция: marriage_children
    Документ ID: auto
    """

    marriage_id: str = ""
    child_telegram_id: int = 0
    adopted_at: str = ""


# ══════════════════════════ AUCTION ═══════════════════════════


@dataclass
class AuctionOrderModel(BaseModel):
    """
    Коллекция: auction_orders
    Документ ID: auto
    order_type: "sell" | "buy"
    """

    user_telegram_id: int = 0
    order_type: str = ""  # "sell" | "buy"
    gcoins_amount: int = 0
    gcoins_filled: int = 0
    price_per_gcoin: int = 0  # цена 1 G-коина в виндах
    is_active: bool = True
    created_at: str = ""

    @property
    def gcoins_remaining(self) -> int:
        return self.gcoins_amount - self.gcoins_filled

    @property
    def total_winds(self) -> int:
        return self.gcoins_amount * self.price_per_gcoin


@dataclass
class AuctionTradeModel(BaseModel):
    """
    Коллекция: auction_trades
    Документ ID: auto
    """

    order_id: str = ""
    buyer_telegram_id: int = 0
    seller_telegram_id: int = 0
    gcoins_amount: int = 0
    winds_amount: int = 0
    traded_at: str = ""


# ══════════════════════════ ЛИДЕРБОРД ═════════════════════════


@dataclass
class DailyWinningsModel(BaseModel):
    """
    Коллекция: daily_winnings
    Документ ID: "{telegram_id}_{YYYY-MM-DD}"
    """

    user_telegram_id: int = 0
    date: str = ""  # "YYYY-MM-DD"
    total_winnings: int = 0


@dataclass
class LeaderboardRewardModel(BaseModel):
    """
    Коллекция: leaderboard_rewards
    Документ ID: auto
    """

    user_telegram_id: int = 0
    date: str = ""  # за какой день
    rank: int = 0   # место 1-5
    reward_amount: int = 0
    created_at: str = ""


# ══════════════════════════ ИГРЫ ══════════════════════════════


@dataclass
class GameSessionModel(BaseModel):
    """
    Коллекция: game_sessions
    Документ ID: auto
    Мультиплеерные сессии (КНБ, Лотерея, Джекпот, Дуэль).
    """

    game_type: str = ""
    status: str = "waiting"  # waiting | in_progress | finished | cancelled
    bet_amount: int = 0
    pot: int = 0
    max_players: int = 2
    winner_telegram_id: Optional[int] = None
    data: Optional[dict] = None
    created_at: str = ""
    finished_at: Optional[str] = None


@dataclass
class GameSessionPlayerModel(BaseModel):
    """
    Коллекция: game_session_players
    Документ ID: auto
    """

    session_id: str = ""
    user_telegram_id: int = 0
    bet_amount: int = 0
    is_winner: bool = False
    data: Optional[dict] = None


@dataclass
class GameHistoryModel(BaseModel):
    """
    Коллекция: game_history
    Документ ID: auto
    Лог каждой одиночной игры.
    """

    user_telegram_id: int = 0
    game_type: str = ""
    bet_amount: int = 0
    win_amount: int = 0   # 0 = проигрыш
    profit: int = 0       # win_amount - bet_amount
    played_at: str = ""

# ══════════════════════════ ЧАТЫ ══════════════════════════════


@dataclass
class ChatModel(BaseModel):
    """
    Коллекция: chats
    Документ ID: str(chat_id)
    """

    chat_id: int = 0
    title: Optional[str] = None
    chat_type: str = ""  # "group", "supergroup", "private"

    # Настройки
    games_enabled: bool = True
    transfers_enabled: bool = True
    min_bet: int = 100  # Минимальная ставка в этом чате

    # Статистика
    total_games: int = 0
    total_volume: int = 0  # Общий оборот виндов

    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def new(chat_id: int, title: str = None, chat_type: str = "group") -> "ChatModel":
        now = datetime.utcnow().isoformat()
        return ChatModel(
            chat_id=chat_id,
            title=title,
            chat_type=chat_type,
            created_at=now,
            updated_at=now,
        )