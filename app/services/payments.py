from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4


SUBSCRIPTION_DAYS = 30

PLAN_STARS_PRICES = {
    "pro": 299,
    "business": 999,
}

PLAN_TITLES = {
    "pro": "Pro",
    "business": "Business",
}


@dataclass(frozen=True)
class StarsPlan:
    plan: str
    title: str
    stars_amount: int
    days: int
    payload: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sqlite_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_sqlite_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_expired(expires_at: str | None) -> bool:
    parsed = parse_sqlite_datetime(expires_at)
    if parsed is None:
        return False

    return parsed <= utc_now()


def calculate_expiry(days: int = SUBSCRIPTION_DAYS, current_expires_at: str | None = None) -> str:
    """
    Если подписка ещё активна — продлеваем от текущей даты окончания.
    Если подписка истекла или даты нет — считаем от текущего момента.
    """
    now = utc_now()
    current_expiry = parse_sqlite_datetime(current_expires_at)

    if current_expiry and current_expiry > now:
        base = current_expiry
    else:
        base = now

    return sqlite_datetime(base + timedelta(days=days))


def build_stars_plan(plan: str) -> StarsPlan:
    normalized = plan.strip().lower()

    if normalized not in PLAN_STARS_PRICES:
        raise ValueError(f"Unsupported Stars plan: {plan}")

    return StarsPlan(
        plan=normalized,
        title=PLAN_TITLES[normalized],
        stars_amount=PLAN_STARS_PRICES[normalized],
        days=SUBSCRIPTION_DAYS,
        payload=f"stars:{normalized}:{SUBSCRIPTION_DAYS}:{uuid4().hex}",
    )


def validate_stars_payload(payload: str | None) -> bool:
    if not payload:
        return False

    parts = payload.split(":")
    if len(parts) != 4:
        return False

    prefix, plan, days, unique_id = parts

    if prefix != "stars":
        return False

    if plan not in PLAN_STARS_PRICES:
        return False

    if days != str(SUBSCRIPTION_DAYS):
        return False

    if not unique_id or len(unique_id) < 12:
        return False

    return True


def plan_from_payload(payload: str) -> str | None:
    if not validate_stars_payload(payload):
        return None

    return payload.split(":")[1]


def format_plan_expiry(expires_at: str | None, plan: str) -> str:
    normalized = (plan or "free").strip().lower()

    if normalized == "admin":
        return "∞"

    if normalized == "free":
        return "—"

    parsed = parse_sqlite_datetime(expires_at)
    if parsed is None:
        return "—"

    return parsed.strftime("%d.%m.%Y")


def payment_success_text(plan: str, expires_at: str) -> str:
    normalized = plan.strip().lower()
    title = PLAN_TITLES.get(normalized, normalized.title())

    return (
        "✅ <b>Оплата прошла успешно</b>\n\n"
        f"Тариф: <b>{title}</b>\n"
        "Срок: <code>30 дней</code>\n"
        f"Действует до: <code>{format_plan_expiry(expires_at, normalized)}</code>\n\n"
        "<b>Что теперь доступно</b>\n"
        "— больше запросов каждый день;\n"
        "— больше голосовых;\n"
        "— DOCX/PDF документы;\n"
        "— комфортная работа с проектами и клиентами.\n\n"
        "<b>С чего начать</b>\n"
        "— 🧠 Ассистент — решить рабочую задачу;\n"
        "— 🗂 Проекты — сохранить контекст;\n"
        "— 📄 Документы — собрать файл."
    )
