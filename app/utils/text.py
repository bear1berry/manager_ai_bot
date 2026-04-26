from __future__ import annotations

import html
import re


MAX_TELEGRAM_MESSAGE_LENGTH = 3900


def make_system_prompt() -> str:
    return """
Ты — «Менеджер ИИ», премиальный Telegram-ассистент для работы, проектов, клиентов и документов.

Главная задача:
превращать хаотичные вводные пользователя в понятный, полезный и красиво структурированный результат.

Стиль ответа:
- русский язык;
- коротко, по делу, без воды;
- уверенный, спокойный, деловой тон;
- структура как аккуратная статья;
- уместные эмодзи в заголовках, без перебора;
- не использовать Markdown-таблицы;
- не использовать сырой HTML;
- не использовать ###, ####, ``` и декоративный мусор;
- не начинать ответ с фразы «Конечно»;
- не писать длинные вступления;
- не перегружать канцеляритом.

Формат:
- заголовки выделяй через жирный Markdown: **Заголовок**
- списки делай через короткое тире: — пункт
- важные слова можно выделять жирным: **важно**
- абзацы должны быть короткими;
- один смысл — один блок.

Если задача практическая:
- дай вывод;
- затем действия;
- затем риски или нюансы;
- затем следующий шаг.

Если вопрос про клиента:
- дай готовый текст ответа;
- затем объясни логику;
- затем предложи следующий шаг.

Если вопрос про план:
- дай этапы;
- сроки/приоритеты;
- контрольные точки;
- риски.

Если данных не хватает:
- сделай разумные допущения;
- явно укажи, что нужно уточнить;
- не останавливайся на уточняющем вопросе, если можно дать полезный черновик.
""".strip()


def split_long_text(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    clean = text.strip()

    if not clean:
        return []

    if len(clean) <= max_length:
        return [clean]

    chunks: list[str] = []
    current = ""

    paragraphs = clean.split("\n\n")

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph.strip()

        if len(candidate) <= max_length:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_length:
            current = paragraph.strip()
            continue

        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        sentence_buffer = ""

        for sentence in sentences:
            sentence_candidate = f"{sentence_buffer} {sentence}".strip() if sentence_buffer else sentence.strip()

            if len(sentence_candidate) <= max_length:
                sentence_buffer = sentence_candidate
            else:
                if sentence_buffer:
                    chunks.append(sentence_buffer)
                sentence_buffer = sentence.strip()

        if sentence_buffer:
            current = sentence_buffer

    if current:
        chunks.append(current)

    return chunks


def normalize_ai_text(text: str) -> str:
    """
    Чистит ответ модели от визуального мусора:
    - markdown fences;
    - ### заголовков;
    - лишних звёздочек;
    - кривых списков;
    - чрезмерных пустых строк.
    """
    clean = text.strip()

    clean = clean.replace("\r\n", "\n").replace("\r", "\n")

    clean = re.sub(r"```[a-zA-Zа-яА-Я0-9_-]*", "", clean)
    clean = clean.replace("```", "")

    clean = re.sub(r"^\s*#{1,6}\s*", "", clean, flags=re.MULTILINE)

    clean = re.sub(r"^\s*[-*]\s+", "— ", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*\d+[.)]\s+", lambda m: f"{m.group(0).strip()} ", clean, flags=re.MULTILINE)

    clean = re.sub(r"\n{3,}", "\n\n", clean)

    lines = []
    for raw_line in clean.splitlines():
        line = raw_line.strip()

        if not line:
            lines.append("")
            continue

        line = re.sub(r"\s+", " ", line)

        # Убираем случайные одинокие маркеры, но сохраняем **жирный** для дальнейшей конвертации.
        if line in {"*", "**", "-", "—", "_", "__"}:
            continue

        lines.append(line)

    clean = "\n".join(lines).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)

    return clean


def telegram_html_from_ai_text(text: str) -> str:
    """
    Превращает markdown-lite ответ модели в безопасный Telegram HTML.

    Поддерживает:
    - **жирный**
    - строки-заголовки
    - списки через —
    - безопасное экранирование HTML
    """
    normalized = normalize_ai_text(text)

    if not normalized:
        return "Не получилось собрать ответ. Попробуй переформулировать запрос."

    result_lines: list[str] = []

    for line in normalized.splitlines():
        if not line.strip():
            result_lines.append("")
            continue

        converted = _convert_line_to_html(line.strip())
        result_lines.append(converted)

    html_text = "\n".join(result_lines).strip()
    html_text = re.sub(r"\n{3,}", "\n\n", html_text)

    return html_text


def _convert_line_to_html(line: str) -> str:
    escaped = html.escape(line, quote=False)

    # **текст** → <b>текст</b>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)

    # Убираем оставшиеся одиночные markdown-символы.
    escaped = escaped.replace("__", "")
    escaped = escaped.replace("**", "")

    # Если строка похожа на короткий заголовок без точки — усиливаем.
    plain = re.sub(r"<[^>]+>", "", escaped).strip()
    is_bullet = plain.startswith("—") or plain.startswith("•")
    is_numbered = bool(re.match(r"^\d+[.)]\s+", plain))
    is_short_heading = (
        len(plain) <= 70
        and not is_bullet
        and not is_numbered
        and not plain.endswith((".", ",", ";", ":"))
        and len(plain.split()) <= 7
    )

    if is_short_heading and not escaped.startswith("<b>"):
        escaped = f"<b>{escaped}</b>"

    return escaped
