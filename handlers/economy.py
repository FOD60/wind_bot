"""
Хендлеры экономики:
  /transfer (/перевод) — перевод виндов
  /level   (/уровень)  — информация и покупка уровня
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.economy_service import (
    buy_next_level,
    get_level_info,
    transfer_winds,
)
from services.user_service import find_by_username, get_or_create_user, get_user
from utils.helpers import (
    display_name,
    format_limit,
    format_number,
    format_winds,
    parse_amount,
    safe_name,
)

router = Router()


# ══════════════════════════════════════════════════════════════
#                       /transfer
# ══════════════════════════════════════════════════════════════


async def _parse_transfer_args(
    message: Message, args: str | None
) -> tuple[int | None, int | None, str | None]:
    """
    Разбор аргументов команды /transfer.

    Варианты:
      • Ответ на сообщение:  /transfer 1000
      • По юзернейму:        /transfer @username 1000
      • По Telegram ID:      /transfer 123456789 1000

    Возвращает (target_tg_id, amount, error_text).
    """
    # ── Режим ответа на сообщение ──
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user

        if target.is_bot:
            return None, None, "❌ Нельзя переводить ботам."

        if not args or not args.strip():
            return None, None, (
                "❌ Укажи сумму.\n"
                "Пример: ответь на сообщение и напиши\n"
                "<code>/transfer 1000</code>"
            )

        amount = parse_amount(args.strip())
        if amount is None:
            return None, None, "❌ Неверная сумма. Примеры: 1000, 5к, 1.5м"

        return target.id, amount, None

    # ── Режим @username / ID ──
    if not args or not args.strip():
        return None, None, (
            "❌ Укажи получателя и сумму.\n\n"
            "Примеры:\n"
            "• Ответь на сообщение: <code>/transfer 1к</code>\n"
            "• По юзернейму: <code>/transfer @username 1000</code>\n"
            "• По ID: <code>/transfer 123456789 500</code>"
        )

    parts = args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None, None, (
            "❌ Укажи получателя И сумму.\n"
            "Пример: <code>/transfer @username 1000</code>"
        )

    target_str, amount_str = parts

    amount = parse_amount(amount_str)
    if amount is None:
        return None, None, "❌ Неверная сумма. Примеры: 1000, 5к, 1.5м"

    # По @username
    if target_str.startswith("@"):
        username = target_str[1:]
        if not username:
            return None, None, "❌ Укажи username после @."

        user = await find_by_username(username)
        if user is None:
            return None, None, (
                f"❌ Пользователь @{safe_name(username)} не найден.\n"
                f"Он должен написать /start боту."
            )
        return user["telegram_id"], amount, None

    # По числовому ID
    try:
        target_tg_id = int(target_str)
    except ValueError:
        return None, None, (
            "❌ Неверный формат получателя.\n"
            "Используй @username или числовой ID."
        )

    user = await get_user(target_tg_id)
    if user is None:
        return None, None, (
            f"❌ Пользователь с ID <code>{target_tg_id}</code> не найден.\n"
            f"Он должен написать /start боту."
        )
    return target_tg_id, amount, None


@router.message(Command("transfer", "перевод", "передать"))
async def cmd_transfer(message: Message, command: CommandObject, chat_data: dict = None) -> None:
    """Перевод виндов — работает и в группах."""
    sender_tg_id = message.from_user.id
    chat_id = message.chat.id if message.chat.type in ("group", "supergroup") else None
    is_group = chat_id is not None

    # Проверяем, включены ли переводы в чате
    if chat_data and not chat_data.get("transfers_enabled", True):
        return await message.answer("🚫 Переводы отключены в этом чате.")

    # ... остальная логика без изменений ...

    # В конце добавляем упоминания для групп:
    if is_group:
        sender_mention = mention_user(sender_tg_id, message.from_user.first_name)
        receiver_mention = mention_user(target_tg_id, receiver_name)
        await message.answer(
            f"✅ <b>Перевод выполнен!</b>\n\n"
            f"📤 {sender_mention} → {receiver_mention}\n"
            f"💰 {format_winds(amount)}"
        )
    else:
        await message.answer(
            f"✅ <b>Перевод выполнен!</b>\n\n"
            f"📤 → {receiver_name}\n"
            f"💰 Сумма: <b>{format_winds(amount)}</b>\n"
            f"📊 Твой баланс: {format_winds(result['new_sender_balance'])}"
        )

# ══════════════════════════════════════════════════════════════
#                       /level
# ══════════════════════════════════════════════════════════════


def _level_keyboard(next_level: int, cost: int) -> InlineKeyboardMarkup:
    """Кнопка покупки уровня."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"⬆️ Купить ур. {next_level} за {format_winds(cost)}",
                callback_data="buy_level",
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_level",
            )
        ],
    ])


