"""
Общий игровой сервис.
Обработка ставок, выплат, запись в game_history и daily_winnings.
Поддержка групповых чатов с настройками.

Все игры используют эти функции.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import pytz

from database.collections import CHATS, GAME_HISTORY, USERS
from database.firestore_client import db_client
from services.leaderboard_service import record_winning
from utils.constants import MIN_BET
from utils.helpers import format_winds

MSK = pytz.timezone("Europe/Moscow")


# ═══════════════════════════════════════════════════════════════
#                    НАСТРОЙКИ ЧАТА
# ═══════════════════════════════════════════════════════════════


async def get_chat_min_bet(chat_id: int | None) -> int:
    """
    Получить минимальную ставку для чата.
    Если chat_id = None (личка), возвращает глобальный MIN_BET.
    """
    if chat_id is None:
        return MIN_BET

    chat = await db_client.get_doc(CHATS, str(chat_id))
    if chat:
        return chat.get("min_bet", MIN_BET)
    return MIN_BET


async def check_games_enabled(chat_id: int | None) -> bool:
    """
    Проверить, включены ли игры в чате.
    В личке всегда True.
    """
    if chat_id is None:
        return True

    chat = await db_client.get_doc(CHATS, str(chat_id))
    if chat:
        return chat.get("games_enabled", True)
    return True


async def increment_chat_stats(
    chat_id: int | None,
    games: int = 0,
    volume: int = 0,
) -> None:
    """
    Увеличить статистику чата.
    games — количество сыгранных игр
    volume — оборот виндов
    """
    if chat_id is None:
        return

    if games > 0:
        await db_client.increment_field(CHATS, str(chat_id), "total_games", games)
    if volume > 0:
        await db_client.increment_field(CHATS, str(chat_id), "total_volume", volume)


# ═══════════════════════════════════════════════════════════════
#                    ПРОВЕРКА И СПИСАНИЕ СТАВКИ
# ═══════════════════════════════════════════════════════════════


async def validate_and_deduct_bet(
    telegram_id: int,
    amount: int,
    chat_id: int | None = None,
) -> dict:
    """
    Проверяет баланс и списывает ставку атомарно.
    Учитывает настройки чата (минимальная ставка, включены ли игры).

    Args:
        telegram_id: ID игрока
        amount: сумма ставки
        chat_id: ID чата (None для личных сообщений)

    Returns:
        {"ok": True, "new_balance": int}
        или
        {"ok": False, "error": str}
    """
    # Проверяем, включены ли игры в чате
    if chat_id is not None:
        games_enabled = await check_games_enabled(chat_id)
        if not games_enabled:
            return {"ok": False, "error": "🚫 Игры отключены в этом чате."}

    # Получаем минимальную ставку для чата
    min_bet = await get_chat_min_bet(chat_id)

    if amount < min_bet:
        return {
            "ok": False,
            "error": f"Минимальная ставка — {format_winds(min_bet)}.",
        }

    def _execute(transaction, db):
        ref = db.collection(USERS).document(str(telegram_id))
        snap = ref.get(transaction=transaction)

        if not snap.exists:
            return {"ok": False, "error": "Ты не зарегистрирован. Напиши /start."}

        user = snap.to_dict()
        balance = user.get("winds_balance", 0)

        if balance < amount:
            return {
                "ok": False,
                "error": (
                    f"Недостаточно виндов.\n"
                    f"Баланс: {format_winds(balance)}\n"
                    f"Ставка: {format_winds(amount)}"
                ),
            }

        new_balance = balance - amount
        transaction.update(ref, {"winds_balance": new_balance})

        return {"ok": True, "new_balance": new_balance}

    return await db_client.run_transaction(_execute)


# ═══════════════════════════════════════════════════════════════
#                    НАЧИСЛЕНИЕ ВЫИГРЫША
# ═══════════════════════════════════════════════════════════════


async def credit_winnings(telegram_id: int, amount: int) -> int:
    """
    Начисляет выигрыш на баланс.

    Args:
        telegram_id: ID игрока
        amount: сумма выигрыша

    Returns:
        Новый баланс игрока
    """
    if amount <= 0:
        doc = await db_client.get_doc(USERS, str(telegram_id))
        return doc.get("winds_balance", 0) if doc else 0

    await db_client.increment_field(
        USERS, str(telegram_id), "winds_balance", amount
    )

    doc = await db_client.get_doc(USERS, str(telegram_id))
    return doc.get("winds_balance", 0) if doc else 0


# ═══════════════════════════════════════════════════════════════
#                    ЗАПИСЬ ИСТОРИИ
# ═══════════════════════════════════════════════════════════════


async def record_game(
    telegram_id: int,
    game_type: str,
    bet_amount: int,
    win_amount: int,
    chat_id: int | None = None,
) -> None:
    """
    Записывает игру в историю + обновляет лидерборд.
    Также обновляет статистику чата, если игра в группе.

    Args:
        telegram_id: ID игрока
        game_type: тип игры (строка, например "flip", "casino")
        bet_amount: ставка
        win_amount: выплата (0 = проигрыш)
        chat_id: ID чата (None для личных сообщений)
    """
    now = datetime.now(MSK).isoformat()
    profit = win_amount - bet_amount

    # Запись в game_history
    game_data = {
        "user_telegram_id": telegram_id,
        "game_type": game_type,
        "bet_amount": bet_amount,
        "win_amount": win_amount,
        "profit": profit,
        "played_at": now,
    }

    # Добавляем chat_id если есть
    if chat_id is not None:
        game_data["chat_id"] = chat_id

    await db_client.add_doc(GAME_HISTORY, game_data)

    # Обновляем лидерборд (только положительный профит)
    if profit > 0:
        await record_winning(telegram_id, game_type, profit)

    # Обновляем статистику чата
    if chat_id is not None:
        await increment_chat_stats(chat_id, games=1, volume=bet_amount)


# ═══════════════════════════════════════════════════════════════
#                    УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ИГРЫ
# ═══════════════════════════════════════════════════════════════


async def play_game(
    telegram_id: int,
    game_type: str,
    bet_amount: int,
    multiplier: float,
    won: bool,
    chat_id: int | None = None,
) -> dict:
    """
    Универсальная функция для простых игр.

    Выполняет все операции:
      1. Проверяет и списывает ставку
      2. Если выиграл — начисляет выигрыш
      3. Записывает в историю и лидерборд

    Args:
        telegram_id: ID игрока
        game_type: тип игры (строка)
        bet_amount: ставка
        multiplier: множитель при выигрыше
        won: True если выиграл
        chat_id: ID чата (None для личных сообщений)

    Returns:
        {
            "ok": True,
            "won": bool,
            "bet": int,
            "win_amount": int,    # 0 если проиграл
            "profit": int,        # отрицательный при проигрыше
            "new_balance": int,
        }
        или {"ok": False, "error": str}
    """
    # 1. Списать ставку
    result = await validate_and_deduct_bet(telegram_id, bet_amount, chat_id)
    if not result["ok"]:
        return result

    balance_after_bet = result["new_balance"]

    # 2. Рассчитать выигрыш
    if won:
        win_amount = int(bet_amount * multiplier)
        new_balance = await credit_winnings(telegram_id, win_amount)
        profit = win_amount - bet_amount
    else:
        win_amount = 0
        new_balance = balance_after_bet
        profit = -bet_amount

    # 3. Записать историю
    await record_game(telegram_id, game_type, bet_amount, win_amount, chat_id)

    return {
        "ok": True,
        "won": won,
        "bet": bet_amount,
        "win_amount": win_amount,
        "profit": profit,
        "new_balance": new_balance,
    }


# ═══════════════════════════════════════════════════════════════
#                    ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════


async def get_user_balance(telegram_id: int) -> int:
    """Получить текущий баланс пользователя."""
    doc = await db_client.get_doc(USERS, str(telegram_id))
    if doc:
        return doc.get("winds_balance", 0)
    return 0


async def check_balance(telegram_id: int, amount: int) -> bool:
    """Проверить, достаточно ли средств (без списания)."""
    balance = await get_user_balance(telegram_id)
    return balance >= amount


async def get_user_game_stats(telegram_id: int, game_type: str = None) -> dict:
    """
    Получить статистику игрока по играм.

    Args:
        telegram_id: ID игрока
        game_type: тип игры (None = все игры)

    Returns:
        {
            "total_games": int,
            "total_bet": int,
            "total_won": int,
            "total_profit": int,
            "win_rate": float,  # процент побед
        }
    """
    filters = [("user_telegram_id", "==", telegram_id)]
    if game_type:
        filters.append(("game_type", "==", game_type))

    results = await db_client.query(GAME_HISTORY, filters=filters, limit=1000)

    total_games = 0
    total_bet = 0
    total_won = 0
    wins = 0

    for doc_id, data in results:
        total_games += 1
        total_bet += data.get("bet_amount", 0)
        win = data.get("win_amount", 0)
        total_won += win
        if win > 0:
            wins += 1

    total_profit = total_won - total_bet
    win_rate = (wins / total_games * 100) if total_games > 0 else 0.0

    return {
        "total_games": total_games,
        "total_bet": total_bet,
        "total_won": total_won,
        "total_profit": total_profit,
        "win_rate": round(win_rate, 1),
    }


async def get_recent_games(
    telegram_id: int,
    limit: int = 10,
) -> list[dict]:
    """
    Получить последние игры пользователя.

    Returns:
        Список словарей с информацией об играх.
    """
    results = await db_client.query(
        GAME_HISTORY,
        filters=[("user_telegram_id", "==", telegram_id)],
        order_by="played_at",
        direction="DESCENDING",
        limit=limit,
    )

    games = []
    for doc_id, data in results:
        games.append({
            "game_type": data.get("game_type", "?"),
            "bet": data.get("bet_amount", 0),
            "win": data.get("win_amount", 0),
            "profit": data.get("profit", 0),
            "played_at": data.get("played_at", ""),
        })

    return games


# ═══════════════════════════════════════════════════════════════
#                    МУЛЬТИПЛЕЕРНЫЕ ИГРЫ
# ═══════════════════════════════════════════════════════════════


async def create_multiplayer_pot(
    players: list[tuple[int, int]],
    game_type: str,
    chat_id: int | None = None,
) -> dict:
    """
    Создать банк для мультиплеерной игры.
    Списывает ставки у всех игроков атомарно.

    Args:
        players: список кортежей (telegram_id, bet_amount)
        game_type: тип игры
        chat_id: ID чата

    Returns:
        {"ok": True, "total_pot": int}
        или {"ok": False, "error": str, "failed_player": int}
    """
    # Проверяем настройки чата
    if chat_id is not None:
        if not await check_games_enabled(chat_id):
            return {"ok": False, "error": "🚫 Игры отключены в этом чате."}

    min_bet = await get_chat_min_bet(chat_id)

    def _execute(transaction, db):
        total_pot = 0

        for tg_id, bet in players:
            if bet < min_bet:
                return {
                    "ok": False,
                    "error": f"Минимальная ставка — {format_winds(min_bet)}.",
                    "failed_player": tg_id,
                }

            ref = db.collection(USERS).document(str(tg_id))
            snap = ref.get(transaction=transaction)

            if not snap.exists:
                return {
                    "ok": False,
                    "error": "Игрок не зарегистрирован.",
                    "failed_player": tg_id,
                }

            user = snap.to_dict()
            balance = user.get("winds_balance", 0)

            if balance < bet:
                return {
                    "ok": False,
                    "error": f"Недостаточно виндов у игрока.",
                    "failed_player": tg_id,
                }

            transaction.update(ref, {"winds_balance": balance - bet})
            total_pot += bet

        return {"ok": True, "total_pot": total_pot}

    return await db_client.run_transaction(_execute)


async def distribute_winnings(
    winners: list[tuple[int, int]],
    losers: list[int],
    game_type: str,
    bets: dict[int, int],
    chat_id: int | None = None,
) -> None:
    """
    Распределить выигрыш в мультиплеерной игре.

    Args:
        winners: список кортежей (telegram_id, win_amount)
        losers: список telegram_id проигравших
        game_type: тип игры
        bets: словарь {telegram_id: bet_amount} для всех игроков
        chat_id: ID чата
    """
    # Начисляем выигрыш победителям
    for tg_id, win_amount in winners:
        await credit_winnings(tg_id, win_amount)
        bet = bets.get(tg_id, 0)
        await record_game(tg_id, game_type, bet, win_amount, chat_id)

    # Записываем проигрыш
    for tg_id in losers:
        bet = bets.get(tg_id, 0)
        await record_game(tg_id, game_type, bet, 0, chat_id)


async def refund_bets(
    players: list[tuple[int, int]],
) -> None:
    """
    Вернуть ставки игрокам (при отмене игры).

    Args:
        players: список кортежей (telegram_id, bet_amount)
    """
    for tg_id, amount in players:
        if amount > 0:
            await credit_winnings(tg_id, amount)