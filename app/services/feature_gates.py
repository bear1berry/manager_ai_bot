from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal

from app.services.limits import BUSINESS_STARS_PRICE, PRO_STARS_PRICE, SUBSCRIPTION_DAYS, normalize_plan, plan_display_name


FeatureKey = Literal[
    "web_search",
    "deep_research",
    "documents",
    "projects",
    "group_gpt",
    "group_memory",
    "group_documents",
    "miniapp_groups",
]


@dataclass(frozen=True)
class FeatureGateResult:
    allowed: bool
    feature: FeatureKey
    plan: str
    required_plan: str
    title: str
    message: str


PLAN_LEVELS = {
    "free": 0,
    "pro": 1,
    "business": 2,
    "admin": 99,
}


FEATURE_REQUIRED_PLAN: dict[FeatureKey, str] = {
    "web_search": "free",
    "deep_research": "pro",
    "documents": "pro",
    "projects": "free",
    "group_gpt": "free",
    "group_memory": "business",
    "group_documents": "pro",
    "miniapp_groups": "pro",
}


FEATURE_TITLES: dict[FeatureKey, str] = {
    "web_search": "Web Search",
    "deep_research": "Deep Research",
    "documents": "DOCX/PDF документы",
    "projects": "Проекты",
    "group_gpt": "Групповой GPT",
    "group_memory": "Память группы",
    "group_documents": "Документы из группы",
    "miniapp_groups": "Группы в Mini App",
}


FEATURE_VALUE: dict[FeatureKey, list[str]] = {
    "web_search": [
        "поиск актуальных данных",
        "источники для проверки",
        "выводы на основе свежего контекста",
    ],
    "deep_research": [
        "несколько поисковых запросов",
        "сравнение источников",
        "выводы, риски и рекомендации",
        "плотный исследовательский отчёт",
    ],
    "documents": [
        "DOCX/PDF файлы",
        "структура под рабочий документ",
        "история документов в Mini App",
        "быстрое превращение диалога в файл",
    ],
    "projects": [
        "рабочая память по клиентам и задачам",
        "заметки и решения",
        "документы из проекта",
    ],
    "group_gpt": [
        "ответы в Telegram-группе",
        "сводки и анализ обсуждений",
        "помощь команде прямо в чате",
    ],
    "group_memory": [
        "память групповой переписки",
        "сводки за день / час / весь период",
        "контекст для командных решений",
        "AI-секретарь для команды",
    ],
    "group_documents": [
        "протоколы по переписке",
        "планы действий по обсуждению",
        "DOCX/PDF из группового контекста",
    ],
    "miniapp_groups": [
        "панель групп",
        "статус памяти",
        "активность и документы групп",
    ],
}


def can_use_feature(plan: str | None, feature: FeatureKey) -> bool:
    normalized = normalize_plan(plan)
    required = FEATURE_REQUIRED_PLAN[feature]

    return PLAN_LEVELS[normalized] >= PLAN_LEVELS[required]


def check_feature(plan: str | None, feature: FeatureKey) -> FeatureGateResult:
    normalized = normalize_plan(plan)
    required = FEATURE_REQUIRED_PLAN[feature]
    allowed = can_use_feature(normalized, feature)

    return FeatureGateResult(
        allowed=allowed,
        feature=feature,
        plan=normalized,
        required_plan=required,
        title=FEATURE_TITLES[feature],
        message="" if allowed else build_paywall_text(feature=feature, plan=normalized, required_plan=required),
    )


def build_paywall_text(feature: FeatureKey, plan: str | None, required_plan: str | None = None) -> str:
    normalized = normalize_plan(plan)
    required = normalize_plan(required_plan or FEATURE_REQUIRED_PLAN[feature])
    title = FEATURE_TITLES[feature]
    values = FEATURE_VALUE.get(feature, [])

    value_lines = "\n".join(f"— {html.escape(item)};" for item in values)

    price_line = _price_line(required)
    current_plan = plan_display_name(normalized)
    required_name = plan_display_name(required)

    return (
        "💎 <b>Это премиум-функция</b>\n\n"
        f"<b>{html.escape(title)}</b> доступен на тарифе <b>{required_name}</b> и выше.\n\n"
        "<b>Что даёт эта функция</b>\n"
        f"{value_lines}\n\n"
        f"Текущий тариф: <b>{current_plan}</b>.\n"
        f"{price_line}\n\n"
        "Чтобы открыть доступ, нажми <b>💎 Подписка</b> в профиле или нижнем меню."
    )


def short_paywall_text(feature: FeatureKey, plan: str | None) -> str:
    normalized = normalize_plan(plan)
    required = FEATURE_REQUIRED_PLAN[feature]

    return (
        f"💎 <b>{html.escape(FEATURE_TITLES[feature])}</b> — функция тарифа "
        f"<b>{plan_display_name(required)}</b> и выше.\n\n"
        f"Текущий тариф: <b>{plan_display_name(normalized)}</b>.\n"
        "Открой <b>💎 Подписка</b>, чтобы усилить доступ."
    )


def is_deep_research_request(text: str) -> bool:
    lower = text.lower()

    markers = [
        "deep research",
        "глубокий ресерч",
        "глубокое исследование",
        "исследуй глубоко",
        "глубоко изучи",
        "проведи исследование",
        "сделай исследование",
        "сделай ресерч",
        "найди и проанализируй",
        "сравни источники",
    ]

    return any(marker in lower for marker in markers)


def _price_line(required_plan: str) -> str:
    if required_plan == "business":
        return f"Business: <code>{BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>."

    if required_plan == "pro":
        return f"Pro: <code>{PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>."

    return "Доступно на текущем тарифе."
