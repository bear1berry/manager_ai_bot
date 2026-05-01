from __future__ import annotations

import html
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import Settings
from app.services.backup import backup_dir, format_bytes, list_backups
from app.services.costs import llm_usage_stats_24h


@dataclass(frozen=True)
class HealthItem:
    name: str
    ok: bool
    value: str
    hint: str = ""


async def build_admin_status_text(db: aiosqlite.Connection, settings: Settings) -> str:
    items: list[HealthItem] = []

    items.extend(_system_items(settings))
    items.extend(await _database_items(db))
    items.extend(await _queue_items(db))
    items.extend(_worker_items(settings))
    items.extend(await _payment_items(db))
    items.extend(await _llm_items(db))
    items.extend(await _abuse_items(db))
    items.extend(await _audit_items(db))
    items.extend(_backup_items())
    items.extend(_web_items(settings))
    items.extend(_disk_items(settings))

    ok_count = sum(1 for item in items if item.ok)
    warn_count = len(items) - ok_count

    status_icon = "✅" if warn_count == 0 else "⚠️"
    status_title = "Система в норме" if warn_count == 0 else "Есть зоны внимания"

    lines = [
        f"{status_icon} <b>Admin Status</b>",
        "",
        f"<b>{status_title}</b>",
        f"Проверок: <code>{len(items)}</code>",
        f"OK: <code>{ok_count}</code>",
        f"Warnings: <code>{warn_count}</code>",
        "",
        "━━━━━━━━━━━━━━",
    ]

    current_group = ""

    for item in items:
        group = _group_for_item(item.name)
        if group != current_group:
            current_group = group
            lines.append("")
            lines.append(f"<b>{html.escape(group)}</b>")

        icon = "✅" if item.ok else "⚠️"
        lines.append(
            f"{icon} <b>{html.escape(item.name)}</b>: "
            f"<code>{html.escape(item.value)}</code>"
        )

        if item.hint:
            lines.append(f"   <i>{html.escape(item.hint)}</i>")

    risks = _risk_summary(items)
    lines.extend(
        [
            "",
            "━━━━━━━━━━━━━━",
            "",
            "<b>Рекомендации</b>",
            risks,
            "",
            "<b>Быстрые команды</b>",
            "— <code>/stats</code> — продуктовая статистика;",
            "— <code>/queues</code> — очередь;",
            "— <code>/admin_backup</code> — backup;",
            "— <code>/admin_security</code> — безопасность;",
            "— <code>/admin_abuse</code> — антиспам;",
            "— <code>/admin_audit</code> — журнал действий.",
        ]
    )

    return "\n".join(lines).strip()


def _system_items(settings: Settings) -> list[HealthItem]:
    return [
        HealthItem(
            name="APP",
            ok=True,
            value=f"{settings.app_name} / {settings.env}",
        ),
        HealthItem(
            name="BOT_TOKEN",
            ok=bool(settings.bot_token),
            value="set" if settings.bot_token else "missing",
            hint="Без токена Telegram-бот не стартует.",
        ),
        HealthItem(
            name="LLM_API_KEY",
            ok=bool(settings.llm_api_key),
            value="set" if settings.llm_api_key else "missing",
            hint="Без ключа ответы LLM могут не работать.",
        ),
        HealthItem(
            name="MINI_APP_API",
            ok=bool(settings.mini_app_api_enabled),
            value=f"enabled={settings.mini_app_api_enabled} {settings.mini_app_api_host}:{settings.mini_app_api_port}",
        ),
        HealthItem(
            name="MINI_APP_URL",
            ok=bool(settings.mini_app_url.strip()),
            value=settings.mini_app_url.strip() or "missing",
            hint="Нужен для системной кнопки Mini App.",
        ),
    ]


async def _database_items(db: aiosqlite.Connection) -> list[HealthItem]:
    items: list[HealthItem] = []

    try:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        users = int((await cursor.fetchone())[0])

        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        messages = int((await cursor.fetchone())[0])

        cursor = await db.execute("SELECT COUNT(*) FROM documents")
        documents = int((await cursor.fetchone())[0])

        cursor = await db.execute("SELECT COUNT(*) FROM group_messages")
        group_messages = int((await cursor.fetchone())[0])

        items.extend(
            [
                HealthItem("DATABASE", True, "available"),
                HealthItem("DB_USERS", True, str(users)),
                HealthItem("DB_MESSAGES", True, str(messages)),
                HealthItem("DB_DOCUMENTS", True, str(documents)),
                HealthItem("DB_GROUP_MESSAGES", True, str(group_messages)),
            ]
        )
    except Exception as exc:
        items.append(
            HealthItem(
                name="DATABASE",
                ok=False,
                value=str(exc)[:160],
                hint="Проверь SQLite-файл, миграции и права доступа.",
            )
        )

    return items


