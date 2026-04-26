from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.limits import plan_display_name
from app.storage.db import connect_db
from app.storage.repositories import AdminRepository, FeedbackRepository, UserRepository

router = Router()


def _is_admin_message(message: Message) -> bool:
    settings = get_settings()
    return settings.is_admin(
        telegram_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
    )


async def _deny(message: Message) -> None:
    await message.answer(
        "⛔ <b>Доступ закрыт</b>\n\n"
        "Эта команда доступна только администратору.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("admin"))
async def admin_panel_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    await message.answer(
        "🛡 <b>Админ-панель</b>\n\n"
        "Доступные команды:\n\n"
        "— <code>/stats</code> — статистика продукта;\n"
        "— <code>/users</code> — последние пользователи;\n"
        "— <code>/queues</code> — состояние очереди;\n"
        "— <code>/feedback</code> — последние оценки ответов;\n"
        "— <code>/setplan telegram_id free|pro|business|admin</code> — сменить тариф.\n\n"
        "Режим владельца нужен не для красоты, а чтобы видеть продукт как систему.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        admin_repo = AdminRepository(db)
        stats = await admin_repo.product_stats()

    await message.answer(
        "📊 <b>Статистика продукта</b>\n\n"
        f"👥 Пользователей всего: <code>{stats['users_total']}</code>\n"
        f"🆕 Новых сегодня: <code>{stats['users_today']}</code>\n\n"
        f"💬 Сообщений всего: <code>{stats['messages_total']}</code>\n"
        f"📨 Сообщений сегодня: <code>{stats['messages_today']}</code>\n\n"
        f"🧠 Текстовых запросов сегодня: <code>{stats['text_usage_today']}</code>\n"
        f"🎧 Голосовых сегодня: <code>{stats['voice_usage_today']}</code>\n\n"
        f"🗂 Проектов всего: <code>{stats['projects_total']}</code>\n"
        f"📄 Активных проектов: <code>{stats['projects_active']}</code>\n\n"
        "👍 <b>Качество ответов</b>\n"
        f"— всего оценок: <code>{stats['feedback_total']}</code>\n"
        f"— полезно: <code>{stats['feedback_positive']}</code>\n"
        f"— не то: <code>{stats['feedback_negative']}</code>\n\n"
        "🧵 <b>Очередь</b>\n"
        f"— pending: <code>{stats['queue_pending']}</code>\n"
        f"— processing: <code>{stats['queue_processing']}</code>\n"
        f"— done: <code>{stats['queue_done']}</code>\n"
        f"— failed: <code>{stats['queue_failed']}</code>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("users"))
async def users_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        admin_repo = AdminRepository(db)
        rows = await admin_repo.latest_users(limit=10)

    if not rows:
        await message.answer(
            "👥 <b>Пользователей пока нет</b>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    lines = ["👥 <b>Последние пользователи</b>\n"]

    for index, row in enumerate(rows, start=1):
        username = f"@{row['username']}" if row["username"] else "без username"
        name = " ".join(
            part for part in [row["first_name"], row["last_name"]]
            if part
        ).strip() or "без имени"

        lines.append(
            f"{index}. <b>{html.escape(name)}</b>\n"
            f"ID: <code>{row['telegram_id']}</code>\n"
            f"Username: <code>{html.escape(username)}</code>\n"
            f"Тариф: <b>{plan_display_name(row['plan'])}</b>\n"
            f"Создан: <code>{row['created_at']}</code>\n"
            f"Обновлён: <code>{row['updated_at']}</code>\n"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("queues"))
async def queues_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        admin_repo = AdminRepository(db)
        stats = await admin_repo.queue_stats()
        failed = await admin_repo.latest_failed_queue(limit=5)

    text = (
        "🧵 <b>Состояние очереди</b>\n\n"
        f"— pending: <code>{stats.get('pending', 0)}</code>\n"
        f"— processing: <code>{stats.get('processing', 0)}</code>\n"
        f"— done: <code>{stats.get('done', 0)}</code>\n"
        f"— failed: <code>{stats.get('failed', 0)}</code>\n"
    )

    if failed:
        text += "\n⚠️ <b>Последние ошибки</b>\n\n"
        for row in failed:
            error = str(row["last_error"] or "без текста ошибки")
            if len(error) > 300:
                error = error[:300].rstrip() + "…"

            text += (
                f"ID: <code>{row['id']}</code>\n"
                f"Тип: <code>{row['kind']}</code>\n"
                f"Попытки: <code>{row['attempts']}</code>\n"
                f"Ошибка: <code>{html.escape(error)}</code>\n\n"
            )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("feedback"))
async def feedback_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        feedback_repo = FeedbackRepository(db)
        stats = await feedback_repo.stats()
        rows = await feedback_repo.latest(limit=10)

    if not rows:
        await message.answer(
            "👍 <b>Оценок пока нет</b>\n\n"
            f"Всего: <code>{stats['total']}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    lines = [
        "👍 <b>Обратная связь</b>\n",
        f"Всего: <code>{stats['total']}</code>",
        f"Полезно: <code>{stats['positive']}</code>",
        f"Не то: <code>{stats['negative']}</code>",
        f"Сегодня: <code>{stats['today']}</code>\n",
    ]

    for index, row in enumerate(rows, start=1):
        username = f"@{row['username']}" if row["username"] else "без username"
        rating = "👍 Полезно" if row["rating"] == "positive" else "👎 Не то"

        comment = str(row["comment"] or "").strip()
        if len(comment) > 250:
            comment = comment[:250].rstrip() + "…"

        message_content = str(row["message_content"] or "").strip()
        if len(message_content) > 250:
            message_content = message_content[:250].rstrip() + "…"

        lines.append(
            f"{index}. <b>{rating}</b>\n"
            f"Пользователь: <code>{html.escape(username)}</code>\n"
            f"Комментарий: <code>{html.escape(comment or '—')}</code>\n"
            f"Ответ: <code>{html.escape(message_content or '—')}</code>\n"
            f"Дата: <code>{row['updated_at']}</code>\n"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text and message.text.startswith("/setplan "))
async def admin_set_plan_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Формат:\n"
            "<code>/setplan telegram_id free|pro|business|admin</code>",
            parse_mode="HTML",
        )
        return

    telegram_id_raw, plan = parts[1], parts[2].lower()

    if not telegram_id_raw.isdigit() or plan not in {"free", "pro", "business", "admin"}:
        await message.answer(
            "Формат:\n"
            "<code>/setplan telegram_id free|pro|business|admin</code>",
            parse_mode="HTML",
        )
        return

    telegram_id = int(telegram_id_raw)

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if user is None:
            await message.answer(
                "⚠️ <b>Пользователь не найден</b>\n\n"
                "Он должен хотя бы один раз нажать <code>/start</code> в боте.",
                parse_mode="HTML",
            )
            return

        await user_repo.set_plan(telegram_id, plan)

    await message.answer(
        f"✅ Тариф пользователя <code>{telegram_id}</code> изменён на <b>{plan_display_name(plan)}</b>.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
