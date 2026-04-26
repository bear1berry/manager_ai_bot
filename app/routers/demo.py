from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import demo_keyboard, main_keyboard

router = Router()


@router.message(Command("demo"))
@router.message(F.text == "🚀 Демо")
async def demo_menu_handler(message: Message) -> None:
    await message.answer(
        "🚀 <b>Демо «Менеджер ИИ»</b>\n\n"
        "За минуту покажу, зачем нужен бот.\n\n"
        "<b>Что можно попробовать</b>\n"
        "— 🧾 разобрать хаос в голове;\n"
        "— 🗂 сохранить рабочий проект;\n"
        "— 📄 собрать документ;\n"
        "— ✅ понять, что делать дальше.\n\n"
        "Выбери демо-сценарий в нижнем меню.",
        reply_markup=demo_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "🧾 Демо: хаос")
async def demo_chaos_handler(message: Message) -> None:
    await message.answer(
        "🧾 <b>Демо: разобрать хаос</b>\n\n"
        "<b>Скопируй и отправь боту этот пример обычным сообщением:</b>\n\n"
        "<code>У меня каша в голове. Есть идея Telegram-бота, GitHub уже есть, локально работает, "
        "облако пока не взлетело из-за Telegram API. Нужно понять, что делать дальше, "
        "какие риски и какой следующий шаг.</code>\n\n"
        "<b>Что должен сделать бот</b>\n"
        "— выделить суть;\n"
        "— разложить задачи;\n"
        "— показать риски;\n"
        "— дать следующий шаг.",
        reply_markup=demo_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "🗂 Демо: проект")
async def demo_project_handler(message: Message) -> None:
    await message.answer(
        "🗂 <b>Демо: сохранить проект</b>\n\n"
        "<b>Шаг 1</b>\n"
        "Нажми: 🗂 Проекты → ➕ Новый проект\n\n"
        "<b>Шаг 2</b>\n"
        "Отправь пример:\n\n"
        "<code>Иванова / ремонт квартиры. Бюджет 450 000 ₽. Дедлайн 20 мая. "
        "Нужно согласовать смету и подготовить КП. Клиент просит не выходить за бюджет.</code>\n\n"
        "<b>Шаг 3</b>\n"
        "Потом спроси обычным сообщением:\n\n"
        "<code>Что у нас по Ивановой и какой следующий шаг?</code>\n\n"
        "<b>Что должен сделать бот</b>\n"
        "— найти проектный контекст;\n"
        "— вспомнить бюджет и дедлайн;\n"
        "— предложить следующий шаг.",
        reply_markup=demo_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "📄 Демо: документ")
async def demo_document_handler(message: Message) -> None:
    await message.answer(
        "📄 <b>Демо: собрать документ</b>\n\n"
        "<b>Шаг 1</b>\n"
        "Нажми: 📄 Документы → 🧾 КП\n\n"
        "<b>Шаг 2</b>\n"
        "Отправь пример:\n\n"
        "<code>КП на настройку рекламы для салона красоты. Бюджет 35 000 рублей. "
        "Срок 14 дней. Цель — заявки из Telegram и VK. Нужно показать клиенту, "
        "что работа будет поэтапной и с понятным результатом.</code>\n\n"
        "<b>Что должен сделать бот</b>\n"
        "— собрать структуру КП;\n"
        "— оформить DOCX;\n"
        "— оформить PDF;\n"
        "— отправить файлы в Telegram.",
        reply_markup=demo_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "✅ Демо: что дальше")
async def demo_next_handler(message: Message) -> None:
    await message.answer(
        "✅ <b>Что делать дальше</b>\n\n"
        "<b>Если тестируешь продукт</b>\n"
        "— начни с 🧠 Ассистент;\n"
        "— скинь реальную рабочую задачу;\n"
        "— оцени ответ через 👍 / 👎.\n\n"
        "<b>Если ведёшь клиента или задачу</b>\n"
        "— создай проект;\n"
        "— добавляй заметки;\n"
        "— спрашивай: «что по проекту?»\n\n"
        "<b>Если нужен результат в файл</b>\n"
        "— открой 📄 Документы;\n"
        "— выбери КП, план, резюме или чек-лист;\n"
        "— отправь вводные как есть.\n\n"
        "<b>Главная идея</b>\n"
        "Не надо писать идеально. Кидай хаос — бот превращает его в рабочий результат.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
