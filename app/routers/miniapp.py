from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings

router = Router()


def _mini_app_private_text(url: str) -> str:
    return (
        "🌐 <b>Mini App</b>\n\n"
        "Кабинет доступен через кнопку <b>🌐 Mini App</b> в нижнем меню.\n\n"
        "<b>Что внутри</b>\n"
        "— профиль и лимиты;\n"
        "— проекты;\n"
        "— документы;\n"
        "— группы;\n"
        "— подписка;\n"
        "— демо-сценарии.\n\n"
        "Если кнопка не открылась, используй ссылку:\n"
        f"<code>{html.escape(url)}</code>"
    )


def _mini_app_group_text(url: str) -> str:
    return (
        "🌐 <b>Mini App / личный кабинет</b>\n\n"
        "В группе Telegram не всегда открывает WebApp-кнопку из нижней клавиатуры. "
        "Это ограничение Telegram, не баг бота.\n\n"
        "<b>Как открыть кабинет</b>\n"
        "1. Открой личный чат с ботом.\n"
        "2. Нажми <b>🌐 Mini App</b> в нижнем меню.\n"
        "3. Или открой ссылку ниже:\n\n"
        f"<code>{html.escape(url)}</code>\n\n"
        "<b>Раздел “Группы”</b>\n"
        "Появится в Mini App после пересборки фронта и деплоя свежего <code>miniapp/dist</code>."
    )


@router.message(Command("miniapp"))
@router.message(Command("cabinet"))
@router.message(Command("groups"))
@router.message(F.text == "🌐 Mini App")
async def mini_app_handler(message: Message) -> None:
    settings = get_settings()
    url = settings.mini_app_url.strip()

    if url:
        if message.chat.type in {"group", "supergroup"}:
            await message.answer(
                _mini_app_group_text(url),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        await message.answer(
            _mini_app_private_text(url),
            reply_markup=main_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        "🌐 <b>Mini App почти готов</b>\n\n"
        "Фронт уже лежит в папке <code>miniapp/</code>.\n\n"
        "<b>Что осталось</b>\n"
        "— собрать фронт;\n"
        "— выложить на HTTPS-хостинг;\n"
        "— добавить ссылку в <code>.env</code>:\n"
        "<code>MINI_APP_URL=https://...</code>\n"
        "— перезапустить бота.\n\n"
        "После этого кнопка <b>🌐 Mini App</b> появится в нижнем меню личного чата.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
