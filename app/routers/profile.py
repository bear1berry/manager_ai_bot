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
    plan_display_name,
    usage_line,
)
from app.services.payments import format_plan_expiry
from app.services.subscription_copy import (
    feature_lines,
    locked_features,
    plan_badge,
    plan_positioning,
    recommended_upgrade,
    tariff_matrix_text,
    unlocked_features,
)
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

    locked = locked_features(snapshot.plan)
    locked_block = ""
    if locked:
        locked_block = (
            "\n🔒 <b>Закрыто на текущем тарифе</b>\n"
            f"{feature_lines(locked)}\n"
        )

    await message.answer(
        "👤 <b>Профиль</b>\n\n"
        "Это не просто статистика. Это твой кабинет доступа к рабочему AI-контуру.\n\n"
        f"🪪 <b>Тариф:</b> {plan_badge(snapshot.plan)}\n"
        f"⏳ <b>Действует до:</b> <code>{expires_text}</code>\n"
        f"🧭 <b>Позиционирование:</b> {plan_positioning(snapshot.plan)}\n\n"
        "📌 <b>Быстрый обзор</b>\n"
        f"— проектов: <code>{snapshot.projects_total}</code>;\n"
        f"— документов: <code>{snapshot.documents_total}</code>;\n"
        f"— сообщений: <code>{snapshot.messages_total}</code>;\n"
        f"— оценок ответов: <code>{snapshot.feedback_total}</code>.\n\n"
        "✅ <b>Открыто сейчас</b>\n"
        f"{feature_lines(unlocked_features(snapshot.plan))}\n"
        f"{locked_block}\n"
        "Выбери ниже: лимиты, активность или подписка.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "📊 Лимиты")
async def limits_handler(message: Message) -> None:
    settings = get_settings()
    snapshot = await _load_profile_snapshot(message)
    limits = get_plan_limits(settings=settings, plan=snapshot.plan)

    await message.answer(
        "📊 <b>Лимиты</b>\n\n"
        f"Тариф: <b>{plan_display_name(snapshot.plan)}</b>\n"
        f"Смысл тарифа: {plan_positioning(snapshot.plan)}\n\n"
        "<b>Сегодня</b>\n"
        f"{usage_line('Текст', snapshot.text_used, limits.text_limit)}\n"
        f"{usage_line('Голосовые', snapshot.voice_used, limits.voice_limit)}\n\n"
        "<b>Активность сегодня</b>\n"
        f"— сообщений: <code>{snapshot.messages_today}</code>;\n"
        f"— документов: <code>{snapshot.documents_today}</code>.\n\n"
        "Лимиты обновляются ежедневно. Чем тяжелее сценарий, тем больше ценности даёт Pro/Business.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "📈 Активность")
async def activity_handler(message: Message) -> None:
    snapshot = await _load_profile_snapshot(message)

    quality_hint = "нужны оценки"
    if snapshot.feedback_total:
        positive_rate = int((snapshot.feedback_positive / max(snapshot.feedback_total, 1)) * 100)
        quality_hint = f"{positive_rate}% полезных оценок"

    await message.answer(
        "📈 <b>Активность</b>\n\n"
        "Это рабочий след: сколько раз бот помог превратить запрос в результат.\n\n"
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
        f"— не то: <code>{snapshot.feedback_negative}</code>;\n"
        f"— индекс качества: <code>{quality_hint}</code>.\n\n"
        "Чем чаще ты оцениваешь ответы, тем проще докручивать продукт без гадания на логах.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "💎 Подписка")
async def subscription_profile_handler(message: Message) -> None:
    snapshot = await _load_profile_snapshot(message)
    expires_text = format_plan_expiry(snapshot.plan_expires_at, snapshot.plan)

    await message.answer(
        "💎 <b>Подписка</b>\n\n"
        f"Сейчас: <b>{plan_badge(snapshot.plan)}</b>\n"
        f"Действует до: <code>{expires_text}</code>\n\n"
        f"{recommended_upgrade(snapshot.plan)}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"{tariff_matrix_text()}\n\n"
        "<b>История оплат</b>\n"
        f"— успешных оплат: <code>{snapshot.payments_paid}</code>;\n"
        f"— Stars оплачено: <code>{snapshot.stars_paid}</code>.\n\n"
        "Оплата проходит внутри Telegram. После оплаты тариф активируется автоматически.",
        reply_markup=subscription_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(lambda message: message.text == "🌐 Mini App")
async def miniapp_hint_handler(message: Message) -> None:
    settings = get_settings()

    if settings.mini_app_url.strip():
        await message.answer(
            "🌐 <b>Mini App</b>\n\n"
            "Это кабинет управления, а не просто красивая витрина.\n\n"
            "<b>Что внутри</b>\n"
            "— проекты;\n"
            "— документы;\n"
            "— группы;\n"
            "— профиль;\n"
            "— подписка;\n"
            "— история результата.\n\n"
            "<b>Как открыть</b>\n"
            "— нажми системную кнопку рядом с полем ввода;\n"
            "— или отправь команду <code>/miniapp</code>.",
            reply_markup=profile_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        "🌐 <b>Mini App пока не подключён</b>\n\n"
        "В <code>.env</code> нужно указать:\n"
        "<code>MINI_APP_URL=https://...</code>\n\n"
        "После этого перезапусти бота.",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text == "🏠 Главное меню")
async def profile_back_to_main_handler(message: Message) -> None:
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Две главные точки входа: 🧠 Режимы и 👤 Профиль.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
