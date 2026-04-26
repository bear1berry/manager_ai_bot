from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧠 Ассистент"),
                KeyboardButton(text="🗂 Проекты"),
            ],
            [
                KeyboardButton(text="📄 Документы"),
                KeyboardButton(text="👤 Профиль"),
            ],
            [
                KeyboardButton(text="💎 Подписка"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши задачу, скинь голосовое или выбери раздел",
    )


def assistant_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✍️ Ответ клиенту"),
                KeyboardButton(text="🧾 Разобрать хаос"),
            ],
            [
                KeyboardButton(text="📌 Сделать план"),
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
    )


def documents_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧾 КП"),
                KeyboardButton(text="📋 План работ"),
            ],
            [
                KeyboardButton(text="📝 Резюме встречи"),
                KeyboardButton(text="✅ Чек-лист"),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
    )


def projects_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Новый проект"),
                KeyboardButton(text="📚 Мои проекты"),
            ],
            [
                KeyboardButton(text="🔎 Найти проект"),
                KeyboardButton(text="🧠 Контекст проектов"),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Добавь проект, найди проект или вернись назад",
    )


def subscription_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💎 Pro"),
                KeyboardButton(text="🏢 Business"),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
    )
