from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.keyboards import main_keyboard, projects_keyboard
from app.config import get_settings
from app.services.projects import create_project_from_text, format_projects
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import ProjectRepository, UserRepository

router = Router()


class ProjectStates(StatesGroup):
    waiting_project_text = State()


@router.message(Command("projects"))
@router.message(F.text == "🗂 Проекты")
async def projects_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🗂 **Проекты**\n\n"
        "Здесь можно хранить рабочий контекст: клиенты, задачи, договорённости, сроки.\n\n"
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
        await create_project_from_text(ProjectRepository(db), user_id, message.text)

    await state.clear()

    await message.answer(
        "✅ **Проект сохранён**\n\n"
        "Теперь его можно использовать как рабочий контекст.",
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
