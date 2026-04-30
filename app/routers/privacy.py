from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.privacy import (
    forget_result_text,
    forget_user_data,
    forget_warning_text,
    load_user_data_snapshot,
    my_data_text,
    privacy_policy_text,
)
from app.storage.db import connect_db

router = Router()


@router.message(Command("privacy"))
async def privacy_handler(message: Message) -> None:
    await message.answer(
        privacy_policy_text(),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("my_data"))
async def my_data_handler(message: Message) -> None:
    if message.from_user is None:
        await message.answer(
            "⚠️ Не удалось определить пользователя.",
            reply_markup=main_keyboard(),
        )
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        snapshot = await load_user_data_snapshot(
            db,
            telegram_id=message.from_user.id,
            settings=settings,
        )

    if snapshot is None:
        await message.answer(
            "📦 <b>Данных пока нет</b>\n\n"
            "Нажми <code>/start</code>, чтобы создать профиль.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        my_data_text(snapshot),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("forget_me"))
async def forget_me_handler(message: Message) -> None:
    if message.from_user is None:
        await message.answer(
            "⚠️ Не удалось определить пользователя.",
            reply_markup=main_keyboard(),
        )
        return

    settings = get_settings()

    if settings.is_admin(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    ):
        await message.answer(
            "🛡 <b>Удаление админ-профиля заблокировано</b>\n\n"
            "Админские аккаунты не удаляются этой командой, чтобы случайно не потерять доступ к управлению ботом.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    async with await connect_db(settings.database_path) as db:
        snapshot = await load_user_data_snapshot(
            db,
            telegram_id=message.from_user.id,
            settings=settings,
        )

    if snapshot is None:
        await message.answer(
            "📦 <b>Данных для удаления нет</b>\n\n"
            "Профиль не найден.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        forget_warning_text(snapshot),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("forget_confirm"))
async def forget_confirm_handler(message: Message) -> None:
    if message.from_user is None:
        await message.answer(
            "⚠️ Не удалось определить пользователя.",
            reply_markup=main_keyboard(),
        )
        return

    settings = get_settings()

    if settings.is_admin(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    ):
        await message.answer(
            "🛡 <b>Удаление админ-профиля заблокировано</b>\n\n"
            "Если реально нужно очистить админские данные, сделай backup и удаляй вручную через базу.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    async with await connect_db(settings.database_path) as db:
        result = await forget_user_data(
            db,
            telegram_id=message.from_user.id,
            settings=settings,
        )

    if result is None:
        await message.answer(
            "📦 <b>Данных для удаления нет</b>\n\n"
            "Профиль не найден.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        forget_result_text(result),
        reply_markup=main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
