from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, subscription_keyboard
from app.config import get_settings
from app.services.limits import (
    get_plan_limits,
    next_plan_suggestion,
    plan_display_name,
    plan_features,
    usage_line,
)
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

        user_id = int(user["id"])
        plan = str(user["plan"])

        text_used = await usage_repo.count_today(user_id, "text")
        voice_used = await usage_repo.count_today(user_id, "voice")

    limits = get_plan_limits(settings=settings, plan=plan)
    features = plan_features(plan)

    features_text = "\n".join(f"— {item};" for item in features)

    await message.answer(
        "👤 **Профиль**\n\n"
        f"Telegram ID: `{message.from_user.id}`\n"
        f"Тариф: **{plan_display_name(plan)}**\n\n"
        "📊 **Лимиты на сегодня**\n"
        f"{usage_line('Текст', text_used, limits.text_limit)}\n"
        f"{usage_line('Голосовые', voice_used, limits.voice_limit)}\n\n"
        "🧩 **Доступно сейчас**\n"
        f"{features_text}\n\n"
        f"{next_plan_suggestion(plan)}\n\n"
        "Платёжный слой подключим отдельно: Telegram Stars / Crypto Bot / YooKassa.",
        reply_markup=subscription_keyboard(),
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text == "📊 Лимиты")
async def limits_handler(message: Message) -> None:
    await profile_handler(message)


@router.message(lambda message: message.text == "🏠 Главное меню")
async def profile_back_to_main_handler(message: Message) -> None:
    await message.answer(
        "Главное меню. Работаем дальше.",
        reply_markup=main_keyboard(),
    )
