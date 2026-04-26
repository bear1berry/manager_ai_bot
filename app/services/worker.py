from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot

from app.config import Settings
from app.services.llm import LLMService
from app.services.speechkit import SpeechKitService
from app.storage.db import connect_db
from app.storage.repositories import MessageRepository, QueueRepository, UsageRepository

logger = logging.getLogger(__name__)


class QueueWorker:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        poll_interval_seconds: float = 2.0,
        max_attempts: int = 3,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.poll_interval_seconds = poll_interval_seconds
        self.max_attempts = max_attempts
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        logger.info("Queue worker started")

        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("Queue worker tick failed")
                await asyncio.sleep(self.poll_interval_seconds)

            await asyncio.sleep(self.poll_interval_seconds)

        logger.info("Queue worker stopped")

    async def stop(self) -> None:
        self._stop_event.set()

    async def _tick(self) -> None:
        async with await connect_db(self.settings.database_path) as db:
            queue_repo = QueueRepository(db)
            row = await queue_repo.claim_next()

            if row is None:
                return

            queue_id = int(row["id"])
            kind = str(row["kind"])
            payload = queue_repo.parse_payload(row)

            logger.info("Task claimed: id=%s kind=%s attempts=%s", queue_id, kind, row["attempts"])

            try:
                if kind == "voice_transcribe":
                    await self._handle_voice(payload)
                else:
                    raise RuntimeError(f"Unknown task kind: {kind}")

                await queue_repo.mark_done(queue_id)
                logger.info("Task done: id=%s kind=%s", queue_id, kind)
            except Exception as exc:
                logger.exception("Task failed: id=%s kind=%s", queue_id, kind)
                await queue_repo.mark_failed_or_retry(
                    queue_id=queue_id,
                    error=str(exc),
                    max_attempts=self.max_attempts,
                )

    async def _handle_voice(self, payload: dict) -> None:
        chat_id = int(payload["chat_id"])
        user_db_id = int(payload["user_db_id"])
        file_path = Path(str(payload["file_path"]))

        speechkit = SpeechKitService(self.settings)
        llm = LLMService(self.settings)

        await self.bot.send_message(
            chat_id=chat_id,
            text="🎧 Голосовое получил. Разбираю и превращаю в структуру.",
        )

        transcript = await speechkit.transcribe_ogg(file_path)

        async with await connect_db(self.settings.database_path) as db:
            msg_repo = MessageRepository(db)
            usage_repo = UsageRepository(db)

            await usage_repo.add(user_id=user_db_id, kind="voice")
            await msg_repo.add(user_id=user_db_id, role="user", content=f"[voice] {transcript}")

            answer = await llm.complete(
                user_text=transcript,
                history=await msg_repo.recent(user_id=user_db_id, limit=10),
                mode="chaos",
            )

            await msg_repo.add(user_id=user_db_id, role="assistant", content=answer)

        await self.bot.send_message(
            chat_id=chat_id,
            text=f"🗣 **Распознал голосовое:**\n\n{transcript[:1500]}",
            parse_mode="Markdown",
        )
        await self.bot.send_message(
            chat_id=chat_id,
            text=answer,
            parse_mode="Markdown",
        )
