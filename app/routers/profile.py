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
from app.services.payments import format_plan_expiry
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UsageRepository, UserRepository

router = Router()


def _html_features(features: list[str]) -> str:
    return "\n".join(f"— {item};" for item in features)


@router.message(Command("profile"))
@router.message(lambda message: message.text == "👤 Профиль")
async def profile_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)

        await ensure_user(user_repo, message.from_user)
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
        plan_expires_at = user["plan_expires_at"]

        text_used = await usage_repo.count_today(user_id, "text")
        voice_used = await usage_repo.count_today(user_id, "voice")

    limits = get_plan_limits(settings=settings, plan=plan)
    features = plan_features(plan)
    expires_text = format_plan_expiry(plan_expires_at, plan)

    await message.answer(
        "👤 <b>Профиль</b>\n\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Тариф: <b>{plan_display_name(plan)}</b>\n"
        f"Действует до: <code>{expires_text}</code>\n\n"
        "📊 <b>Лимиты на сегодня</b>\n"
        f"{usage_line('Текст', text_used, limits.text_limit)}\n"
        f"{usage_line('Голосовые', voice_used, limits.voice_limit)}\n\n"
        "🧩 <b>Доступно сейчас</b>\n"
        f"{_html_features(features)}\n\n"
        f"{next_plan_suggestion(plan)}\n\n"
        "⭐ <b>Оплата</b>\n"
        "Подписка подключается через Telegram Stars.",
        reply_markup=subscription_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "📊 Лимиты")
async def limits_handler(message: Message) -> None:
    await profile_handler(message)


@router.message(lambda message: message.text == "🏠 Главное меню")
async def profile_back_to_main_handler(message: Message) -> None:
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери раздел в нижнем меню или напиши задачу.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
