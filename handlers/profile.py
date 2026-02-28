"""
Хендлеры профиля: /balance (/баланс), /profile (/профиль).
"""
from __future__ import annotations

from aiogram import Router
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from database.collections import COUNTRIES
from database.firestore_client import db_client
from services.economy_service import get_balance_info
from services.user_service import get_or_create_user
from utils.helpers import (
    display_name,
    format_gcoins,
    format_limit,
    format_number,
    format_winds,
    safe_name,
)

router = Router()

# Алиасы для баланса
BALANCE_ALIASES = {"б", "баланс", "balance", "$", "money"}


@router.message(Command("balance", "баланс"))
@router.message(F.text.lower().in_(BALANCE_ALIASES))
async def cmd_balance(message: Message) -> None:
    """Быстрый просмотр баланса."""
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    info = await get_balance_info(tg_id)
    if info is None:
        return await message.answer("❌ Ошибка. Напиши /start.")

    level = info["level"]
    limit = info["transfer_limit"]
    used = info["transfer_used"]

    if limit == -1:
        limit_text = "♾ БЕЗЛИМИТ"
    else:
        limit_text = f"{format_number(used)} / {format_number(limit)}"

    text = (
        f"💰 <b>{format_winds(info['winds_balance'])}</b>\n"
        f"💎 <b>{format_gcoins(info['gcoins_balance'])}</b>\n"
        f"📊 Уровень {level} │ Лимит: {limit_text}"
    )

    await message.answer(text)


# ═══════════════════ /profile ═════════════════════════════════


PROFILE_ALIASES = {"п", "профиль", "проф", "profile", "me", "я"}


@router.message(Command("profile", "профиль"))
@router.message(F.text.lower().in_(PROFILE_ALIASES))
async def cmd_profile(message: Message) -> None:
    """Подробный профиль игрока."""
    tg_id = message.from_user.id
    user_data = await get_or_create_user(
        tg_id, message.from_user.username, message.from_user.first_name
    )
    info = await get_balance_info(tg_id)
    if info is None:
        return await message.answer("❌ Ошибка. Напиши /start.")

    level = info["level"]
    limit = info["transfer_limit"]
    used = info["transfer_used"]
    remaining = info["transfer_remaining"]

    # Лимит переводов
    if limit == -1:
        limit_line = "♾ БЕЗЛИМИТ"
    else:
        limit_line = (
            f"{format_winds(used)} из {format_winds(limit)}\n"
            f"      Осталось: {format_winds(remaining)}"
        )

    # VIP
    if info["is_vip"]:
        vip_line = "⭐ Да"
        if info.get("vip_expires_at"):
            vip_line += f" (до {info['vip_expires_at'][:10]})"
    else:
        vip_line = "Нет"

    # Страна
    country_line = "—"
    if info.get("country_id"):
        country_doc = await db_client.get_doc(COUNTRIES, info["country_id"])
        if country_doc:
            country_line = safe_name(country_doc.get("name", "—"))

    # Дата регистрации
    created = user_data.get("created_at", "")[:10]
    if created:
        parts = created.split("-")
        if len(parts) == 3:
            created = f"{parts[2]}.{parts[1]}.{parts[0]}"

    name = safe_name(
        message.from_user.first_name, "Игрок"
    )
    uname = f" (@{safe_name(message.from_user.username)})" if message.from_user.username else ""

    text = (
        f"👤 <b>Профиль: {name}{uname}</b>\n"
        f"🆔 <code>{tg_id}</code>\n"
        f"\n"
        f"💰 Баланс: <b>{format_winds(info['winds_balance'])}</b>\n"
        f"💎 G-коины: <b>{format_gcoins(info['gcoins_balance'])}</b>\n"
        f"📊 Уровень: <b>{level}</b> / 10\n"
        f"📤 Переводы: {limit_line}\n"
        f"⭐ VIP: {vip_line}\n"
        f"🏛 Страна: {country_line}\n"
        f"\n"
        f"📅 Регистрация: {created}"
    )

    await message.answer(text)