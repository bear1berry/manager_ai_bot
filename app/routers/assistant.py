from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.keyboards import feedback_keyboard, main_keyboard, modes_keyboard
from app.config import get_settings
from app.services.dialogue import (
    build_dialogue_prompt,
    build_search_text_for_dialogue,
    detect_dialogue_action,
)
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
from app.services.web_search import WebSearchBundle, WebSearchService
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
    "🌍 Универсальный": {
        "mode": "assistant",
        "title": "Универсальный",
        "hint": (
            "Это главный режим бота — рабочий мозг под любые задачи.\n\n"
            "Можно писать как угодно: коротко, хаотично, списком, куском переписки или одной фразой.\n\n"
            "Я сам выберу формат: анализ, план, стратегия, текст, идея, решение, инструкция или структурный разбор."
        ),
        "example": (
            "Хочу запустить Telegram-бота для менеджеров, но пока не понимаю, "
            "как упаковать ценность, кому продавать и что показывать первым пользователям."
        ),
        "examples": [
            "Найди свежую информацию по Telegram Stars и объясни, как это влияет на мой бот.",
            "Проверь актуальные изменения Telegram Bot API и дай короткую выжимку.",
            "Разбери мою идею и скажи, есть ли в ней ценность для пользователя.",
            "Составь план на неделю, чтобы продвинуть мой проект без бюджета.",
            "Собери из моих мыслей понятную структуру и следующий шаг.",
        ],
    },
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
        "examples": [
            "Клиент пишет: «Почему так дорого?» Нужно ответить уверенно и без оправданий.",
            "Клиент пропал после цены. Напиши мягкое сообщение, чтобы вернуть диалог.",
            "Клиент недоволен сроками. Составь спокойный ответ и предложи решение.",
            "Нужно отказать клиенту, но сохранить нормальные отношения.",
            "Сделай ответ на претензию: клиент считает, что результат не соответствует ожиданиям.",
        ],
    },
    "🧾 Разобрать хаос": {
        "mode": "chaos",
        "title": "Разбор хаоса",
        "hint": (
            "Отправь любые сырые мысли, список проблем, ситуацию или кусок переписки.\n\n"
            "Я разложу это на смысл, задачи, риски и следующий шаг."
        ),
        "example": (
            "Нужно запустить проект, но непонятно с чего начать: есть клиент, сроки горят, "
            "нет структуры и неясно, что делать первым."
        ),
        "examples": [
            "У меня много задач по боту, всё смешалось. Разложи по приоритетам.",
            "Есть идея, но я не понимаю, с чего начать. Разбери хаос и дай первый шаг.",
            "Я перегорел от проекта. Разложи, что важно, что лишнее и что делать завтра.",
            "Вот список проблем: сроки, деньги, дизайн, пользователи. Собери порядок действий.",
            "Разбери ситуацию без воды: где факты, где эмоции, где риск.",
        ],
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
        "examples": [
            "Составь план запуска Telegram-бота на 14 дней.",
            "Сделай план подготовки продукта к первым 10 пользователям.",
            "Разбей задачу на этапы: Mini App, документы, подписка, тестирование.",
            "Составь план на неделю: что делать каждый день, чтобы не выгореть.",
            "Сделай roadmap развития продукта на месяц.",
        ],
    },
    "🧩 Продукт": {
        "mode": "product",
        "title": "Продукт",
        "hint": (
            "Режим для продуктового мышления: идея, ЦА, боль, ценность, MVP, гипотезы, метрики, roadmap.\n\n"
            "Подходит, если нужно понять, что строить, кому это нужно, как упаковать и как проверить спрос."
        ),
        "example": (
            "Есть Telegram AI-бот для менеджеров. Нужно понять целевую аудиторию, ценность, MVP, "
            "первый платный сценарий и что показать первым пользователям."
        ),
        "examples": [
            "Найди свежие данные по рынку Telegram Mini Apps и дай выводы для продукта.",
            "Разбери идею моего Telegram AI-бота: ЦА, боль, ценность, MVP.",
            "Сформулируй позиционирование продукта для первых пользователей.",
            "Какие 3 гипотезы мне проверить перед запуском подписки?",
            "Придумай первый платный сценарий, за который пользователь реально заплатит.",
        ],
    },
    "🔥 Стратег": {
        "mode": "strategy",
        "title": "Стратег",
        "hint": (
            "Режим для сильных ходов: позиционирование, рост, нестандартные решения, конкуренция, риски и план удара.\n\n"
            "Подходит, когда нужен не просто ответ, а стратегия с приоритетами."
        ),
        "example": (
            "Как мне вывести AI-бота на первых платных пользователей, если бюджета почти нет, "
            "но хочется выглядеть как премиальный продукт?"
        ),
        "examples": [
            "Найди свежую информацию по конкурентам Telegram AI-ботов и дай стратегию.",
            "Как вывести AI-бота на первых платных пользователей без бюджета?",
            "Найди сильный ход, чтобы мой продукт выглядел премиально на старте.",
            "Какие каналы продвижения выбрать, если ресурсов мало?",
            "Составь стратегию на 30 дней: рост, упаковка, первые продажи.",
        ],
    },
}


