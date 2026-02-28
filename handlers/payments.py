"""Хендлеры для покупки G-коинов за Звёзды (Telegram Stars)."""
from __future__ import annotations

import pytz
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from services.admin_service import change_balance
from database.firestore_client import db_client
from database.collections import DONATION_LOGS
from utils.helpers import format_gcoins

router = Router()

# Пакеты доната: {id_пакета: (цена_в_звездах, кол_во_gcoins, описание)}
# ВАЖНО: Ключи не должны содержать символ подчеркивания "_"
DONATE_PACKAGES = {
    "pack1": (50, 50, "Базовый пакет"),
    "pack2": (250, 275, "Продвинутый (+10%)"),
    "pack3": (500, 600, "Элитный (+20%)"),
    "pack4": (1000, 1300, "Магнат (+30%)"),
}

@router.message(Command("donate", "донат", "купить"))
async def cmd_donate(message: Message) -> None:
    kb = []
    for p_id, data in DONATE_PACKAGES.items():
        stars, gcoins, name = data
        kb.append([InlineKeyboardButton(text=f"⭐️ {stars} Звёзд ➔ 💎 {gcoins} G-коин", callback_data=f"buy_{p_id}")])
        
    await message.answer(
        "💎 <b>Магазин G-коинов</b>\n\n"
        "G-коины используются для покупки VIP, P2P-биржи и других преимуществ.\n"
        "Оплата производится официально через <b>Telegram Stars (⭐️)</b>.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.callback_query(F.data.startswith("buy_"))
async def process_buy_button(call: CallbackQuery) -> None:
    # Разделяем строку по первому "_" и берём вторую часть
    parts = call.data.split("_", 1)
    if len(parts) < 2:
        return await call.answer("Ошибка формата кнопки.", show_alert=True)
        
    pack_id = parts[1]
    
    if pack_id not in DONATE_PACKAGES:
        return await call.answer("Ошибка пакета.", show_alert=True)
    
    stars, gcoins, name = DONATE_PACKAGES[pack_id]
    
    try:
        # Отправляем счет (Invoice) в Звездах (валюта "XTR")
        await call.bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"Покупка {format_gcoins(gcoins)}",
            description=f"Пакет: {name}. Оплата официальными звездами Telegram.",
            payload=f"gcoin_{gcoins}", # Передаем кол-во коинов в payload
            provider_token="", # Для XTR (Звезд) токен провайдера ДОЛЖЕН БЫТЬ ПУСТЫМ!
            currency="XTR",
            prices=[LabeledPrice(label="G-коины", amount=stars)], # amount в XTR
        )
        await call.answer()
    except Exception as e:
        await call.answer("Произошла ошибка при создании счёта. Возможно, бот не настроен для приёма платежей.", show_alert=True)
        print(f"Ошибка отправки инвойса: {e}")


# 1. Telegram спрашивает: "Всё ок, можно списывать?"
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery) -> None:
    await pre_checkout.answer(ok=True)


# 2. Пользователь оплатил, Telegram подтвердил
@router.message(F.successful_payment)
async def process_successful_payment(message: Message) -> None:
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("gcoin_"):
        try:
            gcoins_to_add = int(payload.split("_", 1)[1])
            
            # Начисляем G-коины
            await change_balance(message.from_user.id, gcoins_to_add, "gcoins")
            
            # Логируем
            await db_client.add_doc(DONATION_LOGS, {
                "tg_id": message.from_user.id,
                "stars_spent": payment.total_amount,
                "gcoins_received": gcoins_to_add,
                "date": datetime.now(pytz.timezone("Europe/Moscow")).isoformat()
            })
            
            await message.answer(
                f"🎉 <b>Оплата прошла успешно!</b>\n\n"
                f"Спасибо за поддержку проекта! На твой баланс зачислено <b>{format_gcoins(gcoins_to_add)}</b>.\n"
                f"Проверь баланс: /balance"
            )
        except Exception as e:
            await message.answer("Произошла ошибка при начислении валюты. Пожалуйста, обратитесь к администратору.")
            print(f"Ошибка при обработке успешного платежа: {e}")