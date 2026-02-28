"""
Хендлеры P2P-биржи (Аукцион):
  /биржа          — главное меню
  /продать        — создать ордер на продажу G-коинов
  /купитьg        — создать ордер на покупку G-коинов
  /ордера         — мои ордера
  /отменить       — отменить ордер
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

from services.auction_service import (
    cancel_order,
    create_buy_order,
    create_sell_order,
    execute_order,
    get_buy_orders,
    get_my_orders,
    get_sell_orders,
)
from services.user_service import get_or_create_user
from utils.constants import AUCTION_FEE_PERCENT
from utils.helpers import format_gcoins, format_number, format_winds, parse_amount

router = Router()


def _auction_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Продажа G", callback_data="auc:sells"),
            InlineKeyboardButton(text="📉 Покупка G", callback_data="auc:buys"),
        ],
        [
            InlineKeyboardButton(text="📋 Мои ордера", callback_data="auc:my"),
        ],
    ])


@router.message(Command("биржа", "auction", "аукцион", "p2p"))
async def cmd_auction(message: Message) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    await message.answer(
        f"💱 <b>P2P-биржа G-коинов</b>\n\n"
        f"Здесь игроки сами устанавливают курс!\n"
        f"Комиссия: {AUCTION_FEE_PERCENT}%\n\n"
        f"<b>Команды:</b>\n"
        f"• <code>/продать 10 5000</code> — продать 10 G по 5000 виндов\n"
        f"• <code>/купитьg 5 4000</code> — купить 5 G по 4000 виндов\n"
        f"• <code>/ордера</code> — мои ордера\n"
        f"• <code>/отменить ID</code> — отменить ордер",
        reply_markup=_auction_menu_kb(),
    )


# ═══════════════════ Создание ордеров ═════════════════════════


@router.message(Command("продать", "sell"))
async def cmd_sell(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "💱 <b>Продать G-коины</b>\n\n"
            "Формат: <code>/продать КОЛИЧЕСТВО ЦЕНА</code>\n"
            "Пример: <code>/продать 10 5000</code>\n"
            "(Продать 10 G-коинов по 5000 виндов за штуку)"
        )

    parts = command.args.strip().split()
    if len(parts) < 2:
        return await message.answer("❌ Укажи количество и цену.\nПример: <code>/продать 10 5000</code>")

    try:
        gcoins = int(parts[0])
    except ValueError:
        return await message.answer("❌ Неверное количество.")

    price = parse_amount(parts[1])
    if price is None:
        return await message.answer("❌ Неверная цена.")

    result = await create_sell_order(tg_id, gcoins, price)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"✅ <b>Ордер на продажу создан!</b>\n\n"
        f"💎 Продаю: {result['gcoins']} G-коин(ов)\n"
        f"💰 Цена: {format_winds(result['price'])}/шт\n"
        f"💵 Итого получишь: {format_winds(result['total'])}\n"
        f"🆔 ID: <code>{result['order_id'][:8]}...</code>"
    )


@router.message(Command("купитьg", "buyg", "купить_g"))
async def cmd_buy_g(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "💱 <b>Купить G-коины</b>\n\n"
            "Формат: <code>/купитьg КОЛИЧЕСТВО ЦЕНА</code>\n"
            "Пример: <code>/купитьg 5 4000</code>\n"
            "(Купить 5 G-коинов по 4000 виндов за штуку)"
        )

    parts = command.args.strip().split()
    if len(parts) < 2:
        return await message.answer("❌ Укажи количество и цену.")

    try:
        gcoins = int(parts[0])
    except ValueError:
        return await message.answer("❌ Неверное количество.")

    price = parse_amount(parts[1])
    if price is None:
        return await message.answer("❌ Неверная цена.")

    result = await create_buy_order(tg_id, gcoins, price)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"✅ <b>Ордер на покупку создан!</b>\n\n"
        f"💎 Покупаю: {result['gcoins']} G-коин(ов)\n"
        f"💰 Цена: {format_winds(result['price'])}/шт\n"
        f"💵 Заморожено: {format_winds(result['total'])}\n"
        f"🆔 ID: <code>{result['order_id'][:8]}...</code>"
    )


# ═══════════════════ Мои ордера ═══════════════════════════════


@router.message(Command("ордера", "orders", "мои_ордера"))
async def cmd_my_orders(message: Message) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    orders = await get_my_orders(tg_id)
    if not orders:
        return await message.answer("📋 У тебя нет активных ордеров.")

    lines = ["📋 <b>Твои ордера:</b>\n"]
    for doc_id, data in orders:
        o_type = "ПРОДАЖА" if data.get("order_type") == "sell" else "ПОКУПКА"
        remaining = data.get("gcoins_amount", 0) - data.get("gcoins_filled", 0)
        price = data.get("price_per_gcoin", 0)

        lines.append(
            f"• <code>{doc_id[:8]}</code> | {o_type}\n"
            f"  {remaining} G × {format_number(price)} = {format_winds(remaining * price)}"
        )

    lines.append(f"\nОтменить: <code>/отменить ID</code>")
    await message.answer("\n".join(lines))


# ═══════════════════ Отмена ордера ════════════════════════════


@router.message(Command("отменить", "cancel"))
async def cmd_cancel_order(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id

    if not command.args:
        return await message.answer("Использование: <code>/отменить ID_ОРДЕРА</code>")

    order_id = command.args.strip()

    # Пробуем найти по частичному ID
    orders = await get_my_orders(tg_id)
    found_id = None
    for doc_id, _ in orders:
        if doc_id.startswith(order_id) or doc_id == order_id:
            found_id = doc_id
            break

    if not found_id:
        return await message.answer("❌ Ордер не найден.")

    result = await cancel_order(tg_id, found_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(f"✅ Ордер отменён.\n💰 Возвращено: {result['refund']}")


# ═══════════════════ Просмотр ордеров ═════════════════════════


async def _show_sells(message: Message) -> None:
    orders = await get_sell_orders(limit=10)
    if not orders:
        return await message.answer("📈 Нет активных ордеров на продажу.")

    lines = ["📈 <b>Ордера на продажу G-коинов:</b>\n"]
    for doc_id, data in orders:
        remaining = data.get("gcoins_amount", 0) - data.get("gcoins_filled", 0)
        price = data.get("price_per_gcoin", 0)

        lines.append(
            f"<code>{doc_id[:8]}</code> | {remaining} G × {format_number(price)} виндов"
        )

    lines.append(f"\n💡 Купить: отправь <code>/исполнить ID КОЛИЧЕСТВО</code>")
    await message.answer("\n".join(lines))


async def _show_buys(message: Message) -> None:
    orders = await get_buy_orders(limit=10)
    if not orders:
        return await message.answer("📉 Нет активных ордеров на покупку.")

    lines = ["📉 <b>Ордера на покупку G-коинов:</b>\n"]
    for doc_id, data in orders:
        remaining = data.get("gcoins_amount", 0) - data.get("gcoins_filled", 0)
        price = data.get("price_per_gcoin", 0)

        lines.append(
            f"<code>{doc_id[:8]}</code> | {remaining} G × {format_number(price)} виндов"
        )

    lines.append(f"\n💡 Продать: отправь <code>/исполнить ID КОЛИЧЕСТВО</code>")
    await message.answer("\n".join(lines))


# ═══════════════════ Исполнение ордера ════════════════════════


@router.message(Command("исполнить", "execute", "fill"))
async def cmd_execute(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if not command.args:
        return await message.answer(
            "Использование: <code>/исполнить ID КОЛИЧЕСТВО</code>\n"
            "Пример: <code>/исполнить abc123 5</code>"
        )

    parts = command.args.strip().split()
    if len(parts) < 2:
        return await message.answer("❌ Укажи ID ордера и количество.")

    partial_id = parts[0]
    try:
        qty = int(parts[1])
    except ValueError:
        return await message.answer("❌ Неверное количество.")

    # Ищем ордер
    sells = await get_sell_orders(limit=50)
    buys = await get_buy_orders(limit=50)
    all_orders = sells + buys

    found_id = None
    for doc_id, _ in all_orders:
        if doc_id.startswith(partial_id):
            found_id = doc_id
            break

    if not found_id:
        return await message.answer("❌ Ордер не найден.")

    result = await execute_order(tg_id, found_id, qty)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    status = "полностью" if result["complete"] else "частично"
    await message.answer(
        f"✅ <b>Сделка исполнена ({status})!</b>\n\n"
        f"💎 G-коинов: {result['gcoins']}\n"
        f"💰 Виндов: {format_winds(result['winds'])}\n"
        f"📊 Комиссия: {format_winds(result['fee'])}"
    )


# ═══════════════════ Callbacks ════════════════════════════════


@router.callback_query(F.data == "auc:sells")
async def cb_sells(callback: CallbackQuery) -> None:
    await _show_sells(callback.message)
    await callback.answer()


@router.callback_query(F.data == "auc:buys")
async def cb_buys(callback: CallbackQuery) -> None:
    await _show_buys(callback.message)
    await callback.answer()


@router.callback_query(F.data == "auc:my")
async def cb_my_orders(callback: CallbackQuery) -> None:
    await cmd_my_orders(callback.message)
    await callback.answer()