SERVICE_BUTTONS = {
    "⬅️ Назад",
    "👍 Полезно",
    "👎 Не то",
    "🧠 Режимы",
    "🧠 Ассистент",
    "👤 Профиль",
    "📊 Лимиты",
    "📈 Активность",
    "💎 Подписка",
    "💎 Pro",
    "🏢 Business",
    "📄 Документы",
    "🗂 Проекты",
    "🚀 Демо",
    "➕ Новый проект",
    "📚 Мои проекты",
    "🔎 Найти проект",
    "🧠 Контекст проектов",
    "📝 Заметка в проект",
    "🧾 КП",
    "📋 План работ",
    "📝 Резюме встречи",
    "✅ Чек-лист",
    "📄 Документ из проекта",
    "🧾 КП из проекта",
    "📋 План из проекта",
    "📝 Резюме из проекта",
    "✅ Чек-лист из проекта",
    "🧾 Демо: хаос",
    "🗂 Демо: проект",
    "📄 Демо: документ",
    "✅ Демо: что дальше",
}


def _examples_block(examples: list[str]) -> str:
    if not examples:
        return ""

    lines = "\n".join(f"— <code>{example}</code>" for example in examples)

    return (
        "💡 <b>Что можно написать</b>\n"
        f"{lines}"
    )


def _web_status_text(bundle: WebSearchBundle) -> str:
    if not bundle.requested:
        return ""

    if not bundle.enabled:
        return (
            "\n\n🌐 <b>Web-поиск запрошен, но отключён</b>\n"
            "Чтобы искать актуальные данные, включи <code>WEB_SEARCH_ENABLED=true</code> и добавь API-ключ поиска."
        )

    if bundle.has_results:
        return (
            "\n\n🌐 <b>Нашёл данные в сети</b>\n"
            f"Источник: <code>{bundle.provider}</code>. "
            f"Результатов: <code>{len(bundle.results)}</code>."
        )

    return (
        "\n\n🌐 <b>Поиск выполнен, но результатов нет</b>\n"
        "Отвечу осторожно и не буду выдумывать свежие факты."
    )


def _dialogue_status_text(is_followup: bool, title: str) -> str:
    if not is_followup:
        return ""

    return (
        "\n\n💬 <b>Понял продолжение диалога</b>\n"
        f"Действие: <code>{title}</code>."
    )


