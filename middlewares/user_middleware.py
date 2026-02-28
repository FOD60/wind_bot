"""
Middleware для автоматической регистрации пользователей и проверки банов.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from services.user_service import get_or_create_user


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None

        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user and not user.is_bot:
            user_data = await get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
            )
            
            # ⛔ ПРОВЕРКА НА БАН
            if user_data.get("is_banned"):
                if isinstance(event, CallbackQuery):
                    await event.answer("❌ Ты заблокирован.", show_alert=True)
                return  # Прерываем обработку
            
            data["user_data"] = user_data

        return await handler(event, data)