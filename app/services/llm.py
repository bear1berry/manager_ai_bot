from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.utils.text import make_system_prompt

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(
        self,
        user_text: str,
        history: list[dict[str, str]] | None = None,
        mode: str = "assistant",
    ) -> str:
        if not self.settings.llm_api_key:
            return self._fallback_answer(user_text)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": make_system_prompt()},
        ]

        if history:
            messages.extend(history[-12:])

        messages.append(
            {
                "role": "user",
                "content": self._build_user_prompt(user_text=user_text, mode=mode),
            }
        )

        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"

        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1800,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("LLM request failed")
            return (
                "⚠️ **ИИ-сервис временно не ответил**\n\n"
                "Я не потерял задачу, но внешний API сейчас дал сбой.\n\n"
                "Что можно сделать:\n"
                "1. Повторить запрос чуть позже.\n"
                "2. Сократить вводные.\n"
                "3. Проверить `LLM_API_KEY` и `LLM_BASE_URL` в `.env`."
            )

    @staticmethod
    def _build_user_prompt(user_text: str, mode: str) -> str:
        mode_prompts = {
            "client_reply": "Сделай профессиональный ответ клиенту по вводным ниже.",
            "chaos": "Разбери хаотичные вводные в задачи, риски и следующий шаг.",
            "plan": "Сделай рабочий план действий по вводным ниже.",
            "commercial_offer": "Сделай структуру коммерческого предложения по вводным ниже.",
            "meeting_summary": "Сделай резюме встречи: итоги, договорённости, задачи, риски.",
            "checklist": "Сделай практичный чек-лист по вводным ниже.",
            "assistant": "Ответь как деловой ассистент.",
        }

        return f"{mode_prompts.get(mode, mode_prompts['assistant'])}\n\nВводные:\n{user_text}"

    @staticmethod
    def _fallback_answer(user_text: str) -> str:
        return (
            "🧠 **Менеджер ИИ готов к работе**\n\n"
            "Сейчас LLM API не подключён, поэтому я работаю в демо-режиме.\n\n"
            "**Что я понял из задачи:**\n"
            f"{user_text[:800]}\n\n"
            "**Чтобы включить полноценный интеллект:**\n"
            "1. Добавь `LLM_API_KEY` в `.env`.\n"
            "2. Проверь `LLM_BASE_URL`.\n"
            "3. Перезапусти бота."
        )
