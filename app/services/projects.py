from __future__ import annotations

from app.storage.repositories import ProjectRepository


async def create_project_from_text(repo: ProjectRepository, user_id: int, text: str) -> None:
    title = text.strip().split("\n")[0][:80]
    description = text.strip()

    if not title:
        title = "Новый проект"

    await repo.create(user_id=user_id, title=title, description=description)


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
        lines.append(
            f"**{index}. {row['title']}**\n"
            f"Статус: `{row['status']}`\n"
            f"{row['description'][:500]}\n"
        )

    return "\n".join(lines)
