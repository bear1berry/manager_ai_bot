from __future__ import annotations

import re
from dataclasses import dataclass

from app.storage.repositories import ProjectRepository


@dataclass(frozen=True)
class ProjectNoteInput:
    project_query: str
    note: str


def extract_project_title(text: str) -> str:
    clean = text.strip()
    if not clean:
        return "Новый проект"

    first_line = clean.split("\n")[0].strip()
    first_line = re.sub(r"\s+", " ", first_line)

    markers = ["/", "—", "-", ".", ":"]
    for marker in markers:
        if marker in first_line:
            candidate = first_line.split(marker)[0].strip()
            if 3 <= len(candidate) <= 80:
                return candidate[:80]

    return first_line[:80] or "Новый проект"


async def create_project_from_text(repo: ProjectRepository, user_id: int, text: str) -> int:
    title = extract_project_title(text)
    description = text.strip()

    if not description:
        description = "Описание проекта пока не заполнено."

    return await repo.create(user_id=user_id, title=title, description=description)


def parse_project_note_input(text: str) -> ProjectNoteInput | None:
    """
    Поддерживаемые форматы:

    1) Иванова :: Клиент согласовал бюджет.
    2) Иванова — Клиент согласовал бюджет.
    3) Иванова
       Клиент согласовал бюджет.

    Первая часть — поисковый запрос по проекту.
    Вторая часть — заметка.
    """
    clean = text.strip()
    if not clean:
        return None

    separators = ["::", " — ", " - "]

    for separator in separators:
        if separator in clean:
            left, right = clean.split(separator, 1)
            project_query = left.strip()
            note = right.strip()

            if project_query and note:
                return ProjectNoteInput(project_query=project_query[:120], note=note)

    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if len(lines) >= 2:
        project_query = lines[0].strip()
        note = "\n".join(lines[1:]).strip()

        if project_query and note:
            return ProjectNoteInput(project_query=project_query[:120], note=note)

    return None


def format_projects(rows) -> str:
    if not rows:
        return (
            "🗂 **Проектов пока нет**\n\n"
            "Чтобы добавить проект, нажми `➕ Новый проект` и отправь описание.\n\n"
            "Пример:\n"
            "`Иванова / ремонт квартиры. Бюджет 450 000 ₽. Дедлайн 20 мая.`"
        )

    lines = ["🗂 **Мои проекты**\n"]

    for index, row in enumerate(rows, start=1):
        description = str(row["description"] or "").strip()
        if len(description) > 700:
            description = description[:700].rstrip() + "…"

        lines.append(
            f"**{index}. {row['title']}**\n"
            f"Статус: `{row['status']}`\n"
            f"{description}\n"
        )

    return "\n".join(lines)


def format_project_search_results(rows, query: str) -> str:
    if not rows:
        return (
            "🔎 **Ничего не нашёл**\n\n"
            f"Запрос: `{query}`\n\n"
            "Что можно сделать:\n"
            "1. Попробовать другое слово.\n"
            "2. Проверить список через `📚 Мои проекты`.\n"
            "3. Добавить проект через `➕ Новый проект`."
        )

    lines = [f"🔎 **Нашёл проекты по запросу:** `{query}`\n"]

    for index, row in enumerate(rows, start=1):
        description = str(row["description"] or "").strip()
        if len(description) > 600:
            description = description[:600].rstrip() + "…"

        lines.append(
            f"**{index}. {row['title']}**\n"
            f"{description}\n"
        )

    return "\n".join(lines)


def format_project_note_examples() -> str:
    return (
        "📝 **Заметка в проект**\n\n"
        "Отправь название проекта и заметку одним сообщением.\n\n"
        "**Формат 1:**\n"
        "`Иванова :: Клиент согласовал бюджет 450 000 ₽, финальная смета нужна до пятницы.`\n\n"
        "**Формат 2:**\n"
        "`Иванова — Клиент попросил добавить этап проверки.`\n\n"
        "**Формат 3:**\n"
        "`Иванова`\n"
        "`Клиент просит не выходить за бюджет и хочет КП сегодня.`\n\n"
        "Я найду проект по первой части и добавлю заметку в память."
    )


def format_ambiguous_project_note(rows, query: str) -> str:
    lines = [
        "⚠️ **Нашёл несколько похожих проектов**\n",
        f"Запрос: `{query}`\n",
        "Уточни название и отправь заметку ещё раз.\n",
    ]

    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. **{row['title']}**")

    lines.append(
        "\nПример:\n"
        "`Точное название проекта :: новая заметка`"
    )

    return "\n".join(lines)


def build_projects_context(rows) -> str:
    if not rows:
        return ""

    parts = ["Контекст активных проектов пользователя:"]

    for index, row in enumerate(rows, start=1):
        title = str(row["title"] or "").strip()
        description = str(row["description"] or "").strip()

        if len(description) > 900:
            description = description[:900].rstrip() + "…"

        parts.append(
            f"{index}. {title}\n"
            f"{description}"
        )

    return "\n\n".join(parts)


def should_use_project_context(text: str) -> bool:
    lower = text.lower()

    project_markers = [
        "проект",
        "клиент",
        "клиенту",
        "по клиенту",
        "что по",
        "напомни",
        "договор",
        "договорён",
        "договорен",
        "срок",
        "дедлайн",
        "бюджет",
        "задача",
        "работ",
        "иван",
        "иванов",
        "иванова",
        "ремонт",
        "кп",
        "смет",
    ]

    return any(marker in lower for marker in project_markers)


def build_prompt_with_project_context(user_text: str, context: str) -> str:
    if not context:
        return user_text

    return (
        f"{context}\n\n"
        "Используй этот контекст, если он относится к вопросу пользователя. "
        "Если контекст не относится к вопросу — не притягивай его искусственно.\n\n"
        f"Вопрос пользователя:\n{user_text}"
    )
