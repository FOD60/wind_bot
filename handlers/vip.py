"""
Хендлер VIP-статуса.
/vip — информация и покупка
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

from services.vip_service import buy_vip, check_vip_status
from services.user_service import get_or_create_user
from utils.constants import VIP_COST_GCOINS
from utils.helpers import format_gcoins

router = Router()


def _vip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ Купить VIP ({format_gcoins(VIP_COST_GCOINS)} за 30 дней)",
            callback_data="vip_buy",
        )],
    ])


@router.message(Command("vip", "вип"))
async def cmd_vip(message: Message) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    status = await check_vip_status(tg_id)

    if status["is_vip"]:
        expires = status.get("expires_at", "∞")
        days_left = status.get("days_left")
        days_text = f" ({days_left} дн.)" if days_left is not None else ""

        text = (
            f"⭐ <b>У тебя VIP-статус!</b>\n\n"
            f"📅 До: {expires}{days_text}\n\n"
            f"<b>Преимущества:</b>\n"
            f"• 🎨 Особый значок в профиле\n"
            f"• 📈 +10% к выигрышам в играх\n"
            f"• 🚀 Приоритет в поддержке\n"
            f"• 🎁 Эксклюзивные бонусы"
        )
        # Можно продлить
        await message.answer(text, reply_markup=_vip_keyboard())
    else:
        text = (
            f"⭐ <b>VIP-статус</b>\n\n"
            f"💎 Стоимость: {format_gcoins(VIP_COST_GCOINS)} за 30 дней\n\n"
            f"<b>Преимущества:</b>\n"
            f"• 🎨 Особый значок в профиле\n"
            f"• 📈 +10% к выигрышам в играх\n"
            f"• 🚀 Приоритет в поддержке\n"
            f"• 🎁 Эксклюзивные бонусы"
        )
        await message.answer(text, reply_markup=_vip_keyboard())


@router.callback_query(F.data == "vip_buy")
async def cb_vip_buy(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    result = await buy_vip(tg_id, days=30)

    if not result["ok"]:
        return await callback.answer(result["error"], show_alert=True)

    expires = result["expires_at"][:10].replace("-", ".")
    await callback.message.edit_text(
        f"⭐ <b>VIP-статус активирован!</b>\n\n"
        f"📅 Действует до: {expires}\n"
        f"💎 Списано: {format_gcoins(result['cost'])}\n"
        f"💎 Остаток: {format_gcoins(result['new_gcoins'])}"
    )
    await callback.answer("⭐ VIP активирован!", show_alert=True)   