from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from app.config import get_settings

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    settings = get_settings()

    commands = [
        BotCommand(command="start", description="Запустить AI-менеджера"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="help", description="Как пользоваться ботом"),
        BotCommand(command="demo_start", description="5 быстрых примеров"),
        BotCommand(command="demo", description="Демо возможностей"),
        BotCommand(command="miniapp", description="Открыть Mini App"),
        BotCommand(command="privacy", description="Приватность и данные"),
        BotCommand(command="my_data", description="Мои данные"),
        BotCommand(command="forget_me", description="Удалить личные данные"),
        BotCommand(command="profile", description="Профиль, тариф и лимиты"),
        BotCommand(command="projects", description="Проекты и рабочая память"),
        BotCommand(command="grouphelp", description="Как использовать в группе"),
        BotCommand(command="group_on", description="Включить память группы"),
        BotCommand(command="group_off", description="Выключить память группы"),
        BotCommand(command="group_status", description="Статус групповой памяти"),
        BotCommand(command="group_clear", description="Очистить память группы"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="admin_health", description="Диагностика ядра"),
        BotCommand(command="admin_security", description="Отчёт безопасности"),
        BotCommand(command="admin_abuse", description="Abuse Control"),
        BotCommand(command="admin_backup", description="Статус backup"),
        BotCommand(command="admin_backup_now", description="Создать backup"),
        BotCommand(command="admin_backups", description="Список backup"),
        BotCommand(command="stats", description="Статистика продукта"),
        BotCommand(command="feedback", description="Оценки ответов"),
        BotCommand(command="payments", description="Платежи Stars"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Bot commands configured: %s", ", ".join(f"/{item.command}" for item in commands))

    mini_app_url = settings.mini_app_url.strip()

    if mini_app_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Mini App",
                web_app=WebAppInfo(url=mini_app_url),
            )
        )
        logger.info("Telegram menu button configured as Mini App: %s", mini_app_url)
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Telegram menu button configured as commands because MINI_APP_URL is empty")
