from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.commands import setup_bot_commands
from app.config import get_settings
from app.routers import setup_routers
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

    setup_logging(settings.logs_dir)
    await init_db(settings.database_path)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(setup_routers())

    try:
        await setup_bot_commands(bot)
        logger.info("Bot commands installed")
    except Exception:
        logger.exception("Failed to set bot commands. Continue startup without commands.")

    worker = QueueWorker(bot=bot, settings=settings)
    worker_task = asyncio.create_task(worker.start())

    stop_event = asyncio.Event()

    def _stop() -> None:
        logger.info("Stop signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()

    with suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)

    try:
        logger.info("Bot polling started: %s", settings.app_name)
        polling_task = asyncio.create_task(dp.start_polling(bot))
        await stop_event.wait()
        polling_task.cancel()

        with suppress(asyncio.CancelledError):
            await polling_task
    finally:
        await worker.stop()
        worker_task.cancel()

        with suppress(asyncio.CancelledError):
            await worker_task

        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
