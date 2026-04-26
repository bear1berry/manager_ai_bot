from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings

router = Router()


@router.message(Command("miniapp"))
@router.message(F.text == "🌐 Mini App")
async def mini_app_handler(message: Message) -> None:
    settings = get_settings()

    if settings.mini_app_url.strip():
        await message.answer(
            "🌐 <b>Mini App</b>\n\n"
            "Открой кабинет через кнопку <b>🌐 Mini App</b> в нижнем меню.\n\n"
            "<b>Что там будет</b>\n"
            "— обзор тарифа и лимитов;\n"
            "— быстрый доступ к проектам;\n"
            "— документы;\n"
            "— подписка через Stars;\n"
            "— демо-сценарии.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
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
        "После этого кнопка <b>🌐 Mini App</b> в нижнем меню будет открывать кабинет.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
