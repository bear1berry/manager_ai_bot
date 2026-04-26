from __future__ import annotations

from aiogram.types import User as TelegramUser

from app.config import get_settings
from app.services.payments import is_expired
from app.storage.repositories import UserRepository


async def ensure_user(repo: UserRepository, tg_user: TelegramUser) -> int:
    row = await repo.upsert_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )

    settings = get_settings()

    if settings.is_admin(telegram_id=tg_user.id, username=tg_user.username):
        current_plan = str(row["plan"] or "").lower()
        if current_plan != "admin":
            await repo.set_plan(
                telegram_id=tg_user.id,
                plan="admin",
                plan_expires_at=None,
            )

        refreshed = await repo.get_by_telegram_id(tg_user.id)
        if refreshed is not None:
            row = refreshed

        return int(row["id"])

    current_plan = str(row["plan"] or "free").lower()
    expires_at = row["plan_expires_at"]

    if current_plan in {"pro", "business"} and is_expired(expires_at):
        await repo.downgrade_to_free(tg_user.id)
        refreshed = await repo.get_by_telegram_id(tg_user.id)
        if refreshed is not None:
            row = refreshed

    return int(row["id"])
