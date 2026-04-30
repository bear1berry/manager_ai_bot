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
        f"🧠 <b>{name}, это «Менеджер ИИ»</b>\n\n"
        "<b>Не чат-бот. AI-операционный помощник.</b>\n"
        "Я превращаю рабочий хаос в понятный результат: план, текст, проект, документ, сводку или исследование.\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ <b>Главная идея</b>\n\n"
        "Ты пишешь как есть:\n"
        "— мысль;\n"
        "— задачу;\n"
        "— кусок переписки;\n"
        "— идею продукта;\n"
        "— вопрос;\n"
        "— хаос в голове.\n\n"
        "Я превращаю это в рабочую структуру:\n"
        "— <b>что важно</b>;\n"
        "— <b>что делать</b>;\n"
        "— <b>где риск</b>;\n"
        "— <b>какой следующий шаг</b>;\n"
        "— <b>как оформить в DOCX/PDF</b>.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🧩 <b>Что я умею</b>\n\n"
        "🌍 <b>Универсальный режим</b>\n"
        "Любые вопросы: объяснить, придумать, разобрать, сравнить, решить.\n\n"
        "✍️ <b>Ответ клиенту</b>\n"
        "Из нервной переписки — спокойный деловой ответ без оправданий.\n\n"
        "🧾 <b>Разбор хаоса</b>\n"
        "Сырые мысли → суть, риски, порядок действий.\n\n"
        "📌 <b>Планы</b>\n"
        "Цель → этапы → контрольные точки → первый шаг.\n\n"
        "🧩 <b>Продукт</b>\n"
        "ЦА, боль, ценность, MVP, гипотезы, метрики.\n\n"
        "🔥 <b>Стратег</b>\n"
        "Позиционирование, рост, сильные ходы и план удара.\n\n"
        "🗂 <b>Проекты</b>\n"
        "Память по клиентам, задачам, срокам, решениям и документам.\n\n"
        "📄 <b>Документы</b>\n"
        "КП, план работ, чек-лист, резюме встречи в DOCX/PDF.\n\n"
        "🌐 <b>Web Search</b>\n"
        "Актуальные данные из сети, когда нужно проверить свежую информацию.\n\n"
        "🔎 <b>Deep Research</b>\n"
        "Глубокий ресёрч: несколько запросов, источники, выводы, риски, рекомендации.\n\n"
        "👥 <b>Групповой GPT</b>\n"
        "Добавь меня в группу: я смогу делать сводки, анализировать переписку и собирать протоколы.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🚀 <b>Начни с одного сообщения</b>\n\n"
        "Можешь прямо сейчас написать:\n\n"
        "<code>Разбери мою идею Telegram-бота и скажи, как её монетизировать</code>\n\n"
        "или:\n\n"
        "<code>Сделай план запуска Mini App на 14 дней</code>\n\n"
        "или:\n\n"
        "<code>Сделай глубокий ресерч по Telegram Stars</code>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🎛 <b>Навигация</b>\n\n"
        "🧠 <b>Режимы</b> — все рабочие сценарии.\n"
        "👤 <b>Профиль</b> — тариф, лимиты, активность, подписка.\n"
        "🌐 <b>Mini App</b> — кабинет проектов, документов и групп.\n\n"
        f"Текущий тариф: <b>{plan_name}</b>.\n\n"
        "Пиши задачу обычным сообщением. Идеальный промпт не нужен — это моя работа."
    )


def _menu_text() -> str:
    return (
        "🏠 <b>Главное меню</b>\n\n"
        "Минимум кнопок. Максимум смысла.\n\n"
        "🧠 <b>Режимы</b>\n"
        "Все сценарии работы: универсальный ассистент, клиентские ответы, планы, продукт, стратегия, проекты, документы и демо.\n\n"
        "👤 <b>Профиль</b>\n"
        "Тариф, лимиты, активность и подписка.\n\n"
        "🌐 <b>Mini App</b>\n"
        "Кабинет управления: проекты, документы, группы, статистика и рабочая история.\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ <b>Быстрый старт</b>\n\n"
        "Просто напиши задачу. Например:\n\n"
        "<code>Разложи по шагам запуск моего Telegram-бота</code>\n\n"
        "или:\n\n"
        "<code>Найди актуальные данные и сделай выводы для продукта</code>"
    )


