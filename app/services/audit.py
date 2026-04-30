from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEvent:
    id: int
    event_type: str
    user_id: int | None
    telegram_id: int | None
    actor_username: str | None
    chat_id: int | None
    target_type: str | None
    target_id: str | None
    metadata: str | None
    created_at: str


async def record_audit_event(
    db: aiosqlite.Connection,
    *,
    event_type: str,
    user_id: int | None = None,
    telegram_id: int | None = None,
    actor_username: str | None = None,
    chat_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Audit log must never break business flow.
    Use safe_record_audit_event() in handlers when you want guaranteed no-raise behavior.
    """
    await db.execute(
        """
        INSERT INTO audit_events (
            event_type,
            user_id,
            telegram_id,
            actor_username,
            chat_id,
            target_type,
            target_id,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type[:120],
            user_id,
            telegram_id,
            (actor_username or "")[:120] or None,
            chat_id,
            (target_type or "")[:80] or None,
            str(target_id)[:120] if target_id is not None else None,
            json.dumps(metadata or {}, ensure_ascii=False)[:4000],
        ),
    )
    await db.commit()


async def safe_record_audit_event(
    db: aiosqlite.Connection,
    *,
    event_type: str,
    user_id: int | None = None,
    telegram_id: int | None = None,
    actor_username: str | None = None,
    chat_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await record_audit_event(
            db=db,
            event_type=event_type,
            user_id=user_id,
            telegram_id=telegram_id,
            actor_username=actor_username,
            chat_id=chat_id,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )
    except Exception:
        logger.exception("Failed to record audit event: %s", event_type)


async def latest_audit_events(db: aiosqlite.Connection, limit: int = 20) -> list[AuditEvent]:
    cursor = await db.execute(
        """
        SELECT *
        FROM audit_events
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = await cursor.fetchall()
    return [_row_to_event(row) for row in rows]


async def audit_events_for_telegram_id(
    db: aiosqlite.Connection,
    telegram_id: int,
    limit: int = 20,
) -> list[AuditEvent]:
    cursor = await db.execute(
        """
        SELECT *
        FROM audit_events
        WHERE telegram_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (telegram_id, limit),
    )
    rows = await cursor.fetchall()
    return [_row_to_event(row) for row in rows]


async def audit_stats_24h(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """
        SELECT event_type, COUNT(*) AS cnt
        FROM audit_events
        WHERE created_at >= DATETIME('now', '-24 hours')
        GROUP BY event_type
        ORDER BY cnt DESC, event_type ASC
        LIMIT 20
        """
    )
    return await cursor.fetchall()


def audit_events_text(events: list[AuditEvent], title: str = "Audit Log") -> str:
    if not events:
        return (
            f"📋 <b>{html.escape(title)}</b>\n\n"
            "Событий пока нет."
        )

    lines = [f"📋 <b>{html.escape(title)}</b>\n"]

    for index, event in enumerate(events, start=1):
        metadata = event.metadata or "{}"
        if len(metadata) > 260:
            metadata = metadata[:260].rstrip() + "…"

        lines.append(
            f"{index}. <b>{html.escape(event.event_type)}</b>\n"
            f"ID: <code>{event.id}</code>\n"
            f"User: <code>{event.telegram_id or '—'}</code>\n"
            f"Username: <code>{html.escape(event.actor_username or '—')}</code>\n"
            f"Chat: <code>{event.chat_id or '—'}</code>\n"
            f"Target: <code>{html.escape(event.target_type or '—')}:{html.escape(event.target_id or '—')}</code>\n"
            f"Meta: <code>{html.escape(metadata)}</code>\n"
            f"At: <code>{html.escape(event.created_at)}</code>\n"
        )

    return "\n".join(lines)


def audit_stats_text(rows: list[aiosqlite.Row]) -> str:
    if not rows:
        return "— событий за 24 часа пока нет."

    return "\n".join(
        f"— <code>{html.escape(str(row['event_type']))}</code>: <b>{int(row['cnt'])}</b>"
        for row in rows
    )


def _row_to_event(row: aiosqlite.Row) -> AuditEvent:
    return AuditEvent(
        id=int(row["id"]),
        event_type=str(row["event_type"]),
        user_id=int(row["user_id"]) if row["user_id"] is not None else None,
        telegram_id=int(row["telegram_id"]) if row["telegram_id"] is not None else None,
        actor_username=row["actor_username"],
        chat_id=int(row["chat_id"]) if row["chat_id"] is not None else None,
        target_type=row["target_type"],
        target_id=row["target_id"],
        metadata=row["metadata"],
        created_at=str(row["created_at"]),
    )
