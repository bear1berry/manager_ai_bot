from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, subscription_keyboard
from app.config import get_settings
from app.storage.db import connect_db
from app.storage.repositories import UserRepository

router = Router()


@router.message(lambda message: message.text == "💎 Подписка")
async def subscription_handler(message: Message) -> None:
    await message.answer(
        "💎 **Подписка**\n\n"
        "**Free**\n"
        "— базовый ассистент;\n"
        "— ограниченные голосовые;\n"
        "— без расширенной памяти.\n\n"
        "**Pro**\n"
        "— больше запросов;\n"
        "— документы DOCX/PDF;\n"
        "— больше голосовых;\n"
        "— проекты.\n\n"
        "**Business**\n"
        "— высокие лимиты;\n"
        "— больше проектной памяти;\n"
        "— будущие бизнес-шаблоны.\n\n"
        "В MVP можно вручную активировать тариф через админа.",
        reply_markup=subscription_keyboard(),
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text in {"💎 Pro", "🏢 Business"})
async def plan_request_handler(message: Message) -> None:
    await message.answer(
        "🧾 **Тариф выбран**\n\n"
        "Платёжный модуль подключим отдельным слоем: Telegram Stars / Crypto Bot / YooKassa.\n\n"
        "Для MVP логика тарифов уже есть: лимиты, профиль, ограничения и ручная активация.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text and message.text.startswith("/setplan "))
async def admin_set_plan_handler(message: Message) -> None:
    settings = get_settings()

    if message.from_user.id not in settings.admin_ids:
        await message.answer("⛔ Команда доступна только администратору.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: `/setplan telegram_id free|pro|business`", parse_mode="Markdown")
        return

    telegram_id_raw, plan = parts[1], parts[2].lower()

    if not telegram_id_raw.isdigit() or plan not in {"free", "pro", "business"}:
        await message.answer("Формат: `/setplan telegram_id free|pro|business`", parse_mode="Markdown")
        return

    async with await connect_db(settings.database_path) as db:
        await UserRepository(db).set_plan(int(telegram_id_raw), plan)

    await message.answer(f"✅ Тариф пользователя `{telegram_id_raw}` изменён на `{plan}`.", parse_mode="Markdown")
