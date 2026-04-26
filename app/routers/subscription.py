from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, subscription_keyboard
from app.config import get_settings
from app.services.limits import get_plan_limits, plan_display_name
from app.storage.db import connect_db
from app.storage.repositories import UserRepository

router = Router()


def _tariff_card(settings) -> str:
    free = get_plan_limits(settings, "free")
    pro = get_plan_limits(settings, "pro")
    business = get_plan_limits(settings, "business")

    return (
        "💎 <b>Подписка</b>\n\n"
        "Тарифы нужны не для красоты. Они разделяют демо-режим, ежедневную работу и бизнес-нагрузку.\n\n"
        "🆓 <b>Free</b>\n"
        f"— текст: <code>{free.text_limit}/день</code>;\n"
        f"— голосовые: <code>{free.voice_limit}/день</code>;\n"
        "— базовый ассистент;\n"
        "— проекты и документы в MVP-режиме.\n\n"
        "💎 <b>Pro</b>\n"
        f"— текст: <code>{pro.text_limit}/день</code>;\n"
        f"— голосовые: <code>{pro.voice_limit}/день</code>;\n"
        "— DOCX/PDF документы;\n"
        "— больше проектной работы;\n"
        "— комфортный ежедневный режим.\n\n"
        "🏢 <b>Business</b>\n"
        f"— текст: <code>{business.text_limit}/день</code>;\n"
        f"— голосовые: <code>{business.voice_limit}/день</code>;\n"
        "— максимальные лимиты MVP;\n"
        "— будущие бизнес-шаблоны;\n"
        "— база под командное использование.\n\n"
        "🛡 <b>Admin</b>\n"
        "— без дневных ограничений;\n"
        "— полный доступ к MVP-функциям;\n"
        "— ручное управление тарифами.\n\n"
        "Сейчас оплата ещё не подключена. Тариф можно активировать вручную через админ-команду."
    )


@router.message(lambda message: message.text == "💎 Подписка")
async def subscription_handler(message: Message) -> None:
    settings = get_settings()

    await message.answer(
        _tariff_card(settings),
        reply_markup=subscription_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text in {"💎 Pro", "🏢 Business"})
async def plan_request_handler(message: Message) -> None:
    selected = "Pro" if message.text == "💎 Pro" else "Business"

    await message.answer(
        f"🧾 <b>Выбран тариф {selected}</b>\n\n"
        "<b>Что дальше</b>\n"
        "Платёжный модуль подключим отдельным слоем.\n\n"
        "<b>План интеграции</b>\n"
        "— Telegram Stars — быстрый старт внутри Telegram;\n"
        "— Crypto Bot — USDT/TON для гибкой оплаты;\n"
        "— YooKassa — классический платёжный контур.\n\n"
        "<b>Временная ручная активация</b>\n"
        "<code>/setplan telegram_id pro</code>\n"
        "<code>/setplan telegram_id business</code>\n"
        "<code>/setplan telegram_id admin</code>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text and message.text.startswith("/setplan "))
async def admin_set_plan_handler(message: Message) -> None:
    settings = get_settings()

    if not settings.is_admin(telegram_id=message.from_user.id, username=message.from_user.username):
        await message.answer("⛔ <b>Команда доступна только администратору.</b>", parse_mode="HTML")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Формат:\n<code>/setplan telegram_id free|pro|business|admin</code>",
            parse_mode="HTML",
        )
        return

    telegram_id_raw, plan = parts[1], parts[2].lower()

    if not telegram_id_raw.isdigit() or plan not in {"free", "pro", "business", "admin"}:
        await message.answer(
            "Формат:\n<code>/setplan telegram_id free|pro|business|admin</code>",
            parse_mode="HTML",
        )
        return

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(int(telegram_id_raw))

        if user is None:
            await message.answer(
                "⚠️ <b>Пользователь не найден</b>\n\n"
                "Он должен хотя бы один раз нажать <code>/start</code> в боте.",
                parse_mode="HTML",
            )
            return

        await user_repo.set_plan(int(telegram_id_raw), plan)

    await message.answer(
        f"✅ Тариф пользователя <code>{telegram_id_raw}</code> изменён на <b>{plan_display_name(plan)}</b>.",
        parse_mode="HTML",
    )
