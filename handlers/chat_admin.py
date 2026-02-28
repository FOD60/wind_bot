"""
Команды администратора чата:
  /чат             — информация о чате
  /чат игры вкл    — включить игры
  /чат игры выкл   — выключить игры
  /чат переводы вкл/выкл
  /чат минставка 500
  /чат стата       — статистика чата
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from services.chat_service import get_chat, update_chat_settings, get_chat_stats
from utils.helpers import format_winds, parse_amount

router = Router()


async def _is_chat_admin(message: Message) -> bool:
    """Проверяет, является ли отправитель админом чата."""
    if message.chat.type == "private":
        return True

    try:
        member = await message.bot.get_chat_member(
            message.chat.id, message.from_user.id
        )
        return member.status in ("creator", "administrator")
    except:
        return False


@router.message(Command("чат", "chat"))
async def cmd_chat(message: Message, command: CommandObject) -> None:
    if message.chat.type == "private":
        return await message.answer("ℹ️ Эта команда работает только в группах.")

    chat_id = message.chat.id
    chat_data = await get_chat(chat_id)

    if not command.args:
        # Показать информацию
        if not chat_data:
            return await message.answer("❌ Чат не зарегистрирован.")

        games = "✅" if chat_data.get("games_enabled", True) else "❌"
        transfers = "✅" if chat_data.get("transfers_enabled", True) else "❌"
        min_bet = chat_data.get("min_bet", 100)

        stats = await get_chat_stats(chat_id)

        text = (
            f"💬 <b>Настройки чата</b>\n\n"
            f"🎮 Игры: {games}\n"
            f"💸 Переводы: {transfers}\n"
            f"💰 Мин. ставка: {format_winds(min_bet)}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"🎲 Игр сыграно: {stats['total_games']}\n"
            f"💰 Оборот: {format_winds(stats['total_volume'])}\n\n"
            f"<i>Админы могут настроить:</i>\n"
            f"<code>/чат игры вкл</code>\n"
            f"<code>/чат переводы выкл</code>\n"
            f"<code>/чат минставка 500</code>"
        )
        return await message.answer(text)

    # Проверяем права админа
    if not await _is_chat_admin(message):
        return await message.answer("❌ Только админы могут менять настройки.")

    args = command.args.strip().lower().split()
    action = args[0]

    if action in ("игры", "games"):
        if len(args) < 2:
            return await message.answer("Использование: <code>/чат игры вкл</code> или <code>/чат игры выкл</code>")

        enabled = args[1] in ("вкл", "on", "да", "true", "1")
        await update_chat_settings(chat_id, games_enabled=enabled)
        status = "включены ✅" if enabled else "выключены ❌"
        await message.answer(f"🎮 Игры {status}")

    elif action in ("переводы", "transfers"):
        if len(args) < 2:
            return await message.answer("Использование: <code>/чат переводы вкл</code>")

        enabled = args[1] in ("вкл", "on", "да", "true", "1")
        await update_chat_settings(chat_id, transfers_enabled=enabled)
        status = "включены ✅" if enabled else "выключены ❌"
        await message.answer(f"💸 Переводы {status}")

    elif action in ("минставка", "minbet", "мин"):
        if len(args) < 2:
            return await message.answer("Использование: <code>/чат минставка 500</code>")

        amount = parse_amount(args[1])
        if not amount or amount < 100:
            return await message.answer("❌ Минимум 100 виндов.")
        if amount > 1_000_000:
            return await message.answer("❌ Максимум 1 000 000 виндов.")

        await update_chat_settings(chat_id, min_bet=amount)
        await message.answer(f"💰 Минимальная ставка: {format_winds(amount)}")

    elif action in ("стата", "стат", "stats"):
        stats = await get_chat_stats(chat_id)
        await message.answer(
            f"📊 <b>Статистика чата</b>\n\n"
            f"🎲 Игр сыграно: {stats['total_games']}\n"
            f"💰 Оборот: {format_winds(stats['total_volume'])}"
        )

    else:
        await message.answer(
            "❌ Неизвестная настройка.\n"
            "Доступно: игры, переводы, минставка, стата"
        )