def _help_text() -> str:
    return (
        "🧭 <b>Как пользоваться «Менеджером ИИ»</b>\n\n"
        "Тут не нужно писать идеальные промпты. Пиши как в жизни: криво, коротко, кусками, с эмоциями. "
        "Я сам соберу структуру.\n\n"
        "━━━━━━━━━━━━━━\n"
        "1️⃣ <b>Если не знаешь, с чего начать</b>\n\n"
        "Жми <b>🧠 Режимы → 🌍 Универсальный</b>\n\n"
        "Или просто напиши:\n"
        "<code>Помоги разобраться с задачей...</code>\n\n"
        "━━━━━━━━━━━━━━\n"
        "2️⃣ <b>Если нужно превратить хаос в порядок</b>\n\n"
        "Напиши:\n"
        "<code>Разбери это и скажи, что делать дальше...</code>\n\n"
        "Я выделю:\n"
        "— суть;\n"
        "— факты;\n"
        "— риски;\n"
        "— порядок действий;\n"
        "— первый шаг.\n\n"
        "━━━━━━━━━━━━━━\n"
        "3️⃣ <b>Если нужен документ</b>\n\n"
        "Сначала попроси разобрать задачу, потом напиши:\n"
        "<code>сделай это документом</code>\n\n"
        "И я соберу DOCX/PDF.\n\n"
        "Доступные форматы:\n"
        "— КП;\n"
        "— план работ;\n"
        "— чек-лист;\n"
        "— резюме встречи;\n"
        "— документ из проекта;\n"
        "— документ из диалога.\n\n"
        "━━━━━━━━━━━━━━\n"
        "4️⃣ <b>Если нужны свежие данные</b>\n\n"
        "Напиши:\n"
        "<code>Найди актуальные данные по...</code>\n\n"
        "или:\n"
        "<code>Проверь это в сети</code>\n\n"
        "━━━━━━━━━━━━━━\n"
        "5️⃣ <b>Если нужен глубокий ресёрч</b>\n\n"
        "Напиши:\n"
        "<code>Сделай глубокий ресерч по...</code>\n\n"
        "Я соберу источники, сравню данные, покажу ограничения и дам рекомендации.\n\n"
        "━━━━━━━━━━━━━━\n"
        "6️⃣ <b>Если хочешь работать с проектом</b>\n\n"
        "Жми <b>🧠 Режимы → 🗂 Проекты</b>\n\n"
        "Проекты нужны, чтобы хранить:\n"
        "— клиента;\n"
        "— цель;\n"
        "— сроки;\n"
        "— бюджет;\n"
        "— решения;\n"
        "— заметки;\n"
        "— документы.\n\n"
        "━━━━━━━━━━━━━━\n"
        "7️⃣ <b>Если хочешь использовать в группе</b>\n\n"
        "Добавь бота в Telegram-группу и напиши:\n"
        "<code>/group_on</code>\n\n"
        "Потом можно вызывать:\n"
        "<code>@user_managerGPT_Bot подведи итоги за сегодня</code>\n\n"
        "или:\n"
        "<code>@user_managerGPT_Bot сделай протокол по переписке</code>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🌐 <b>Mini App</b>\n\n"
        "Открывается кнопкой <b>🌐 Mini App</b> или командой <code>/miniapp</code>.\n\n"
        "Там будут:\n"
        "— проекты;\n"
        "— документы;\n"
        "— группы;\n"
        "— профиль;\n"
        "— подписка;\n"
        "— история результата.\n\n"
        "Главное правило: <b>не думай, какую кнопку нажать — просто напиши задачу.</b>"
    )


def _demo_start_text() -> str:
    return (
        "🎬 <b>Быстрое демо</b>\n\n"
        "Скопируй любой пример и отправь мне:\n\n"
        "1. <code>Разбери идею AI-бота для менеджеров: ЦА, боль, MVP, монетизация и риски</code>\n\n"
        "2. <code>Сделай стратегию запуска Telegram-бота на первые 30 дней без бюджета</code>\n\n"
        "3. <code>Клиент пишет: почему так дорого? Напиши уверенный ответ</code>\n\n"
        "4. <code>Найди актуальные данные по Telegram Stars и объясни, как это влияет на монетизацию бота</code>\n\n"
        "5. <code>Сделай глубокий ресерч по рынку Telegram Mini Apps</code>\n\n"
        "После любого сильного ответа можешь написать:\n\n"
        "<code>сделай это документом</code>\n\n"
        "И я соберу DOCX/PDF."
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
        disable_web_page_preview=True,
    )


@router.message(Command("menu"))
@router.message(F.text == "⬅️ Назад")
async def menu_handler(message: Message) -> None:
    await message.answer(
        _menu_text(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        _help_text(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("demo_start"))
async def demo_start_handler(message: Message) -> None:
    await message.answer(
        _demo_start_text(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
