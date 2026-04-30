from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserDataSnapshot:
    user_db_id: int
    telegram_id: int
    plan: str
    messages_count: int
    usage_count: int
    projects_count: int
    documents_count: int
    feedback_count: int
    payments_count: int
    paid_payments_count: int
    group_messages_count: int
    files_count: int
    files_size_bytes: int


@dataclass(frozen=True)
class ForgetResult:
    deleted_messages: int
    deleted_usage: int
    deleted_projects: int
    deleted_documents: int
    deleted_feedback: int
    anonymized_payments: int
    deleted_group_messages: int
    deleted_files: int
    failed_files: int


def privacy_policy_text() -> str:
    return (
        "🛡 <b>Приватность и данные</b>\n\n"
        "Менеджер ИИ хранит данные только для рабочих функций: памяти, проектов, документов, лимитов и подписки.\n\n"
        "<b>Что может храниться</b>\n"
        "— профиль Telegram: ID, username, имя;\n"
        "— история сообщений с ботом;\n"
        "— проекты и заметки;\n"
        "— документы DOCX/PDF;\n"
        "— статистика лимитов;\n"
        "— оценки ответов;\n"
        "— платежи Telegram Stars;\n"
        "— сообщения группы, если включена память группы.\n\n"
        "<b>Зачем это нужно</b>\n"
        "— чтобы бот помнил контекст;\n"
        "— чтобы работали проекты и документы;\n"
        "— чтобы считать лимиты;\n"
        "— чтобы активировать подписку;\n"
        "— чтобы в Mini App показывались история и файлы.\n\n"
        "<b>Что можно сделать</b>\n"
        "— <code>/my_data</code> — посмотреть сводку данных;\n"
        "— <code>/forget_me</code> — запросить удаление личных данных;\n"
        "— <code>/forget_confirm</code> — подтвердить удаление.\n\n"
        "<b>Важный нюанс</b>\n"
        "Платежи не удаляются полностью: финансовый след нужен для аудита. "
        "Но чувствительный raw payload очищается."
    )


def forget_warning_text(snapshot: UserDataSnapshot) -> str:
    return (
        "⚠️ <b>Удаление личных данных</b>\n\n"
        "Это действие необратимо для рабочей памяти бота.\n\n"
        "<b>Будет удалено</b>\n"
        f"— сообщений: <code>{snapshot.messages_count}</code>;\n"
        f"— usage-событий: <code>{snapshot.usage_count}</code>;\n"
        f"— проектов: <code>{snapshot.projects_count}</code>;\n"
        f"— документов: <code>{snapshot.documents_count}</code>;\n"
        f"— файлов документов: <code>{snapshot.files_count}</code> / <code>{format_bytes(snapshot.files_size_bytes)}</code>;\n"
        f"— оценок ответов: <code>{snapshot.feedback_count}</code>;\n"
        f"— сообщений в групповой памяти от тебя: <code>{snapshot.group_messages_count}</code>.\n\n"
        "<b>Платежи</b>\n"
        f"— платежей всего: <code>{snapshot.payments_count}</code>;\n"
        f"— оплаченных: <code>{snapshot.paid_payments_count}</code>.\n"
        "Финансовые записи останутся для аудита, но raw payload будет очищен.\n\n"
        "Для подтверждения отправь:\n"
        "<code>/forget_confirm</code>"
    )


def my_data_text(snapshot: UserDataSnapshot) -> str:
    return (
        "📦 <b>Мои данные</b>\n\n"
        f"Telegram ID: <code>{snapshot.telegram_id}</code>\n"
        f"Тариф: <code>{html.escape(snapshot.plan)}</code>\n\n"
        "<b>Личная рабочая память</b>\n"
        f"— сообщений с ботом: <code>{snapshot.messages_count}</code>;\n"
        f"— usage-событий: <code>{snapshot.usage_count}</code>;\n"
        f"— проектов: <code>{snapshot.projects_count}</code>;\n"
        f"— документов: <code>{snapshot.documents_count}</code>;\n"
        f"— файлов документов: <code>{snapshot.files_count}</code> / <code>{format_bytes(snapshot.files_size_bytes)}</code>;\n"
        f"— оценок ответов: <code>{snapshot.feedback_count}</code>.\n\n"
        "<b>Группы</b>\n"
        f"— сообщений в групповой памяти от тебя: <code>{snapshot.group_messages_count}</code>.\n\n"
        "<b>Платежи</b>\n"
        f"— платежей всего: <code>{snapshot.payments_count}</code>;\n"
        f"— оплаченных: <code>{snapshot.paid_payments_count}</code>.\n\n"
        "Чтобы удалить личные данные, отправь <code>/forget_me</code>."
    )


def forget_result_text(result: ForgetResult) -> str:
    return (
        "✅ <b>Личные данные удалены</b>\n\n"
        "<b>Очищено</b>\n"
        f"— сообщений: <code>{result.deleted_messages}</code>;\n"
        f"— usage-событий: <code>{result.deleted_usage}</code>;\n"
        f"— проектов: <code>{result.deleted_projects}</code>;\n"
        f"— документов: <code>{result.deleted_documents}</code>;\n"
        f"— оценок: <code>{result.deleted_feedback}</code>;\n"
        f"— сообщений группы: <code>{result.deleted_group_messages}</code>;\n"
        f"— файлов удалено: <code>{result.deleted_files}</code>;\n"
        f"— файлов с ошибкой: <code>{result.failed_files}</code>.\n\n"
        "<b>Платежи</b>\n"
        f"— очищено raw payload: <code>{result.anonymized_payments}</code>.\n\n"
        "Профиль будет пересоздан при следующем <code>/start</code>."
    )


