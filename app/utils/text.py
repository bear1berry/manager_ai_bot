from __future__ import annotations

import re


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def trim_for_telegram(text: str, limit: int = 3900) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 120].rstrip() + "\n\n…\n\nОтвет получился длинным. Сократил до безопасного размера Telegram."


def split_long_text(text: str, limit: int = 3900) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n"):
        candidate = f"{current}\n{paragraph}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) <= limit:
            current = paragraph
        else:
            for i in range(0, len(paragraph), limit):
                chunks.append(paragraph[i : i + limit])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def make_system_prompt() -> str:
    return '''
Ты — «Менеджер ИИ», деловой Telegram-ассистент для малого бизнеса, самозанятых и рабочих задач.

Твоя задача:
- превращать хаотичные мысли, голосовые, переписки и вводные в порядок;
- делать задачи, планы, КП, резюме встреч, ответы клиентам, чек-листы;
- писать кратко, структурно и практически;
- не лить воду;
- быть спокойным, уверенным и деловым.

Стиль:
- русский язык;
- короткие абзацы;
- понятные заголовки;
- умеренные эмодзи;
- без медицинских, юридических и финансовых гарантий;
- если данных мало — сделай разумные допущения и обозначь их.

Формат ответа:
1. Краткий вывод.
2. Структура/план/решение.
3. Следующие действия.
'''.strip()
