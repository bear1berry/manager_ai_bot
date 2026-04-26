from __future__ import annotations

from aiogram import Router

from app.routers import admin, assistant, documents, feedback, profile, projects, start, subscription


def setup_routers() -> Router:
    router = Router()

    router.include_router(start.router)
    router.include_router(admin.router)
    router.include_router(profile.router)
    router.include_router(subscription.router)
    router.include_router(projects.router)
    router.include_router(documents.router)
    router.include_router(feedback.router)
    router.include_router(assistant.router)

    return router
