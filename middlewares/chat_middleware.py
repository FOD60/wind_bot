"""
Middleware для регистрации и проверки настроек чата.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from services.chat_service import get_or_create_chat


class ChatMiddleware(BaseMiddleware):
    """Регистрирует чат и передаёт его настройки в хендлер."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.chat:
            chat = event.chat

            # Только для групп и супергрупп регистрируем
            if chat.type in ("group", "supergroup"):
                chat_data = await get_or_create_chat(
                    chat_id=chat.id,
                    title=chat.title,
                    chat_type=chat.type,
                )
                data["chat_data"] = chat_data
                data["is_group"] = True
            else:
                data["chat_data"] = None
                data["is_group"] = False

        return await handler(event, data)