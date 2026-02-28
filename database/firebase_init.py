"""
Инициализация Firebase Admin SDK + Firestore.
Вызовите init_firebase() один раз при старте приложения.
Далее используйте get_db() для получения Firestore-клиента.
"""
from __future__ import annotations

import logging

import firebase_admin
from firebase_admin import credentials, firestore

from config import settings

logger = logging.getLogger(__name__)

_db = None
_initialized = False


def init_firebase():
    """Инициализирует Firebase App и возвращает Firestore client."""
    global _db, _initialized
    if _initialized:
        return _db

    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred)
    _db = firestore.client()
    _initialized = True
    logger.info("Firebase инициализирован, Firestore подключён.")
    return _db


def get_db():
    """Возвращает Firestore client (инициализирует при первом вызове)."""
    if _db is None:
        return init_firebase()
    return _db