@router.message(F.text.in_({"🧠 Режимы", "🧠 Ассистент"}))
async def assistant_menu_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🧠 <b>Режимы</b>\n\n"
        "Это витрина рабочих сценариев. Если не знаешь, куда нажимать — выбирай <b>🌍 Универсальный</b>.\n\n"
        "🌍 <b>Универсальный</b>\n"
        "Для любых задач: стратегия, тексты, идеи, анализ, объяснения, планы, решения и поиск актуальных данных.\n\n"
        "✍️ <b>Ответ клиенту</b>\n"
        "Готовый деловой ответ без оправданий, воды и нервов.\n\n"
        "🧾 <b>Разобрать хаос</b>\n"
        "Сырые мысли → суть, риски, порядок действий.\n\n"
        "📌 <b>Сделать план</b>\n"
        "Цель → шаги, сроки, контрольные точки.\n\n"
        "🧩 <b>Продукт</b>\n"
        "Идея → ЦА, боль, ценность, MVP, гипотезы, метрики.\n\n"
        "🔥 <b>Стратег</b>\n"
        "Позиционирование, рост, сильные ходы, риски и план удара.\n\n"
        "🌐 <b>Web-поиск</b>\n"
        "Напиши: <code>найди</code>, <code>проверь</code>, <code>актуальные данные</code>, <code>что нового</code>.\n\n"
        "💬 <b>Диалог</b>\n"
        "После ответа можно писать: <code>сделай короче</code>, <code>продолжи</code>, "
        "<code>подробнее</code>, <code>перепиши</code>, <code>проверь это в сети</code>.\n\n"
        "Выбери режим ниже. После выбора я покажу примеры запросов.",
        reply_markup=modes_keyboard(),
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
            await message.answer(limit_message(result), reply_markup=main_keyboard(), parse_mode="HTML")
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
            "Сейчас разберу и верну структуру: смысл, задачи, риски и следующий шаг.",
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
    examples = mode_data.get("examples", [])

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
        f"{_examples_block(examples)}\n\n"
        "Отправь вводные следующим сообщением. Можно скопировать любой пример и заменить детали.\n\n"
        "Чтобы выйти из режима — нажми ⬅️ Назад.",
        reply_markup=modes_keyboard(),
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
                parse_mode="HTML",
            )
            return

        history = await msg_repo.recent(user_id=user_db_id, limit=16)
        dialogue_action = detect_dialogue_action(text)

        search_text = build_search_text_for_dialogue(
            user_text=text,
            history=history,
            action=dialogue_action,
        )

        project_context = ""
        should_search_projects = should_use_project_context(text) or dialogue_action.is_followup

        if use_project_context and should_search_projects:
            project_query = search_text if dialogue_action.needs_web else text
            found_projects = await project_repo.search_active(user_id=user_db_id, query=project_query, limit=5)

            if not found_projects:
                found_projects = await project_repo.latest_context(user_id=user_db_id, limit=3)

            project_context = build_projects_context(found_projects)

        await usage_repo.add(user_id=user_db_id, kind="text")
        await msg_repo.add(user_id=user_db_id, role="user", content=text)

    web_service = WebSearchService(settings)
    web_bundle = await web_service.search_if_needed(search_text)
    web_context = web_service.build_context(web_bundle)

    dialogue_prompt = build_dialogue_prompt(
        user_text=text,
        history=history,
        action=dialogue_action,
    )

    enriched_text = build_prompt_with_project_context(dialogue_prompt, project_context)

    if web_context:
        enriched_text = (
            f"{enriched_text}\n\n"
            "=== WEB SEARCH CONTEXT ===\n"
            f"{web_context}\n"
            "=== END WEB SEARCH CONTEXT ==="
        )

    await message.answer(
        telegram_html_from_ai_text(status_text(intent, has_project_context=bool(project_context)))
        + _dialogue_status_text(dialogue_action.is_followup, dialogue_action.title)
        + _web_status_text(web_bundle),
        parse_mode="HTML",
    )

    llm = LLMService(settings)
    answer = await llm.complete(user_text=enriched_text, history=history, mode=intent.mode)

    async with await connect_db(settings.database_path) as db:
        user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
        if user:
            await MessageRepository(db).add(user_id=int(user["id"]), role="assistant", content=answer)

    chunks = split_long_text(answer)

    for index, chunk in enumerate(chunks):
        is_last = index == len(chunks) - 1

        await message.answer(
            telegram_html_from_ai_text(chunk),
            reply_markup=feedback_keyboard() if is_last else None,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    sources_html = web_service.format_sources_html(web_bundle)
    if sources_html:
        await message.answer(
            sources_html,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
