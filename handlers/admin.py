"""
Хендлеры админ-панели:
  /admin        — меню админа и статистика
  /give @user 100  — выдать винды
  /giveg @user 100 — выдать G-коины
  /take @user 100  — забрать винды
  /ban @user       — забанить
  /unban @user     — разбанить
  /broadcast       — рассылка (на всех пользователей)
  /makepromo       — создать промокод
  /addquest        — создать задание
  /delquest        — удалить задание
"""
from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message

from config import settings
from services.admin_service import change_balance, get_bot_stats, set_ban_status
from services.user_service import find_by_username
from services.promo_quest_service import create_promo, add_quest, del_quest
from utils.helpers import format_gcoins, format_winds, parse_amount


class IsAdmin(BaseFilter):
    """Фильтр: пропускает только админов."""
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in settings.ADMIN_IDS


router = Router()
# Применяем фильтр ко всем хендлерам в этом роутере
router.message.filter(IsAdmin())


async def _get_target_id(message: Message, args: str) -> tuple[int | None, str | None]:
    """Вспомогательная функция для поиска ID по реплаю, @username или ID."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, None
        
    if not args:
        return None, "Укажи @username, ID или ответь на сообщение."
        
    target_str = args.split()[0]
    
    if target_str.startswith("@"):
        user_data = await find_by_username(target_str[1:])
        if not user_data:
            return None, f"Пользователь {target_str} не найден."
        return user_data["telegram_id"], None
        
    if target_str.isdigit():
        return int(target_str), None
        
    return None, "Неверный формат. Используй @username или ID."


# ═══════════════════ Главное меню ═════════════════════════════


@router.message(Command("admin", "админ"))
async def cmd_admin(message: Message) -> None:
    stats = await get_bot_stats()
    
    text = (
        f"👑 <b>Панель Администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Игроков: <b>{stats['users']}</b> (в бане: {stats['banned']})\n"
        f"💰 Всего виндов: <b>{format_winds(stats['winds'])}</b>\n"
        f"💎 Всего G-коинов: <b>{format_gcoins(stats['gcoins'])}</b>\n\n"
        f"🛠 <b>Экономика:</b>\n"
        f"• <code>/give @user 1000</code> — выдать винды\n"
        f"• <code>/giveg @user 10</code> — выдать G-коины\n"
        f"• <code>/take @user 1000</code> — забрать винды\n"
        f"• <code>/ban @user</code> / <code>/unban @user</code>\n\n"
        f"🎟 <b>Промо и Квесты:</b>\n"
        f"• <code>/makepromo КОД ВИНДЫ GКОИНЫ ЛИМИТ</code>\n"
        f"• <code>/addquest ID | Текст | Ссылка | Награда</code>\n"
        f"• <code>/delquest ID</code>\n\n"
        f"📢 <b>Рассылка:</b>\n"
        f"• <code>/broadcast текст</code>"
    )
    await message.answer(text)


# ═══════════════════ Экономика ════════════════════════════════


@router.message(Command("give", "add"))
async def cmd_give(message: Message, command: CommandObject) -> None:
    target_id, err = await _get_target_id(message, command.args)
    if err:
        return await message.answer(f"❌ {err}")
        
    parts = command.args.split() if command.args else []
    if len(parts) < (1 if message.reply_to_message else 2):
        return await message.answer("❌ Укажи сумму. Пример: <code>/give @user 10к</code>")
        
    amount_str = parts[-1]
    amount = parse_amount(amount_str)
    if not amount:
        return await message.answer("❌ Неверная сумма.")
        
    res = await change_balance(target_id, amount, "winds")
    if not res["ok"]:
        return await message.answer(f"❌ {res['error']}")
        
    await message.answer(f"✅ Успешно! Выдано {format_winds(amount)}.\nНовый баланс: {format_winds(res['new_balance'])}")


@router.message(Command("take", "remove"))
async def cmd_take(message: Message, command: CommandObject) -> None:
    target_id, err = await _get_target_id(message, command.args)
    if err:
        return await message.answer(f"❌ {err}")
        
    parts = command.args.split() if command.args else []
    if len(parts) < (1 if message.reply_to_message else 2):
        return await message.answer("❌ Укажи сумму.")
        
    amount = parse_amount(parts[-1])
    if not amount:
        return await message.answer("❌ Неверная сумма.")
        
    res = await change_balance(target_id, -amount, "winds")
    if not res["ok"]:
        return await message.answer(f"❌ {res['error']}")
        
    await message.answer(f"✅ Изъято {format_winds(amount)}.\nНовый баланс: {format_winds(res['new_balance'])}")


@router.message(Command("giveg", "addg"))
async def cmd_give_gcoins(message: Message, command: CommandObject) -> None:
    target_id, err = await _get_target_id(message, command.args)
    if err:
        return await message.answer(f"❌ {err}")
        
    parts = command.args.split() if command.args else []
    if len(parts) < (1 if message.reply_to_message else 2):
        return await message.answer("❌ Укажи сумму.")
        
    amount = parse_amount(parts[-1])
    if not amount:
        return await message.answer("❌ Неверная сумма.")
        
    res = await change_balance(target_id, amount, "gcoins")
    if not res["ok"]:
        return await message.answer(f"❌ {res['error']}")
        
    await message.answer(f"✅ Выдано {format_gcoins(amount)}.\nНовый баланс: {format_gcoins(res['new_balance'])}")


# ═══════════════════ Баны ═════════════════════════════════════


@router.message(Command("ban", "бан"))
async def cmd_ban(message: Message, command: CommandObject) -> None:
    target_id, err = await _get_target_id(message, command.args)
    if err:
        return await message.answer(f"❌ {err}")
        
    if target_id in settings.ADMIN_IDS:
        return await message.answer("❌ Нельзя забанить админа!")
        
    success = await set_ban_status(target_id, True)
    if success:
        await message.answer(f"🔨 Пользователь <code>{target_id}</code> забанен.")
    else:
        await message.answer("❌ Пользователь не найден в БД.")


@router.message(Command("unban", "разбан"))
async def cmd_unban(message: Message, command: CommandObject) -> None:
    target_id, err = await _get_target_id(message, command.args)
    if err:
        return await message.answer(f"❌ {err}")
        
    success = await set_ban_status(target_id, False)
    if success:
        await message.answer(f"🕊 Пользователь <code>{target_id}</code> разбанен.")
    else:
        await message.answer("❌ Пользователь не найден в БД.")


# ═══════════════════ Рассылка ═════════════════════════════════


@router.message(Command("broadcast", "рассылка"))
async def cmd_broadcast(message: Message, command: CommandObject) -> None:
    if not command.args:
        return await message.answer("❌ Напиши текст для рассылки после команды.")
        
    text = command.args
    stats = await get_bot_stats()
    users = stats["all_user_ids"]
    
    await message.answer(f"📢 Начинаю рассылку для {len(users)} пользователей...")
    
    sent = 0
    blocked = 0
    
    for tg_id in users:
        try:
            await message.bot.send_message(chat_id=tg_id, text=text)
            sent += 1
        except Exception:
            blocked += 1
            
        await asyncio.sleep(0.05)
        
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Успешно отправлено: {sent}\n"
        f"Заблокировали бота: {blocked}"
    )


# ═══════════════════ Промокоды и Квесты ═══════════════════════


@router.message(Command("makepromo"))
async def cmd_makepromo(message: Message, command: CommandObject) -> None:
    if not command.args:
        return await message.answer(
            "🎟 <b>Создание промокода</b>\n"
            "Формат: <code>/makepromo КОД ВИНДЫ G-КОИНЫ ЛИМИТ</code>\n"
            "Пример: <code>/makepromo FREE 5000 10 100</code>"
        )
    parts = command.args.split()
    try:
        res = await create_promo(parts[0], int(parts[1]), int(parts[2]), int(parts[3]))
        if res["ok"]:
            await message.answer(f"✅ Промокод <b>{parts[0]}</b> создан!")
        else:
            await message.answer(f"❌ {res['error']}")
    except Exception:
        await message.answer("❌ Ошибка формата. Проверь пробелы и числа.")


@router.message(Command("addquest"))
async def cmd_addquest(message: Message, command: CommandObject) -> None:
    if not command.args:
        return await message.answer(
            "📋 <b>Создание задания</b>\n"
            "Формат: <code>/addquest ID | Текст | Ссылка | Награда_Виндов</code>\n"
            "Пример: <code>/addquest sub1 | Подпишись на канал | https://t.me/durov | 10000</code>"
        )
    parts = [p.strip() for p in command.args.split("|")]
    if len(parts) == 4:
        try:
            await add_quest(parts[0], parts[1], parts[2], int(parts[3]))
            await message.answer(f"✅ Задание <b>{parts[0]}</b> успешно добавлено!")
        except Exception as e:
            await message.answer(f"❌ Ошибка при добавлении задания: {e}")
    else:
        await message.answer("❌ Ошибка формата. Не забудь разделитель `|`")


@router.message(Command("delquest"))
async def cmd_delquest(message: Message, command: CommandObject) -> None:
    if not command.args:
        return await message.answer("Укажи ID задания: <code>/delquest sub1</code>")
    await del_quest(command.args.strip())
    await message.answer(f"✅ Задание <b>{command.args.strip()}</b> удалено.")