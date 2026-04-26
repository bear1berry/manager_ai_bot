from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from app.bot.keyboards import documents_keyboard, main_keyboard
from app.config import get_settings
from app.services.documents import DocumentService
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UsageRepository, UserRepository

router = Router()


class DocumentStates(StatesGroup):
    waiting_source_text = State()


DOC_TYPES = {
    "🧾 КП": ("commercial_offer", "Коммерческое предложение"),
    "📋 План работ": ("work_plan", "План работ"),
    "📝 Резюме встречи": ("meeting_summary", "Резюме встречи"),
    "✅ Чек-лист": ("checklist", "Чек-лист"),
}


@router.message(F.text == "📄 Документы")
async def documents_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📄 **Документы**\n\n"
        "Выбери, что нужно собрать из вводных:\n"
        "— КП;\n"
        "— план работ;\n"
        "— резюме встречи;\n"
        "— чек-лист.\n\n"
        "На выходе дам DOCX и PDF, если размер и шрифт позволяют.",
        reply_markup=documents_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text.in_(DOC_TYPES.keys()))
async def choose_document_handler(message: Message, state: FSMContext) -> None:
    doc_type, title = DOC_TYPES[message.text]
    await state.update_data(doc_type=doc_type, title=title)
    await state.set_state(DocumentStates.waiting_source_text)

    await message.answer(
        f"📄 **{title}**\n\n"
        "Отправь вводные одним сообщением.\n\n"
        "Пример:\n"
        "`КП на настройку рекламы для салона красоты. Бюджет 35 000 ₽. Срок 14 дней. Цель — заявки.`",
        reply_markup=documents_keyboard(),
        parse_mode="Markdown",
    )


@router.message(DocumentStates.waiting_source_text)
async def generate_document_handler(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Нужны текстовые вводные для документа.")
        return

    settings = get_settings()
    data = await state.get_data()
    doc_type = str(data.get("doc_type", "checklist"))
    title = str(data.get("title", "Документ"))

    async with await connect_db(settings.database_path) as db:
        user_id = await ensure_user(UserRepository(db), message.from_user)
        await UsageRepository(db).add(user_id=user_id, kind="text")

    service = DocumentService(settings)
    generated = service.generate(title=title, source_text=message.text, doc_type=doc_type)

    await state.clear()

    await message.answer(
        "✅ **Документ собран**\n\n"
        "Отправляю файлы. Если PDF не пришёл — значит сработал безопасный fallback на DOCX.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )

    await message.answer_document(
        FSInputFile(generated.docx_path),
        caption=f"📄 {title} / DOCX",
    )

    if generated.pdf_path:
        await message.answer_document(
            FSInputFile(generated.pdf_path),
            caption=f"📄 {title} / PDF",
        )