async def _queue_items(db: aiosqlite.Connection) -> list[HealthItem]:
    try:
        rows = await _group_count(db, "queue", "status")
        pending = rows.get("pending", 0)
        processing = rows.get("processing", 0)
        failed = rows.get("failed", 0)

        return [
            HealthItem("QUEUE_PENDING", pending < 25, str(pending), "Очередь растёт — проверь worker." if pending >= 25 else ""),
            HealthItem("QUEUE_PROCESSING", processing < 10, str(processing), "Много processing — возможен зависший worker." if processing >= 10 else ""),
            HealthItem("QUEUE_FAILED", failed == 0, str(failed), "Есть failed-задачи. Открой /queues." if failed else ""),
        ]
    except Exception as exc:
        return [HealthItem("QUEUE", False, str(exc)[:160])]



def _worker_items(settings: Settings) -> list[HealthItem]:
    concurrency = max(1, int(settings.worker_concurrency))
    heavy_concurrency = max(1, int(settings.worker_heavy_concurrency))
    poll_interval = float(settings.worker_poll_interval_seconds)
    max_attempts = max(1, int(settings.worker_max_attempts))

    return [
        HealthItem(
            name="WORKER_CONCURRENCY",
            ok=concurrency <= 4,
            value=str(concurrency),
            hint="Для слабого сервера держи 1–2." if concurrency > 4 else "",
        ),
        HealthItem(
            name="WORKER_HEAVY_CONCURRENCY",
            ok=heavy_concurrency <= concurrency,
            value=str(heavy_concurrency),
            hint="Heavy concurrency не должен быть выше общего worker pool.",
        ),
        HealthItem(
            name="WORKER_POLL_INTERVAL",
            ok=poll_interval >= 0.5,
            value=f"{poll_interval}s",
            hint="Слишком частый polling может давить SQLite." if poll_interval < 0.5 else "",
        ),
        HealthItem(
            name="WORKER_MAX_ATTEMPTS",
            ok=1 <= max_attempts <= 10,
            value=str(max_attempts),
            hint="Слишком много retry может долго гонять битые задачи." if max_attempts > 10 else "",
        ),
    ]


async def _payment_items(db: aiosqlite.Connection) -> list[HealthItem]:
    try:
        paid = await _count(db, "SELECT COUNT(*) FROM payments WHERE status = 'paid'")
        created = await _count(db, "SELECT COUNT(*) FROM payments WHERE status = 'created'")
        rejected = await _count(db, "SELECT COUNT(*) FROM payments WHERE status = 'rejected'")
        stars = await _count(db, "SELECT COALESCE(SUM(stars_amount), 0) FROM payments WHERE status = 'paid'")

        return [
            HealthItem("PAYMENTS_PAID", True, str(paid)),
            HealthItem("PAYMENTS_CREATED", created < 20, str(created), "Много неоплаченных счетов." if created >= 20 else ""),
            HealthItem("PAYMENTS_REJECTED", rejected < 10, str(rejected), "Много отклонённых платежей." if rejected >= 10 else ""),
            HealthItem("STARS_PAID", True, str(stars)),
        ]
    except Exception as exc:
        return [HealthItem("PAYMENTS", False, str(exc)[:160])]



async def _llm_items(db: aiosqlite.Connection) -> list[HealthItem]:
    try:
        stats = await llm_usage_stats_24h(db)
        requests = int(stats["requests"])
        cost = float(stats["estimated_cost_usd"])
        statuses = stats.get("statuses", {})
        failed = int(statuses.get("failed", 0))

        return [
            HealthItem("LLM_REQUESTS_24H", True, str(requests)),
            HealthItem("LLM_FAILED_24H", failed == 0, str(failed), "Есть падения LLM. Открой /admin_llm_usage." if failed else ""),
            HealthItem("LLM_COST_24H", cost < 5, f"${cost:.6f}", "Расход LLM заметный. Проверь маршруты моделей." if cost >= 5 else ""),
        ]
    except Exception as exc:
        return [HealthItem("LLM_USAGE", False, str(exc)[:160])]


async def _abuse_items(db: aiosqlite.Connection) -> list[HealthItem]:
    try:
        blocked = await _count(
            db,
            "SELECT COUNT(*) FROM abuse_events WHERE reason != 'allowed' AND created_at >= DATETIME('now', '-24 hours')",
        )
        allowed = await _count(
            db,
            "SELECT COUNT(*) FROM abuse_events WHERE reason = 'allowed' AND created_at >= DATETIME('now', '-24 hours')",
        )

        return [
            HealthItem("ABUSE_ALLOWED_24H", True, str(allowed)),
            HealthItem(
                "ABUSE_BLOCKED_24H",
                blocked < 50,
                str(blocked),
                "Много блокировок. Проверь /admin_abuse." if blocked >= 50 else "",
            ),
        ]
    except Exception as exc:
        return [HealthItem("ABUSE", False, str(exc)[:160])]


