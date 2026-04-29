from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueAction:
    is_followup: bool
    action: str
    title: str
    needs_web: bool
    prompt_hint: str


FOLLOWUP_MARKERS = [
    "это",
    "его",
    "ее",
    "её",
    "их",
    "так",
    "теперь",
    "дальше",
    "продолжи",
    "продолжай",
    "сделай короче",
    "короче",
    "сократи",
    "укороти",
    "подробнее",
    "раскрой",
    "разверни",
    "перепиши",
    "переоформи",
    "сделай мягче",
    "сделай жестче",
    "сделай жёстче",
    "сделай дерзко",
    "добавь дерзости",
    "в деловом стиле",
    "в дружелюбном стиле",
    "в премиальном стиле",
    "как пост",
    "сделай пост",
    "сделай текст",
    "сделай документом",
    "оформи документом",
    "сделай файлом",
    "проверь в сети",
    "проверь это",
    "найди по этому",
    "актуализируй",
    "обнови данные",
]

WEB_FOLLOWUP_MARKERS = [
    "проверь в сети",
    "проверь это в сети",
    "проверь в интернете",
    "найди по этому",
    "найди это",
    "актуализируй",
    "обнови данные",
    "свежие данные",
    "актуальные данные",
    "что нового по этому",
]

SHORT_FOLLOWUP_PATTERNS = [
    r"^продолжи[.!?]*$",
    r"^продолжай[.!?]*$",
    r"^короче[.!?]*$",
    r"^сделай короче[.!?]*$",
    r"^сократи[.!?]*$",
    r"^подробнее[.!?]*$",
    r"^разверни[.!?]*$",
    r"^раскрой[.!?]*$",
    r"^перепиши[.!?]*$",
    r"^сделай мягче[.!?]*$",
    r"^сделай жестче[.!?]*$",
    r"^сделай жёстче[.!?]*$",
    r"^сделай дерзко[.!?]*$",
    r"^добавь дерзости[.!?]*$",
    r"^проверь в сети[.!?]*$",
    r"^проверь это в сети[.!?]*$",
]


def detect_dialogue_action(text: str) -> DialogueAction:
    cleaned = re.sub(r"\s+", " ", text.strip())
    lower = cleaned.lower()

    needs_web = any(marker in lower for marker in WEB_FOLLOWUP_MARKERS)

    if _matches_any_pattern(lower, SHORT_FOLLOWUP_PATTERNS):
        return _action_for_text(lower, needs_web)

    if any(marker in lower for marker in FOLLOWUP_MARKERS) and len(cleaned) <= 180:
        return _action_for_text(lower, needs_web)

    return DialogueAction(
        is_followup=False,
        action="new_request",
        title="Новый запрос",
        needs_web=needs_web,
        prompt_hint=(
            "Пользователь начал новый запрос. Историю можно учитывать как общий контекст, "
            "но основной фокус — на текущем сообщении."
        ),
    )


def build_dialogue_prompt(
    user_text: str,
    history: list[dict[str, str]],
    action: DialogueAction,
) -> str:
    if not action.is_followup:
        return user_text

    compact_history = _format_history(history)

    return (
        "Пользователь продолжает предыдущий диалог.\n"
        "Нужно использовать историю ниже как основной контекст для текущей команды.\n\n"
        f"Тип продолжения: {action.title}\n"
        f"Инструкция: {action.prompt_hint}\n\n"
        "История диалога:\n"
        f"{compact_history}\n\n"
        "Текущая команда пользователя:\n"
        f"{user_text}\n\n"
        "Ответь так, будто ты понял, к чему относится команда пользователя. "
        "Не спрашивай повторно, если контекст ясен из истории."
    )


def build_search_text_for_dialogue(
    user_text: str,
    history: list[dict[str, str]],
    action: DialogueAction,
) -> str:
    if not action.needs_web:
        return user_text

    compact_history = _format_history(history, max_chars=2500)

    return (
        f"{user_text}\n\n"
        "Контекст для web-поиска из предыдущего диалога:\n"
        f"{compact_history}"
    )


def _action_for_text(lower: str, needs_web: bool) -> DialogueAction:
    if "продолж" in lower:
        return DialogueAction(
            is_followup=True,
            action="continue",
            title="Продолжение",
            needs_web=needs_web,
            prompt_hint=(
                "Продолжи предыдущий ответ или предыдущую мысль. "
                "Не начинай заново, развивай уже начатую структуру."
            ),
        )

    if "короче" in lower or "сократи" in lower or "укороти" in lower:
        return DialogueAction(
            is_followup=True,
            action="shorten",
            title="Сокращение",
            needs_web=needs_web,
            prompt_hint=(
                "Сократи предыдущий ответ. Оставь только суть, без потери смысла. "
                "Сделай плотнее и практичнее."
            ),
        )

    if "подробнее" in lower or "разверни" in lower or "раскрой" in lower:
        return DialogueAction(
            is_followup=True,
            action="expand",
            title="Расширение",
            needs_web=needs_web,
            prompt_hint=(
                "Раскрой предыдущий ответ подробнее. Добавь объяснение, примеры, риски и следующий шаг."
            ),
        )

    if "проверь" in lower or "найди" in lower or "актуализ" in lower or "обнови" in lower:
        return DialogueAction(
            is_followup=True,
            action="web_check",
            title="Проверка в сети",
            needs_web=True,
            prompt_hint=(
                "Проверь предыдущую тему через web-контекст. "
                "Сравни прошлую идею с актуальными данными и дай выводы."
            ),
        )

    if "документ" in lower or "файлом" in lower or "docx" in lower or "pdf" in lower:
        return DialogueAction(
            is_followup=True,
            action="document",
            title="Подготовка к документу",
            needs_web=needs_web,
            prompt_hint=(
                "Подготовь предыдущий материал к оформлению в документ: структура, заголовки, разделы, "
                "что войдёт в DOCX/PDF. Если прямой генерации файла нет в этом сценарии — дай готовую структуру."
            ),
        )

    if "перепиши" in lower or "стиле" in lower or "мягче" in lower or "жестче" in lower or "жёстче" in lower:
        return DialogueAction(
            is_followup=True,
            action="rewrite",
            title="Переписывание",
            needs_web=needs_web,
            prompt_hint=(
                "Перепиши предыдущий ответ в стиле, который просит пользователь. "
                "Сохрани смысл, улучши подачу."
            ),
        )

    if "дерз" in lower:
        return DialogueAction(
            is_followup=True,
            action="spice",
            title="Добавить характер",
            needs_web=needs_web,
            prompt_hint=(
                "Добавь больше энергии, дерзости и уверенности, но не превращай ответ в клоунаду. "
                "Юмор — только точечно и по делу."
            ),
        )

    return DialogueAction(
        is_followup=True,
        action="generic_followup",
        title="Продолжение диалога",
        needs_web=needs_web,
        prompt_hint=(
            "Пойми из истории, к чему относится короткая команда пользователя, и выполни её."
        ),
    )


def _format_history(history: list[dict[str, str]], max_chars: int = 5000) -> str:
    if not history:
        return "Истории пока нет."

    lines: list[str] = []

    for item in history[-12:]:
        role = item.get("role", "unknown")
        content = str(item.get("content", "")).strip()

        if not content:
            continue

        role_label = "Пользователь" if role == "user" else "Ассистент"
        lines.append(f"{role_label}: {content}")

    formatted = "\n\n".join(lines)

    if len(formatted) > max_chars:
        formatted = formatted[-max_chars:]

    return formatted or "Истории пока нет."


def _matches_any_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.match(pattern, text) for pattern in patterns)
