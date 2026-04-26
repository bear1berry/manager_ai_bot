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


def calculate_expiry(days: int = SUBSCRIPTION_DAYS) -> str:
    return sqlite_datetime(utc_now() + timedelta(days=days))


def is_expired(expires_at: str | None) -> bool:
    parsed = parse_sqlite_datetime(expires_at)
    if parsed is None:
        return False

    return parsed <= utc_now()


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
