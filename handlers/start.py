"""Хендлеры /start и /help — работают и в группах."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from utils.helpers import mention_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user_data: dict = None) -> None:
    """Приветствие — работает и в личке, и в группе."""
    tg_id = message.from_user.id
    name = message.from_user.first_name or "Игрок"
    is_group = message.chat.type in ("group", "supergroup")

    if is_group:
        # В группе — короткое сообщение
        mention = mention_user(tg_id, name)
        await message.answer(
            f"👋 {mention}, добро пожаловать!\n"
            f"Баланс: <b>{user_data.get('winds_balance', 0):,}</b> виндов\n"
            f"Напиши /help для списка команд."
        )
    else:
        # В личке — полное приветствие
        if user_data and user_data.get("created_at"):
            await message.answer(
                f"С возвращением, <b>{name}</b>! 🎮\n"
                f"Баланс: <b>{user_data.get('winds_balance', 0):,}</b> виндов\n"
                f"Используй /help для списка команд."
            )
        else:
            await message.answer(
                f"👋 Добро пожаловать, <b>{name}</b>!\n"
                f"Твой аккаунт создан. Баланс: 0 виндов.\n"
                f"Используй /help для списка команд."
            )


@router.message(Command("help", "помощь"))
async def cmd_help(message: Message) -> None:
    is_group = message.chat.type in ("group", "supergroup")

    if is_group:
        text = (
            "🎮 <b>Wind Bot — команды</b>\n\n"
            "💰 /balance • /transfer • /level\n"
            "🎲 /казино • /рулетка • /кубик • /флип\n"
            "🎯 /дартс • /футбол • /баскетбол • /боулинг\n"
            "💣 /мины • /башня • /краш • /спин\n"
            "👥 /кнб • /дуэль • /джекпот • /лотерея\n"
            "📊 /top • /profile\n"
            "⚙️ /чат — настройки (админы)\n\n"
            "<i>Полный список: /help в личке бота</i>"
        )
    else:
        text = (
            "<b>🎮 Wind Bot — команды:</b>\n\n"
            "💰 <b>Экономика:</b>\n"
            "/balance — баланс\n"
            "/transfer — перевести винды\n"
            "/level — купить уровень\n\n"
            "🎲 <b>Одиночные игры (мин. 100 виндов):</b>\n"
            "/казино • /рулетка • /слоты • /кубик\n"
            "/краш • /мины • /башня • /дартс\n"
            "/флип • /спин • /нвути • /трейд\n"
            "/охота • /футбол • /баскетбол • /боулинг\n"
            "/вилин • /рр\n\n"
            "👥 <b>Мультиплеер:</b>\n"
            "/кнб • /лотерея • /джекпот • /дуэль\n\n"
            "🏛 <b>Страны:</b> /страна\n"
            "💍 <b>Браки:</b> /брак • /женить • /развод\n"
            "💱 <b>Биржа:</b> /биржа • /продать • /купитьg\n"
            "⭐ <b>VIP:</b> /vip\n"
            "📊 <b>Топ:</b> /top\n\n"
            "💬 <b>В группах:</b>\n"
            "Добавь бота в чат и играй с друзьями!\n"
            "Админы могут настроить: /чат"
        )

    await message.answer(text)