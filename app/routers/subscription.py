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
        "💎 **Подписка**\n\n"
        "**Free**\n"
        f"— текст: `{free.text_limit}/день`;\n"
        f"— голосовые: `{free.voice_limit}/день`;\n"
        "— базовый ассистент;\n"
        "— проекты и документы в MVP-режиме.\n\n"
        "**Pro**\n"
        f"— текст: `{pro.text_limit}/день`;\n"
        f"— голосовые: `{pro.voice_limit}/день`;\n"
        "— DOCX/PDF документы;\n"
        "— больше проектной работы;\n"
        "— комфортный ежедневный режим.\n\n"
        "**Business**\n"
        f"— текст: `{business.text_limit}/день`;\n"
        f"— голосовые: `{business.voice_limit}/день`;\n"
        "— максимальные лимиты MVP;\n"
        "— будущие бизнес-шаблоны;\n"
        "— база под командное использование.\n\n"
        "**Admin**\n"
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
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text in {"💎 Pro", "🏢 Business"})
async def plan_request_handler(message: Message) -> None:
    selected = "Pro" if message.text == "💎 Pro" else "Business"

    await message.answer(
        f"🧾 **Выбран тариф {selected}**\n\n"
        "Платёжный модуль подключим отдельным слоем.\n\n"
        "План интеграции:\n"
        "1. Telegram Stars — быстрый старт внутри Telegram.\n"
        "2. Crypto Bot — USDT/TON для гибкой оплаты.\n"
        "3. YooKassa — если нужен классический платёжный контур.\n\n"
        "Пока тариф можно активировать вручную через админ-команду:\n"
        "`/setplan telegram_id pro`\n"
        "или\n"
        "`/setplan telegram_id business`\n\n"
        "Админ-режим:\n"
        "`/setplan telegram_id admin`",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text and message.text.startswith("/setplan "))
async def admin_set_plan_handler(message: Message) -> None:
    settings = get_settings()

    if not settings.is_admin(telegram_id=message.from_user.id, username=message.from_user.username):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: `/setplan telegram_id free|pro|business|admin`", parse_mode="Markdown")
        return

    telegram_id_raw, plan = parts[1], parts[2].lower()

    if not telegram_id_raw.isdigit() or plan not in {"free", "pro", "business", "admin"}:
        await message.answer("Формат: `/setplan telegram_id free|pro|business|admin`", parse_mode="Markdown")
        return

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(int(telegram_id_raw))

        if user is None:
            await message.answer(
                "⚠️ Пользователь ещё не найден в базе.\n\n"
                "Он должен хотя бы один раз нажать `/start` в боте.",
                parse_mode="Markdown",
            )
            return

        await user_repo.set_plan(int(telegram_id_raw), plan)

    await message.answer(
        f"✅ Тариф пользователя `{telegram_id_raw}` изменён на **{plan_display_name(plan)}**.",
        parse_mode="Markdown",
    )
