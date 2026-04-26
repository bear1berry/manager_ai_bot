from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.keyboards import assistant_keyboard, main_keyboard
from app.config import get_settings
from app.services.intents import IntentResult, detect_intent, status_text
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
from app.utils.text import split_long_text, telegram_html_from_ai_text

logger = logging.getLogger(__name__)
router = Router()


class AssistantStates(StatesGroup):
    waiting_mode_input = State()


MODE_BY_BUTTON = {
    "✍️ Ответ клиенту": {
        "mode": "client_reply",
        "title": "Ответ клиенту",
        "hint": (
            "Отправь переписку, претензию, вопрос клиента или короткие вводные.\n\n"
            "Я соберу спокойный, профессиональный ответ без лишней воды."
        ),
        "example": (
            "Клиент пишет: «Почему так дорого?» "
            "Нужно ответить уверенно, без оправданий, показать ценность услуги."
        ),
    },
    "🧾 Разобрать хаос": {
        "mode": "chaos",
        "title": "Разбор хаоса",
        "hint": (
            "Отправь любые сырые мысли, голос из головы, список проблем или кусок переписки.\n\n"
            "Я разложу это на смысл, задачи, риски и следующий шаг."
        ),
        "example": (
            "Нужно запустить проект, но непонятно с чего начать: есть клиент, сроки горят, "
            "нет структуры и неясно, что делать первым."
        ),
    },
    "📌 Сделать план": {
        "mode": "plan",
        "title": "План действий",
        "hint": (
            "Отправь цель, задачу или ситуацию.\n\n"
            "Я соберу пошаговый план: что делать, в каком порядке и где контрольные точки."
        ),
        "example": (
            "Нужно за 2 недели подготовить запуск Telegram-бота: тексты, меню, тесты, GitHub, деплой."
        ),
    },
}


SERVICE_BUTTONS = {
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
    "📝 Заметка в проект",
    "🧾 КП",
    "📋 План работ",
    "📝 Резюме встречи",
    "✅ Чек-лист",
}


@router.message(F.text == "🧠 Ассистент")
async def assistant_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🧠 <b>Ассистент</b>\n\n"
        "Выбери быстрый режим или просто напиши задачу обычным сообщением.\n\n"
        "<b>Режимы</b>\n"
        "— ✍️ Ответ клиенту — деловой ответ без оправданий;\n"
        "— 🧾 Разобрать хаос — мысли → структура;\n"
        "— 📌 Сделать план — цель → действия.\n\n"
        "Я также умею сам определить сценарий по тексту. "
        "Если вопрос похож на проектный — подмешаю контекст из 🗂 Проекты.",
        reply_markup=assistant_keyboard(),
        parse_mode="HTML",
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
async def fast_mode_handler(message: Message, state: FSMContext) -> None:
    mode_data = MODE_BY_BUTTON[message.text]

    await state.set_state(AssistantStates.waiting_mode_input)
    await state.update_data(
        assistant_mode=mode_data["mode"],
        assistant_mode_title=mode_data["title"],
    )

    await message.answer(
        f"⚡ <b>Режим: {mode_data['title']}</b>\n\n"
        f"{mode_data['hint']}\n\n"
        "<b>Пример</b>\n"
        f"<code>{mode_data['example']}</code>\n\n"
        "Чтобы выйти из режима — нажми ⬅️ Назад.",
        reply_markup=assistant_keyboard(),
        parse_mode="HTML",
    )


@router.message(AssistantStates.waiting_mode_input, F.text == "⬅️ Назад")
async def cancel_fast_mode_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Режим сброшен. Возвращаю в главное меню.",
        reply_markup=main_keyboard(),
    )


@router.message(AssistantStates.waiting_mode_input, F.text)
async def fast_mode_input_handler(message: Message, state: FSMContext) -> None:
    if not message.text:
        return

    text = message.text.strip()

    if text in SERVICE_BUTTONS:
        await state.clear()
        return

    data = await state.get_data()
    mode = str(data.get("assistant_mode") or "assistant")
    mode_title = str(data.get("assistant_mode_title") or "Ассистент")

    await state.clear()

    manual_intent = IntentResult(
        mode=mode,
        title=mode_title,
        confidence=1.0,
        reason="Режим выбран пользователем вручную",
    )

    await _process_text_request(
        message=message,
        text=text,
        intent=manual_intent,
        use_project_context=True,
    )


@router.message(F.text)
async def text_assistant_handler(message: Message) -> None:
    if not message.text:
        return

    text = message.text.strip()

    if text in SERVICE_BUTTONS or text in MODE_BY_BUTTON:
        return

    detected_intent = detect_intent(text)

    await _process_text_request(
        message=message,
        text=text,
        intent=detected_intent,
        use_project_context=True,
    )


async def _process_text_request(
    message: Message,
    text: str,
    intent: IntentResult,
    use_project_context: bool,
) -> None:
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
        if use_project_context and should_use_project_context(text):
            found_projects = await project_repo.search_active(user_id=user_db_id, query=text, limit=5)

            if not found_projects:
                found_projects = await project_repo.latest_context(user_id=user_db_id, limit=3)

            project_context = build_projects_context(found_projects)

        enriched_text = build_prompt_with_project_context(text, project_context)

        await usage_repo.add(user_id=user_db_id, kind="text")
        await msg_repo.add(user_id=user_db_id, role="user", content=text)

        history = await msg_repo.recent(user_id=user_db_id, limit=12)

    await message.answer(
        telegram_html_from_ai_text(status_text(intent, has_project_context=bool(project_context))),
        parse_mode="HTML",
    )

    llm = LLMService(settings)
    answer = await llm.complete(user_text=enriched_text, history=history, mode=intent.mode)

    async with await connect_db(settings.database_path) as db:
        user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
        if user:
            await MessageRepository(db).add(user_id=int(user["id"]), role="assistant", content=answer)

    for chunk in split_long_text(answer):
        await message.answer(
            telegram_html_from_ai_text(chunk),
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
