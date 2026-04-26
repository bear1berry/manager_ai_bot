from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить Менеджер ИИ"),
            BotCommand(command="help", description="Как пользоваться ботом"),
            BotCommand(command="profile", description="Профиль и лимиты"),
            BotCommand(command="projects", description="Проекты"),
        ]
    )
