from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, profile_keyboard, subscription_keyboard
from app.config import get_settings
from app.services.limits import (
    get_plan_limits,
    next_plan_suggestion,
    plan_display_name,
    plan_features,
    stars_pricing_summary,
    usage_line,
)
from app.services.payments import format_plan_expiry
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UsageRepository, UserRepository

router = Router()


@dataclass(frozen=True)
class ProfileSnapshot:
    telegram_id: int
    user_db_id: int
    plan: str
    plan_expires_at: str | None
    text_used: int
    voice_used: int
    messages_total: int
    messages_today: int
    projects_total: int
    documents_total: int
    documents_today: int
    feedback_total: int
    feedback_positive: int
    feedback_negative: int
    payments_paid: int
    stars_paid: int


def _html_features(features: list[str]) -> str:
    return "\n".join(f"— {item};" for item in features)


async def _count_scalar(db: Any, sql: str, params: tuple[Any, ...] = ()) -> int:
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()

    if row is None:
        return 0

    return int(row[0] or 0)


async def _load_profile_snapshot(message: Message) -> ProfileSnapshot:
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

        user_db_id = int(user["id"])
        plan = str(user["plan"])
        plan_expires_at = user["plan_expires_at"]

        text_used = await usage_repo.count_today(user_db_id, "text")
        voice_used = await usage_repo.count_today(user_db_id, "voice")

        messages_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM messages WHERE user_id = ?",
            (user_db_id,),
        )
        messages_today = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM messages WHERE user_id = ? AND DATE(created_at) = DATE('now')",
            (user_db_id,),
        )
        projects_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM projects WHERE user_id = ? AND status = 'active'",
            (user_db_id,),
        )
        documents_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM documents WHERE user_id = ?",
            (user_db_id,),
        )
        documents_today = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM documents WHERE user_id = ? AND DATE(created_at) = DATE('now')",
            (user_db_id,),
        )
        feedback_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM feedback WHERE user_id = ?",
            (user_db_id,),
        )
        feedback_positive = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM feedback WHERE user_id = ? AND rating = 'positive'",
            (user_db_id,),
        )
        feedback_negative = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM feedback WHERE user_id = ? AND rating = 'negative'",
            (user_db_id,),
        )
        payments_paid = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'paid'",
            (user_db_id,),
        )
        stars_paid = await _count_scalar(
            db,
            "SELECT COALESCE(SUM(stars_amount), 0) FROM payments WHERE user_id = ? AND status = 'paid'",
            (user_db_id,),
        )

    return ProfileSnapshot(
        telegram_id=message.from_user.id,
        user_db_id=user_db_id,
        plan=plan,
        plan_expires_at=plan_expires_at,
        text_used=text_used,
        voice_used=voice_used,
        messages_total=messages_total,
        messages_today=messages_today,
        projects_total=projects_total,
        documents_total=documents_total,
        documents_today=documents_today,
        feedback_total=feedback_total,
        feedback_positive=feedback_positive,
        feedback_negative=feedback_negative,
        payments_paid=payments_paid,
        stars_paid=stars_paid,
    )


