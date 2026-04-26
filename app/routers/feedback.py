from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.keyboards import main_keyboard
from app.config import get_settings
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import FeedbackRepository, MessageRepository, UserRepository

router = Router()


class FeedbackStates(StatesGroup):
    waiting_negative_comment = State()


@router.message(F.text == "👍 Полезно")
async def positive_feedback_handler(message: Message, state: FSMContext) -> None:
    await state.clear()

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        message_repo = MessageRepository(db)
        feedback_repo = FeedbackRepository(db)

        user_id = await ensure_user(user_repo, message.from_user)
        latest_message = await message_repo.latest_assistant_message(user_id)
        latest_message_id = int(latest_message["id"]) if latest_message else None

        await feedback_repo.upsert_feedback(
            user_id=user_id,
            message_id=latest_message_id,
            rating="positive",
            comment=None,
        )

    await message.answer(
        "👍 <b>Принял оценку</b>\n\n"
        "Это помогает понимать, какие ответы реально полезны.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "👎 Не то")
async def negative_feedback_handler(message: Message, state: FSMContext) -> None:
    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        message_repo = MessageRepository(db)
        feedback_repo = FeedbackRepository(db)

        user_id = await ensure_user(user_repo, message.from_user)
        latest_message = await message_repo.latest_assistant_message(user_id)
        latest_message_id = int(latest_message["id"]) if latest_message else None

        feedback_id = await feedback_repo.upsert_feedback(
            user_id=user_id,
            message_id=latest_message_id,
            rating="negative",
            comment=None,
        )

    await state.set_state(FeedbackStates.waiting_negative_comment)
    await state.update_data(feedback_id=feedback_id)

    await message.answer(
        "👎 <b>Принял: ответ не попал</b>\n\n"
        "Напиши коротко, что было не так:\n"
        "— не тот тон;\n"
        "— мало конкретики;\n"
        "— слишком длинно;\n"
        "— не понял задачу;\n"
        "— другое.\n\n"
        "Можно одним сообщением. Если не хочешь — нажми ⬅️ Назад.",
        parse_mode="HTML",
    )


@router.message(FeedbackStates.waiting_negative_comment, F.text == "⬅️ Назад")
async def skip_negative_comment_handler(message: Message, state: FSMContext) -> None:
    await state.clear()

    await message.answer(
        "Ок, комментарий пропустили. Возвращаю главное меню.",
        reply_markup=main_keyboard(),
    )


@router.message(FeedbackStates.waiting_negative_comment, F.text)
async def save_negative_comment_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    feedback_id = int(data.get("feedback_id") or 0)

    if feedback_id <= 0:
        await state.clear()
        await message.answer(
            "Не нашёл запись обратной связи. Возвращаю главное меню.",
            reply_markup=main_keyboard(),
        )
        return

    settings = get_settings()

    async with await connect_db(settings.database_path) as db:
        await FeedbackRepository(db).add_comment(feedback_id=feedback_id, comment=message.text)

    await state.clear()

    await message.answer(
        "✅ <b>Комментарий сохранён</b>\n\n"
        "Это пойдёт в улучшение качества ответов.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
