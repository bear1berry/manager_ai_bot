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
        "📄 <b>Документы</b>\n\n"
        "Соберу из вводных аккуратный рабочий файл в DOCX/PDF.\n\n"
        "<b>Что можно подготовить</b>\n"
        "— коммерческое предложение;\n"
        "— план работ;\n"
        "— резюме встречи;\n"
        "— чек-лист.\n\n"
        "<b>Как пользоваться</b>\n"
        "Выбери тип документа и отправь вводные одним сообщением. Можно писать сыро — я структурирую.",
        reply_markup=documents_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text.in_(DOC_TYPES.keys()))
async def choose_document_handler(message: Message, state: FSMContext) -> None:
    doc_type, title = DOC_TYPES[message.text]
    await state.update_data(doc_type=doc_type, title=title)
    await state.set_state(DocumentStates.waiting_source_text)

    await message.answer(
        f"📄 <b>{title}</b>\n\n"
        "Отправь вводные одним сообщением.\n\n"
        "<b>Пример</b>\n"
        "<code>КП на настройку рекламы для салона красоты. Бюджет 35 000 ₽. "
        "Срок 14 дней. Цель — заявки из Telegram и VK.</code>\n\n"
        "После этого я соберу структуру и отправлю файлы.",
        reply_markup=documents_keyboard(),
        parse_mode="HTML",
    )


@router.message(DocumentStates.waiting_source_text)
async def generate_document_handler(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer(
            "⚠️ <b>Нужны текстовые вводные</b>\n\n"
            "Отправь описание задачи одним сообщением.",
            parse_mode="HTML",
        )
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
                parse_mode="HTML",
            )
            return

        await usage_repo.add(user_id=user_id, kind="text")

    await message.answer(
        "🧠 <b>Собираю документ</b>\n\n"
        "— анализирую вводные;\n"
        "— формирую структуру;\n"
        "— готовлю DOCX/PDF.",
        reply_markup=documents_keyboard(),
        parse_mode="HTML",
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
            "✅ <b>Документ собран</b>\n\n"
            "Отправляю файлы. Если PDF не пришёл — значит временно сработал fallback на DOCX.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
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
            "⚠️ <b>Не удалось собрать документ</b>\n\n"
            "<b>Что случилось</b>\n"
            "Во время генерации произошла ошибка.\n\n"
            "<b>Что сделать</b>\n"
            "— сократи вводные;\n"
            "— попробуй ещё раз;\n"
            "— если ошибка повторится, проверь логи приложения.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
