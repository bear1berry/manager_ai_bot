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
        f"👋 **{name}, добро пожаловать в «Менеджер ИИ»**\n\n"
        "Я превращаю рабочий хаос в понятный результат: текст, план, проект или документ.\n\n"
        "Что можно делать уже сейчас:\n\n"
        "🧠 **Ассистент**\n"
        "— ответить клиенту;\n"
        "— разобрать хаотичные вводные;\n"
        "— собрать план действий.\n\n"
        "🗂 **Проекты**\n"
        "— сохранять клиентов, задачи, сроки и договорённости;\n"
        "— спрашивать: `Что у нас по Ивановой?`;\n"
        "— получать ответ с учётом рабочей памяти.\n\n"
        "📄 **Документы**\n"
        "— КП;\n"
        "— план работ;\n"
        "— резюме встречи;\n"
        "— чек-лист в DOCX/PDF.\n\n"
        "👤 **Профиль**\n"
        "— тариф;\n"
        "— лимиты;\n"
        "— доступные функции.\n\n"
        f"Текущий режим: **{plan_name}**.\n\n"
        "Выбери раздел в нижнем меню или просто напиши задачу одним сообщением."
    )


def _help_text() -> str:
    return (
        "🧭 **Как пользоваться «Менеджер ИИ»**\n\n"
        "Самый простой сценарий:\n"
        "1. Напиши задачу обычным сообщением.\n"
        "2. Получи структурный ответ.\n"
        "3. При необходимости сохрани контекст как проект или собери документ.\n\n"
        "⚡ **Быстрые режимы**\n"
        "Открой `🧠 Ассистент` и выбери:\n"
        "— `✍️ Ответ клиенту` — для переписок и возражений;\n"
        "— `🧾 Разобрать хаос` — для сырых мыслей и каши в голове;\n"
        "— `📌 Сделать план` — для целей и задач.\n\n"
        "🗂 **Проекты**\n"
        "Сохраняй рабочие вводные: клиенты, сроки, бюджеты, договорённости.\n"
        "Потом можно спросить: `Что у нас по этому проекту?`\n\n"
        "📄 **Документы**\n"
        "Дай вводные — бот соберёт DOCX/PDF: КП, план работ, резюме встречи или чек-лист.\n\n"
        "💎 **Подписка**\n"
        "Тарифы и лимиты смотри в `👤 Профиль` и `💎 Подписка`.\n\n"
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
        parse_mode="Markdown",
    )


@router.message(Command("menu"))
@router.message(F.text == "⬅️ Назад")
async def menu_handler(message: Message) -> None:
    await message.answer(
        "🏠 **Главное меню**\n\n"
        "Выбери раздел в нижнем меню или просто напиши задачу.\n\n"
        "🧠 Ассистент — быстро решить задачу\n"
        "🗂 Проекты — рабочая память\n"
        "📄 Документы — DOCX/PDF\n"
        "👤 Профиль — тариф и лимиты",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        _help_text(),
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )
