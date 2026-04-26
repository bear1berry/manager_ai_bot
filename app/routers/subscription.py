from __future__ import annotations

import json
import logging

from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from app.bot.keyboards import main_keyboard, subscription_keyboard
from app.config import get_settings
from app.services.limits import get_plan_limits, plan_display_name
from app.services.payments import build_stars_plan, calculate_expiry
from app.services.users import ensure_user
from app.storage.db import connect_db
from app.storage.repositories import PaymentRepository, UserRepository

logger = logging.getLogger(__name__)
router = Router()


def _tariff_card(settings) -> str:
    free = get_plan_limits(settings, "free")
    pro = get_plan_limits(settings, "pro")
    business = get_plan_limits(settings, "business")

    return (
        "💎 <b>Подписка через Telegram Stars</b>\n\n"
        "Оплата проходит внутри Telegram. После успешной оплаты тариф активируется автоматически на 30 дней.\n\n"
        "🆓 <b>Free</b>\n"
        f"— текст: <code>{free.text_limit}/день</code>;\n"
        f"— голосовые: <code>{free.voice_limit}/день</code>;\n"
        "— базовый ассистент;\n"
        "— проекты и документы в MVP-режиме.\n\n"
        "💎 <b>Pro — 299 ⭐ / 30 дней</b>\n"
        f"— текст: <code>{pro.text_limit}/день</code>;\n"
        f"— голосовые: <code>{pro.voice_limit}/день</code>;\n"
        "— DOCX/PDF документы;\n"
        "— больше проектной работы;\n"
        "— комфортный ежедневный режим.\n\n"
        "🏢 <b>Business — 999 ⭐ / 30 дней</b>\n"
        f"— текст: <code>{business.text_limit}/день</code>;\n"
        f"— голосовые: <code>{business.voice_limit}/день</code>;\n"
        "— максимальные лимиты MVP;\n"
        "— будущие бизнес-шаблоны;\n"
        "— база под командное использование.\n\n"
        "Выбери тариф в нижнем меню."
    )


@router.message(lambda message: message.text == "💎 Подписка")
async def subscription_handler(message: Message) -> None:
    settings = get_settings()

    await message.answer(
        _tariff_card(settings),
        reply_markup=subscription_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text in {"💎 Pro", "🏢 Business"})
async def plan_request_handler(message: Message, bot: Bot) -> None:
    settings = get_settings()

    selected_plan = "pro" if message.text == "💎 Pro" else "business"
    stars_plan = build_stars_plan(selected_plan)

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        payment_repo = PaymentRepository(db)

        user_id = await ensure_user(user_repo, message.from_user)

        await payment_repo.create_payment(
            user_id=user_id,
            plan=stars_plan.plan,
            stars_amount=stars_plan.stars_amount,
            payload=stars_plan.payload,
        )

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Менеджер ИИ {stars_plan.title}",
        description=f"Подписка {stars_plan.title} на {stars_plan.days} дней.",
        payload=stars_plan.payload,
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label=f"{stars_plan.title} на {stars_plan.days} дней",
                amount=stars_plan.stars_amount,
            )
        ],
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery) -> None:
    settings = get_settings()
    payload = pre_checkout_query.invoice_payload

    async with await connect_db(settings.database_path) as db:
        payment = await PaymentRepository(db).get_by_payload(payload)

    if payment is None:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Платёж не найден. Попробуй создать счёт заново.",
        )
        return

    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    settings = get_settings()
    successful_payment = message.successful_payment
    payload = successful_payment.invoice_payload

    raw_payload = json.dumps(
        successful_payment.model_dump(mode="json"),
        ensure_ascii=False,
    )

    async with await connect_db(settings.database_path) as db:
        payment_repo = PaymentRepository(db)
        user_repo = UserRepository(db)

        payment = await payment_repo.mark_paid(
            payload=payload,
            telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
            provider_payment_charge_id=successful_payment.provider_payment_charge_id,
            raw_payload=raw_payload,
        )

        if payment is None:
            logger.error("Successful payment without local payment row: %s", payload)
            await message.answer(
                "⚠️ <b>Оплата получена, но запись не найдена</b>\n\n"
                "Напиши администратору. Платёж не потерян: Telegram сохранил charge id.",
                reply_markup=main_keyboard(),
                parse_mode="HTML",
            )
            return

        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user is None:
            await message.answer(
                "⚠️ <b>Пользователь не найден</b>\n\n"
                "Нажми /start и напиши администратору.",
                reply_markup=main_keyboard(),
                parse_mode="HTML",
            )
            return

        plan = str(payment["plan"])
        expires_at = calculate_expiry()

        await user_repo.set_plan(
            telegram_id=message.from_user.id,
            plan=plan,
            plan_expires_at=expires_at,
        )

    await message.answer(
        "✅ <b>Оплата прошла успешно</b>\n\n"
        f"Тариф: <b>{plan_display_name(plan)}</b>\n"
        f"Срок: <code>30 дней</code>\n"
        f"Действует до: <code>{expires_at}</code>\n\n"
        "Теперь можно пользоваться расширенными возможностями.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@router.message(lambda message: message.text and message.text.startswith("/setplan "))
async def admin_set_plan_handler(message: Message) -> None:
    settings = get_settings()

    if not settings.is_admin(telegram_id=message.from_user.id, username=message.from_user.username):
        await message.answer("⛔ <b>Команда доступна только администратору.</b>", parse_mode="HTML")
        return

    parts = message.text.split()
    if len(parts) not in {3, 4}:
        await message.answer(
            "Формат:\n"
            "<code>/setplan telegram_id free</code>\n"
            "<code>/setplan telegram_id pro 30</code>\n"
            "<code>/setplan telegram_id business 30</code>\n"
            "<code>/setplan telegram_id admin</code>",
            parse_mode="HTML",
        )
        return

    telegram_id_raw = parts[1]
    plan = parts[2].lower()
    days_raw = parts[3] if len(parts) == 4 else None

    if not telegram_id_raw.isdigit() or plan not in {"free", "pro", "business", "admin"}:
        await message.answer(
            "Формат:\n<code>/setplan telegram_id free|pro|business|admin [days]</code>",
            parse_mode="HTML",
        )
        return

    plan_expires_at = None

    if plan in {"pro", "business"}:
        days = 30
        if days_raw is not None:
            if not days_raw.isdigit():
                await message.answer("Количество дней должно быть числом.", parse_mode="HTML")
                return
            days = int(days_raw)

        plan_expires_at = calculate_expiry(days)

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(int(telegram_id_raw))

        if user is None:
            await message.answer(
                "⚠️ <b>Пользователь не найден</b>\n\n"
                "Он должен хотя бы один раз нажать <code>/start</code> в боте.",
                parse_mode="HTML",
            )
            return

        await user_repo.set_plan(
            telegram_id=int(telegram_id_raw),
            plan=plan,
            plan_expires_at=plan_expires_at,
        )

    await message.answer(
        f"✅ Тариф пользователя <code>{telegram_id_raw}</code> изменён на <b>{plan_display_name(plan)}</b>.\n"
        f"Действует до: <code>{plan_expires_at or '—'}</code>",
        parse_mode="HTML",
    )
