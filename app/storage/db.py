from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType

import aiosqlite

logger = logging.getLogger(__name__)

PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    plan TEXT NOT NULL DEFAULT 'free',
    plan_expires_at TEXT,
    plan_updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_user_id_created_at
ON messages(user_id, created_at);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TEXT GENERATED ALWAYS AS (DATE(created_at)) STORED,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_usage_events_user_kind_date
ON usage_events(user_id, kind, created_date);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_projects_user_status_updated
ON projects(user_id, status, updated_at);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    group_chat_id INTEGER,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    docx_path TEXT,
    pdf_path TEXT,
    docx_size_bytes INTEGER NOT NULL DEFAULT 0,
    pdf_size_bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_chat_id) REFERENCES group_chats(chat_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_user_created_at
ON documents(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_documents_user_type_created_at
ON documents(user_id, doc_type, created_at);

CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_status_id
ON queue(status, id);



CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    telegram_id INTEGER,
    actor_username TEXT,
    chat_id INTEGER,
    target_type TEXT,
    target_id TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_type_created
ON audit_events(event_type, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_telegram_created
ON audit_events(telegram_id, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_chat_created
ON audit_events(chat_id, created_at);

CREATE TABLE IF NOT EXISTS abuse_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    telegram_id INTEGER,
    chat_id INTEGER,
    feature TEXT NOT NULL,
    reason TEXT NOT NULL,
    text_hash TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_abuse_events_feature_created
ON abuse_events(feature, created_at);

CREATE INDEX IF NOT EXISTS idx_abuse_events_user_feature_created
ON abuse_events(user_id, feature, created_at);

CREATE INDEX IF NOT EXISTS idx_abuse_events_chat_feature_created
ON abuse_events(chat_id, feature, created_at);

CREATE INDEX IF NOT EXISTS idx_abuse_events_reason_created
ON abuse_events(reason, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message_id INTEGER,
    rating TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
    UNIQUE(user_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_rating_created_at
ON feedback(rating, created_at);

CREATE INDEX IF NOT EXISTS idx_feedback_user_created_at
ON feedback(user_id, created_at);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    telegram_payment_charge_id TEXT,
    provider_payment_charge_id TEXT,
    plan TEXT NOT NULL,
    stars_amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    payload TEXT NOT NULL UNIQUE,
    raw_payload TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_payments_user_created_at
ON payments(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_payments_status_created_at
ON payments(status, created_at);

CREATE TABLE IF NOT EXISTS group_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL UNIQUE,
    title TEXT,
    username TEXT,
    memory_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_group_chats_memory_enabled
ON group_chats(memory_enabled, updated_at);

CREATE TABLE IF NOT EXISTS group_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    user_telegram_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES group_chats(chat_id) ON DELETE CASCADE,
    UNIQUE(chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_group_messages_chat_created
ON group_messages(chat_id, created_at);

CREATE INDEX IF NOT EXISTS idx_group_messages_chat_message
ON group_messages(chat_id, message_id);
"""


class DatabaseContext:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self.db: aiosqlite.Connection | None = None

    async def __aenter__(self) -> aiosqlite.Connection:
        db_file = Path(self.database_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        self.db = await aiosqlite.connect(db_file)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(PRAGMAS)
        return self.db

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return any(str(row[1]) == column for row in rows)


async def _table_exists(db: aiosqlite.Connection, table: str) -> bool:
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    row = await cursor.fetchone()
    return row is not None


async def _run_migrations(db: aiosqlite.Connection) -> None:
    if await _table_exists(db, "users"):
        if not await _column_exists(db, "users", "plan_expires_at"):
            await db.execute("ALTER TABLE users ADD COLUMN plan_expires_at TEXT")

        if not await _column_exists(db, "users", "plan_updated_at"):
            await db.execute("ALTER TABLE users ADD COLUMN plan_updated_at TEXT")

    if await _table_exists(db, "documents"):
        if not await _column_exists(db, "documents", "group_chat_id"):
            await db.execute("ALTER TABLE documents ADD COLUMN group_chat_id INTEGER")

        if not await _column_exists(db, "documents", "docx_size_bytes"):
            await db.execute("ALTER TABLE documents ADD COLUMN docx_size_bytes INTEGER NOT NULL DEFAULT 0")

        if not await _column_exists(db, "documents", "pdf_size_bytes"):
            await db.execute("ALTER TABLE documents ADD COLUMN pdf_size_bytes INTEGER NOT NULL DEFAULT 0")

        if await _column_exists(db, "documents", "group_chat_id"):
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_group_chat_created_at "
                "ON documents(group_chat_id, created_at)"
            )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS abuse_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            telegram_id INTEGER,
            chat_id INTEGER,
            feature TEXT NOT NULL,
            reason TEXT NOT NULL,
            text_hash TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_abuse_events_feature_created "
        "ON abuse_events(feature, created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_abuse_events_user_feature_created "
        "ON abuse_events(user_id, feature, created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_abuse_events_chat_feature_created "
        "ON abuse_events(chat_id, feature, created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_abuse_events_reason_created "
        "ON abuse_events(reason, created_at)"
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id INTEGER,
            telegram_id INTEGER,
            actor_username TEXT,
            chat_id INTEGER,
            target_type TEXT,
            target_id TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_type_created "
        "ON audit_events(event_type, created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_telegram_created "
        "ON audit_events(telegram_id, created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_chat_created "
        "ON audit_events(chat_id, created_at)"
    )

    await db.commit()


async def init_db(database_path: str) -> None:
    db_file = Path(database_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(PRAGMAS)
        await db.executescript(SCHEMA)
        await _run_migrations(db)
        await db.commit()

    logger.info("Database initialized: %s", db_file)


async def connect_db(database_path: str) -> DatabaseContext:
    return DatabaseContext(database_path)
