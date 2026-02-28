"""Конфигурация Wind Bot."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    FIREBASE_CREDENTIALS: str = os.getenv(
        "FIREBASE_CREDENTIALS", "./serviceAccountKey.json"
    )
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    TIMEZONE: str = "Europe/Moscow"
    
    # НОВОЕ: Читаем список админов
ADMIN_IDS: list[int] = [7270041746, 7501660940]  # 👈 ВСТАВЬ СВОИ ЦИФРЫ СЮДА


settings = Settings()
