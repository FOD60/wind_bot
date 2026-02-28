"""Вспомогательные функции Wind Bot."""
from __future__ import annotations

import html as _html
from typing import Optional


def format_winds(amount: int) -> str:
    """Склонение: 1 винда, 2 винды, 5 виндов."""
    abs_amount = abs(amount)
    last_two = abs_amount % 100
    last_one = abs_amount % 10

    if 11 <= last_two <= 19:
        word = "виндов"
    elif last_one == 1:
        word = "винда"
    elif 2 <= last_one <= 4:
        word = "винды"
    else:
        word = "виндов"

    return f"{amount:,} {word}".replace(",", " ")


def format_gcoins(amount: int) -> str:
    """Склонение G-коинов."""
    abs_a = abs(amount)
    lt = abs_a % 100
    lo = abs_a % 10
    if 11 <= lt <= 19:
        w = "G-коинов"
    elif lo == 1:
        w = "G-коин"
    elif 2 <= lo <= 4:
        w = "G-коина"
    else:
        w = "G-коинов"
    return f"{amount:,} {w}".replace(",", " ")


def format_number(n: int) -> str:
    """1234567 → '1 234 567'."""
    return f"{n:,}".replace(",", " ")


def format_limit(limit: int) -> str:
    """Лимит переводов: -1 → БЕЗЛИМИТ, иначе форматированные винды."""
    if limit == -1:
        return "♾ БЕЗЛИМИТ"
    return format_winds(limit)


def parse_amount(text: str) -> Optional[int]:
    """
    Парсинг суммы с русскими сокращениями:
      1к / 1k   → 1 000
      1.5к      → 1 500
      1м / 1m   → 1 000 000
      1кк / 1kk → 1 000 000
      500       → 500

    Возвращает None если формат неверный или число <= 0.
    """
    if not text:
        return None

    text = text.strip().lower().replace(" ", "").replace(",", ".")

    multipliers = [
        ("кк", 1_000_000),
        ("kk", 1_000_000),
        ("к", 1_000),
        ("k", 1_000),
        ("м", 1_000_000),
        ("m", 1_000_000),
    ]

    for suffix, mult in multipliers:
        if text.endswith(suffix):
            num_part = text[: -len(suffix)]
            if not num_part:
                return None
            try:
                result = int(round(float(num_part) * mult))
                return result if result > 0 else None
            except (ValueError, OverflowError):
                return None

    try:
        result = int(float(text))
        return result if result > 0 else None
    except (ValueError, OverflowError):
        return None


def safe_name(text: Optional[str], fallback: str = "Игрок") -> str:
    """HTML-safe отображение имени."""
    if not text:
        return fallback
    return _html.escape(text)


def display_name(user_data: dict) -> str:
    """Красивое имя пользователя для сообщений."""
    username = user_data.get("username")
    if username:
        return f"@{safe_name(username)}"
    return safe_name(user_data.get("first_name"), "Игрок")


def mention_user(user_id: int, name: str) -> str:
    """Создаёт HTML-ссылку на пользователя для упоминания."""
    safe = safe_name(name)
    return f'<a href="tg://user?id={user_id}">{safe}</a>'


def get_user_mention(message_or_user) -> tuple[int, str]:
    """
    Извлекает ID и имя для упоминания из Message или User.
    
    Args:
        message_or_user: объект Message или User из aiogram
        
    Returns:
        Кортеж (telegram_id, mention_html)
    """
    if hasattr(message_or_user, 'from_user'):
        user = message_or_user.from_user
    else:
        user = message_or_user

    name = user.first_name or user.username or "Игрок"
    return user.id, mention_user(user.id, name)