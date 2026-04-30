from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class AbuseCheckResult:
    allowed: bool
    feature: str
    reason: str
    retry_after_seconds: int = 0
    message: str = ""


COOLDOWNS_SECONDS = {
    "text": 0,
    "web_search": 30,
    "deep_research": 180,
    "document": 75,
    "group_mention": 12,
    "group_web_search": 30,
    "group_deep_research": 180,
    "group_document": 90,
}

DUPLICATE_WINDOWS_SECONDS = {
    "web_search": 60,
    "deep_research": 240,
    "document": 120,
    "group_mention": 20,
    "group_web_search": 60,
    "group_deep_research": 240,
    "group_document": 120,
}


def abuse_cooldown_seconds(feature: str) -> int:
    return int(COOLDOWNS_SECONDS.get(feature, 0))


def abuse_duplicate_window_seconds(feature: str) -> int:
    return int(DUPLICATE_WINDOWS_SECONDS.get(feature, 0))


def choose_abuse_feature(
    *,
    is_group: bool,
    needs_web: bool,
    needs_deep_research: bool,
    needs_document: bool,
) -> str:
    if is_group:
        if needs_document:
            return "group_document"
        if needs_deep_research:
            return "group_deep_research"
        if needs_web:
            return "group_web_search"
        return "group_mention"

    if needs_document:
        return "document"
    if needs_deep_research:
        return "deep_research"
    if needs_web:
        return "web_search"
    return "text"


