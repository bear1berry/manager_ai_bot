from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.storage.repositories import UsageRepository

ADMIN_LIMIT = 999_999_999

PRO_STARS_PRICE = 299
BUSINESS_STARS_PRICE = 999
SUBSCRIPTION_DAYS = 30


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
        return f"— {label}: <code>{used}/∞</code> · без ограничений"

    remaining = max(limit - used, 0)
    return f"— {label}: <code>{used}/{limit}</code> · осталось <code>{remaining}</code>"


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
            "максимальные дневные лимиты MVP",
            "проекты и рабочий контекст",
            "DOCX/PDF документы",
            "голосовые через очередь",
            "комфортный режим для активной рабочей нагрузки",
            "база под будущие бизнес-шаблоны",
        ]

    if normalized == "pro":
        return [
            "увеличенные дневные лимиты",
            "проекты и рабочий контекст",
            "DOCX/PDF документы",
            "больше голосовых",
            "комфортная ежедневная работа",
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
            "🛡 <b>Admin активен</b>\n"
            "Лимиты отключены. Можно тестировать продукт без ограничений и вручную управлять тарифами."
        )

    if normalized == "free":
        return (
            "💎 <b>Рекомендуемый следующий шаг</b>\n"
            f"Pro за <code>{PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "<b>Что даст Pro</b>\n"
            "— больше текстовых запросов;\n"
            "— больше голосовых;\n"
            "— полноценная работа с DOCX/PDF;\n"
            "— удобнее вести проекты и клиентов."
        )

    if normalized == "pro":
        return (
            "🏢 <b>Можно усилить до Business</b>\n"
            f"Business за <code>{BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "<b>Что даст Business</b>\n"
            "— максимальные лимиты MVP;\n"
            "— больше пространства под рабочие сценарии;\n"
            "— будущие бизнес-шаблоны;\n"
            "— подготовка к командному использованию."
        )

    return (
        "🏢 <b>Business активен</b>\n"
        "Ты уже на верхнем уровне MVP. Следующий шаг — тестировать продукт на реальных рабочих сценариях."
    )


def limit_message(result: LimitResult) -> str:
    plan = normalize_plan(result.plan)
    kind_label = "голосовые" if result.kind == "voice" else "текстовые запросы"

    if plan == "free":
        return (
            "🚧 <b>Лимит на сегодня исчерпан</b>\n\n"
            f"Ты использовал Free-лимит на <b>{kind_label}</b>:\n"
            f"— использовано: <code>{result.used}/{result.limit}</code>.\n\n"
            "💎 <b>Что даст Pro</b>\n"
            "— больше запросов каждый день;\n"
            "— больше голосовых;\n"
            "— DOCX/PDF документы;\n"
            "— удобная работа с проектами и клиентами.\n\n"
            f"Стоимость: <code>{PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "Чтобы продолжить без ожидания, нажми <b>💎 Подписка</b> в нижнем меню."
        )

    if plan == "pro":
        return (
            "🚧 <b>Лимит Pro на сегодня исчерпан</b>\n\n"
            f"Тип: <b>{kind_label}</b>\n"
            f"Использовано: <code>{result.used}/{result.limit}</code>.\n\n"
            "🏢 <b>Что даст Business</b>\n"
            "— максимальные лимиты MVP;\n"
            "— комфорт для активной рабочей нагрузки;\n"
            "— больше пространства под документы, проекты и голосовые.\n\n"
            f"Стоимость: <code>{BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "Чтобы усилить тариф, нажми <b>💎 Подписка</b>."
        )

    return (
        "🚧 <b>Лимит на сегодня исчерпан</b>\n\n"
        f"Тариф: <b>{plan_display_name(result.plan)}</b>\n"
        f"Тип: <b>{kind_label}</b>\n"
        f"Использовано: <code>{result.used}/{result.limit}</code>.\n\n"
        "Что можно сделать:\n"
        "— продолжить завтра;\n"
        "— сократить количество тяжёлых запросов;\n"
        "— проверить тариф в профиле."
    )


def stars_pricing_summary() -> str:
    return (
        f"💎 Pro — <code>{PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>\n"
        f"🏢 Business — <code>{BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>"
    )
