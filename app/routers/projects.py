from __future__ import annotations

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from app.bot.keyboards import (
    main_keyboard,
    project_document_type_keyboard,
    projects_keyboard,
)
from app.config import get_settings
from app.services.documents import DocumentService
from app.services.limits import check_limit, limit_message
from app.services.llm import LLMService
from app.services.projects import (
    build_projects_context,
    create_project_from_text,
    format_ambiguous_project_note,
    format_project_note_examples,
    format_project_search_results,
    format_projects,
    parse_project_note_input,
)
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import (
    DocumentRepository,
    ProjectRepository,
    UsageRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)
router = Router()


class ProjectStates(StatesGroup):
    waiting_project_text = State()
    waiting_search_text = State()
    waiting_note_text = State()
    waiting_project_document_target = State()
    waiting_project_document_type = State()


PROJECT_DOCUMENT_TYPES = {
    "🧾 КП из проекта": ("commercial_offer", "Коммерческое предложение"),
    "📋 План из проекта": ("work_plan", "План работ"),
    "📝 Резюме из проекта": ("meeting_summary", "Резюме встречи"),
    "✅ Чек-лист из проекта": ("checklist", "Чек-лист"),
}


@router.message(Command("projects"))
@router.message(F.text == "🗂 Проекты")
async def projects_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🗂 <b>Проекты</b>\n\n"
        "Здесь хранится рабочая память: клиенты, задачи, договорённости, сроки и вводные.\n\n"
        "<b>Что можно делать</b>\n"
        "— добавить проект;\n"
        "— посмотреть список;\n"
        "— найти проект;\n"
        "— добавить заметку;\n"
        "— собрать документ из проекта;\n"
        "— посмотреть контекст, который ассистент может учитывать.\n\n"
        "Выбери действие в нижнем меню.",
        reply_markup=projects_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "➕ Новый проект")
async def new_project_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(ProjectStates.waiting_project_text)
    await message.answer(
        "➕ <b>Новый проект</b>\n\n"
        "Отправь описание проекта одним сообщением.\n\n"
        "<b>Пример</b>\n"
        "<code>Иванова / ремонт квартиры. Бюджет 450 000 ₽. Дедлайн 20 мая. Нужно согласовать смету.</code>",
        reply_markup=projects_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProjectStates.waiting_project_text)
async def save_project_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer(
            "⚠️ <b>Нужно текстовое описание проекта</b>",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        project_id = await create_project_from_text(ProjectRepository(db), user_id, message.text)

    await state.clear()

    await message.answer(
        "✅ <b>Проект сохранён</b>\n\n"
        f"ID проекта: <code>{project_id}</code>\n\n"
        "Теперь ассистент сможет учитывать этот контекст, когда ты спросишь что-то вроде:\n"
        "<code>Что у нас по Ивановой?</code>\n\n"
        "Также можно собрать документ на основе проекта через кнопку:\n"
        "<b>📄 Документ из проекта</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "📚 Мои проекты")
async def list_projects_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        projects = await ProjectRepository(db).list_active(user_id)

    await message.answer(
        format_projects(projects),
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "🔎 Найти проект")
async def search_project_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(ProjectStates.waiting_search_text)
    await message.answer(
        "🔎 <b>Поиск проекта</b>\n\n"
        "Напиши слово или фразу для поиска.\n\n"
        "<b>Пример</b>\n"
        "<code>Иванова</code>, <code>ремонт</code>, <code>салон</code>, <code>КП</code>, <code>дедлайн</code>",
        reply_markup=projects_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProjectStates.waiting_search_text)
async def search_project_result_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer(
            "⚠️ Нужен текст для поиска.",
            reply_markup=projects_keyboard(),
        )
        return

    query = message.text.strip()

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        rows = await ProjectRepository(db).search_active(user_id=user_id, query=query, limit=10)

    await state.clear()

    await message.answer(
        format_project_search_results(rows, query),
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "📝 Заметка в проект")
async def project_note_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(ProjectStates.waiting_note_text)

    await message.answer(
        format_project_note_examples(),
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(ProjectStates.waiting_note_text)
async def save_project_note_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer(
            "⚠️ Нужен текст заметки.",
            reply_markup=projects_keyboard(),
        )
        return

    parsed = parse_project_note_input(message.text)

    if parsed is None:
        await message.answer(
            "⚠️ **Не понял формат заметки**\n\n"
            "Используй формат:\n"
            "`Название проекта :: текст заметки`\n\n"
            "Пример:\n"
            "`Иванова :: Клиент согласовал бюджет, но просит финальную смету до пятницы.`",
            reply_markup=projects_keyboard(),
            parse_mode="Markdown",
        )
        return

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        project_repo = ProjectRepository(db)

        rows = await project_repo.search_active(
            user_id=user_id,
            query=parsed.project_query,
            limit=5,
        )

        if not rows:
            await state.clear()
            await message.answer(
                "🔎 **Проект не найден**\n\n"
                f"Искал по запросу: `{parsed.project_query}`\n\n"
                "Что сделать:\n"
                "1. Проверь название.\n"
                "2. Посмотри список через `📚 Мои проекты`.\n"
                "3. Или создай новый проект через `➕ Новый проект`.",
                reply_markup=projects_keyboard(),
                parse_mode="Markdown",
            )
            return

        if len(rows) > 1:
            exact_rows = [
                row for row in rows
                if str(row["title"]).strip().lower() == parsed.project_query.strip().lower()
            ]

            if len(exact_rows) == 1:
                target = exact_rows[0]
            else:
                await message.answer(
                    format_ambiguous_project_note(rows, parsed.project_query),
                    reply_markup=projects_keyboard(),
                    parse_mode="Markdown",
                )
                return
        else:
            target = rows[0]

        await project_repo.append_note(project_id=int(target["id"]), note=parsed.note)

    await state.clear()

    await message.answer(
        "✅ **Заметка добавлена в проект**\n\n"
        f"Проект: **{target['title']}**\n\n"
        "Теперь ассистент сможет учитывать эту новую информацию в ответах.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "📄 Документ из проект")
@router.message(F.text == "📄 Документ из проекта")
async def project_document_start_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        rows = await ProjectRepository(db).list_active(user_id=user_id, limit=10)

    if not rows:
        await state.clear()
        await message.answer(
            "🗂 <b>Проектов пока нет</b>\n\n"
            "Чтобы собрать документ из проекта, сначала создай проект через кнопку:\n"
            "<b>➕ Новый проект</b>.",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    await state.set_state(ProjectStates.waiting_project_document_target)

    project_lines = []
    for row in rows:
        description = str(row["description"] or "").strip().replace("\n", " ")
        preview = description[:90].rstrip() + "…" if len(description) > 90 else description
        project_lines.append(
            f"— <code>{row['id']}</code> · <b>{row['title']}</b>"
            + (f"\n  <i>{preview}</i>" if preview else "")
        )

    await message.answer(
        "📄 <b>Документ из проекта</b>\n\n"
        "Выбери проект, из которого нужно собрать документ.\n\n"
        "<b>Как выбрать</b>\n"
        "Отправь ID проекта или точное название.\n\n"
        "<b>Последние проекты</b>\n"
        f"{chr(10).join(project_lines)}",
        reply_markup=projects_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProjectStates.waiting_project_document_target)
async def project_document_target_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer(
            "⚠️ <b>Нужен ID или название проекта</b>",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    text = message.text.strip()

    if text == "⬅️ Назад":
        await state.clear()
        await message.answer(
            "Возвращаю в главное меню.",
            reply_markup=main_keyboard(),
        )
        return

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        project_repo = ProjectRepository(db)

        if text.isdigit():
            project = await project_repo.get_owned(project_id=int(text), user_id=user_id)
            rows = [project] if project is not None else []
        else:
            rows = await project_repo.search_active(user_id=user_id, query=text, limit=5)

    if not rows:
        await message.answer(
            "🔎 <b>Проект не найден</b>\n\n"
            f"Искал по запросу: <code>{text}</code>\n\n"
            "<b>Что сделать</b>\n"
            "— отправь ID проекта;\n"
            "— или посмотри список через <b>📚 Мои проекты</b>.",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    if len(rows) > 1:
        exact_rows = [
            row for row in rows
            if str(row["title"]).strip().lower() == text.strip().lower()
        ]

        if len(exact_rows) == 1:
            project = exact_rows[0]
        else:
            variants = "\n".join(
                f"— <code>{row['id']}</code> · <b>{row['title']}</b>"
                for row in rows
            )
            await message.answer(
                "⚠️ <b>Нашёл несколько проектов</b>\n\n"
                "Отправь ID нужного проекта:\n\n"
                f"{variants}",
                reply_markup=projects_keyboard(),
                parse_mode="HTML",
            )
            return
    else:
        project = rows[0]

    await _show_project_document_type_picker(
        message=message,
        state=state,
        project=project,
    )


@router.message(ProjectStates.waiting_project_document_type)
async def project_document_type_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer(
            "⚠️ Выбери тип документа кнопкой ниже.",
            reply_markup=project_document_type_keyboard(),
        )
        return

    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer(
            "Возвращаю в главное меню.",
            reply_markup=main_keyboard(),
        )
        return

    if message.text not in PROJECT_DOCUMENT_TYPES:
        await message.answer(
            "⚠️ <b>Не понял тип документа</b>\n\n"
            "Выбери один из вариантов в нижнем меню.",
            reply_markup=project_document_type_keyboard(),
            parse_mode="HTML",
        )
        return

    doc_type, doc_title = PROJECT_DOCUMENT_TYPES[message.text]
    data = await state.get_data()
    project_id = int(data.get("project_id") or 0)

    if project_id <= 0:
        await state.clear()
        await message.answer(
            "⚠️ <b>Проект не выбран</b>\n\n"
            "Запусти сценарий заново через <b>📄 Документ из проекта</b>.",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    user_id = 0
    project = None

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)
        project_repo = ProjectRepository(db)

        user_id = await ensure_user(user_repo, message.from_user)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        plan = str(user["plan"]) if user else "free"

        limit_result = await check_limit(
            usage_repo=usage_repo,
            settings=settings,
            user_id=user_id,
            plan=plan,
            kind="text",
        )

        if not limit_result.allowed:
            await state.clear()
            await message.answer(
                limit_message(limit_result),
                reply_markup=main_keyboard(),
                parse_mode="HTML",
            )
            return

        project = await project_repo.get_owned(project_id=project_id, user_id=user_id)

        if project is None:
            await state.clear()
            await message.answer(
                "⚠️ <b>Проект не найден</b>\n\n"
                "Возможно, он удалён или принадлежит другому пользователю.",
                reply_markup=projects_keyboard(),
                parse_mode="HTML",
            )
            return

        await usage_repo.add(user_id=user_id, kind="text")

    project_title = str(project["title"])
    project_description = str(project["description"] or "").strip()

    source_text = _build_project_document_source(
        project_id=project_id,
        project_title=project_title,
        project_description=project_description,
        doc_title=doc_title,
    )

    await message.answer(
        "🧠 <b>Собираю документ из проекта</b>\n\n"
        f"Проект: <b>{project_title}</b>\n"
        f"Тип документа: <b>{doc_title}</b>\n\n"
        "— подтягиваю память проекта;\n"
        "— формирую структуру;\n"
        "— готовлю DOCX/PDF;\n"
        "— сохраню результат в историю.",
        reply_markup=project_document_type_keyboard(),
        parse_mode="HTML",
    )

    try:
        llm = LLMService(settings)
        document_data = await llm.generate_document_data(
            source_text=source_text,
            doc_type=doc_type,
            title=f"{doc_title}: {project_title}",
        )

        service = DocumentService(settings)
        generated = service.generate_from_data(
            data=document_data,
            fallback_title=f"{doc_title}: {project_title}",
        )

        document_title = str(document_data.get("title") or f"{doc_title}: {project_title}")

        async with await connect_db(settings.database_path) as db:
            await DocumentRepository(db).create(
                user_id=user_id,
                doc_type=doc_type,
                title=document_title,
                docx_path=str(generated.docx_path),
                pdf_path=str(generated.pdf_path) if generated.pdf_path else None,
                status="created",
            )

        await state.clear()

        await message.answer(
            "✅ <b>Документ из проекта собран</b>\n\n"
            f"Проект: <b>{project_title}</b>\n"
            f"Документ: <b>{document_title}</b>\n\n"
            "Файлы отправляю ниже. История документа доступна в Mini App.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )

        await message.answer_document(
            FSInputFile(generated.docx_path),
            caption=f"📄 {document_title} / DOCX",
        )

        if generated.pdf_path and Path(generated.pdf_path).exists():
            await message.answer_document(
                FSInputFile(generated.pdf_path),
                caption=f"📄 {document_title} / PDF",
            )

    except Exception:
        logger.exception("Project document generation failed")
        await state.clear()
        await message.answer(
            "⚠️ <b>Не удалось собрать документ из проекта</b>\n\n"
            "<b>Что случилось</b>\n"
            "Во время генерации произошла ошибка.\n\n"
            "<b>Что сделать</b>\n"
            "— проверь, что в проекте есть нормальное описание;\n"
            "— добавь заметку в проект;\n"
            "— попробуй ещё раз;\n"
            "— если ошибка повторится, проверь логи приложения.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )


@router.message(F.text == "🧠 Контекст проектов")
async def projects_context_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        rows = await ProjectRepository(db).latest_context(user_id=user_id, limit=5)

    context = build_projects_context(rows)

    if not context:
        await message.answer(
            "🧠 **Контекст проектов пуст**\n\n"
            "Добавь первый проект через `➕ Новый проект`.",
            reply_markup=projects_keyboard(),
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "🧠 **Контекст, который ассистент может учитывать:**\n\n"
        f"{context}",
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


async def open_project_document_deeplink(
    message: Message,
    state: FSMContext,
    project_id: int,
) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        project = await ProjectRepository(db).get_owned(project_id=project_id, user_id=user_id)

    if project is None:
        await state.clear()
        await message.answer(
            "⚠️ <b>Проект не найден</b>\n\n"
            "Возможно, проект удалён или принадлежит другому пользователю.\n\n"
            "Открой список через <b>🗂 Проекты</b> → <b>📚 Мои проекты</b>.",
            reply_markup=projects_keyboard(),
            parse_mode="HTML",
        )
        return

    await _show_project_document_type_picker(
        message=message,
        state=state,
        project=project,
    )


async def _show_project_document_type_picker(
    message: Message,
    state: FSMContext,
    project,
) -> None:
    await state.update_data(
        project_id=int(project["id"]),
        project_title=str(project["title"]),
    )
    await state.set_state(ProjectStates.waiting_project_document_type)

    description = str(project["description"] or "").strip()
    preview = description[:650].rstrip() + "…" if len(description) > 650 else description

    if preview:
        context_block = f"<b>Контекст проекта</b>\n{preview}"
    else:
        context_block = "<i>Описание проекта пока пустое.</i>"

    weak_context_note = ""
    if len(description) < 120:
        weak_context_note = (
            "\n⚠️ <b>В проекте пока мало данных</b>\n"
            "Документ получится черновым. Лучше добавить заметку через <b>📝 Заметка в проект</b>, "
            "если нужны точные сроки, условия или договорённости.\n"
        )

    await message.answer(
        "✅ <b>Проект выбран</b>\n\n"
        f"ID: <code>{project['id']}</code>\n"
        f"Название: <b>{project['title']}</b>\n\n"
        f"{context_block}\n"
        f"{weak_context_note}\n"
        "Теперь выбери тип документа.",
        reply_markup=project_document_type_keyboard(),
        parse_mode="HTML",
    )


def _build_project_document_source(
    project_id: int,
    project_title: str,
    project_description: str,
    doc_title: str,
) -> str:
    description = project_description.strip() or "Описание проекта не заполнено."

    return (
        f"Нужно подготовить документ типа: {doc_title}.\n\n"
        f"Источник данных — проект пользователя.\n\n"
        f"ID проекта: {project_id}\n"
        f"Название проекта: {project_title}\n\n"
        "Контекст проекта:\n"
        f"{description}\n\n"
        "Требования:\n"
        "- документ должен опираться именно на контекст проекта;\n"
        "- не выдумывать факты, если данных нет;\n"
        "- если данных мало — явно отметить допущения;\n"
        "- сохранить деловой, понятный и практичный стиль;\n"
        "- структура должна быть пригодна для DOCX/PDF."
    )
