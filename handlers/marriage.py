"""
Хендлеры браков:
  /брак           — информация о браке
  /женить @user   — предложение брака
  /развод         — развод
  /усыновить @user — усыновление
  /изгнать @user  — изгнание ребёнка
  /семья бюджет   — внести в бюджет
  /семья апгрейд  — повысить уровень
  /семья награда  — забрать ежедневную награду
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

from services.marriage_service import (
    adopt_child,
    claim_daily_reward,
    deposit_to_family,
    divorce,
    get_marriage_info,
    kick_child,
    propose_marriage,
    upgrade_marriage,
)
from services.user_service import find_by_username, get_or_create_user
from utils.constants import (
    MARRIAGE_ADOPT_COST,
    MARRIAGE_CREATION_COST,
    MARRIAGE_DIVORCE_COST,
    MARRIAGE_LEVELS,
    MARRIAGE_MAX_LEVEL,
)
from utils.helpers import format_winds, parse_amount, safe_name

router = Router()

# Ожидающие подтверждения предложений брака
# {target_tg_id: {"proposer_tg_id": ..., "proposer_name": ...}}
_pending_proposals: dict[int, dict] = {}


def _marriage_menu_kb(can_claim: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📊 Инфо", callback_data="m:info"),
            InlineKeyboardButton(text="👶 Дети", callback_data="m:children"),
        ],
        [
            InlineKeyboardButton(text="💰 Бюджет", callback_data="m:budget"),
            InlineKeyboardButton(text="⬆️ Апгрейд", callback_data="m:upgrade"),
        ],
    ]
    if can_claim:
        buttons.append([
            InlineKeyboardButton(text="🎁 Забрать награду", callback_data="m:claim"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════ /брак ════════════════════════════════════


@router.message(Command("брак", "marriage", "семья", "family"))
async def cmd_marriage(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    if command.args:
        args = command.args.strip().split(maxsplit=1)
        action = args[0].lower()
        param = args[1] if len(args) > 1 else ""

        if action in ("бюджет", "budget"):
            return await _budget(message, tg_id, param)
        elif action in ("апгрейд", "upgrade", "уровень"):
            return await _upgrade(message, tg_id)
        elif action in ("награда", "reward", "daily"):
            return await _claim(message, tg_id)

    info = await get_marriage_info(tg_id)
    if not info:
        return await message.answer(
            "💍 <b>Браки</b>\n\n"
            "Ты не в браке.\n\n"
            f"• <code>/женить @username</code> — предложить брак ({format_winds(MARRIAGE_CREATION_COST // 2)} с каждого)\n"
            f"• <code>/развод</code> — развестись ({format_winds(MARRIAGE_DIVORCE_COST)})"
        )

    p1 = info["partner1"]
    p2 = info["partner2"]
    p1_name = safe_name(p1.get("first_name", "?")) if p1 else "?"
    p2_name = safe_name(p2.get("first_name", "?")) if p2 else "?"

    level = info["level"]
    daily = info["daily_reward"]
    can_claim = info["can_claim_reward"]
    children_count = len(info["children"])

    claim_status = "✅ Доступна" if can_claim else "❌ Получена"

    text = (
        f"💍 <b>Брак</b>\n\n"
        f"❤️ {p1_name} + {p2_name}\n"
        f"💰 Бюджет: {format_winds(info['budget'])}\n"
        f"📊 Уровень: {level}/{MARRIAGE_MAX_LEVEL}\n"
        f"🎁 Награда: {format_winds(daily)}/день ({claim_status})\n"
        f"👶 Детей: {children_count}/3"
    )

    await message.answer(text, reply_markup=_marriage_menu_kb(can_claim))


# ═══════════════════ /женить ══════════════════════════════════


@router.message(Command("женить", "marry", "свадьба"))
async def cmd_marry(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    # Проверяем, не в браке ли уже
    info = await get_marriage_info(tg_id)
    if info:
        return await message.answer("❌ Ты уже в браке! Сначала разведись.")

    target_tg_id = None

    # Ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return await message.answer("❌ Нельзя жениться на боте!")
        target_tg_id = target.id
        target_name = safe_name(target.first_name)

    # По @username
    elif command.args and command.args.startswith("@"):
        username = command.args[1:].split()[0]
        user_data = await find_by_username(username)
        if not user_data:
            return await message.answer(f"❌ @{safe_name(username)} не найден.")
        target_tg_id = user_data["telegram_id"]
        target_name = safe_name(user_data.get("first_name", username))

    else:
        return await message.answer(
            "💍 <b>Предложение брака</b>\n\n"
            f"Стоимость: {format_winds(MARRIAGE_CREATION_COST // 2)} с каждого.\n\n"
            "Использование:\n"
            "• Ответь на сообщение: <code>/женить</code>\n"
            "• По юзернейму: <code>/женить @username</code>"
        )

    if target_tg_id == tg_id:
        return await message.answer("❌ Нельзя жениться на себе!")

    # Проверяем, не в браке ли партнёр
    target_info = await get_marriage_info(target_tg_id)
    if target_info:
        return await message.answer(f"❌ {target_name} уже в браке!")

    # Сохраняем предложение
    _pending_proposals[target_tg_id] = {
        "proposer_tg_id": tg_id,
        "proposer_name": safe_name(message.from_user.first_name),
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💍 Принять", callback_data="marry_accept"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data="marry_decline"),
        ]
    ])

    await message.answer(
        f"💍 <b>Предложение руки и сердца!</b>\n\n"
        f"{safe_name(message.from_user.first_name)} предлагает брак {target_name}!\n"
        f"💰 С каждого: {format_winds(MARRIAGE_CREATION_COST // 2)}\n\n"
        f"{target_name}, примешь?",
        reply_markup=kb,
    )


@router.callback_query(F.data == "marry_accept")
async def cb_marry_accept(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    proposal = _pending_proposals.get(tg_id)

    if not proposal:
        return await callback.answer("❌ Предложение не найдено или истекло.", show_alert=True)

    proposer_tg_id = proposal["proposer_tg_id"]

    await get_or_create_user(tg_id, callback.from_user.username, callback.from_user.first_name)

    result = await propose_marriage(proposer_tg_id, tg_id)

    del _pending_proposals[tg_id]

    if not result["ok"]:
        await callback.message.edit_text(f"❌ {result['error']}")
        return await callback.answer()

    await callback.message.edit_text(
        f"💍 <b>Совет да любовь!</b> 🎉\n\n"
        f"{proposal['proposer_name']} и {safe_name(callback.from_user.first_name)} теперь в браке!\n"
        f"💰 С каждого списано: {format_winds(result['cost_each'])}"
    )
    await callback.answer("💍 Поздравляем!", show_alert=True)


@router.callback_query(F.data == "marry_decline")
async def cb_marry_decline(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    if tg_id in _pending_proposals:
        del _pending_proposals[tg_id]

    await callback.message.edit_text("💔 Предложение отклонено.")
    await callback.answer()


# ═══════════════════ /развод ══════════════════════════════════


@router.message(Command("развод", "divorce"))
async def cmd_divorce(message: Message) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    result = await divorce(tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"💔 <b>Развод оформлен.</b>\n\n"
        f"💰 Бюджет разделён: каждому по {format_winds(result['budget_split'])}"
    )


# ═══════════════════ /усыновить ═══════════════════════════════


@router.message(Command("усыновить", "adopt"))
async def cmd_adopt(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    child_tg_id = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return await message.answer("❌ Нельзя усыновить бота!")
        child_tg_id = target.id

    elif command.args and command.args.startswith("@"):
        username = command.args[1:].split()[0]
        user_data = await find_by_username(username)
        if not user_data:
            return await message.answer(f"❌ @{safe_name(username)} не найден.")
        child_tg_id = user_data["telegram_id"]

    else:
        return await message.answer(
            f"👶 <b>Усыновление</b>\n\n"
            f"Стоимость: {format_winds(MARRIAGE_ADOPT_COST)}\n\n"
            f"Использование:\n"
            f"• Ответь на сообщение: <code>/усыновить</code>\n"
            f"• По юзернейму: <code>/усыновить @username</code>"
        )

    result = await adopt_child(tg_id, child_tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer("👶 Ребёнок усыновлён! Добро пожаловать в семью!")


# ═══════════════════ /изгнать ═════════════════════════════════


@router.message(Command("изгнать", "kick"))
async def cmd_kick(message: Message, command: CommandObject) -> None:
    tg_id = message.from_user.id
    await get_or_create_user(tg_id, message.from_user.username, message.from_user.first_name)

    child_tg_id = None

    if message.reply_to_message and message.reply_to_message.from_user:
        child_tg_id = message.reply_to_message.from_user.id

    elif command.args and command.args.startswith("@"):
        username = command.args[1:].split()[0]
        user_data = await find_by_username(username)
        if not user_data:
            return await message.answer(f"❌ @{safe_name(username)} не найден.")
        child_tg_id = user_data["telegram_id"]

    else:
        return await message.answer(
            "Использование:\n"
            "• Ответь на сообщение: <code>/изгнать</code>\n"
            "• По юзернейму: <code>/изгнать @username</code>"
        )

    result = await kick_child(tg_id, child_tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer("👋 Ребёнок изгнан из семьи.")


# ═══════════════════ Бюджет семьи ═════════════════════════════


async def _budget(message: Message, tg_id: int, param: str) -> None:
    if not param:
        info = await get_marriage_info(tg_id)
        if not info:
            return await message.answer("❌ Ты не в браке.")
        return await message.answer(
            f"💰 <b>Семейный бюджет: {format_winds(info['budget'])}</b>\n\n"
            f"Внести: <code>/семья бюджет 1000</code>"
        )

    amount = parse_amount(param)
    if amount is None:
        return await message.answer("❌ Неверная сумма.")

    result = await deposit_to_family(tg_id, amount)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"✅ Внесено {format_winds(amount)} в семейный бюджет.\n"
        f"💰 Твой баланс: {format_winds(result['new_balance'])}\n"
        f"👨‍👩‍👧 Бюджет семьи: {format_winds(result['new_budget'])}"
    )


# ═══════════════════ Апгрейд брака ════════════════════════════


async def _upgrade(message: Message, tg_id: int) -> None:
    result = await upgrade_marriage(tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"⬆️ <b>Уровень брака повышен!</b>\n\n"
        f"📊 Новый уровень: {result['new_level']}\n"
        f"💰 Потрачено: {format_winds(result['cost'])}\n"
        f"👨‍👩‍👧 Бюджет: {format_winds(result['new_budget'])}\n"
        f"🎁 Новая награда: {format_winds(result['new_reward'])}/день"
    )


# ═══════════════════ Награда ══════════════════════════════════


async def _claim(message: Message, tg_id: int) -> None:
    result = await claim_daily_reward(tg_id)
    if not result["ok"]:
        return await message.answer(f"❌ {result['error']}")

    await message.answer(
        f"🎁 <b>Ежедневная награда получена!</b>\n\n"
        f"💰 Всего: {format_winds(result['total_reward'])}\n"
        f"👫 Каждому: {format_winds(result['each_received'])}"
    )


# ═══════════════════ Inline callbacks ═════════════════════════


@router.callback_query(F.data == "m:info")
async def cb_m_info(callback: CallbackQuery) -> None:
    await cmd_marriage(callback.message, type("", (), {"args": None})())
    await callback.answer()


@router.callback_query(F.data == "m:children")
async def cb_m_children(callback: CallbackQuery) -> None:
    info = await get_marriage_info(callback.from_user.id)
    if not info:
        return await callback.answer("❌ Ты не в браке.", show_alert=True)

    children = info["children"]
    if not children:
        return await callback.answer("Детей пока нет.", show_alert=True)

    lines = ["👶 <b>Дети:</b>\n"]
    for c in children:
        name = safe_name(c["user"].get("first_name", "?")) if c["user"] else "?"
        lines.append(f"  • {name}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "m:budget")
async def cb_m_budget(callback: CallbackQuery) -> None:
    await _budget(callback.message, callback.from_user.id, "")
    await callback.answer()


@router.callback_query(F.data == "m:upgrade")
async def cb_m_upgrade(callback: CallbackQuery) -> None:
    await _upgrade(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "m:claim")
async def cb_m_claim(callback: CallbackQuery) -> None:
    await _claim(callback.message, callback.from_user.id)
    await callback.answer()