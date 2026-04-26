from __future__ import annotations

from aiogram.types import User as TelegramUser

from app.storage.repositories import UserRepository


async def ensure_user(repo: UserRepository, tg_user: TelegramUser) -> int:
    row = await repo.upsert_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    return int(row["id"])
