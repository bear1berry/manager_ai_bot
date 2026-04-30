from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.config import Settings
from app.services.backup import create_backup

logger = logging.getLogger(__name__)


class BackupScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.auto_backup_enabled:
            logger.info("Auto backup disabled")
            return

        start_delay = max(0, int(self.settings.auto_backup_start_delay_seconds))
        interval_hours = max(1, int(self.settings.auto_backup_interval_hours))
        interval_seconds = interval_hours * 60 * 60
        keep_files = max(2, int(self.settings.auto_backup_keep_files))

        logger.info(
            "Auto backup scheduler started: delay=%ss interval=%sh keep=%s",
            start_delay,
            interval_hours,
            keep_files,
        )

        if start_delay > 0:
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=start_delay)
                return
            except asyncio.TimeoutError:
                pass

        while not self._stopped.is_set():
            await self._run_once(keep_files=keep_files)

            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        self._stopped.set()

    async def _run_once(self, keep_files: int) -> None:
        try:
            result = await asyncio.to_thread(
                create_backup,
                self.settings,
                keep_files,
            )

            created_names = ", ".join(item.path.name for item in result.created) or "none"
            skipped = ", ".join(result.skipped) or "none"

            logger.info(
                "Auto backup completed: created=%s skipped=%s deleted=%s",
                created_names,
                skipped,
                len(result.deleted),
            )
        except Exception:
            logger.exception("Auto backup failed")


async def stop_backup_scheduler(task: asyncio.Task | None, scheduler: BackupScheduler | None) -> None:
    if scheduler is not None:
        await scheduler.stop()

    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
