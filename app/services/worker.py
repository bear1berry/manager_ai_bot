from __future__ import annotations

import asyncio
import html
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from app.config import Settings
from app.services.documents import DocumentService
from app.services.deep_research import DeepResearchService
from app.services.heavy_jobs import HEAVY_DEEP_RESEARCH, HEAVY_DOCUMENT, HEAVY_GROUP_DOCUMENT
from app.services.llm import LLMService
from app.services.audit import safe_record_audit_event
from app.services.speechkit import SpeechKitService
from app.storage.db import connect_db
from app.storage.repositories import DocumentRepository, MessageRepository, QueueRepository, UsageRepository
from app.utils.text import split_long_text, telegram_html_from_ai_text

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
                elif kind == HEAVY_DEEP_RESEARCH:
                    await self._handle_deep_research(payload)
                elif kind == HEAVY_DOCUMENT:
                    await self._handle_document(payload, is_group=False)
                elif kind == HEAVY_GROUP_DOCUMENT:
                    await self._handle_document(payload, is_group=True)
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
                user_id=user_db_id,
                telegram_id=int(payload.get("telegram_user_id") or 0) or None,
                chat_id=chat_id,
                feature="voice",
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



    async def _handle_deep_research(self, payload: dict) -> None:
        chat_id = int(payload["chat_id"])
        user_db_id = int(payload["user_db_id"])
        telegram_id = int(payload.get("telegram_id") or 0) or None
        user_text = str(payload["user_text"])
        mode = str(payload.get("mode") or "assistant")
        history = payload.get("history") or []
        extra_context = str(payload.get("extra_context") or "")

        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "🔎 <b>Deep Research в работе</b>\n\n"
                "Задача ушла в worker. Собираю источники и готовлю выводы."
            ),
            parse_mode="HTML",
        )

        service = DeepResearchService(self.settings)

        try:
            result = await service.run(
                user_text=user_text,
                history=history,
                mode=mode,
                extra_context=extra_context,
            )

            async with await connect_db(self.settings.database_path) as db:
                msg_repo = MessageRepository(db)
                await msg_repo.add(user_id=user_db_id, role="assistant", content=result.answer)
                await safe_record_audit_event(
                    db=db,
                    event_type="heavy.deep_research.done",
                    user_id=user_db_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    target_type="queue_job",
                    metadata={
                        "mode": mode,
                        "sources": len(result.sources),
                    },
                )

            chunks = split_long_text(result.answer)
            for chunk in chunks:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=telegram_html_from_ai_text(chunk),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )

            sources_html = service.format_sources_html(result)
            if sources_html:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=sources_html,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )

        except Exception as exc:
            async with await connect_db(self.settings.database_path) as db:
                await safe_record_audit_event(
                    db=db,
                    event_type="heavy.deep_research.failed",
                    user_id=user_db_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    target_type="queue_job",
                    metadata={"error": str(exc)[:800]},
                )
            raise

    async def _handle_document(self, payload: dict, is_group: bool) -> None:
        chat_id = int(payload["chat_id"])
        user_db_id = int(payload["user_db_id"])
        telegram_id = int(payload.get("telegram_id") or 0) or None
        source_text = str(payload["source_text"])
        doc_type = str(payload["doc_type"])
        title = str(payload["title"])
        group_chat_id = payload.get("group_chat_id")

        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "📄 <b>Генерирую документ</b>\n\n"
                "Задача выполняется в worker: готовлю структуру, DOCX и PDF."
            ),
            parse_mode="HTML",
        )

        llm = LLMService(self.settings)
        document_service = DocumentService(self.settings)

        try:
            document_data = await llm.generate_document_data(
                source_text=source_text,
                doc_type=doc_type,
                title=title,
                user_id=user_db_id,
                telegram_id=telegram_id,
                chat_id=chat_id,
            )
            generated = document_service.generate_from_data(
                data=document_data,
                fallback_title=title,
            )

            document_title = str(document_data.get("title") or title)

            async with await connect_db(self.settings.database_path) as db:
                document_repo = DocumentRepository(db)

                try:
                    document_id = await document_repo.create(
                        user_id=user_db_id,
                        doc_type=doc_type,
                        title=document_title,
                        docx_path=str(generated.docx_path),
                        pdf_path=str(generated.pdf_path) if generated.pdf_path else None,
                        status="created",
                        group_chat_id=int(group_chat_id) if group_chat_id is not None else None,
                    )
                except TypeError:
                    # Backward compatibility if local DocumentRepository has not yet accepted group_chat_id.
                    document_id = await document_repo.create(
                        user_id=user_db_id,
                        doc_type=doc_type,
                        title=document_title,
                        docx_path=str(generated.docx_path),
                        pdf_path=str(generated.pdf_path) if generated.pdf_path else None,
                        status="created",
                    )

                await MessageRepository(db).add(
                    user_id=user_db_id,
                    role="assistant",
                    content=f"Документ создан через очередь: {document_title}",
                )

                await safe_record_audit_event(
                    db=db,
                    event_type="heavy.group_document.done" if is_group else "heavy.document.done",
                    user_id=user_db_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    target_type="document",
                    target_id=document_id,
                    metadata={
                        "doc_type": doc_type,
                        "title": document_title,
                        "group_chat_id": group_chat_id,
                    },
                )

            await self.bot.send_message(
                chat_id=chat_id,
                text=(
                    "✅ <b>Документ готов</b>\n\n"
                    f"Название: <b>{html.escape(document_title)}</b>\n"
                    "Файлы отправляю ниже."
                ),
                parse_mode="HTML",
            )

            await self.bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(generated.docx_path),
                caption=f"📄 {document_title} / DOCX",
            )

            if generated.pdf_path and Path(generated.pdf_path).exists():
                await self.bot.send_document(
                    chat_id=chat_id,
                    document=FSInputFile(generated.pdf_path),
                    caption=f"📄 {document_title} / PDF",
                )

        except Exception as exc:
            async with await connect_db(self.settings.database_path) as db:
                await safe_record_audit_event(
                    db=db,
                    event_type="heavy.group_document.failed" if is_group else "heavy.document.failed",
                    user_id=user_db_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    target_type="queue_job",
                    metadata={
                        "doc_type": doc_type,
                        "title": title,
                        "error": str(exc)[:800],
                    },
                )
            raise