async def check_abuse_guard(
    db: aiosqlite.Connection,
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
    text: str,
    cooldown_seconds: int | None = None,
    duplicate_window_seconds: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AbuseCheckResult:
    cooldown = abuse_cooldown_seconds(feature) if cooldown_seconds is None else cooldown_seconds
    duplicate_window = (
        abuse_duplicate_window_seconds(feature)
        if duplicate_window_seconds is None
        else duplicate_window_seconds
    )

    normalized_text = _normalize_text(text)
    text_hash = _hash_text(normalized_text)

    if cooldown > 0:
        retry_after = await _cooldown_retry_after(
            db=db,
            user_id=user_id,
            telegram_id=telegram_id,
            chat_id=chat_id,
            feature=feature,
            cooldown_seconds=cooldown,
        )

        if retry_after > 0:
            await record_abuse_event(
                db=db,
                user_id=user_id,
                telegram_id=telegram_id,
                chat_id=chat_id,
                feature=feature,
                reason="cooldown",
                text_hash=text_hash,
                metadata={
                    **(metadata or {}),
                    "cooldown_seconds": cooldown,
                    "retry_after_seconds": retry_after,
                },
            )
            return AbuseCheckResult(
                allowed=False,
                feature=feature,
                reason="cooldown",
                retry_after_seconds=retry_after,
                message=abuse_wait_text(feature=feature, retry_after_seconds=retry_after),
            )

    if duplicate_window > 0 and text_hash:
        is_duplicate = await _has_recent_duplicate(
            db=db,
            user_id=user_id,
            telegram_id=telegram_id,
            chat_id=chat_id,
            feature=feature,
            text_hash=text_hash,
            window_seconds=duplicate_window,
        )

        if is_duplicate:
            await record_abuse_event(
                db=db,
                user_id=user_id,
                telegram_id=telegram_id,
                chat_id=chat_id,
                feature=feature,
                reason="duplicate",
                text_hash=text_hash,
                metadata={
                    **(metadata or {}),
                    "duplicate_window_seconds": duplicate_window,
                },
            )
            return AbuseCheckResult(
                allowed=False,
                feature=feature,
                reason="duplicate",
                retry_after_seconds=duplicate_window,
                message=duplicate_request_text(feature=feature, retry_after_seconds=duplicate_window),
            )

    await record_abuse_event(
        db=db,
        user_id=user_id,
        telegram_id=telegram_id,
        chat_id=chat_id,
        feature=feature,
        reason="allowed",
        text_hash=text_hash,
        metadata=metadata or {},
    )

    return AbuseCheckResult(
        allowed=True,
        feature=feature,
        reason="allowed",
        retry_after_seconds=0,
        message="",
    )


async def record_abuse_event(
    db: aiosqlite.Connection,
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
    reason: str,
    text_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO abuse_events (
            user_id,
            telegram_id,
            chat_id,
            feature,
            reason,
            text_hash,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            telegram_id,
            chat_id,
            feature[:80],
            reason[:80],
            text_hash,
            json.dumps(metadata or {}, ensure_ascii=False)[:4000],
        ),
    )
    await db.commit()


def abuse_wait_text(feature: str, retry_after_seconds: int) -> str:
    title = _feature_title(feature)

    return (
        "⏳ <b>Нужно немного подождать</b>\n\n"
        f"Сценарий: <b>{html.escape(title)}</b>\n"
        f"Повтори через: <code>{retry_after_seconds} сек.</code>\n\n"
        "<b>Почему так</b>\n"
        "Этот контур нагружает LLM, web-поиск, документы или групповую память. "
        "Я защищаю очередь и бюджет, чтобы бот работал стабильно для всех."
    )


def duplicate_request_text(feature: str, retry_after_seconds: int) -> str:
    title = _feature_title(feature)

    return (
        "♻️ <b>Похожий запрос уже обрабатывался недавно</b>\n\n"
        f"Сценарий: <b>{html.escape(title)}</b>\n"
        f"Повтори через: <code>{retry_after_seconds} сек.</code>\n\n"
        "Так мы не плодим дубликаты, не забиваем очередь и не тратим лишние запросы."
    )


def _feature_title(feature: str) -> str:
    mapping = {
        "text": "Обычный ответ",
        "web_search": "Web Search",
        "deep_research": "Deep Research",
        "document": "DOCX/PDF документ",
        "group_mention": "Групповой GPT",
        "group_web_search": "Групповой Web Search",
        "group_deep_research": "Групповой Deep Research",
        "group_document": "Документ из группы",
    }

    return mapping.get(feature, feature)


async def _cooldown_retry_after(
    db: aiosqlite.Connection,
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
    cooldown_seconds: int,
) -> int:
    where_sql, params = _scope_filter(
        user_id=user_id,
        telegram_id=telegram_id,
        chat_id=chat_id,
        feature=feature,
    )

    cursor = await db.execute(
        f"""
        SELECT
            CAST(
                ? - ((julianday('now') - julianday(MAX(created_at))) * 86400)
                AS INTEGER
            ) AS retry_after
        FROM abuse_events
        WHERE {where_sql}
          AND reason = 'allowed'
          AND created_at >= DATETIME('now', ?)
        """,
        (
            cooldown_seconds,
            *params,
            f"-{cooldown_seconds} seconds",
        ),
    )
    row = await cursor.fetchone()

    if row is None:
        return 0

    retry_after = int(row["retry_after"] or 0)
    return max(retry_after, 0)


async def _has_recent_duplicate(
    db: aiosqlite.Connection,
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
    text_hash: str,
    window_seconds: int,
) -> bool:
    where_sql, params = _scope_filter(
        user_id=user_id,
        telegram_id=telegram_id,
        chat_id=chat_id,
        feature=feature,
    )

    cursor = await db.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM abuse_events
        WHERE {where_sql}
          AND reason = 'allowed'
          AND text_hash = ?
          AND created_at >= DATETIME('now', ?)
        """,
        (
            *params,
            text_hash,
            f"-{window_seconds} seconds",
        ),
    )
    row = await cursor.fetchone()
    return int(row["cnt"] or 0) > 0 if row else False


def _scope_filter(
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
) -> tuple[str, tuple[Any, ...]]:
    if feature.startswith("group_") and chat_id is not None:
        return "chat_id = ? AND feature = ?", (chat_id, feature)

    if user_id is not None:
        return "user_id = ? AND feature = ?", (user_id, feature)

    if telegram_id is not None:
        return "telegram_id = ? AND feature = ?", (telegram_id, feature)

    return "chat_id = ? AND feature = ?", (chat_id, feature)


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())[:2000]


def _hash_text(value: str) -> str:
    if not value:
        return ""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
