from __future__ import annotations

import random
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalityDecision:
    enabled: bool
    level: str
    title: str
    instruction: str


DISABLE_MARKERS = [
    "без шуток",
    "без юмора",
    "строго",
    "официально",
    "сухо",
    "без дерзости",
    "без сарказма",
    "максимально формально",
    "деловой стиль",
    "официальный стиль",
]

RISK_MARKERS = [
    "врач",
    "медицина",
    "медицин",
    "симптом",
    "диагноз",
    "лечение",
    "лекарство",
    "препарат",
    "анализы",
    "боль",
    "температура",
    "юрид",
    "закон",
    "иск",
    "суд",
    "штраф",
    "договор",
    "налог",
    "финанс",
    "инвестиции",
    "кредит",
    "долг",
    "банкрот",
    "ошибка",
    "не работает",
    "упал",
    "краш",
    "traceback",
    "exception",
    "авария",
    "угроза",
    "самоповреж",
    "суицид",
]

SPICE_FRIENDLY_MODES = {
    "assistant",
    "chaos",
    "plan",
    "product",
    "strategy",
}

NO_SPICE_MODES = {
    "client_reply",
    "medicine",
    "legal",
    "finance",
}


def decide_personality(
    user_text: str,
    mode: str,
    is_group: bool = False,
    is_document: bool = False,
) -> PersonalityDecision:
    text = _normalize(user_text)

    if is_document:
        return _disabled("Документный режим")

    if mode in NO_SPICE_MODES:
        return _disabled("Строгий режим")

    if any(marker in text for marker in DISABLE_MARKERS):
        return _disabled("Пользователь попросил без юмора")

    if any(marker in text for marker in RISK_MARKERS):
        return _disabled("Высокорисковая или чувствительная тема")

    if mode not in SPICE_FRIENDLY_MODES:
        return _disabled("Нейтральный режим")

    direct_markers = [
        "дерзко",
        "дерзкий",
        "добавь огня",
        "с огнем",
        "с огнём",
        "жестче",
        "жёстче",
        "заряди",
        "поострее",
        "с характером",
    ]

    if any(marker in text for marker in direct_markers):
        return _enabled(level="high", is_group=is_group)

    if _is_too_serious(text):
        return _disabled("Слишком серьёзный контекст")

    chance = 0.25 if not is_group else 0.18

    if random.random() <= chance:
        return _enabled(level="medium", is_group=is_group)

    return _disabled("Спонтанный spice не выбран")


def build_personality_instruction(decision: PersonalityDecision) -> str:
    if not decision.enabled:
        return ""

    return (
        "=== PERSONALITY LAYER ===\n"
        f"{decision.instruction}\n"
        "=== END PERSONALITY LAYER ==="
    )


def personality_status_text(decision: PersonalityDecision) -> str:
    if not decision.enabled:
        return ""

    return (
        "\n\n😈 <b>Тон</b>\n"
        f"Добавлю немного характера: <code>{decision.title}</code>."
    )


def _enabled(level: str, is_group: bool) -> PersonalityDecision:
    if level == "high":
        title = "дерзко, но по делу"
        instruction = (
            "Можно добавить больше энергии, уверенности и лёгкой дерзости. "
            "Используй 1 короткую острую метафору или фразу с характером, но без клоунады. "
            "Не унижай пользователя и участников. Не шути над чувствительными темами. "
            "Сначала польза, потом стиль."
        )
    else:
        title = "лёгкий характер"
        instruction = (
            "Можно добавить живой премиальный тон: 1 короткую метафору, лёгкий сарказм "
            "или энергичный вывод. Очень умеренно. Не превращай ответ в стендап. "
            "Структура и польза важнее юмора."
        )

    if is_group:
        instruction += (
            " Учитывай, что ответ видит группа: не провоцируй конфликт, не высмеивай участников, "
            "держи тон уверенным и командным."
        )

    return PersonalityDecision(
        enabled=True,
        level=level,
        title=title,
        instruction=instruction,
    )


def _disabled(reason: str) -> PersonalityDecision:
    return PersonalityDecision(
        enabled=False,
        level="off",
        title="нейтрально",
        instruction=f"Personality layer disabled: {reason}",
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_too_serious(text: str) -> bool:
    serious_markers = [
        "срочно",
        "паника",
        "страшно",
        "плохо",
        "опасно",
        "помоги пожалуйста",
        "важно",
        "критично",
        "конфликт с клиентом",
        "жалоба",
        "претензия",
    ]

    return any(marker in text for marker in serious_markers)