@router.message(Command("level", "уровень", "lvl"))
async def cmd_level(message: Message) -> None:
    """Информация о текущем уровне и возможность купить следующий."""
    tg_id = message.from_user.id
    await get_or_create_user(
        tg_id, message.from_user.username, message.from_user.first_name
    )

    info = await get_level_info(tg_id)
    if info is None:
        return await message.answer("❌ Ошибка. Напиши /start.")

    level = info["level"]
    limit = info["limit"]
    used = info["used"]
    balance = info["balance"]

    # Текущий лимит
    if limit == -1:
        usage_line = "♾ БЕЗЛИМИТ"
    else:
        usage_line = f"{format_number(used)} / {format_number(limit)} виндов"

    text = (
        f"📊 <b>Уровень: {level} / 10</b>\n\n"
        f"📤 Лимит переводов: {format_limit(limit)}/день\n"
        f"📊 Использовано сегодня: {usage_line}\n"
        f"💰 Баланс: {format_winds(balance)}\n"
    )

    if info["is_max"]:
        text += "\n🏆 <b>Максимальный уровень достигнут!</b>"
        return await message.answer(text)

    # Информация о следующем уровне
    next_level = info["next_level"]
    next_cost = info["next_cost"]
    next_limit = info["next_limit"]
    can_afford = info["can_afford"]

    text += (
        f"\n📈 <b>Следующий уровень: {next_level}</b>\n"
        f"💰 Стоимость: {format_winds(next_cost)}\n"
        f"📤 Новый лимит: {format_limit(next_limit)}/день\n"
    )

    if not can_afford:
        need = next_cost - balance
        text += f"\n⚠️ Не хватает: {format_winds(need)}"
        return await message.answer(text)

    await message.answer(
        text,
        reply_markup=_level_keyboard(next_level, next_cost),
    )


@router.callback_query(F.data == "buy_level")
async def cb_buy_level(callback: CallbackQuery) -> None:
    """Подтверждение покупки уровня."""
    tg_id = callback.from_user.id
    result = await buy_next_level(tg_id)

    if not result["ok"]:
        await callback.message.edit_text(f"❌ {result['error']}")
        return await callback.answer()

    new_level = result["new_level"]
    cost = result["cost"]
    new_limit = result["new_limit"]
    new_balance = result["new_balance"]

    text = (
        f"✅ <b>Уровень повышен!</b>\n\n"
        f"📊 Новый уровень: <b>{new_level}</b>\n"
        f"📤 Лимит переводов: {format_limit(new_limit)}/день\n"
        f"💰 Списано: {format_winds(cost)}\n"
        f"💰 Баланс: {format_winds(new_balance)}"
    )

    await callback.message.edit_text(text)
    await callback.answer("✅ Уровень куплен!")


@router.callback_query(F.data == "cancel_level")
async def cb_cancel_level(callback: CallbackQuery) -> None:
    """Отмена покупки уровня."""
    await callback.message.edit_text("❌ Покупка уровня отменена.")
    await callback.answer()