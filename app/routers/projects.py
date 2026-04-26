from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, projects_keyboard
from app.config import get_settings
from app.services.projects import (
    build_projects_context,
    create_project_from_text,
    format_project_search_results,
    format_projects,
)
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import ProjectRepository, UserRepository

router = Router()


class ProjectStates(StatesGroup):
    waiting_project_text = State()
    waiting_search_text = State()


@router.message(Command("projects"))
@router.message(F.text == "🗂 Проекты")
async def projects_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🗂 **Проекты**\n\n"
        "Здесь хранится рабочая память: клиенты, задачи, договорённости, сроки и вводные.\n\n"
        "Теперь ассистент может использовать проекты как контекст в обычном чате.\n\n"
        "Выбери действие в нижнем таскбаре.",
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "➕ Новый проект")
async def new_project_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(ProjectStates.waiting_project_text)
    await message.answer(
        "➕ **Новый проект**\n\n"
        "Отправь описание проекта одним сообщением.\n\n"
        "Пример:\n"
        "`Иванова / ремонт квартиры. Бюджет 450 000 ₽. Дедлайн 20 мая. Нужно согласовать смету.`",
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(ProjectStates.waiting_project_text)
async def save_project_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer("Нужно текстовое описание проекта.")
        return

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        project_id = await create_project_from_text(ProjectRepository(db), user_id, message.text)

    await state.clear()

    await message.answer(
        "✅ **Проект сохранён**\n\n"
        f"ID проекта: `{project_id}`\n\n"
        "Теперь ассистент сможет учитывать этот контекст, когда ты спросишь что-то вроде:\n"
        "`Что у нас по Ивановой?`",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
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
        "🔎 **Поиск проекта**\n\n"
        "Напиши слово или фразу для поиска.\n\n"
        "Пример:\n"
        "`Иванова`, `ремонт`, `салон`, `КП`, `дедлайн`",
        reply_markup=projects_keyboard(),
        parse_mode="Markdown",
    )


@router.message(ProjectStates.waiting_search_text)
async def search_project_result_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    if not message.text:
        await message.answer("Нужен текст для поиска.")
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
