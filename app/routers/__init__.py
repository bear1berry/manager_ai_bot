from __future__ import annotations

from aiogram import Router

from app.routers import (
    admin,
    assistant,
    demo,
    documents,
    feedback,
    group_assistant,
    miniapp,
    privacy,
    profile,
    projects,
    start,
    subscription,
)


def setup_routers() -> Router:
    router = Router()

    router.include_router(start.router)
    router.include_router(admin.router)
    router.include_router(profile.router)
    router.include_router(subscription.router)
    router.include_router(projects.router)
    router.include_router(documents.router)
    router.include_router(demo.router)
    router.include_router(miniapp.router)
    router.include_router(privacy.router)
    router.include_router(feedback.router)

    # Важно: групповой роутер должен быть до assistant.router,
    # чтобы бот не отвечал на каждое сообщение в группе.
    router.include_router(group_assistant.router)
    router.include_router(assistant.router)

    return router
