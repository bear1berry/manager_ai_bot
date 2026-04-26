from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Запустить Менеджер ИИ"),
        BotCommand(command="menu", description="Открыть главное меню"),
        BotCommand(command="help", description="Как пользоваться ботом"),
        BotCommand(command="demo", description="Быстрое демо возможностей"),
        BotCommand(command="miniapp", description="Открыть Mini App"),
        BotCommand(command="profile", description="Профиль, тариф и лимиты"),
        BotCommand(command="projects", description="Проекты и рабочая память"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="stats", description="Статистика продукта"),
        BotCommand(command="feedback", description="Оценки ответов"),
        BotCommand(command="payments", description="Платежи Stars"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Bot commands configured: %s", ", ".join(f"/{item.command}" for item in commands))
