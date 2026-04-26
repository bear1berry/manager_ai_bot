from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.limits import get_limit
from app.storage.db import connect_db
from app.storage.repositories import UsageRepository, UserRepository

router = Router()


@router.message(Command("profile"))
@router.message(lambda message: message.text == "👤 Профиль")
async def profile_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)

        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user is None:
            user = await user_repo.upsert_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )

        text_used = await usage_repo.count_today(int(user["id"]), "text")
        voice_used = await usage_repo.count_today(int(user["id"]), "voice")

        plan = str(user["plan"])

        text_limit = get_limit(settings, plan, "text")
        voice_limit = get_limit(settings, plan, "voice")

    await message.answer(
        "👤 **Профиль**\n\n"
        f"ID: `{message.from_user.id}`\n"
        f"Тариф: `{plan}`\n\n"
        "**Лимиты сегодня:**\n"
        f"— Текст: `{text_used}/{text_limit}`\n"
        f"— Голосовые: `{voice_used}/{voice_limit}`\n\n"
        "Сейчас монетизация в MVP-режиме: тарифы уже заложены, оплату подключим следующим слоем.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )
