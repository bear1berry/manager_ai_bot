from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UserRepository

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        await ensure_user(UserRepository(db), message.from_user)

    await message.answer(
        "🧠 **Менеджер ИИ включён**\n\n"
        "Я превращаю хаос в рабочий порядок:\n"
        "— голосовые → задачи и резюме;\n"
        "— вводные → КП, план, чек-лист;\n"
        "— переписки → итоги и ответ клиенту;\n"
        "— проекты → память и структура.\n\n"
        "**Как начать:**\n"
        "Просто напиши задачу или выбери раздел в нижнем таскбаре.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "📌 **Как пользоваться «Менеджер ИИ»**\n\n"
        "1. Напиши задачу обычным текстом.\n"
        "2. Скинь голосовое — я разберу его через очередь.\n"
        "3. Выбери `📄 Документы`, чтобы создать КП, план, резюме встречи или чек-лист.\n"
        "4. Выбери `🗂 Проекты`, чтобы сохранить рабочий контекст.\n\n"
        "Управление — только через нижний таскбар.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(lambda message: message.text == "⬅️ Назад")
async def back_handler(message: Message) -> None:
    await message.answer(
        "Главное меню. Работаем спокойно и по делу.",
        reply_markup=main_keyboard(),
    )
