from __future__ import annotations

import html
import logging
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from app.config import Settings

logger = logging.getLogger(__name__)

BackupKind = Literal["sqlite", "exports"]


@dataclass(frozen=True)
class BackupFile:
    path: Path
    kind: BackupKind
    size_bytes: int
    created_at: str


@dataclass(frozen=True)
class BackupResult:
    created: list[BackupFile]
    skipped: list[str]
    deleted: list[Path]


DEFAULT_BACKUP_DIR = Path("backups")
DEFAULT_KEEP_FILES = 20
TELEGRAM_SAFE_FILE_BYTES = 45 * 1024 * 1024


def backup_dir() -> Path:
    path = DEFAULT_BACKUP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(settings: Settings, keep_files: int = DEFAULT_KEEP_FILES) -> BackupResult:
    directory = backup_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    created: list[BackupFile] = []
    skipped: list[str] = []

    database_backup = _backup_sqlite(settings=settings, directory=directory, stamp=stamp)
    if database_backup is not None:
        created.append(database_backup)
    else:
        skipped.append("SQLite database not found or backup failed")

    exports_backup = _backup_exports(settings=settings, directory=directory, stamp=stamp)
    if exports_backup is not None:
        created.append(exports_backup)
    else:
        skipped.append("Exports directory is empty or not found")

    deleted = cleanup_old_backups(keep_files=keep_files)

    return BackupResult(
        created=created,
        skipped=skipped,
        deleted=deleted,
    )


