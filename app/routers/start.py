from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
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
        "Я превращаю рабочий хаос в понятный результат: текст, план, стратегию, проект или документ.\n\n"
        "🧠 <b>Что я умею</b>\n"
        "— отвечать клиентам без воды и оправданий;\n"
        "— разбирать идеи, хаос и сложные ситуации;\n"
        "— собирать планы действий;\n"
        "— думать как продакт и стратег;\n"
        "— вести проекты и рабочий контекст;\n"
        "— создавать DOCX/PDF документы.\n\n"
        "🚀 <b>С чего начать</b>\n"
        "Нажми <b>🧠 Режимы</b> и выбери сценарий.\n"
        "Если не знаешь, что выбрать — жми <b>🌍 Универсальный</b>.\n\n"
        "👤 <b>Профиль</b>\n"
        "Тариф, лимиты, активность и подписка Stars.\n\n"
        "🌐 <b>Mini App</b>\n"
        "Кабинет открывается отдельной кнопкой рядом с полем ввода или командой <code>/miniapp</code>.\n\n"
        f"Текущий тариф: <b>{plan_name}</b>.\n\n"
        "Можно начать прямо сейчас: просто напиши задачу обычным сообщением."
    )


def _help_text() -> str:
    return (
        "🧭 <b>Быстрый старт</b>\n\n"
        "Не нужно писать идеально. Кидай вводные как есть — я разложу.\n\n"
        "1️⃣ <b>Хочешь просто спросить?</b>\n"
        "→ 🧠 Режимы → 🌍 Универсальный\n\n"
        "Подходит для:\n"
        "— вопросов;\n"
        "— объяснений;\n"
        "— идей;\n"
        "— анализа;\n"
        "— личных и рабочих задач.\n\n"
        "2️⃣ <b>Нужно ответить клиенту?</b>\n"
        "→ 🧠 Режимы → ✍️ Ответ клиенту\n\n"
        "Кинь переписку или суть ситуации — получишь готовый ответ.\n\n"
        "3️⃣ <b>В голове хаос?</b>\n"
        "→ 🧠 Режимы → 🧾 Разобрать хаос\n\n"
        "Сырые мысли → суть, риски, порядок действий.\n\n"
        "4️⃣ <b>Нужен план?</b>\n"
        "→ 🧠 Режимы → 📌 Сделать план\n\n"
        "Цель → шаги, сроки, контрольные точки.\n\n"
        "5️⃣ <b>Есть идея продукта?</b>\n"
        "→ 🧠 Режимы → 🧩 Продукт\n\n"
        "ЦА, боль, ценность, MVP, гипотезы и метрики.\n\n"
        "6️⃣ <b>Нужен сильный ход?</b>\n"
        "→ 🧠 Режимы → 🔥 Стратег\n\n"
        "Позиционирование, рост, риски и план удара.\n\n"
        "7️⃣ <b>Нужно сохранить контекст?</b>\n"
        "→ 🧠 Режимы → 🗂 Проекты\n\n"
        "Клиенты, сроки, бюджеты и договорённости будут в рабочей памяти.\n\n"
        "8️⃣ <b>Нужен файл?</b>\n"
        "→ 🧠 Режимы → 📄 Документы\n\n"
        "КП, план работ, резюме встречи или чек-лист в DOCX/PDF.\n\n"
        "🌐 <b>Mini App</b>\n"
        "Открывается кнопкой рядом с полем ввода или командой <code>/miniapp</code>."
    )


def _extract_start_payload(message: Message) -> str:
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return ""

    return parts[1].strip()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    payload = _extract_start_payload(message)

    if payload.startswith("project_doc_"):
        project_id_raw = payload.removeprefix("project_doc_").strip()

        if project_id_raw.isdigit():
            from app.routers.projects import open_project_document_deeplink

            await open_project_document_deeplink(
                message=message,
                state=state,
                project_id=int(project_id_raw),
            )
            return

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
        "Две главные точки входа — без визуального шума.\n\n"
        "🧠 <b>Режимы</b>\n"
        "Все рабочие сценарии: универсальный ассистент, клиентские ответы, планы, продукт, стратегия, проекты, документы и демо.\n\n"
        "👤 <b>Профиль</b>\n"
        "Тариф, лимиты, активность и подписка.\n\n"
        "🌐 <b>Mini App</b>\n"
        "Открывается кнопкой рядом с полем ввода или командой <code>/miniapp</code>.",
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
