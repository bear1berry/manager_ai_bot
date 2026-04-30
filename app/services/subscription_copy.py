from __future__ import annotations

import html

from app.services.limits import (
    BUSINESS_STARS_PRICE,
    PRO_STARS_PRICE,
    SUBSCRIPTION_DAYS,
    normalize_plan,
    plan_display_name,
)


def plan_positioning(plan: str | None) -> str:
    normalized = normalize_plan(plan)

    if normalized == "admin":
        return "Режим владельца: полный доступ, диагностика, тестирование без лимитов."

    if normalized == "business":
        return "Командный контур: группы, память, документы из обсуждений и максимальные лимиты."

    if normalized == "pro":
        return "Личный рабочий контур: Deep Research, документы, проекты и повышенные лимиты."

    return "Стартовый контур: попробовать AI-менеджера, понять ценность и базовые сценарии."


def plan_badge(plan: str | None) -> str:
    normalized = normalize_plan(plan)

    mapping = {
        "free": "🆓 Free",
        "pro": "💎 Pro",
        "business": "🏢 Business",
        "admin": "🛡 Admin",
    }

    return mapping[normalized]


def unlocked_features(plan: str | None) -> list[str]:
    normalized = normalize_plan(plan)

    base = [
        "универсальный AI-ассистент",
        "режимы: клиент, хаос, план, продукт, стратег",
        "базовая работа с проектами",
        "Mini App как кабинет",
    ]

    if normalized in {"pro", "business", "admin"}:
        base.extend(
            [
                "Deep Research",
                "DOCX/PDF документы",
                "документ из диалога",
                "документ из проекта",
                "повышенные дневные лимиты",
                "комфортная ежедневная работа",
            ]
        )

    if normalized in {"business", "admin"}:
        base.extend(
            [
                "память Telegram-группы",
                "групповые сводки по переписке",
                "документы из группового обсуждения",
                "командные сценарии",
                "максимальные лимиты MVP",
            ]
        )

    if normalized == "admin":
        base.extend(
            [
                "ручное управление тарифами",
                "админ-диагностика",
                "без дневных ограничений",
            ]
        )

    return base


def locked_features(plan: str | None) -> list[str]:
    normalized = normalize_plan(plan)

    if normalized == "free":
        return [
            "Deep Research",
            "DOCX/PDF документы",
            "документ из диалога",
            "документ из проекта",
            "групповые документы",
            "память Telegram-группы",
            "командные сценарии Business",
        ]

    if normalized == "pro":
        return [
            "память Telegram-группы",
            "Business-лимиты",
            "командный AI-секретарь",
        ]

    return []


def recommended_upgrade(plan: str | None) -> str:
    normalized = normalize_plan(plan)

    if normalized == "free":
        return (
            "💎 <b>Рекомендуемый апгрейд: Pro</b>\n"
            f"Стоимость: <code>{PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "<b>Почему Pro</b>\n"
            "— открывает Deep Research;\n"
            "— включает DOCX/PDF;\n"
            "— превращает диалог в документ;\n"
            "— даёт больше лимитов;\n"
            "— подходит для личной рабочей продуктивности."
        )

    if normalized == "pro":
        return (
            "🏢 <b>Следующий уровень: Business</b>\n"
            f"Стоимость: <code>{BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</code>.\n\n"
            "<b>Почему Business</b>\n"
            "— память Telegram-группы;\n"
            "— AI-секретарь для команды;\n"
            "— документы из групповой переписки;\n"
            "— максимальные лимиты MVP."
        )

    if normalized == "business":
        return (
            "🏢 <b>Business активен</b>\n"
            "Ты на верхнем пользовательском тарифе. Следующий шаг — использовать группы, документы и Mini App как рабочую систему."
        )

    return (
        "🛡 <b>Admin активен</b>\n"
        "Полный доступ для тестирования продукта, диагностики и ручного управления тарифами."
    )


def feature_lines(items: list[str]) -> str:
    if not items:
        return "— всё ключевое уже открыто."

    return "\n".join(f"— {html.escape(item)};" for item in items)


def tariff_matrix_text() -> str:
    return (
        "💎 <b>Тарифы Менеджера ИИ</b>\n\n"
        "Не покупаешь “ещё один чат”. Открываешь рабочий контур: ресёрч, документы, проекты и команды.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🆓 <b>Free — попробовать</b>\n"
        "Для знакомства и базовых задач.\n\n"
        "Открыто:\n"
        "— универсальный ассистент;\n"
        "— базовые режимы;\n"
        "— Mini App;\n"
        "— ограниченные дневные запросы.\n\n"
        "Ограничено:\n"
        "— Deep Research;\n"
        "— DOCX/PDF;\n"
        "— память групп;\n"
        "— документы из групп.\n\n"
        "━━━━━━━━━━━━━━\n"
        f"💎 <b>Pro — {PRO_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</b>\n"
        "Для личной работы, проектов и документов.\n\n"
        "Открывает:\n"
        "— Deep Research;\n"
        "— DOCX/PDF документы;\n"
        "— документ из диалога;\n"
        "— документ из проекта;\n"
        "— больше лимитов;\n"
        "— комфортную ежедневную работу.\n\n"
        "━━━━━━━━━━━━━━\n"
        f"🏢 <b>Business — {BUSINESS_STARS_PRICE} ⭐ / {SUBSCRIPTION_DAYS} дней</b>\n"
        "Для команд, групп и активной нагрузки.\n\n"
        "Открывает:\n"
        "— всё из Pro;\n"
        "— память Telegram-группы;\n"
        "— групповые сводки;\n"
        "— документы из групповой переписки;\n"
        "— максимальные лимиты MVP;\n"
        "— AI-секретаря для команды.\n\n"
        "━━━━━━━━━━━━━━\n"
        "<b>Как оплатить</b>\n"
        "Нажми <b>💎 Pro</b> или <b>🏢 Business</b> ниже. Telegram создаст счёт в Stars, а тариф включится автоматически после оплаты."
    )


def invoice_intro_text(selected_plan: str, current_plan: str, current_expires_text: str) -> str:
    plan = normalize_plan(selected_plan)
    current = normalize_plan(current_plan)

    if plan == "business":
        title = "🏢 Business"
        price = BUSINESS_STARS_PRICE
        value = (
            "— всё из Pro;\n"
            "— память Telegram-группы;\n"
            "— документы из групповой переписки;\n"
            "— максимальные лимиты;\n"
            "— командные сценарии."
        )
    else:
        title = "💎 Pro"
        price = PRO_STARS_PRICE
        value = (
            "— Deep Research;\n"
            "— DOCX/PDF документы;\n"
            "— документ из диалога;\n"
            "— документ из проекта;\n"
            "— повышенные лимиты."
        )

    prolong_note = ""
    if current == plan:
        prolong_note = (
            "\n♻️ <b>Продление</b>\n"
            f"Текущий тариф действует до: <code>{html.escape(current_expires_text)}</code>.\n"
            "Новый срок прибавится к текущей дате окончания.\n"
        )

    return (
        "⭐ <b>Счёт Telegram Stars</b>\n\n"
        f"Тариф: <b>{title}</b>\n"
        f"Срок: <code>{SUBSCRIPTION_DAYS} дней</code>\n"
        f"Стоимость: <code>{price} ⭐</code>\n"
        f"{prolong_note}\n"
        "<b>Что откроется</b>\n"
        f"{value}\n\n"
        "После оплаты Telegram пришлёт подтверждение, а бот автоматически активирует тариф."
    )
