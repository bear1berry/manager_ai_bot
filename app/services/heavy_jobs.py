from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.storage.repositories import QueueRepository

logger = logging.getLogger(__name__)

HEAVY_DEEP_RESEARCH = "heavy_deep_research"
HEAVY_DOCUMENT = "heavy_document"
HEAVY_GROUP_DOCUMENT = "heavy_group_document"


def make_dedupe_key(kind: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{kind}:{digest}"


async def enqueue_heavy_job(
    queue_repo: QueueRepository,
    *,
    kind: str,
    payload: dict[str, Any],
    dedupe_key: str,
) -> bool:
    task_id = await queue_repo.enqueue(
        kind=kind,
        payload=payload,
        dedupe_key=dedupe_key,
    )

    if task_id is None:
        logger.info("Heavy job dedupe skipped: kind=%s dedupe_key=%s", kind, dedupe_key)
        return False

    logger.info("Heavy job enqueued: id=%s kind=%s dedupe_key=%s", task_id, kind, dedupe_key)
    return True


def queued_text(kind: str, inserted: bool) -> str:
    if not inserted:
        return (
            "♻️ <b>Эта задача уже в очереди</b>\n\n"
            "Дубликат не создаю. Как только обработка закончится — результат придёт в чат."
        )

    if kind == HEAVY_DEEP_RESEARCH:
        return (
            "🔎 <b>Deep Research принят в работу</b>\n\n"
            "Я поставил задачу в очередь:\n"
            "— соберу web-контекст;\n"
            "— сравню источники;\n"
            "— выделю выводы и риски;\n"
            "— верну результат сюда.\n\n"
            "Можно продолжать пользоваться ботом — polling не блокируется."
        )

    if kind in {HEAVY_DOCUMENT, HEAVY_GROUP_DOCUMENT}:
        return (
            "📄 <b>Документ принят в работу</b>\n\n"
            "Я поставил генерацию DOCX/PDF в очередь:\n"
            "— соберу структуру;\n"
            "— создам файлы;\n"
            "— сохраню документ;\n"
            "— отправлю результат сюда.\n\n"
            "Дубликаты не плодим, очередь держим чистой."
        )

    return (
        "⚙️ <b>Задача принята в работу</b>\n\n"
        "Результат придёт сюда после обработки."
    )
