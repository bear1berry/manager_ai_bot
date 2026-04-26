from __future__ import annotations

import logging
from typing import Any

from app.storage.repositories import QueueRepository

logger = logging.getLogger(__name__)


async def enqueue_media_task(
    queue_repo: QueueRepository,
    kind: str,
    payload: dict[str, Any],
    dedupe_key: str,
) -> bool:
    task_id = await queue_repo.enqueue(kind=kind, payload=payload, dedupe_key=dedupe_key)

    if task_id is None:
        logger.info("Queue dedupe skipped: kind=%s dedupe_key=%s", kind, dedupe_key)
        return False

    logger.info("Task enqueued: id=%s kind=%s dedupe_key=%s", task_id, kind, dedupe_key)
    return True
