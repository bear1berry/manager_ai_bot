from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from app.config import Settings
from app.services.limits import get_plan_limits, plan_display_name
from app.services.miniapp_auth import extract_user_from_init_data, verify_telegram_init_data
from app.services.payments import format_plan_expiry
from app.storage.db import connect_db
from app.storage.repositories import UserRepository

logger = logging.getLogger(__name__)


def _cors_headers(settings: Settings) -> dict[str, str]:
    origins = [item.strip().rstrip("/") for item in settings.mini_app_cors_origins.split(",") if item.strip()]
    allow_origin = "*"

    if settings.mini_app_url.strip():
        allow_origin = settings.mini_app_url.strip().rstrip("/")
    elif origins:
        allow_origin = origins[0]

    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Telegram-Init-Data",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Max-Age": "86400",
    }


def _json_response(data: dict[str, Any], settings: Settings, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, headers=_cors_headers(settings))


async def options_handler(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    return web.Response(status=204, headers=_cors_headers(settings))


async def health_handler(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    return _json_response(
        {
            "ok": True,
            "service": "manager-ai-miniapp-api",
            "env": settings.env,
        },
        settings=settings,
    )


def _get_init_data(request: web.Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("tma "):
        return auth.removeprefix("tma ").strip()

    header_value = request.headers.get("X-Telegram-Init-Data", "")
    if header_value:
        return header_value.strip()

    return request.query.get("initData", "").strip()


async def miniapp_me_handler(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    init_data = _get_init_data(request)

    if not settings.mini_app_auth_required and not init_data:
        return _json_response(_demo_payload(), settings=settings)

    if not verify_telegram_init_data(init_data=init_data, bot_token=settings.bot_token):
        return _json_response(
            {
                "ok": False,
                "error": "invalid_init_data",
                "message": "Не удалось подтвердить Telegram Mini App initData.",
            },
            settings=settings,
            status=401,
        )

    tg_user = extract_user_from_init_data(init_data)
    if tg_user is None:
        return _json_response(
            {
                "ok": False,
                "error": "user_not_found_in_init_data",
                "message": "В initData нет пользователя.",
            },
            settings=settings,
            status=400,
        )

    async with await connect_db(settings.database_path) as db:
        user_repo = UserRepository(db)
        user = await user_repo.upsert_user(
            telegram_id=tg_user.telegram_id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )

        user_id = int(user["id"])
        plan = str(user["plan"] or "free")
        limits = get_plan_limits(settings=settings, plan=plan)

        text_used = await _count_today(db, user_id=user_id, kind="text")
        voice_used = await _count_today(db, user_id=user_id, kind="voice")

        projects_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM projects WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        messages_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM messages WHERE user_id = ?",
            (user_id,),
        )
        documents_generated = await _count_scalar(
            db,
            """
            SELECT COUNT(*)
            FROM messages
            WHERE user_id = ?
              AND role = 'assistant'
              AND (
                    content LIKE '%DOCX%'
                 OR content LIKE '%PDF%'
                 OR content LIKE '%Документ%'
              )
            """,
            (user_id,),
        )
        feedback_total = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM feedback WHERE user_id = ?",
            (user_id,),
        )
        payments_paid = await _count_scalar(
            db,
            "SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'paid'",
            (user_id,),
        )
        stars_paid = await _count_scalar(
            db,
            "SELECT COALESCE(SUM(stars_amount), 0) FROM payments WHERE user_id = ? AND status = 'paid'",
            (user_id,),
        )

        latest_projects = await _latest_projects(db, user_id=user_id, limit=8)

    payload = {
        "ok": True,
        "user": {
            "telegram_id": tg_user.telegram_id,
            "username": tg_user.username,
            "first_name": tg_user.first_name,
            "last_name": tg_user.last_name,
        },
        "subscription": {
            "plan": plan,
            "plan_name": plan_display_name(plan),
            "expires_at": user["plan_expires_at"],
            "expires_text": format_plan_expiry(user["plan_expires_at"], plan),
        },
        "limits": {
            "text": {
                "used": text_used,
                "limit": limits.text_limit,
                "remaining": max(limits.text_limit - text_used, 0),
            },
            "voice": {
                "used": voice_used,
                "limit": limits.voice_limit,
                "remaining": max(limits.voice_limit - voice_used, 0),
            },
        },
        "stats": {
            "projects_total": projects_total,
            "messages_total": messages_total,
            "documents_generated": documents_generated,
            "feedback_total": feedback_total,
            "payments_paid": payments_paid,
            "stars_paid": stars_paid,
        },
        "projects": latest_projects,
        "latest_projects": latest_projects,
    }

    return _json_response(payload, settings=settings)


async def _count_today(db, user_id: int, kind: str) -> int:
    return await _count_scalar(
        db,
        """
        SELECT COUNT(*)
        FROM usage_events
        WHERE user_id = ?
          AND kind = ?
          AND created_date = DATE('now')
        """,
        (user_id, kind),
    )


async def _count_scalar(db, sql: str, params: tuple[Any, ...] = ()) -> int:
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()

    if row is None:
        return 0

    return int(row[0] or 0)


def _format_project_date(value: str | None) -> str:
    if not value:
        return "—"

    # SQLite CURRENT_TIMESTAMP usually returns YYYY-MM-DD HH:MM:SS.
    try:
        date_part = value.split(" ")[0]
        year, month, day = date_part.split("-")
        return f"{day}.{month}.{year}"
    except Exception:
        return value


def _project_summary(description: str) -> str:
    cleaned = " ".join(description.strip().split())

    if not cleaned:
        return "Описание пока не добавлено. Можно докинуть заметку в проект через бота."

    if len(cleaned) > 220:
        return cleaned[:220].rstrip() + "…"

    return cleaned


def _last_note_preview(description: str) -> str:
    cleaned = description.strip()
    if not cleaned:
        return ""

    marker = "Заметка:"
    if marker in cleaned:
        last_note = cleaned.split(marker)[-1].strip()
        last_note = " ".join(last_note.split())
        if len(last_note) > 160:
            return last_note[:160].rstrip() + "…"
        return last_note

    preview = " ".join(cleaned.split())
    if len(preview) > 160:
        return preview[:160].rstrip() + "…"

    return preview


def _notes_count(description: str) -> int:
    if not description:
        return 0

    return description.count("Заметка:")


async def _latest_projects(db, user_id: int, limit: int) -> list[dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT id, title, description, status, created_at, updated_at
        FROM projects
        WHERE user_id = ?
          AND status = 'active'
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = await cursor.fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        description = str(row["description"] or "")
        result.append(
            {
                "id": int(row["id"]),
                "title": str(row["title"]),
                "description": _project_summary(description),
                "status": str(row["status"]),
                "status_label": "Активен" if str(row["status"]) == "active" else str(row["status"]),
                "notes_count": _notes_count(description),
                "last_note_preview": _last_note_preview(description),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "updated_text": _format_project_date(row["updated_at"]),
            }
        )

    return result


def _demo_payload() -> dict[str, Any]:
    projects = [
        {
            "id": 1,
            "title": "Запуск Telegram-бота",
            "description": "Mini App, подписка Stars, документы, проекты, HTTPS API и подготовка к первым пользователям.",
            "status": "active",
            "status_label": "Активен",
            "notes_count": 3,
            "last_note_preview": "Следующий шаг — карточки проектов и история документов.",
            "created_at": "demo",
            "updated_at": "demo",
            "updated_text": "сегодня",
        },
        {
            "id": 2,
            "title": "Клиент Иванова",
            "description": "Бюджет 450 000 ₽, дедлайн 20 мая, нужно подготовить КП и не выйти за бюджет.",
            "status": "active",
            "status_label": "Активен",
            "notes_count": 1,
            "last_note_preview": "Клиент просит показать поэтапный план работ.",
            "created_at": "demo",
            "updated_at": "demo",
            "updated_text": "вчера",
        },
    ]

    return {
        "ok": True,
        "demo": True,
        "user": {
            "telegram_id": 0,
            "username": "demo",
            "first_name": "Demo",
            "last_name": None,
        },
        "subscription": {
            "plan": "free",
            "plan_name": "Free",
            "expires_at": None,
            "expires_text": "—",
        },
        "limits": {
            "text": {
                "used": 3,
                "limit": 20,
                "remaining": 17,
            },
            "voice": {
                "used": 1,
                "limit": 3,
                "remaining": 2,
            },
        },
        "stats": {
            "projects_total": 2,
            "messages_total": 14,
            "documents_generated": 1,
            "feedback_total": 3,
            "payments_paid": 0,
            "stars_paid": 0,
        },
        "projects": projects,
        "latest_projects": projects,
    }


def create_miniapp_api_app(settings: Settings) -> web.Application:
    app = web.Application()
    app["settings"] = settings

    app.router.add_route("OPTIONS", "/api/health", options_handler)
    app.router.add_route("OPTIONS", "/api/miniapp/me", options_handler)

    app.router.add_get("/api/health", health_handler)
    app.router.add_get("/api/miniapp/me", miniapp_me_handler)

    return app


async def start_miniapp_api(settings: Settings) -> web.AppRunner | None:
    if not settings.mini_app_api_enabled:
        logger.info("Mini App API disabled")
        return None

    app = create_miniapp_api_app(settings)
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner=runner,
        host=settings.mini_app_api_host,
        port=settings.mini_app_api_port,
    )
    await site.start()

    logger.info(
        "Mini App API started: http://%s:%s",
        settings.mini_app_api_host,
        settings.mini_app_api_port,
    )

    return runner
