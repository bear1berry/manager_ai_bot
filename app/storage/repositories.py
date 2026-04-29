from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite
import orjson


class UserRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> aiosqlite.Row:
        await self.db.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, username, first_name, last_name),
        )
        await self.db.commit()

        cursor = await self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("User upsert failed")
        return row

    async def get_by_telegram_id(self, telegram_id: int) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return await cursor.fetchone()

    async def set_plan(
        self,
        telegram_id: int,
        plan: str,
        plan_expires_at: str | None = None,
    ) -> None:
        await self.db.execute(
            """
            UPDATE users
            SET plan = ?,
                plan_expires_at = ?,
                plan_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (plan, plan_expires_at, telegram_id),
        )
        await self.db.commit()

    async def downgrade_to_free(self, telegram_id: int) -> None:
        await self.set_plan(
            telegram_id=telegram_id,
            plan="free",
            plan_expires_at=None,
        )


class MessageRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def add(self, user_id: int, role: str, content: str) -> int:
        cursor = await self.db.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        await self.db.commit()
        return int(cursor.lastrowid)

    async def recent(self, user_id: int, limit: int = 12) -> list[dict[str, str]]:
        cursor = await self.db.execute(
            """
            SELECT role, content
            FROM messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        rows = list(reversed(rows))
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    async def latest_assistant_message(self, user_id: int) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM messages
            WHERE user_id = ?
              AND role = 'assistant'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return await cursor.fetchone()


class UsageRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def count_today(self, user_id: int, kind: str) -> int:
        cursor = await self.db.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM usage_events
            WHERE user_id = ?
              AND kind = ?
              AND created_date = DATE('now')
            """,
            (user_id, kind),
        )
        row = await cursor.fetchone()
        return int(row["cnt"]) if row else 0

    async def add(self, user_id: int, kind: str) -> None:
        await self.db.execute(
            "INSERT INTO usage_events (user_id, kind) VALUES (?, ?)",
            (user_id, kind),
        )
        await self.db.commit()


class ProjectRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, user_id: int, title: str, description: str = "") -> int:
        cursor = await self.db.execute(
            """
            INSERT INTO projects (user_id, title, description)
            VALUES (?, ?, ?)
            """,
            (user_id, title, description),
        )
        await self.db.commit()
        return int(cursor.lastrowid)

    async def list_active(self, user_id: int, limit: int = 20) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM projects
            WHERE user_id = ?
              AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return await cursor.fetchall()

    async def get_owned(self, project_id: int, user_id: int) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM projects
            WHERE id = ?
              AND user_id = ?
              AND status = 'active'
            LIMIT 1
            """,
            (project_id, user_id),
        )
        return await cursor.fetchone()

    async def search_active(self, user_id: int, query: str, limit: int = 5) -> list[aiosqlite.Row]:
        normalized = f"%{query.strip()}%"

        cursor = await self.db.execute(
            """
            SELECT *
            FROM projects
            WHERE user_id = ?
              AND status = 'active'
              AND (
                    title LIKE ?
                 OR description LIKE ?
              )
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, normalized, normalized, limit),
        )
        return await cursor.fetchall()

    async def latest_context(self, user_id: int, limit: int = 5) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM projects
            WHERE user_id = ?
              AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return await cursor.fetchall()

    async def append_note(self, project_id: int, note: str) -> None:
        cursor = await self.db.execute(
            "SELECT description FROM projects WHERE id = ?",
            (project_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return

        old_description = str(row["description"] or "")
        new_description = f"{old_description}\n\nЗаметка:\n{note.strip()}".strip()

        await self.db.execute(
            """
            UPDATE projects
            SET description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_description, project_id),
        )
        await self.db.commit()


class DocumentRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(
        self,
        user_id: int,
        doc_type: str,
        title: str,
        docx_path: str | None,
        pdf_path: str | None,
        status: str = "created",
    ) -> int:
        docx_size = self._file_size(docx_path)
        pdf_size = self._file_size(pdf_path)

        cursor = await self.db.execute(
            """
            INSERT INTO documents (
                user_id,
                doc_type,
                title,
                docx_path,
                pdf_path,
                docx_size_bytes,
                pdf_size_bytes,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                doc_type,
                title,
                docx_path,
                pdf_path,
                docx_size,
                pdf_size,
                status,
            ),
        )
        await self.db.commit()
        return int(cursor.lastrowid)

    async def latest(self, user_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM documents
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return await cursor.fetchall()

    async def get_owned(self, document_id: int, user_id: int) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM documents
            WHERE id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (document_id, user_id),
        )
        return await cursor.fetchone()

    async def count(self, user_id: int) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM documents WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def count_today(self, user_id: int) -> int:
        cursor = await self.db.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE user_id = ?
              AND DATE(created_at) = DATE('now')
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _file_size(path: str | None) -> int:
        if not path:
            return 0

        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return 0

        return int(file_path.stat().st_size)


class FeedbackRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def upsert_feedback(
        self,
        user_id: int,
        message_id: int | None,
        rating: str,
        comment: str | None = None,
    ) -> int:
        cursor = await self.db.execute(
            """
            INSERT INTO feedback (user_id, message_id, rating, comment)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, message_id) DO UPDATE SET
                rating = excluded.rating,
                comment = COALESCE(excluded.comment, feedback.comment),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, message_id, rating, comment),
        )
        await self.db.commit()

        if cursor.lastrowid:
            return int(cursor.lastrowid)

        cursor = await self.db.execute(
            """
            SELECT id
            FROM feedback
            WHERE user_id = ?
              AND (
                    message_id = ?
                 OR (message_id IS NULL AND ? IS NULL)
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, message_id, message_id),
        )
        row = await cursor.fetchone()
        return int(row["id"]) if row else 0

    async def add_comment(self, feedback_id: int, comment: str) -> None:
        await self.db.execute(
            """
            UPDATE feedback
            SET comment = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (comment.strip()[:2000], feedback_id),
        )
        await self.db.commit()

    async def latest(self, limit: int = 10) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT
                feedback.*,
                users.telegram_id,
                users.username,
                users.first_name,
                users.last_name,
                messages.content AS message_content
            FROM feedback
            JOIN users ON users.id = feedback.user_id
            LEFT JOIN messages ON messages.id = feedback.message_id
            ORDER BY feedback.updated_at DESC, feedback.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()

    async def stats(self) -> dict[str, int]:
        return {
            "total": await self._count("SELECT COUNT(*) FROM feedback"),
            "positive": await self._count("SELECT COUNT(*) FROM feedback WHERE rating = 'positive'"),
            "negative": await self._count("SELECT COUNT(*) FROM feedback WHERE rating = 'negative'"),
            "today": await self._count("SELECT COUNT(*) FROM feedback WHERE DATE(created_at) = DATE('now')"),
        }

    async def _count(self, sql: str) -> int:
        cursor = await self.db.execute(sql)
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


class PaymentRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create_payment(
        self,
        user_id: int,
        plan: str,
        stars_amount: int,
        payload: str,
    ) -> int:
        cursor = await self.db.execute(
            """
            INSERT INTO payments (user_id, plan, stars_amount, payload, status)
            VALUES (?, ?, ?, ?, 'created')
            """,
            (user_id, plan, stars_amount, payload),
        )
        await self.db.commit()
        return int(cursor.lastrowid)

    async def mark_paid(
        self,
        payload: str,
        telegram_payment_charge_id: str | None,
        provider_payment_charge_id: str | None,
        raw_payload: str,
    ) -> aiosqlite.Row | None:
        await self.db.execute(
            """
            UPDATE payments
            SET status = 'paid',
                telegram_payment_charge_id = ?,
                provider_payment_charge_id = ?,
                raw_payload = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE payload = ?
            """,
            (
                telegram_payment_charge_id,
                provider_payment_charge_id,
                raw_payload,
                payload,
            ),
        )
        await self.db.commit()

        cursor = await self.db.execute(
            "SELECT * FROM payments WHERE payload = ?",
            (payload,),
        )
        return await cursor.fetchone()

    async def mark_rejected(self, payload: str, reason: str) -> None:
        await self.db.execute(
            """
            UPDATE payments
            SET status = 'rejected',
                raw_payload = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE payload = ?
            """,
            (reason[:2000], payload),
        )
        await self.db.commit()

    async def get_by_payload(self, payload: str) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            "SELECT * FROM payments WHERE payload = ?",
            (payload,),
        )
        return await cursor.fetchone()

    async def latest_created_for_user_plan(
        self,
        user_id: int,
        plan: str,
    ) -> aiosqlite.Row | None:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM payments
            WHERE user_id = ?
              AND plan = ?
              AND status = 'created'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (user_id, plan),
        )
        return await cursor.fetchone()

    async def stats(self) -> dict[str, int]:
        return {
            "total": await self._count("SELECT COUNT(*) FROM payments"),
            "paid": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'paid'"),
            "created": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'created'"),
            "rejected": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'rejected'"),
            "stars_paid": await self._count("SELECT COALESCE(SUM(stars_amount), 0) FROM payments WHERE status = 'paid'"),
            "paid_today": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'paid' AND DATE(updated_at) = DATE('now')"),
        }

    async def latest(self, limit: int = 10) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT
                payments.*,
                users.telegram_id,
                users.username,
                users.first_name,
                users.last_name
            FROM payments
            JOIN users ON users.id = payments.user_id
            ORDER BY payments.updated_at DESC, payments.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()

    async def _count(self, sql: str) -> int:
        cursor = await self.db.execute(sql)
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


class QueueRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def enqueue(self, kind: str, payload: dict[str, Any], dedupe_key: str) -> int | None:
        try:
            cursor = await self.db.execute(
                """
                INSERT INTO queue (kind, payload, dedupe_key)
                VALUES (?, ?, ?)
                """,
                (
                    kind,
                    orjson.dumps(payload).decode("utf-8"),
                    dedupe_key,
                ),
            )
            await self.db.commit()
            return int(cursor.lastrowid)
        except aiosqlite.IntegrityError:
            return None

    async def claim_next(self) -> aiosqlite.Row | None:
        await self.db.execute("BEGIN IMMEDIATE")
        cursor = await self.db.execute(
            """
            SELECT *
            FROM queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()

        if row is None:
            await self.db.commit()
            return None

        await self.db.execute(
            """
            UPDATE queue
            SET status = 'processing',
                attempts = attempts + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'pending'
            """,
            (row["id"],),
        )
        await self.db.commit()

        cursor = await self.db.execute("SELECT * FROM queue WHERE id = ?", (row["id"],))
        return await cursor.fetchone()

    async def mark_done(self, queue_id: int) -> None:
        await self.db.execute(
            """
            UPDATE queue
            SET status = 'done',
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE id = ?
            """,
            (queue_id,),
        )
        await self.db.commit()

    async def mark_failed_or_retry(self, queue_id: int, error: str, max_attempts: int) -> None:
        cursor = await self.db.execute(
            "SELECT attempts FROM queue WHERE id = ?",
            (queue_id,),
        )
        row = await cursor.fetchone()
        attempts = int(row["attempts"]) if row else max_attempts

        status = "failed" if attempts >= max_attempts else "pending"

        await self.db.execute(
            """
            UPDATE queue
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP,
                last_error = ?
            WHERE id = ?
            """,
            (status, error[:2000], queue_id),
        )
        await self.db.commit()

    @staticmethod
    def parse_payload(row: aiosqlite.Row) -> dict[str, Any]:
        return json.loads(row["payload"])


class AdminRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def product_stats(self) -> dict[str, int]:
        return {
            "users_total": await self._count("SELECT COUNT(*) FROM users"),
            "users_today": await self._count("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')"),
            "messages_total": await self._count("SELECT COUNT(*) FROM messages"),
            "messages_today": await self._count("SELECT COUNT(*) FROM messages WHERE DATE(created_at) = DATE('now')"),
            "text_usage_today": await self._count(
                "SELECT COUNT(*) FROM usage_events WHERE kind = 'text' AND created_date = DATE('now')"
            ),
            "voice_usage_today": await self._count(
                "SELECT COUNT(*) FROM usage_events WHERE kind = 'voice' AND created_date = DATE('now')"
            ),
            "projects_total": await self._count("SELECT COUNT(*) FROM projects"),
            "projects_active": await self._count("SELECT COUNT(*) FROM projects WHERE status = 'active'"),
            "documents_total": await self._count("SELECT COUNT(*) FROM documents"),
            "documents_today": await self._count("SELECT COUNT(*) FROM documents WHERE DATE(created_at) = DATE('now')"),
            "feedback_total": await self._count("SELECT COUNT(*) FROM feedback"),
            "feedback_positive": await self._count("SELECT COUNT(*) FROM feedback WHERE rating = 'positive'"),
            "feedback_negative": await self._count("SELECT COUNT(*) FROM feedback WHERE rating = 'negative'"),
            "payments_total": await self._count("SELECT COUNT(*) FROM payments"),
            "payments_paid": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'paid'"),
            "payments_rejected": await self._count("SELECT COUNT(*) FROM payments WHERE status = 'rejected'"),
            "stars_paid": await self._count("SELECT COALESCE(SUM(stars_amount), 0) FROM payments WHERE status = 'paid'"),
            "queue_pending": await self._count("SELECT COUNT(*) FROM queue WHERE status = 'pending'"),
            "queue_processing": await self._count("SELECT COUNT(*) FROM queue WHERE status = 'processing'"),
            "queue_done": await self._count("SELECT COUNT(*) FROM queue WHERE status = 'done'"),
            "queue_failed": await self._count("SELECT COUNT(*) FROM queue WHERE status = 'failed'"),
        }

    async def queue_stats(self) -> dict[str, int]:
        cursor = await self.db.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM queue
            GROUP BY status
            """
        )
        rows = await cursor.fetchall()

        result = {
            "pending": 0,
            "processing": 0,
            "done": 0,
            "failed": 0,
        }

        for row in rows:
            result[str(row["status"])] = int(row["cnt"])

        return result

    async def latest_failed_queue(self, limit: int = 5) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM queue
            WHERE status = 'failed'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()

    async def latest_users(self, limit: int = 10) -> list[aiosqlite.Row]:
        cursor = await self.db.execute(
            """
            SELECT *
            FROM users
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()

    async def _count(self, sql: str) -> int:
        cursor = await self.db.execute(sql)
        row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])
