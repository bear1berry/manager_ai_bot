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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    created_date TEXT NOT NULL DEFAULT (DATE('now')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_usage_user_kind_date
ON usage_events(user_id, kind, created_date);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_projects_user_status
ON projects(user_id, status);

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

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


class DatabaseContext:
    """
    Безопасный async context manager для aiosqlite.

    Проект использует паттерн:

        async with await connect_db(path) as db:
            ...

    Поэтому connect_db возвращает не готовое соединение,
    а контекст, который открывает соединение внутри __aenter__.
    """

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


async def init_db(database_path: str) -> None:
    db_file = Path(database_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(PRAGMAS)
        await db.executescript(SCHEMA)
        await db.commit()

    logger.info("Database initialized: %s", db_file)


async def connect_db(database_path: str) -> DatabaseContext:
    return DatabaseContext(database_path)
