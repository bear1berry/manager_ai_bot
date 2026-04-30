from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from app.bot.keyboards import main_keyboard
from app.services.observability import build_admin_status_text
from app.services.audit import (
    audit_events_for_telegram_id,
    audit_events_text,
    audit_stats_24h,
    audit_stats_text,
    latest_audit_events,
    safe_record_audit_event,
)
from app.services.backup import (
    backup_created_text,
    backup_list_text,
    backup_status_text,
    create_backup,
    files_safe_to_send,
)
from app.config import get_settings
from app.services.diagnostics import run_diagnostics
from app.services.limits import plan_display_name
from app.services.security import admin_security_report
from app.services.payments import format_plan_expiry
from app.storage.db import connect_db
from app.storage.repositories import AdminRepository, FeedbackRepository, PaymentRepository, UserRepository

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
        "— <code>/payments</code> — последние платежи Stars;\n"
        "— <code>/setplan telegram_id free|pro|business|admin [days]</code> — сменить тариф.\n\n"
        "Режим владельца нужен, чтобы видеть продукт как систему.",
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
        "⭐ <b>Telegram Stars</b>\n"
        f"— платежей всего: <code>{stats['payments_total']}</code>\n"
        f"— оплачено: <code>{stats['payments_paid']}</code>\n"
        f"— отклонено: <code>{stats['payments_rejected']}</code>\n"
        f"— Stars получено: <code>{stats['stars_paid']}</code>\n\n"
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

        expires_text = format_plan_expiry(row["plan_expires_at"], row["plan"])

        lines.append(
            f"{index}. <b>{html.escape(name)}</b>\n"
            f"ID: <code>{row['telegram_id']}</code>\n"
            f"Username: <code>{html.escape(username)}</code>\n"
            f"Тариф: <b>{plan_display_name(row['plan'])}</b>\n"
            f"Действует до: <code>{expires_text}</code>\n"
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


@router.message(Command("payments"))
async def payments_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        payment_repo = PaymentRepository(db)
        stats = await payment_repo.stats()
        rows = await payment_repo.latest(limit=10)

    if not rows:
        await message.answer(
            "⭐ <b>Платежей пока нет</b>\n\n"
            f"Всего: <code>{stats['total']}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    lines = [
        "⭐ <b>Платежи Telegram Stars</b>\n",
        f"Всего: <code>{stats['total']}</code>",
        f"Оплачено: <code>{stats['paid']}</code>",
        f"Создано счетов: <code>{stats['created']}</code>",
        f"Отклонено: <code>{stats['rejected']}</code>",
        f"Stars получено: <code>{stats['stars_paid']}</code>",
        f"Оплат сегодня: <code>{stats['paid_today']}</code>\n",
    ]

    for index, row in enumerate(rows, start=1):
        username = f"@{row['username']}" if row["username"] else "без username"
        charge_id = str(row["telegram_payment_charge_id"] or "—")
        payload = str(row["payload"] or "—")

        if len(payload) > 48:
            payload = payload[:48] + "…"

        lines.append(
            f"{index}. <b>{plan_display_name(row['plan'])}</b>\n"
            f"Пользователь: <code>{html.escape(username)}</code>\n"
            f"Telegram ID: <code>{row['telegram_id']}</code>\n"
            f"Stars: <code>{row['stars_amount']}</code>\n"
            f"Статус: <code>{row['status']}</code>\n"
            f"Charge ID: <code>{html.escape(charge_id)}</code>\n"
            f"Payload: <code>{html.escape(payload)}</code>\n"
            f"Дата: <code>{row['updated_at']}</code>\n"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )



@router.message(Command("admin_health"))
async def admin_health_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()
    items = run_diagnostics(settings)

    lines = ["🛡 <b>Диагностика ядра</b>\n"]

    for item in items:
        icon = "✅" if item.ok else "⚠️"
        lines.append(
            f"{icon} <b>{html.escape(item.name)}</b>\n"
            f"Значение: <code>{html.escape(str(item.value))}</code>"
        )

        if item.hint:
            lines.append(f"Подсказка: <i>{html.escape(item.hint)}</i>")

        lines.append("")

    await message.answer(
        "\n".join(lines).strip(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )



@router.message(Command("admin_security"))
async def admin_security_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()
    await message.answer(
        admin_security_report(settings),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )



@router.message(Command("admin_abuse"))
async def admin_abuse_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        cursor = await db.execute(
            """
            SELECT feature, reason, COUNT(*) AS cnt
            FROM abuse_events
            WHERE created_at >= DATETIME('now', '-24 hours')
            GROUP BY feature, reason
            ORDER BY cnt DESC
            LIMIT 20
            """
        )
        stats = await cursor.fetchall()

        cursor = await db.execute(
            """
            SELECT *
            FROM abuse_events
            WHERE reason != 'allowed'
            ORDER BY created_at DESC, id DESC
            LIMIT 10
            """
        )
        latest = await cursor.fetchall()

    lines = ["🛡 <b>Abuse Control</b>\n"]

    if stats:
        lines.append("<b>Последние 24 часа</b>")
        for row in stats:
            lines.append(
                f"— <code>{html.escape(str(row['feature']))}</code> / "
                f"<code>{html.escape(str(row['reason']))}</code>: "
                f"<b>{row['cnt']}</b>"
            )
    else:
        lines.append("<b>Последние 24 часа</b>\n— событий пока нет.")

    lines.append("\n<b>Последние блокировки</b>")

    if latest:
        for row in latest:
            metadata = str(row["metadata"] or "{}")
            if len(metadata) > 180:
                metadata = metadata[:180].rstrip() + "…"

            lines.append(
                f"\nID: <code>{row['id']}</code>\n"
                f"Feature: <code>{html.escape(str(row['feature']))}</code>\n"
                f"Reason: <code>{html.escape(str(row['reason']))}</code>\n"
                f"User: <code>{row['telegram_id'] or '—'}</code>\n"
                f"Chat: <code>{row['chat_id'] or '—'}</code>\n"
                f"Meta: <code>{html.escape(metadata)}</code>\n"
                f"At: <code>{row['created_at']}</code>"
            )
    else:
        lines.append("— блокировок пока нет.")

    await message.answer(
        "\n".join(lines),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )



@router.message(Command("admin_backup"))
async def admin_backup_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    await message.answer(
        backup_status_text(settings),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("admin_backups"))
async def admin_backups_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    await message.answer(
        backup_list_text(limit=15),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("admin_backup_now"))
async def admin_backup_now_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    await message.answer(
        "💾 <b>Создаю backup</b>\n\n"
        "Собираю SQLite и exports. Если файлы не превысят лимит Telegram — отправлю их ниже.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    result = create_backup(settings=settings)

    async with await connect_db(settings.database_path) as db:
        await safe_record_audit_event(
            db=db,
            event_type="backup.created",
            telegram_id=message.from_user.id if message.from_user else None,
            actor_username=message.from_user.username if message.from_user else None,
            chat_id=message.chat.id,
            target_type="backup",
            metadata={
                "created": [item.path.name for item in result.created],
                "skipped": result.skipped,
                "deleted": [path.name for path in result.deleted],
            },
        )

    await message.answer(
        backup_created_text(result),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    for path in files_safe_to_send(result):
        await message.answer_document(
            FSInputFile(path),
            caption=f"💾 Backup: {path.name}",
        )



@router.message(Command("admin_audit"))
async def admin_audit_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        rows = await audit_stats_24h(db)
        events = await latest_audit_events(db, limit=15)

    await message.answer(
        "📋 <b>Audit Log</b>\n\n"
        "<b>События за 24 часа</b>\n"
        f"{audit_stats_text(rows)}\n\n"
        f"{audit_events_text(events, title='Последние события')}",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("admin_audit_user"))
async def admin_audit_user_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer(
            "Формат:\n<code>/admin_audit_user telegram_id</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    telegram_id = int(parts[1].strip())
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        events = await audit_events_for_telegram_id(db, telegram_id=telegram_id, limit=25)

    await message.answer(
        audit_events_text(events, title=f"Audit пользователя {telegram_id}"),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )



@router.message(Command("admin_status"))
async def admin_status_handler(message: Message) -> None:
    if not _is_admin_message(message):
        await _deny(message)
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        status_text = await build_admin_status_text(db=db, settings=settings)

    await message.answer(
        status_text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
