"""Хендлеры для игроков: промокоды и задания."""
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from services.promo_quest_service import activate_promo, get_active_quests, claim_quest_reward
from utils.helpers import format_winds, format_gcoins

router = Router()

@router.message(Command("promo", "промо"))
async def cmd_promo(message: Message, command: CommandObject) -> None:
    if not command.args:
        return await message.answer("Введи код: <code>/promo КОД</code>")
    
    res = await activate_promo(message.from_user.id, command.args)
    if res["ok"]:
        w, g = res["winds"], res["gcoins"]
        text = "🎉 <b>Промокод активирован!</b>\n"
        if w: text += f"💰 +{format_winds(w)}\n"
        if g: text += f"💎 +{format_gcoins(g)}\n"
        await message.answer(text)
    else:
        await message.answer(f"❌ {res['error']}")

@router.message(Command("quests", "задания", "квесты"))
async def cmd_quests(message: Message) -> None:
    quests = await get_active_quests(message.from_user.id)
    if not quests:
        return await message.answer("📭 Пока нет доступных заданий. Возвращайся позже!")
    
    text = "📋 <b>Доступные задания:</b>\nВыполни и нажми 'Проверить'."
    kb = []
    for q in quests:
        kb.append([InlineKeyboardButton(text=f"Перейти: {q['title']} (+{format_winds(q['reward_winds'])})", url=q['url'])])
        kb.append([InlineKeyboardButton(text=f"✅ Проверить '{q['title']}'", callback_data=f"checkq_{q['id']}")])
        
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("checkq_"))
async def cb_check_quest(call: CallbackQuery) -> None:
    q_id = call.data.split("_")[1]
    res = await claim_quest_reward(call.from_user.id, q_id)
    
    if res["ok"]:
        await call.message.answer(f"✅ Задание выполнено! Начислено: <b>{format_winds(res['reward'])}</b>")
        # Обновляем список
        await cmd_quests(call.message)
    else:
        await call.answer(res["error"], show_alert=True)