from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from app.bot.keyboards import documents_keyboard, main_keyboard
from app.config import get_settings
from app.services.documents import DocumentService
from app.services.limits import check_limit, limit_message
from app.services.llm import LLMService
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import UsageRepository, UserRepository

logger = logging.getLogger(__name__)
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
        "Я подготовлю структуру, соберу DOCX и PDF. "
        "Если LLM API не подключён — сработает безопасный демо-шаблон.",
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
        "`КП на настройку рекламы для салона красоты. Бюджет 35 000 ₽. "
        "Срок 14 дней. Цель — заявки из Telegram и VK.`",
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
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)

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
            await message.answer(
                limit_message(limit_result),
                reply_markup=main_keyboard(),
                parse_mode="Markdown",
            )
            return

        await usage_repo.add(user_id=user_id, kind="text")

    await message.answer(
        "🧠 Собираю документ: анализирую вводные, формирую структуру и готовлю файлы.",
        reply_markup=documents_keyboard(),
    )

    try:
        llm = LLMService(settings)
        document_data = await llm.generate_document_data(
            source_text=message.text,
            doc_type=doc_type,
            title=title,
        )

        service = DocumentService(settings)
        generated = service.generate_from_data(data=document_data, fallback_title=title)

        await state.clear()

        await message.answer(
            "✅ **Документ собран**\n\n"
            "Отправляю DOCX и PDF. Если PDF не пришёл — значит сработал безопасный fallback на DOCX.",
            reply_markup=main_keyboard(),
            parse_mode="Markdown",
        )

        await message.answer_document(
            FSInputFile(generated.docx_path),
            caption=f"📄 {document_data.get('title', title)} / DOCX",
        )

        if generated.pdf_path:
            await message.answer_document(
                FSInputFile(generated.pdf_path),
                caption=f"📄 {document_data.get('title', title)} / PDF",
            )

    except Exception:
        logger.exception("Document generation failed")
        await state.clear()
        await message.answer(
            "⚠️ **Не удалось собрать документ**\n\n"
            "Что случилось: во время генерации произошла ошибка.\n\n"
            "Что сделать:\n"
            "1. Сократи вводные и попробуй ещё раз.\n"
            "2. Проверь, подключён ли LLM API.\n"
            "3. Если ошибка повторится — смотри логи приложения.",
            reply_markup=main_keyboard(),
            parse_mode="Markdown",
        )
