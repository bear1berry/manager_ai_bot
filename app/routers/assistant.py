from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.types import Message

from app.bot.keyboards import assistant_keyboard, main_keyboard
from app.config import get_settings
from app.services.limits import check_limit, limit_message
from app.services.llm import LLMService
from app.services.projects import (
    build_projects_context,
    build_prompt_with_project_context,
    should_use_project_context,
)
from app.services.queue import enqueue_media_task
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import (
    MessageRepository,
    ProjectRepository,
    QueueRepository,
    UsageRepository,
    UserRepository,
)
from app.utils.files import ensure_dir
from app.utils.text import split_long_text

logger = logging.getLogger(__name__)
router = Router()


MODE_BY_BUTTON = {
    "✍️ Ответ клиенту": "client_reply",
    "🧾 Разобрать хаос": "chaos",
    "📌 Сделать план": "plan",
}


@router.message(F.text == "🧠 Ассистент")
async def assistant_menu_handler(message: Message) -> None:
    await message.answer(
        "🧠 **Ассистент**\n\n"
        "Можешь просто написать задачу или выбрать быстрый режим:\n\n"
        "— ответ клиенту;\n"
        "— разобрать хаос;\n"
        "— сделать план.\n\n"
        "Если вопрос похож на проектный — я подмешаю контекст из `🗂 Проекты`.",
        reply_markup=assistant_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.voice)
async def voice_handler(message: Message, bot: Bot) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)
        queue_repo = QueueRepository(db)

        user_db_id = await ensure_user(user_repo, message.from_user)
        user = await user_repo.get_by_telegram_id(message.from_user.id)

        plan = str(user["plan"]) if user else "free"
        result = await check_limit(
            usage_repo=usage_repo,
            settings=settings,
            user_id=user_db_id,
            plan=plan,
            kind="voice",
        )

        if not result.allowed:
            await message.answer(limit_message(result), reply_markup=main_keyboard(), parse_mode="Markdown")
            return

        voice = message.voice
        file = await bot.get_file(voice.file_id)

        voices_dir = ensure_dir(Path("data") / "voices")
        local_path = voices_dir / f"{message.from_user.id}_{message.message_id}_{uuid4().hex}.ogg"

        await bot.download_file(file.file_path, destination=local_path)

        dedupe_key = f"voice:{message.chat.id}:{message.message_id}:{voice.file_unique_id}"

        payload = {
            "chat_id": message.chat.id,
            "user_db_id": user_db_id,
            "telegram_user_id": message.from_user.id,
            "message_id": message.message_id,
            "file_id": voice.file_id,
            "file_unique_id": voice.file_unique_id,
            "file_path": str(local_path),
        }

        inserted = await enqueue_media_task(
            queue_repo=queue_repo,
            kind="voice_transcribe",
            payload=payload,
            dedupe_key=dedupe_key,
        )

    if inserted:
        await message.answer(
            "🎧 Голосовое поставил в очередь.\n\n"
            "Сейчас разберу и верну структуру: задачи, риски и следующий шаг.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "♻️ Это голосовое уже было поставлено в обработку. Дубликат не создаю.",
            reply_markup=main_keyboard(),
        )


@router.message(F.text.in_(MODE_BY_BUTTON.keys()))
async def fast_mode_handler(message: Message) -> None:
    await message.answer(
        "Принял режим.\n\n"
        "Теперь отправь вводные следующим сообщением или сразу напиши задачу полностью.",
        reply_markup=assistant_keyboard(),
    )


@router.message(F.text)
async def text_assistant_handler(message: Message) -> None:
    if not message.text:
        return

    text = message.text.strip()

    service_buttons = {
        "⬅️ Назад",
        "📄 Документы",
        "🗂 Проекты",
        "👤 Профиль",
        "💎 Подписка",
        "💎 Pro",
        "🏢 Business",
        "➕ Новый проект",
        "📚 Мои проекты",
        "🔎 Найти проект",
        "🧠 Контекст проектов",
        "🧾 КП",
        "📋 План работ",
        "📝 Резюме встречи",
        "✅ Чек-лист",
    }

    if text in service_buttons:
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        usage_repo = UsageRepository(db)
        msg_repo = MessageRepository(db)
        project_repo = ProjectRepository(db)

        user_db_id = await ensure_user(user_repo, message.from_user)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        plan = str(user["plan"]) if user else "free"

        limit_result = await check_limit(
            usage_repo=usage_repo,
            settings=settings,
            user_id=user_db_id,
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

        project_context = ""
        if should_use_project_context(text):
            found_projects = await project_repo.search_active(user_id=user_db_id, query=text, limit=5)

            if not found_projects:
                found_projects = await project_repo.latest_context(user_id=user_db_id, limit=3)

            project_context = build_projects_context(found_projects)

        enriched_text = build_prompt_with_project_context(text, project_context)

        await usage_repo.add(user_id=user_db_id, kind="text")
        await msg_repo.add(user_id=user_db_id, role="user", content=text)

        history = await msg_repo.recent(user_id=user_db_id, limit=12)

    if project_context:
        await message.answer("🧠 Нашёл проектный контекст. Отвечаю с учётом памяти.")
    else:
        await message.answer("Думаю и собираю ответ в рабочую структуру 🧠")

    llm = LLMService(settings)
    answer = await llm.complete(user_text=enriched_text, history=history, mode="assistant")

    async with await connect_db(settings.database_path) as db:
        user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
        if user:
            await MessageRepository(db).add(user_id=int(user["id"]), role="assistant", content=answer)

    for chunk in split_long_text(answer):
        await message.answer(
            chunk,
            reply_markup=main_keyboard(),
            parse_mode="Markdown",
        )