def list_backups(limit: int = 20) -> list[BackupFile]:
    directory = backup_dir()

    files: list[BackupFile] = []
    for path in directory.glob("*"):
        if not path.is_file():
            continue

        kind: BackupKind
        if path.name.startswith("manager_ai_") and path.suffix == ".sqlite3":
            kind = "sqlite"
        elif path.name.startswith("exports_") and path.suffix == ".zip":
            kind = "exports"
        else:
            continue

        stat = path.stat()
        files.append(
            BackupFile(
                path=path,
                kind=kind,
                size_bytes=int(stat.st_size),
                created_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    files.sort(key=lambda item: item.path.stat().st_mtime, reverse=True)
    return files[:limit]


def cleanup_old_backups(keep_files: int = DEFAULT_KEEP_FILES) -> list[Path]:
    directory = backup_dir()
    files = list_backups(limit=1000)

    if keep_files <= 0:
        keep_files = DEFAULT_KEEP_FILES

    to_delete = files[keep_files:]
    deleted: list[Path] = []

    for item in to_delete:
        try:
            item.path.unlink(missing_ok=True)
            deleted.append(item.path)
        except Exception:
            logger.exception("Failed to delete old backup: %s", item.path)

    return deleted


def backup_status_text(settings: Settings) -> str:
    directory = backup_dir()
    backups = list_backups(limit=10)

    database_path = Path(settings.database_path)
    exports_path = Path(settings.exports_dir)

    database_state = "найдена" if database_path.exists() else "не найдена"
    exports_state = "найдена" if exports_path.exists() else "не найдена"

    writable = _is_writable(directory)
    total_size = sum(item.size_bytes for item in backups)

    latest_text = "— backup-файлов пока нет."
    if backups:
        latest = backups[0]
        latest_text = (
            f"— последний: <code>{html.escape(latest.path.name)}</code>\n"
            f"— тип: <code>{latest.kind}</code>\n"
            f"— размер: <code>{format_bytes(latest.size_bytes)}</code>\n"
            f"— дата: <code>{html.escape(latest.created_at)}</code>"
        )

    return (
        "💾 <b>Backup Center</b>\n\n"
        "<b>Источник данных</b>\n"
        f"— SQLite: <code>{html.escape(str(database_path))}</code> / {database_state}\n"
        f"— exports: <code>{html.escape(str(exports_path))}</code> / {exports_state}\n\n"
        "<b>Хранилище backup</b>\n"
        f"— папка: <code>{html.escape(str(directory))}</code>\n"
        f"— доступ на запись: <code>{writable}</code>\n"
        f"— файлов в обзоре: <code>{len(backups)}</code>\n"
        f"— размер последних файлов: <code>{format_bytes(total_size)}</code>\n\n"
        "<b>Последний backup</b>\n"
        f"{latest_text}\n\n"
        "<b>Команды</b>\n"
        "— <code>/admin_backup_now</code> — создать backup сейчас;\n"
        "— <code>/admin_backups</code> — список последних backup."
    )


def backup_list_text(limit: int = 15) -> str:
    backups = list_backups(limit=limit)

    if not backups:
        return (
            "💾 <b>Backup-файлов пока нет</b>\n\n"
            "Создай первый backup командой <code>/admin_backup_now</code>."
        )

    lines = ["💾 <b>Последние backup-файлы</b>\n"]

    for index, item in enumerate(backups, start=1):
        icon = "🗄" if item.kind == "sqlite" else "📦"
        lines.append(
            f"{index}. {icon} <b>{html.escape(item.path.name)}</b>\n"
            f"Тип: <code>{item.kind}</code>\n"
            f"Размер: <code>{format_bytes(item.size_bytes)}</code>\n"
            f"Дата: <code>{html.escape(item.created_at)}</code>\n"
            f"Путь: <code>{html.escape(str(item.path))}</code>\n"
        )

    return "\n".join(lines)


def backup_created_text(result: BackupResult) -> str:
    lines = ["✅ <b>Backup создан</b>\n"]

    if result.created:
        lines.append("<b>Файлы</b>")
        for item in result.created:
            icon = "🗄" if item.kind == "sqlite" else "📦"
            lines.append(
                f"{icon} <code>{html.escape(item.path.name)}</code>\n"
                f"Размер: <code>{format_bytes(item.size_bytes)}</code>\n"
                f"Путь: <code>{html.escape(str(item.path))}</code>"
            )

    if result.skipped:
        lines.append("\n<b>Пропущено</b>")
        for item in result.skipped:
            lines.append(f"— {html.escape(item)};")

    if result.deleted:
        lines.append("\n<b>Удалены старые backup</b>")
        for path in result.deleted[:10]:
            lines.append(f"— <code>{html.escape(path.name)}</code>;")

    lines.append(
        "\n<b>Важно</b>\n"
        "Если файл больше лимита Telegram, бот не отправит его сообщением, но путь на сервере останется в отчёте."
    )

    return "\n".join(lines)


def files_safe_to_send(result: BackupResult, max_bytes: int = TELEGRAM_SAFE_FILE_BYTES) -> list[Path]:
    safe: list[Path] = []

    for item in result.created:
        if item.size_bytes <= max_bytes and item.path.exists():
            safe.append(item.path)

    return safe


def _backup_sqlite(settings: Settings, directory: Path, stamp: str) -> BackupFile | None:
    source = Path(settings.database_path)

    if not source.exists() or not source.is_file():
        return None

    target = directory / f"manager_ai_{stamp}.sqlite3"

    try:
        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(target)

        with target_conn:
            source_conn.backup(target_conn)

        source_conn.close()
        target_conn.close()
    except Exception:
        logger.exception("SQLite backup failed")
        try:
            source_conn.close()
        except Exception:
            pass
        try:
            target_conn.close()
        except Exception:
            pass
        target.unlink(missing_ok=True)
        return None

    stat = target.stat()
    return BackupFile(
        path=target,
        kind="sqlite",
        size_bytes=int(stat.st_size),
        created_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _backup_exports(settings: Settings, directory: Path, stamp: str) -> BackupFile | None:
    source = Path(settings.exports_dir)

    if not source.exists() or not source.is_dir():
        return None

    allowed_files = [
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in {".docx", ".pdf", ".txt", ".json"}
    ]

    if not allowed_files:
        return None

    target = directory / f"exports_{stamp}.zip"

    try:
        with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in allowed_files:
                archive.write(file_path, arcname=file_path.relative_to(source))
    except Exception:
        logger.exception("Exports backup failed")
        target.unlink(missing_ok=True)
        return None

    stat = target.stat()
    return BackupFile(
        path=target,
        kind="exports",
        size_bytes=int(stat.st_size),
        created_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


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
