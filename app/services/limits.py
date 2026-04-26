from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.storage.repositories import UsageRepository


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    used: int
    limit: int
    plan: str
    kind: str


def get_limit(settings: Settings, plan: str, kind: str) -> int:
    plan = plan.lower()

    if plan == "business":
        return (
            settings.business_daily_voice_limit
            if kind == "voice"
            else settings.business_daily_text_limit
        )

    if plan == "pro":
        return settings.pro_daily_voice_limit if kind == "voice" else settings.pro_daily_text_limit

    return settings.free_daily_voice_limit if kind == "voice" else settings.free_daily_text_limit


async def check_limit(
    usage_repo: UsageRepository,
    settings: Settings,
    user_id: int,
    plan: str,
    kind: str,
) -> LimitResult:
    used = await usage_repo.count_today(user_id=user_id, kind=kind)
    limit = get_limit(settings=settings, plan=plan, kind=kind)

    return LimitResult(
        allowed=used < limit,
        used=used,
        limit=limit,
        plan=plan,
        kind=kind,
    )


def limit_message(result: LimitResult) -> str:
    return (
        "🚧 **Лимит на сегодня исчерпан**\n\n"
        f"Тариф: `{result.plan}`\n"
        f"Тип: `{result.kind}`\n"
        f"Использовано: `{result.used}/{result.limit}`\n\n"
        "Что делать дальше:\n"
        "1. Продолжить завтра.\n"
        "2. Перейти на Pro/Business.\n"
        "3. Сократить количество тяжёлых запросов."
    )