async def _audit_items(db: aiosqlite.Connection) -> list[HealthItem]:
    try:
        total_24h = await _count(
            db,
            "SELECT COUNT(*) FROM audit_events WHERE created_at >= DATETIME('now', '-24 hours')",
        )
        total = await _count(db, "SELECT COUNT(*) FROM audit_events")

        return [
            HealthItem("AUDIT_EVENTS_24H", True, str(total_24h)),
            HealthItem("AUDIT_EVENTS_TOTAL", True, str(total)),
        ]
    except Exception as exc:
        return [HealthItem("AUDIT", False, str(exc)[:160])]


def _backup_items() -> list[HealthItem]:
    try:
        directory = backup_dir()
        backups = list_backups(limit=10)

        if not backups:
            return [
                HealthItem(
                    "BACKUP_DIR",
                    _is_writable(directory),
                    str(directory),
                    "Backup-файлов пока нет. Запусти /admin_backup_now.",
                ),
                HealthItem("BACKUP_LATEST", False, "missing", "Нет ни одного backup."),
            ]

        latest = backups[0]
        return [
            HealthItem("BACKUP_DIR", _is_writable(directory), str(directory)),
            HealthItem("BACKUP_FILES", True, str(len(backups))),
            HealthItem(
                "BACKUP_LATEST",
                True,
                f"{latest.path.name} / {format_bytes(latest.size_bytes)} / {latest.created_at}",
            ),
        ]
    except Exception as exc:
        return [HealthItem("BACKUP", False, str(exc)[:160])]


def _web_items(settings: Settings) -> list[HealthItem]:
    provider = settings.web_search_provider

    if provider == "tavily":
        has_key = bool(settings.tavily_api_key)
    elif provider == "serper":
        has_key = bool(settings.serper_api_key)
    elif provider == "brave":
        has_key = bool(settings.brave_api_key)
    else:
        has_key = False

    return [
        HealthItem("WEB_ENABLED", True, str(settings.web_search_enabled)),
        HealthItem("WEB_PROVIDER", True, provider),
        HealthItem(
            "WEB_API_KEY",
            (not settings.web_search_enabled) or has_key,
            "set" if has_key else "missing",
            "Web включён, но ключ провайдера отсутствует." if settings.web_search_enabled and not has_key else "",
        ),
    ]


def _disk_items(settings: Settings) -> list[HealthItem]:
    paths = [
        ("DIR_DATA", Path(settings.database_path).parent),
        ("DIR_EXPORTS", Path(settings.exports_dir)),
        ("DIR_LOGS", Path(settings.logs_dir)),
        ("DIR_BACKUPS", backup_dir()),
    ]

    items: list[HealthItem] = []

    for name, path in paths:
        path.mkdir(parents=True, exist_ok=True)
        items.append(
            HealthItem(
                name=name,
                ok=_is_writable(path),
                value=str(path),
                hint="Нет записи в директорию." if not _is_writable(path) else "",
            )
        )

    usage = shutil.disk_usage(Path.cwd())
    free_mb = usage.free // 1024 // 1024
    items.append(
        HealthItem(
            name="DISK_FREE",
            ok=free_mb >= 1024,
            value=f"{free_mb} MB",
            hint="Мало места для backup/export." if free_mb < 1024 else "",
        )
    )

    return items


async def _group_count(db: aiosqlite.Connection, table: str, column: str) -> dict[str, int]:
    cursor = await db.execute(
        f"""
        SELECT {column} AS key, COUNT(*) AS cnt
        FROM {table}
        GROUP BY {column}
        """
    )
    rows = await cursor.fetchall()
    return {str(row["key"]): int(row["cnt"]) for row in rows}


async def _count(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    return int(row[0] or 0) if row else 0


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _group_for_item(name: str) -> str:
    if name.startswith(("APP", "BOT", "LLM", "MINI")):
        return "Система"
    if name.startswith(("DATABASE", "DB_")):
        return "База данных"
    if name.startswith("QUEUE"):
        return "Очередь"
    if name.startswith("WORKER"):
        return "Worker"
    if name.startswith(("PAYMENTS", "STARS")):
        return "Платежи"
    if name.startswith("LLM"):
        return "LLM Usage"
    if name.startswith("ABUSE"):
        return "Abuse Control"
    if name.startswith("AUDIT"):
        return "Audit"
    if name.startswith("BACKUP"):
        return "Backup"
    if name.startswith("WEB"):
        return "Web Search"
    if name.startswith(("DIR", "DISK")):
        return "Файлы и диск"
    return "Другое"


def _risk_summary(items: list[HealthItem]) -> str:
    warnings = [item for item in items if not item.ok]

    if not warnings:
        return "— критичных замечаний нет. Система выглядит здоровой."

    lines = []
    for item in warnings[:10]:
        hint = f" — {item.hint}" if item.hint else ""
        lines.append(f"— {html.escape(item.name)}: {html.escape(item.value)}{html.escape(hint)}")

    if len(warnings) > 10:
        lines.append(f"— и ещё {len(warnings) - 10} предупреждений.")

    return "\n".join(lines)
