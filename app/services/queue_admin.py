from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class QueueAdminResult:
    affected: int
    message: str


async def queue_status_text(db: aiosqlite.Connection) -> str:
    by_status = await _rows(
        db,
        """
        SELECT status, COUNT(*) AS cnt
        FROM queue
        GROUP BY status
        ORDER BY status ASC
        """,
    )

    by_kind_status = await _rows(
        db,
        """
        SELECT kind, status, COUNT(*) AS cnt
        FROM queue
        GROUP BY kind, status
        ORDER BY kind ASC, status ASC
        """,
    )

    latest = await _rows(
        db,
        """
        SELECT id, kind, status, attempts, dedupe_key, last_error, created_at, updated_at
        FROM queue
        ORDER BY updated_at DESC, id DESC
        LIMIT 10
        """,
    )

    lines = [
        "⚙️ <b>Queue Control Panel</b>\n",
        "<b>Сводка по статусам</b>",
    ]

    if by_status:
        for row in by_status:
            lines.append(f"— <code>{html.escape(str(row['status']))}</code>: <b>{int(row['cnt'])}</b>")
    else:
        lines.append("— очередь пустая.")

    lines.append("\n<b>По типам задач</b>")

    if by_kind_status:
        current_kind = ""
        for row in by_kind_status:
            kind = str(row["kind"])
            if kind != current_kind:
                current_kind = kind
                lines.append(f"\n<b>{html.escape(kind)}</b>")
            lines.append(f"— <code>{html.escape(str(row['status']))}</code>: <b>{int(row['cnt'])}</b>")
    else:
        lines.append("— задач пока нет.")

    lines.append("\n<b>Последние задачи</b>")

    if latest:
        for row in latest:
            error = _short(row["last_error"], 180)
            lines.append(
                f"\nID: <code>{row['id']}</code>\n"
                f"Kind: <code>{html.escape(str(row['kind']))}</code>\n"
                f"Status: <code>{html.escape(str(row['status']))}</code>\n"
                f"Attempts: <code>{row['attempts']}</code>\n"
                f"Dedupe: <code>{html.escape(_short(row['dedupe_key'], 90))}</code>\n"
                f"Error: <code>{html.escape(error or '—')}</code>\n"
                f"Updated: <code>{row['updated_at']}</code>"
            )
    else:
        lines.append("— задач пока нет.")

    lines.extend(
        [
            "\n<b>Команды</b>",
            "— <code>/queue_failed</code> — последние failed-задачи;",
            "— <code>/queue_retry_failed</code> — вернуть все failed в pending;",
            "— <code>/queue_retry_failed kind</code> — retry только по kind;",
            "— <code>/queue_cleanup_done 7</code> — удалить done старше 7 дней.",
        ]
    )

    return "\n".join(lines)


async def queue_failed_text(db: aiosqlite.Connection, limit: int = 15) -> str:
    rows = await _rows(
        db,
        """
        SELECT id, kind, status, attempts, dedupe_key, payload, last_error, created_at, updated_at
        FROM queue
        WHERE status = 'failed'
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    if not rows:
        return (
            "✅ <b>Failed-задач нет</b>\n\n"
            "Очередь чистая. Worker пока не оставил аварийных хвостов."
        )

    lines = ["⚠️ <b>Failed-задачи</b>\n"]

    for row in rows:
        payload_preview = _payload_preview(str(row["payload"] or ""))
        error = _short(row["last_error"], 500)

        lines.append(
            f"ID: <code>{row['id']}</code>\n"
            f"Kind: <code>{html.escape(str(row['kind']))}</code>\n"
            f"Attempts: <code>{row['attempts']}</code>\n"
            f"Dedupe: <code>{html.escape(_short(row['dedupe_key'], 100))}</code>\n"
            f"Error: <code>{html.escape(error or '—')}</code>\n"
            f"Payload: <code>{html.escape(payload_preview)}</code>\n"
            f"Created: <code>{row['created_at']}</code>\n"
            f"Updated: <code>{row['updated_at']}</code>\n"
        )

    lines.extend(
        [
            "<b>Retry</b>",
            "— <code>/queue_retry_failed</code> — вернуть все failed;",
            "— <code>/queue_retry_failed heavy_document</code> — вернуть только конкретный kind.",
        ]
    )

    return "\n".join(lines)


async def retry_failed_tasks(
    db: aiosqlite.Connection,
    *,
    kind: str | None = None,
) -> QueueAdminResult:
    if kind:
        cursor = await db.execute(
            """
            UPDATE queue
            SET status = 'pending',
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE status = 'failed'
              AND kind = ?
            """,
            (kind,),
        )
    else:
        cursor = await db.execute(
            """
            UPDATE queue
            SET status = 'pending',
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE status = 'failed'
            """
        )

    await db.commit()
    affected = int(cursor.rowcount or 0)

    if affected == 0:
        return QueueAdminResult(
            affected=0,
            message="✅ Failed-задач для retry не найдено.",
        )

    scope = f"kind <code>{html.escape(kind)}</code>" if kind else "все kind"
    return QueueAdminResult(
        affected=affected,
        message=(
            "♻️ <b>Failed-задачи возвращены в очередь</b>\n\n"
            f"Scope: {scope}\n"
            f"Задач: <code>{affected}</code>\n\n"
            "Worker заберёт их на следующих тиках."
        ),
    )


async def cleanup_done_tasks(
    db: aiosqlite.Connection,
    *,
    older_than_days: int,
) -> QueueAdminResult:
    older_than_days = max(1, min(int(older_than_days), 365))

    cursor = await db.execute(
        """
        DELETE FROM queue
        WHERE status = 'done'
          AND updated_at < DATETIME('now', ?)
        """,
        (f"-{older_than_days} days",),
    )
    await db.commit()

    affected = int(cursor.rowcount or 0)

    if affected == 0:
        return QueueAdminResult(
            affected=0,
            message=(
                "✅ <b>Чистить нечего</b>\n\n"
                f"Done-задач старше <code>{older_than_days}</code> дней не найдено."
            ),
        )

    return QueueAdminResult(
        affected=affected,
        message=(
            "🧹 <b>Очередь очищена</b>\n\n"
            f"Удалено done-задач: <code>{affected}</code>\n"
            f"Порог: старше <code>{older_than_days}</code> дней."
        ),
    )


async def queue_stats_compact(db: aiosqlite.Connection) -> dict[str, int]:
    rows = await _rows(
        db,
        """
        SELECT status, COUNT(*) AS cnt
        FROM queue
        GROUP BY status
        """
    )

    result = {
        "pending": 0,
        "processing": 0,
        "done": 0,
        "failed": 0,
    }

    for row in rows:
        result[str(row["status"])] = int(row["cnt"] or 0)

    return result


async def _rows(
    db: aiosqlite.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[aiosqlite.Row]:
    cursor = await db.execute(sql, params)
    return await cursor.fetchall()


def _short(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _payload_preview(raw_payload: str) -> str:
    try:
        payload = json.loads(raw_payload)
    except Exception:
        return _short(raw_payload, 260)

    safe: dict[str, Any] = {}

    for key in [
        "chat_id",
        "group_chat_id",
        "user_db_id",
        "telegram_id",
        "kind",
        "mode",
        "doc_type",
        "title",
        "user_text",
        "source_text",
    ]:
        if key in payload:
            value = payload[key]
            if isinstance(value, str):
                safe[key] = _short(value, 120)
            else:
                safe[key] = value

    return _short(json.dumps(safe, ensure_ascii=False), 360)
