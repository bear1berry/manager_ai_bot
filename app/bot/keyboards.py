from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧠 Режимы"),
                KeyboardButton(text="👤 Профиль"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши задачу или выбери раздел",
    )


def modes_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🌍 Универсальный"),
                KeyboardButton(text="✍️ Ответ клиенту"),
            ],
            [
                KeyboardButton(text="🧾 Разобрать хаос"),
                KeyboardButton(text="📌 Сделать план"),
            ],
            [
                KeyboardButton(text="🧩 Продукт"),
                KeyboardButton(text="🔥 Стратег"),
            ],
            [
                KeyboardButton(text="🗂 Проекты"),
                KeyboardButton(text="📄 Документы"),
            ],
            [
                KeyboardButton(text="🚀 Демо"),
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери режим или напиши задачу",
    )


def assistant_keyboard() -> ReplyKeyboardMarkup:
    """
    Обратная совместимость: старые импорты не ломаем.
    Фактически теперь это клавиатура раздела «Режимы».
    """
    return modes_keyboard()


def profile_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Лимиты"),
                KeyboardButton(text="📈 Активность"),
            ],
            [
                KeyboardButton(text="💎 Подписка"),
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Профиль, лимиты и подписка",
    )


def feedback_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👍 Полезно"),
                KeyboardButton(text="👎 Не то"),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Оцени последний ответ",
    )


def demo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧾 Демо: хаос"),
                KeyboardButton(text="🗂 Демо: проект"),
            ],
            [
                KeyboardButton(text="📄 Демо: документ"),
                KeyboardButton(text="✅ Демо: что дальше"),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери демо-сценарий",
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
        input_field_placeholder="Выбери тип документа",
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
                KeyboardButton(text="📝 Заметка в проект"),
            ],
            [
                KeyboardButton(text="🧠 Контекст проектов"),
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Добавь проект, найди проект или обнови память",
    )


def subscription_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💎 Pro"),
                KeyboardButton(text="🏢 Business"),
            ],
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="⬅️ Назад"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери тариф",
    )
