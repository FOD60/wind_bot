"""
Хендлеры стран:
  /страна            — меню страны
  /страна создать    — создание
  /страна инфо       — информация
  /страна вступить   — вступление
  /страна выйти      — выход
  /страна бюджет     — операции с бюджетом
  /страна армия      — покупка армии
  /страна дипломатия — союзы, войны
  /страна список     — все страны
  /страна распустить — удалить страну
  /страна передать   — передать президентство
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

from services.country_service import (
    break_alliance,
    buy_army,
    create_country,
    declare_war,
    deposit_to_budget,
    disband_country,
    get_country_by_name,
    get_country_info,
    get_user_country,
    join_country,
    leave_country,
    list_countries,
    make_peace,
    propose_alliance,
    transfer_presidency,
    withdraw_from_budget,
)
from services.user_service import find_by_username, get_or_create_user
from utils.constants import (
    ARMY_EQUIPMENT_COST,
    ARMY_MISSILE_COST,
    ARMY_VEHICLE_COST,
    COUNTRY_CREATION_COST,
)
from utils.helpers import format_number, format_winds, parse_amount, safe_name

router = Router()


# ═══════════════════ Главное меню ═════════════════════════════

def _country_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Инфо", callback_data="c:info"),
            InlineKeyboardButton(text="👥 Участники", callback_data="c:members"),
        ],
        [
            InlineKeyboardButton(text="💰 Бюджет", callback_data="c:budget"),
            InlineKeyboardButton(text="⚔️ Армия", callback_data="c:army"),
        ],
        [
            InlineKeyboardButton(text="🤝 Дипломатия", callback_data="c:diplo"),
            InlineKeyboardButton(text="🌍 Все страны", callback_data="c:list"),
        ],
    ])


@router.message(Command("страна", "country"))
async def cmd_country(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        country = await get_user_country(tg_id)
        if country:
            await message.answer(
                f"🏛 Ты в стране: <b>{safe_name(country.get('name', '?'))}</b>\n\n"
                f"Что хочешь сделать?",
                reply_markup=_country_menu_kb(),
            )
        else:
            await message.answer(
                "🏛 <b>Страны</b>\n\n"
                "Ты не состоишь в стране.\n\n"
                f"• <code>/страна создать Название</code> — создать ({format_winds(COUNTRY_CREATION_COST)})\n"
                f"• <code>/страна вступить Название</code> — вступить\n"
                f"• <code>/страна список</code> — все страны"
            )
        return

    args = command.args.strip()
    sub = args.split(maxsplit=1)
    action = sub[0].lower()
    param = sub[1] if len(sub) > 1 else ""

    if action in ("создать", "create"):
        await _create(message, tg_id, param)
    elif action in ("вступить", "join"):
        await _join(message, tg_id, param)
    elif action in ("выйти", "leave"):
        await _leave(message, tg_id)
    elif action in ("инфо", "info"):
        await _info(message, tg_id)
    elif action in ("бюджет", "budget"):
        await _budget(message, tg_id, param)
    elif action in ("армия", "army"):
        await _army(message, tg_id, param)
    elif action in ("дипломатия", "diplo"):
        await _diplo(message, tg_id, param)
    elif action in ("список", "list"):
        await _list(message)
    elif action in ("распустить", "disband"):
        await _disband(message, tg_id)
    elif action in ("передать", "transfer"):
        await _transfer_pres(message, tg_id, param)
    else:
        await message.answer(
            "❌ Неизвестная подкоманда.\n"
            "Доступно: создать, вступить, выйти, инфо, бюджет, армия, дипломатия, список, распустить, передать"
        )


# ═══════════════════ Создание ═════════════════════════════════

async def _create(message: Message, tg_id: int, name: str) -> None:
    if not name:
        return await message.answer(
            f"Использование: <code>/страна создать Название</code>\n"
            f"Стоимость: {format_winds(COUNTRY_CREATION_COST)}"
        )

    result = await create_country(tg_id, name)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"🏛 <b>Страна «{safe_name(result['name'])}» создана!</b>\n\n"
        f"👑 Ты — президент!\n"
        f"💰 Списано: {format_winds(result['cost'])}\n"
        f"📊 Баланс: {format_winds(result['new_balance'])}"
    )


# ═══════════════════ Вступление ═══════════════════════════════

async def _join(message: Message, tg_id: int, name: str) -> None:
    if not name:
        return await message.answer("Использование: <code>/страна вступить Название</code>")

    target = await get_country_by_name(name.strip())
    if not target:
        return await message.answer(f"❌ Страна «{safe_name(name)}» не найдена.")

    country_id, country_data = target
    result = await join_country(tg_id, country_id)

    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(f"✅ Ты вступил в страну <b>{safe_name(result['country_name'])}</b>!")


# ═══════════════════ Выход ════════════════════════════════════

async def _leave(message: Message, tg_id: int) -> None:
    result = await leave_country(tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")
    await message.answer("✅ Ты покинул страну.")


# ═══════════════════ Информация ═══════════════════════════════

async def _info(message: Message, tg_id: int) -> None:
    country_data = await get_user_country(tg_id)
    if not country_data:
        return await message.answer("❌ Ты не в стране.")

    info = await get_country_info(country_data["_id"])
    if not info:
        return await message.answer("❌ Страна не найдена.")

    c = info["country"]
    p = info["president"]
    pres_name = safe_name(p.get("first_name", "?")) if p else "?"

    alliances = [d for d in info["diplomacy"] if d["status"] == "alliance"]
    wars = [d for d in info["diplomacy"] if d["status"] == "war"]

    alliance_text = ", ".join(d["other_name"] for d in alliances) or "—"
    war_text = ", ".join(d["other_name"] for d in wars) or "—"

    text = (
        f"🏛 <b>{safe_name(c.get('name', '?'))}</b>\n\n"
        f"👑 Президент: {pres_name}\n"
        f"👥 Участников: {info['member_count']}\n"
        f"💰 Бюджет: {format_winds(c.get('budget_winds', 0))}\n\n"
        f"⚔️ <b>Армия:</b>\n"
        f"  🚛 Техника: {c.get('army_vehicles', 0)}\n"
        f"  🛡 Снаряжение: {c.get('army_equipment', 0)}\n"
        f"  🚀 Ракеты: {c.get('army_missiles', 0)}\n"
        f"  📊 Готовность: {info['readiness']:.1f}%\n\n"
        f"🤝 Союзы: {alliance_text}\n"
        f"⚔️ Войны: {war_text}"
    )
    await message.answer(text)


# ═══════════════════ Бюджет ═══════════════════════════════════

async def _budget(message: Message, tg_id: int, param: str) -> None:
    if not param:
        return await message.answer(
            "💰 <b>Бюджет страны</b>\n\n"
            "• <code>/страна бюджет внести 1000</code>\n"
            "• <code>/страна бюджет снять 1000</code> (президент)"
        )

    parts = param.strip().split(maxsplit=1)
    action = parts[0].lower()
    amount_str = parts[1] if len(parts) > 1 else ""

    amount = parse_amount(amount_str) if amount_str else None
    if amount is None:
        return await message.answer("❌ Укажи сумму.")

    if action in ("внести", "deposit", "в"):
        result = await deposit_to_budget(tg_id, amount)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(
            f"✅ Внесено {format_winds(amount)} в бюджет.\n"
            f"💰 Твой баланс: {format_winds(result['new_balance'])}\n"
            f"🏛 Бюджет: {format_winds(result['new_budget'])}"
        )

    elif action in ("снять", "withdraw", "с"):
        result = await withdraw_from_budget(tg_id, amount)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(
            f"✅ Снято {format_winds(amount)} из бюджета.\n"
            f"💰 Твой баланс: {format_winds(result['new_balance'])}\n"
            f"🏛 Бюджет: {format_winds(result['new_budget'])}"
        )
    else:
        await message.answer("❌ Используй: <b>внести</b> или <b>снять</b>.")


# ═══════════════════ Армия ════════════════════════════════════

async def _army(message: Message, tg_id: int, param: str) -> None:
    if not param:
        return await message.answer(
            "⚔️ <b>Армия</b>\n\n"
            f"🚛 Техника — {format_winds(ARMY_VEHICLE_COST)}/шт\n"
            f"🛡 Снаряжение — {format_winds(ARMY_EQUIPMENT_COST)}/шт\n"
            f"🚀 Ракеты — {format_winds(ARMY_MISSILE_COST)}/шт\n\n"
            "Покупка из бюджета (президент):\n"
            "<code>/страна армия техника 10</code>\n"
            "<code>/страна армия снаряжение 20</code>\n"
            "<code>/страна армия ракеты 5</code>"
        )

    parts = param.strip().split(maxsplit=1)
    unit_text = parts[0].lower()
    qty_str = parts[1] if len(parts) > 1 else ""

    unit_map = {
        "техника": "vehicles", "техн": "vehicles", "т": "vehicles",
        "снаряжение": "equipment", "снар": "equipment", "с": "equipment",
        "ракеты": "missiles", "ракета": "missiles", "р": "missiles",
    }

    unit_type = unit_map.get(unit_text)
    if not unit_type:
        return await message.answer("❌ Тип: техника, снаряжение, ракеты.")

    try:
        qty = int(qty_str) if qty_str else 0
    except ValueError:
        qty = 0

    if qty <= 0:
        return await message.answer("❌ Укажи количество > 0.")

    result = await buy_army(tg_id, unit_type, qty)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"✅ Куплено: {result['unit_name']} x{result['quantity']}\n"
        f"💰 Стоимость: {format_winds(result['total_cost'])}\n"
        f"📊 Всего: {result['new_count']} ед.\n"
        f"🏛 Бюджет: {format_winds(result['new_budget'])}\n"
        f"⚔️ Готовность: {result['readiness']:.1f}%"
    )


# ═══════════════════ Дипломатия ═══════════════════════════════

async def _diplo(message: Message, tg_id: int, param: str) -> None:
    if not param:
        return await message.answer(
            "🤝 <b>Дипломатия</b>\n\n"
            "Команды (президент):\n"
            "<code>/страна дипломатия союз Название</code>\n"
            "<code>/страна дипломатия война Название</code>\n"
            "<code>/страна дипломатия мир Название</code>\n"
            "<code>/страна дипломатия разорвать Название</code>"
        )

    parts = param.strip().split(maxsplit=1)
    action = parts[0].lower()
    target_name = parts[1].strip() if len(parts) > 1 else ""

    if not target_name:
        return await message.answer("❌ Укажи название страны.")

    if action in ("союз", "alliance", "с"):
        result = await propose_alliance(tg_id, target_name)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(
            f"🤝 Союз заключён!\n"
            f"<b>{result['my_name']}</b> 🤝 <b>{result['target_name']}</b>"
        )

    elif action in ("война", "war", "в"):
        result = await declare_war(tg_id, target_name)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(
            f"⚔️ <b>ВОЙНА ОБЪЯВЛЕНА!</b>\n"
            f"<b>{result['my_name']}</b> ⚔️ <b>{result['target_name']}</b>"
        )

    elif action in ("мир", "peace", "м"):
        result = await make_peace(tg_id, target_name)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(f"🕊 Мир заключён с <b>{result['target_name']}</b>!")

    elif action in ("разорвать", "break", "р"):
        result = await break_alliance(tg_id, target_name)
        if not result["ok"]:
            return await message.answer(f"❌ {result['error']}")
        await message.answer(f"💔 Союз с <b>{result['target_name']}</b> разорван.")

    else:
        await message.answer("❌ Действия: союз, война, мир, разорвать.")


# ═══════════════════ Список стран ═════════════════════════════

async def _list(message: Message) -> None:
    countries = await list_countries(limit=20)
    if not countries:
        return await message.answer("🌍 Стран пока нет. Создай первую: <code>/страна создать</code>")

    lines = ["🌍 <b>Список стран:</b>\n"]
    for i, (doc_id, data) in enumerate(countries, 1):
        name = safe_name(data.get("name", "?"))
        budget = format_number(data.get("budget_winds", 0))
        lines.append(f"  {i}. <b>{name}</b> — 💰 {budget}")

    await message.answer("\n".join(lines))


# ═══════════════════ Распустить ═══════════════════════════════

async def _disband(message: Message, tg_id: int) -> None:
    result = await disband_country(tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")
    await message.answer("🏚 Страна распущена. Все участники свободны.")


# ═══════════════════ Передать президентство ═══════════════════

async def _transfer_pres(message: Message, tg_id: int, param: str) -> None:
    if not param:
        return await message.answer(
            "Использование: <code>/страна передать @username</code>"
        )

    if param.startswith("@"):
        username = param[1:]
        target_user = await find_by_username(username)
        if not target_user:
            return await message.answer(f"❌ @{safe_name(username)} не найден.")
        target_tg_id = target_user["telegram_id"]
    else:
        try:
            target_tg_id = int(param)
        except ValueError:
            return await message.answer("❌ Укажи @username или ID.")

    result = await transfer_presidency(tg_id, target_tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer("✅ Президентство передано! Ты больше не президент.")


# ═══════════════════ Inline callbacks ═════════════════════════

@router.callback_query(F.data == "c:info")
async def cb_info(callback: CallbackQuery) -> None:
    await _info(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "c:members")
async def cb_members(callback: CallbackQuery) -> None:
    from services.country_service import get_country_members, get_user_country

    country = await get_user_country(callback.from_user.id)
    if not country:
        return await callback.answer("❌ Ты не в стране.", show_alert=True)

    members = await get_country_members(country["_id"])
    if not members:
        return await callback.answer("Нет участников.", show_alert=True)

    lines = [f"👥 <b>Участники ({len(members)}):</b>\n"]
    for m in members:
        name = safe_name(m.get("first_name", "?"))
        prefix = "👑 " if m.get("is_president") else "  "
        lines.append(f"{prefix}{name}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "c:budget")
async def cb_budget(callback: CallbackQuery) -> None:
    country = await get_user_country(callback.from_user.id)
    if not country:
        return await callback.answer("❌ Ты не в стране.", show_alert=True)

    await callback.message.answer(
        f"💰 <b>Бюджет: {format_winds(country.get('budget_winds', 0))}</b>\n\n"
        f"• <code>/страна бюджет внести 1000</code>\n"
        f"• <code>/страна бюджет снять 1000</code> (президент)"
    )
    await callback.answer()


@router.callback_query(F.data == "c:army")
async def cb_army(callback: CallbackQuery) -> None:
    await _army(callback.message, callback.from_user.id, "")
    await callback.answer()


@router.callback_query(F.data == "c:diplo")
async def cb_diplo(callback: CallbackQuery) -> None:
    await _diplo(callback.message, callback.from_user.id, "")
    await callback.answer()


@router.callback_query(F.data == "c:list")
async def cb_list(callback: CallbackQuery) -> None:
    await _list(callback.message)
    await callback.answer()