from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.limits import plan_display_name
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UserRepository

router = Router()


def _first_name(message: Message) -> str:
    if message.from_user and message.from_user.first_name:
        return message.from_user.first_name

    return "друг"


def _start_text(message: Message, plan: str) -> str:
    name = _first_name(message)
    plan_name = plan_display_name(plan)

    return (
        f"👋 <b>{name}, добро пожаловать в «Менеджер ИИ»</b>\n\n"
        "Я превращаю рабочий хаос в понятный результат: ответ, план, проект или документ.\n\n"
        "🧠 <b>Ассистент</b>\n"
        "— отвечает клиентам;\n"
        "— разбирает хаотичные вводные;\n"
        "— делает планы действий.\n\n"
        "🗂 <b>Проекты</b>\n"
        "— хранит клиентов, задачи, сроки и договорённости;\n"
        "— помогает вспомнить контекст;\n"
        "— отвечает на вопросы вроде: <code>Что у нас по Ивановой?</code>\n\n"
        "📄 <b>Документы</b>\n"
        "— коммерческие предложения;\n"
        "— планы работ;\n"
        "— резюме встреч;\n"
        "— чек-листы в DOCX/PDF.\n\n"
        "👤 <b>Профиль</b>\n"
        "— тариф;\n"
        "— лимиты;\n"
        "— доступные функции.\n\n"
        f"Текущий режим: <b>{plan_name}</b>.\n\n"
        "Выбери раздел в нижнем меню или просто напиши задачу одним сообщением."
    )


def _help_text() -> str:
    return (
        "🧭 <b>Как пользоваться «Менеджер ИИ»</b>\n\n"
        "<b>Быстрый старт</b>\n"
        "— напиши задачу обычным сообщением;\n"
        "— бот сам определит сценарий;\n"
        "— получишь структурный ответ;\n"
        "— оцени результат через 👍 / 👎.\n\n"
        "⚡ <b>Быстрые режимы</b>\n"
        "Открой 🧠 Ассистент и выбери:\n"
        "— ✍️ Ответ клиенту;\n"
        "— 🧾 Разобрать хаос;\n"
        "— 📌 Сделать план.\n\n"
        "🗂 <b>Проекты</b>\n"
        "Сохраняй клиентов, сроки, бюджеты и договорённости. Потом можно спросить:\n"
        "<code>Что у нас по этому проекту?</code>\n\n"
        "📄 <b>Документы</b>\n"
        "Дай вводные — бот соберёт КП, план работ, резюме встречи или чек-лист в DOCX/PDF.\n\n"
        "🚀 <b>Демо</b>\n"
        "Если хочешь быстро понять возможности — нажми 🚀 Демо.\n\n"
        "Главное правило: не пытайся писать идеально. Кидай как есть — я разложу."
    )


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        await ensure_user(user_repo, message.from_user)

        user = await user_repo.get_by_telegram_id(message.from_user.id)
        plan = str(user["plan"]) if user else "free"

    await message.answer(
        _start_text(message, plan),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
@router.message(F.text == "⬅️ Назад")
async def menu_handler(message: Message) -> None:
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери раздел в нижнем меню или просто напиши задачу.\n\n"
        "🧠 <b>Ассистент</b> — быстро решить задачу\n"
        "🗂 <b>Проекты</b> — рабочая память\n"
        "📄 <b>Документы</b> — DOCX/PDF\n"
        "🚀 <b>Демо</b> — быстрый показ возможностей\n"
        "👤 <b>Профиль</b> — тариф и лимиты",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        _help_text(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