async def load_user_data_snapshot(
    db: aiosqlite.Connection,
    *,
    telegram_id: int,
    settings: Settings,
) -> UserDataSnapshot | None:
    user = await _get_user_by_telegram_id(db, telegram_id)
    if user is None:
        return None

    user_db_id = int(user["id"])

    document_rows = await _get_user_documents(db, user_db_id)
    files = _collect_document_files(document_rows, settings=settings)

    return UserDataSnapshot(
        user_db_id=user_db_id,
        telegram_id=int(user["telegram_id"]),
        plan=str(user["plan"] or "free"),
        messages_count=await _count(db, "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_db_id,)),
        usage_count=await _count(db, "SELECT COUNT(*) FROM usage_events WHERE user_id = ?", (user_db_id,)),
        projects_count=await _count(db, "SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_db_id,)),
        documents_count=await _count(db, "SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_db_id,)),
        feedback_count=await _count(db, "SELECT COUNT(*) FROM feedback WHERE user_id = ?", (user_db_id,)),
        payments_count=await _count(db, "SELECT COUNT(*) FROM payments WHERE user_id = ?", (user_db_id,)),
        paid_payments_count=await _count(
            db,
            "SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'paid'",
            (user_db_id,),
        ),
        group_messages_count=await _count(
            db,
            "SELECT COUNT(*) FROM group_messages WHERE user_telegram_id = ?",
            (telegram_id,),
        ),
        files_count=len(files),
        files_size_bytes=sum(path.stat().st_size for path in files if path.exists() and path.is_file()),
    )


async def forget_user_data(
    db: aiosqlite.Connection,
    *,
    telegram_id: int,
    settings: Settings,
) -> ForgetResult | None:
    user = await _get_user_by_telegram_id(db, telegram_id)
    if user is None:
        return None

    user_db_id = int(user["id"])
    document_rows = await _get_user_documents(db, user_db_id)
    files = _collect_document_files(document_rows, settings=settings)

    deleted_files = 0
    failed_files = 0

    for path in files:
        try:
            path.unlink(missing_ok=True)
            deleted_files += 1
        except Exception:
            logger.exception("Failed to delete user document file: %s", path)
            failed_files += 1

    deleted_feedback = await _delete(db, "DELETE FROM feedback WHERE user_id = ?", (user_db_id,))
    deleted_messages = await _delete(db, "DELETE FROM messages WHERE user_id = ?", (user_db_id,))
    deleted_usage = await _delete(db, "DELETE FROM usage_events WHERE user_id = ?", (user_db_id,))
    deleted_projects = await _delete(db, "DELETE FROM projects WHERE user_id = ?", (user_db_id,))
    deleted_documents = await _delete(db, "DELETE FROM documents WHERE user_id = ?", (user_db_id,))
    deleted_group_messages = await _delete(
        db,
        "DELETE FROM group_messages WHERE user_telegram_id = ?",
        (telegram_id,),
    )

    anonymized_payments = await _update(
        db,
        """
        UPDATE payments
        SET raw_payload = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (user_db_id,),
    )

    await _delete(db, "DELETE FROM abuse_events WHERE user_id = ? OR telegram_id = ?", (user_db_id, telegram_id))

    await _delete(db, "DELETE FROM users WHERE id = ?", (user_db_id,))

    await db.commit()

    return ForgetResult(
        deleted_messages=deleted_messages,
        deleted_usage=deleted_usage,
        deleted_projects=deleted_projects,
        deleted_documents=deleted_documents,
        deleted_feedback=deleted_feedback,
        anonymized_payments=anonymized_payments,
        deleted_group_messages=deleted_group_messages,
        deleted_files=deleted_files,
        failed_files=failed_files,
    )


async def _get_user_by_telegram_id(db: aiosqlite.Connection, telegram_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,),
    )
    return await cursor.fetchone()


async def _get_user_documents(db: aiosqlite.Connection, user_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT docx_path, pdf_path FROM documents WHERE user_id = ?",
        (user_id,),
    )
    return await cursor.fetchall()


async def _count(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> int:
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    return int(row[0] or 0) if row else 0


async def _delete(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> int:
    cursor = await db.execute(sql, params)
    return int(cursor.rowcount or 0)


async def _update(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> int:
    cursor = await db.execute(sql, params)
    return int(cursor.rowcount or 0)


def _collect_document_files(rows: list[aiosqlite.Row], *, settings: Settings) -> list[Path]:
    files: list[Path] = []

    for row in rows:
        for key in ("docx_path", "pdf_path"):
            raw_path = row[key]
            if not raw_path:
                continue

            safe_path = _safe_export_path(str(raw_path), settings=settings)
            if safe_path is not None and safe_path.exists() and safe_path.is_file():
                files.append(safe_path)

    # Убираем дубли, если docx/pdf случайно указывают на один файл.
    unique: dict[str, Path] = {}
    for path in files:
        unique[str(path.resolve())] = path

    return list(unique.values())


def _safe_export_path(raw_path: str, *, settings: Settings) -> Path | None:
    try:
        exports_root = Path(settings.exports_dir).resolve()
        candidate = Path(raw_path)

        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        resolved = candidate.resolve()

        if exports_root != resolved and exports_root not in resolved.parents:
            logger.warning("Blocked unsafe privacy delete path: %s", raw_path)
            return None

        return resolved
    except Exception:
        logger.exception("Failed to resolve privacy delete path: %s", raw_path)
        return None


def format_bytes(value: int) -> str:
    if value <= 0:
        return "0 Б"

    mb = value / 1024 / 1024
    if mb >= 1:
        return f"{mb:.1f} МБ"

    kb = value / 1024
    if kb >= 1:
        return f"{kb:.0f} КБ"

    return f"{value} Б"