@router.message(Command("profile"))
@router.message(lambda message: message.text == "👤 Профиль")
async def profile_handler(message: Message) -> None:
    snapshot = await _load_profile_snapshot(message)

    expires_text = format_plan_expiry(snapshot.plan_expires_at, snapshot.plan)

    admin_note = ""
    if snapshot.plan == "admin":
        admin_note = "\n🛡 <b>Admin</b>: лимиты отключены, оплата не требуется.\n"

    await message.answer(
        "👤 <b>Профиль</b>\n\n"
        "Короткий центр управления твоим рабочим AI-контуром.\n\n"
        f"🪪 <b>Тариф:</b> {plan_display_name(snapshot.plan)}\n"
        f"⏳ <b>Действует до:</b> <code>{expires_text}</code>\n"
        f"{admin_note}\n"
        "📌 <b>Быстрый обзор</b>\n"
        f"— проектов: <code>{snapshot.projects_total}</code>;\n"
        f"— документов: <code>{snapshot.documents_total}</code>;\n"
        f"— сообщений: <code>{snapshot.messages_total}</code>;\n"
        f"— оценок ответов: <code>{snapshot.feedback_total}</code>.\n\n"
        "Выбери, что открыть ниже.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "📊 Лимиты")
async def limits_handler(message: Message) -> None:
    settings = get_settings()
    snapshot = await _load_profile_snapshot(message)
    limits = get_plan_limits(settings=settings, plan=snapshot.plan)

    plan_note = ""
    if snapshot.plan == "admin":
        plan_note = "\n🛡 <b>Admin-режим:</b> дневные лимиты отключены.\n"

    await message.answer(
        "📊 <b>Лимиты</b>\n\n"
        f"Тариф: <b>{plan_display_name(snapshot.plan)}</b>\n"
        f"{plan_note}\n"
        "<b>Сегодня</b>\n"
        f"{usage_line('Текст', snapshot.text_used, limits.text_limit)}\n"
        f"{usage_line('Голосовые', snapshot.voice_used, limits.voice_limit)}\n\n"
        "<b>Активность сегодня</b>\n"
        f"— сообщений: <code>{snapshot.messages_today}</code>;\n"
        f"— документов: <code>{snapshot.documents_today}</code>.\n\n"
        "Лимиты обновляются ежедневно.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "📈 Активность")
async def activity_handler(message: Message) -> None:
    snapshot = await _load_profile_snapshot(message)

    await message.answer(
        "📈 <b>Активность</b>\n\n"
        "Твоя рабочая статистика внутри бота.\n\n"
        "<b>Всего</b>\n"
        f"— сообщений: <code>{snapshot.messages_total}</code>;\n"
        f"— активных проектов: <code>{snapshot.projects_total}</code>;\n"
        f"— документов: <code>{snapshot.documents_total}</code>;\n"
        f"— оценок ответов: <code>{snapshot.feedback_total}</code>.\n\n"
        "<b>Сегодня</b>\n"
        f"— сообщений: <code>{snapshot.messages_today}</code>;\n"
        f"— документов: <code>{snapshot.documents_today}</code>.\n\n"
        "<b>Качество ответов</b>\n"
        f"— полезно: <code>{snapshot.feedback_positive}</code>;\n"
        f"— не то: <code>{snapshot.feedback_negative}</code>.\n\n"
        "Чем больше оценок, тем проще понимать, где бот реально попадает, а где надо докручивать.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "💎 Подписка")
async def subscription_profile_handler(message: Message) -> None:
    snapshot = await _load_profile_snapshot(message)
    features = plan_features(snapshot.plan)
    expires_text = format_plan_expiry(snapshot.plan_expires_at, snapshot.plan)

    plan_note = ""
    if snapshot.plan == "admin":
        plan_note = "\n🛡 <b>Admin</b>: оплата не требуется, лимиты отключены.\n"
    elif snapshot.plan in {"pro", "business"}:
        plan_note = "\n♻️ Подписку можно продлить заранее. Новый срок прибавится к текущей дате окончания.\n"

    await message.answer(
        "💎 <b>Подписка</b>\n\n"
        f"Текущий тариф: <b>{plan_display_name(snapshot.plan)}</b>\n"
        f"Действует до: <code>{expires_text}</code>\n"
        f"{plan_note}\n"
        "🧩 <b>Доступно сейчас</b>\n"
        f"{_html_features(features)}\n\n"
        f"{next_plan_suggestion(snapshot.plan)}\n\n"
        "⭐ <b>Цены в Telegram Stars</b>\n"
        f"{stars_pricing_summary()}\n\n"
        "<b>История оплат</b>\n"
        f"— успешных оплат: <code>{snapshot.payments_paid}</code>;\n"
        f"— Stars оплачено: <code>{snapshot.stars_paid}</code>.\n\n"
        "Оплата проходит внутри Telegram. После оплаты тариф активируется автоматически.",
        reply_markup=subscription_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "🌐 Mini App")
async def miniapp_hint_handler(message: Message) -> None:
    settings = get_settings()

    if settings.mini_app_url.strip():
        await message.answer(
            "🌐 <b>Mini App</b>\n\n"
            "Кабинет вынесен отдельно от нижнего меню, чтобы не захламлять главный таскбар.\n\n"
            "<b>Как открыть</b>\n"
            "— нажми системную кнопку рядом с полем ввода;\n"
            "— или отправь команду <code>/miniapp</code>.\n\n"
            "Там доступны проекты, документы, подписка и рабочая статистика.",
            reply_markup=profile_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        "🌐 <b>Mini App пока не подключён</b>\n\n"
        "В `.env` нужно указать:\n"
        "<code>MINI_APP_URL=https://...</code>\n\n"
        "После этого перезапусти бота.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "🏠 Главное меню")
async def profile_back_to_main_handler(message: Message) -> None:
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Теперь здесь только два входа: 🧠 Режимы и 👤 Профиль.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
