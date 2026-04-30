from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from app.api.miniapp import start_miniapp_api
from app.bot.commands import setup_bot_commands
from app.config import get_settings
from app.routers import setup_routers
from app.services.backup_scheduler import BackupScheduler, stop_backup_scheduler
from app.services.worker import QueueWorker
from app.storage.db import init_db
from app.utils.files import ensure_dir
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    ensure_dir(settings.exports_path)
    ensure_dir(settings.logs_path)
    ensure_dir("data")
    ensure_dir("backups")

    setup_logging(settings.logs_path)
    await init_db(settings.database_path)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher()
    dispatcher.include_router(setup_routers())

    worker = QueueWorker(settings=settings, bot=bot)
    backup_scheduler = BackupScheduler(settings)
    worker_task: asyncio.Task | None = None
    backup_task: asyncio.Task | None = None
    api_runner: web.AppRunner | None = None

    try:
        try:
            await setup_bot_commands(bot)
            logger.info("Bot commands installed")
        except TelegramNetworkError:
            logger.exception("Failed to set bot commands. Continue startup without commands.")

        api_runner = await start_miniapp_api(settings)

        worker_task = asyncio.create_task(worker.start(), name="queue-worker")
        backup_task = asyncio.create_task(backup_scheduler.start(), name="backup-scheduler")

        logger.info("Bot polling started: %s", settings.app_name)
        await dispatcher.start_polling(bot)

    finally:
        await stop_backup_scheduler(backup_task, backup_scheduler)

        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task

        if api_runner is not None:
            await api_runner.cleanup()

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
