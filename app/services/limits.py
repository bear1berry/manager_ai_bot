from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.storage.repositories import UsageRepository

ADMIN_LIMIT = 999_999_999


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    used: int
    limit: int
    plan: str
    kind: str

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)


@dataclass(frozen=True)
class PlanLimits:
    plan: str
    text_limit: int
    voice_limit: int


def normalize_plan(plan: str | None) -> str:
    value = (plan or "free").strip().lower()
    if value not in {"free", "pro", "business", "admin"}:
        return "free"
    return value


def get_plan_limits(settings: Settings, plan: str) -> PlanLimits:
    normalized = normalize_plan(plan)

    if normalized == "admin":
        return PlanLimits(
            plan="admin",
            text_limit=ADMIN_LIMIT,
            voice_limit=ADMIN_LIMIT,
        )

    if normalized == "business":
        return PlanLimits(
            plan="business",
            text_limit=settings.business_daily_text_limit,
            voice_limit=settings.business_daily_voice_limit,
        )

    if normalized == "pro":
        return PlanLimits(
            plan="pro",
            text_limit=settings.pro_daily_text_limit,
            voice_limit=settings.pro_daily_voice_limit,
        )

    return PlanLimits(
        plan="free",
        text_limit=settings.free_daily_text_limit,
        voice_limit=settings.free_daily_voice_limit,
    )


def get_limit(settings: Settings, plan: str, kind: str) -> int:
    limits = get_plan_limits(settings=settings, plan=plan)
    return limits.voice_limit if kind == "voice" else limits.text_limit


async def check_limit(
    usage_repo: UsageRepository,
    settings: Settings,
    user_id: int,
    plan: str,
    kind: str,
) -> LimitResult:
    normalized_plan = normalize_plan(plan)
    used = await usage_repo.count_today(user_id=user_id, kind=kind)
    limit = get_limit(settings=settings, plan=normalized_plan, kind=kind)

    if normalized_plan == "admin":
        return LimitResult(
            allowed=True,
            used=used,
            limit=limit,
            plan=normalized_plan,
            kind=kind,
        )

    return LimitResult(
        allowed=used < limit,
        used=used,
        limit=limit,
        plan=normalized_plan,
        kind=kind,
    )


def plan_display_name(plan: str | None) -> str:
    normalized = normalize_plan(plan)

    mapping = {
        "free": "Free",
        "pro": "Pro",
        "business": "Business",
        "admin": "Admin",
    }

    return mapping[normalized]


def usage_line(label: str, used: int, limit: int) -> str:
    if limit >= ADMIN_LIMIT:
        return f"— {label}: `{used}/∞` · без ограничений"

    remaining = max(limit - used, 0)
    return f"— {label}: `{used}/{limit}` · осталось `{remaining}`"


def plan_features(plan: str | None) -> list[str]:
    normalized = normalize_plan(plan)

    if normalized == "admin":
        return [
            "режим администратора без дневных ограничений",
            "доступ ко всем MVP-функциям",
            "проекты и рабочий контекст",
            "DOCX/PDF документы",
            "голосовые через очередь",
            "ручное управление тарифами пользователей",
        ]

    if normalized == "business":
        return [
            "высокие дневные лимиты",
            "проекты и рабочий контекст",
            "DOCX/PDF документы",
            "голосовые через очередь",
            "будущие бизнес-шаблоны и командные сценарии",
        ]

    if normalized == "pro":
        return [
            "увеличенные дневные лимиты",
            "проекты и рабочий контекст",
            "DOCX/PDF документы",
            "больше голосовых",
            "приоритет на продуктивные сценарии",
        ]

    return [
        "базовый AI-ассистент",
        "ограниченные дневные запросы",
        "проекты в MVP-режиме",
        "документы в демо-режиме",
        "голосовые с малым лимитом",
    ]


def next_plan_suggestion(plan: str | None) -> str:
    normalized = normalize_plan(plan)

    if normalized == "admin":
        return (
            "🛡 **Admin активен**\n"
            "Лимиты отключены. Можно тестировать продукт без ограничений и вручную управлять тарифами."
        )

    if normalized == "free":
        return (
            "💎 **Что даст Pro:**\n"
            "— больше текстовых запросов;\n"
            "— больше голосовых;\n"
            "— полноценная работа с DOCX/PDF;\n"
            "— удобнее вести проекты и клиентов."
        )

    if normalized == "pro":
        return (
            "🏢 **Что даст Business:**\n"
            "— максимальные лимиты;\n"
            "— больше пространства под рабочие сценарии;\n"
            "— будущие шаблоны для бизнеса;\n"
            "— подготовка к командному использованию."
        )

    return (
        "🏢 **Business активен**\n"
        "Ты уже на верхнем уровне MVP. Следующий шаг — подключение оплат, брендирования и расширенной памяти."
    )


def limit_message(result: LimitResult) -> str:
    return (
        "🚧 **Лимит на сегодня исчерпан**\n\n"
        f"Тариф: `{plan_display_name(result.plan)}`\n"
        f"Тип: `{result.kind}`\n"
        f"Использовано: `{result.used}/{result.limit}`\n\n"
        "Что делать дальше:\n"
        "1. Продолжить завтра.\n"
        "2. Перейти на Pro/Business.\n"
        "3. Сократить количество тяжёлых запросов."
    )
