from __future__ import annotations

import json
import logging
import re
from typing import Any

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

        try:
            return await self._request_text(messages=messages, max_tokens=1800, temperature=0.35)
        except Exception:
            logger.exception("LLM request failed")
            return (
                "⚠️ **ИИ-сервис временно не ответил**\n\n"
                "**Что случилось**\n"
                "Внешний API не вернул ответ.\n\n"
                "**Что делать**\n"
                "— повтори запрос чуть позже;\n"
                "— сократи вводные;\n"
                "— проверь `LLM_API_KEY` и `LLM_BASE_URL` в `.env`."
            )

    async def generate_document_data(
        self,
        source_text: str,
        doc_type: str,
        title: str,
    ) -> dict[str, Any]:
        source_text = source_text.strip()
        if not source_text:
            source_text = "Вводные не указаны."

        if not self.settings.llm_api_key:
            return self._fallback_document_data(title=title, source_text=source_text, doc_type=doc_type)

        system_prompt = """
Ты — «Менеджер ИИ», деловой ассистент, который готовит аккуратные документы для малого бизнеса и самозанятых.

Твоя задача:
- из вводных пользователя собрать готовый деловой документ;
- писать на русском языке;
- делать текст практичным, ясным, без воды;
- не использовать markdown;
- не использовать HTML;
- не придумывать юридические гарантии;
- если данных не хватает — делай разумные допущения и явно отмечай их;
- структура должна быть пригодна для DOCX/PDF.

Верни строго JSON без пояснений, без ```json и без markdown.

Формат JSON:
{
  "title": "Название документа",
  "meta": ["Короткая строка 1", "Короткая строка 2"],
  "sections": [
    {
      "heading": "Заголовок раздела",
      "paragraphs": ["Абзац 1", "Абзац 2"],
      "bullets": ["Пункт 1", "Пункт 2"]
    }
  ]
}
""".strip()

        user_prompt = f"""
Тип документа: {self._human_doc_type(doc_type)}
Рабочее название: {title}

Вводные пользователя:
{source_text}

Собери полноценный документ.

Требования к содержанию:
- 5–8 разделов;
- каждый раздел должен быть полезным;
- если это КП — добавь цель, задачу клиента, решение, этапы, сроки, стоимость/условия, результат, следующий шаг;
- если это план работ — добавь цель, этапы, контрольные точки, риски, сроки, критерии готовности;
- если это резюме встречи — добавь краткий итог, договорённости, задачи, ответственных, риски, следующий шаг;
- если это чек-лист — добавь блоки проверки, действия, контроль качества, финальную проверку.

Верни только валидный JSON.
""".strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = await self._request_text(messages=messages, max_tokens=2600, temperature=0.25)
            data = self._parse_json_object(raw)
            normalized = self._normalize_document_data(data=data, fallback_title=title)

            if not normalized["sections"]:
                raise ValueError("LLM document has empty sections")

            return normalized
        except Exception:
            logger.exception("LLM document generation failed")
            return self._fallback_document_data(title=title, source_text=source_text, doc_type=doc_type)

    async def _request_text(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"

        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _build_user_prompt(user_text: str, mode: str) -> str:
        mode_prompts = {
            "client_reply": (
                "Сделай профессиональный ответ клиенту.\n\n"
                "Структура ответа:\n"
                "**Готовый ответ клиенту**\n"
                "— текст, который можно отправить;\n\n"
                "**Почему так**\n"
                "— короткая логика;\n\n"
                "**Следующий шаг**\n"
                "— что сделать дальше."
            ),
            "chaos": (
                "Разбери хаотичные вводные.\n\n"
                "Структура ответа:\n"
                "**Суть**\n"
                "**Что важно**\n"
                "**Риски**\n"
                "**План действий**\n"
                "**Следующий шаг**"
            ),
            "plan": (
                "Сделай рабочий план действий.\n\n"
                "Структура ответа:\n"
                "**Цель**\n"
                "**План по шагам**\n"
                "**Контрольные точки**\n"
                "**Риски**\n"
                "**Что сделать первым**"
            ),
            "commercial_offer": (
                "Сделай структуру коммерческого предложения.\n\n"
                "Структура ответа:\n"
                "**Задача клиента**\n"
                "**Решение**\n"
                "**Этапы работ**\n"
                "**Сроки и условия**\n"
                "**Следующий шаг**"
            ),
            "meeting_summary": (
                "Сделай резюме встречи.\n\n"
                "Структура ответа:\n"
                "**Краткий итог**\n"
                "**Договорённости**\n"
                "**Задачи**\n"
                "**Риски**\n"
                "**Следующий шаг**"
            ),
            "checklist": (
                "Сделай практичный чек-лист.\n\n"
                "Структура ответа:\n"
                "**Перед стартом**\n"
                "**Основные действия**\n"
                "**Контроль качества**\n"
                "**Финальная проверка**"
            ),
            "assistant": (
                "Ответь как деловой ассистент.\n\n"
                "Сделай ответ структурным: заголовки, короткие абзацы, списки через тире, без воды."
            ),
        }

        return f"{mode_prompts.get(mode, mode_prompts['assistant'])}\n\nВводные:\n{user_text}"

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        cleaned = raw.strip()

        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")

        return parsed

    @staticmethod
    def _normalize_document_data(data: dict[str, Any], fallback_title: str) -> dict[str, Any]:
        title = str(data.get("title") or fallback_title).strip() or fallback_title

        raw_meta = data.get("meta") or []
        meta = [str(item).strip() for item in raw_meta if str(item).strip()]
        meta = meta[:8]

        raw_sections = data.get("sections") or []
        sections: list[dict[str, Any]] = []

        if isinstance(raw_sections, list):
            for section in raw_sections:
                if not isinstance(section, dict):
                    continue

                heading = str(section.get("heading") or "Раздел").strip() or "Раздел"

                raw_paragraphs = section.get("paragraphs") or []
                raw_bullets = section.get("bullets") or []

                paragraphs = [str(item).strip() for item in raw_paragraphs if str(item).strip()]
                bullets = [str(item).strip() for item in raw_bullets if str(item).strip()]

                if not paragraphs and not bullets:
                    continue

                sections.append(
                    {
                        "heading": heading[:120],
                        "paragraphs": paragraphs[:8],
                        "bullets": bullets[:16],
                    }
                )

        return {
            "title": title[:140],
            "meta": meta,
            "sections": sections[:10],
        }

    @staticmethod
    def _human_doc_type(doc_type: str) -> str:
        mapping = {
            "commercial_offer": "Коммерческое предложение",
            "work_plan": "План работ",
            "meeting_summary": "Резюме встречи",
            "checklist": "Чек-лист",
        }
        return mapping.get(doc_type, "Документ")

    @staticmethod
    def _fallback_answer(user_text: str) -> str:
        return (
            "🧠 **Менеджер ИИ готов к работе**\n\n"
            "**Сейчас**\n"
            "LLM API не подключён, поэтому я работаю в демо-режиме.\n\n"
            "**Что я понял**\n"
            f"— {user_text[:800]}\n\n"
            "**Как включить полноценный интеллект**\n"
            "— добавь `LLM_API_KEY` в `.env`;\n"
            "— проверь `LLM_BASE_URL`;\n"
            "— перезапусти бота."
        )

    @staticmethod
    def _fallback_document_data(title: str, source_text: str, doc_type: str) -> dict[str, Any]:
        source_text = source_text.strip() or "Вводные не указаны."

        if doc_type == "commercial_offer":
            return {
                "title": title,
                "meta": [
                    "Документ создан в демо-режиме без LLM.",
                    "После подключения LLM_API_KEY содержание станет глубже и точнее.",
                ],
                "sections": [
                    {
                        "heading": "Цель предложения",
                        "paragraphs": [
                            "Подготовить понятное коммерческое предложение на основе вводных клиента.",
                            "Документ фиксирует задачу, предполагаемое решение, этапы работ и следующий шаг.",
                        ],
                        "bullets": [],
                    },
                    {
                        "heading": "Вводные",
                        "paragraphs": [source_text],
                        "bullets": [],
                    },
                    {
                        "heading": "Предлагаемое решение",
                        "paragraphs": [
                            "На основе вводных предлагается выполнить работу поэтапно: уточнение задачи, подготовка материалов, выполнение, проверка результата и финальная передача.",
                        ],
                        "bullets": [
                            "Уточнить цель и критерии результата.",
                            "Согласовать объём работ и сроки.",
                            "Зафиксировать стоимость и порядок оплаты.",
                            "Передать результат в согласованном формате.",
                        ],
                    },
                    {
                        "heading": "Следующий шаг",
                        "paragraphs": [
                            "Согласовать условия, подтвердить старт работ и зафиксировать договорённости в переписке или отдельном документе.",
                        ],
                        "bullets": [],
                    },
                ],
            }

        if doc_type == "work_plan":
            return {
                "title": title,
                "meta": ["Документ создан в демо-режиме без LLM."],
                "sections": [
                    {
                        "heading": "Цель",
                        "paragraphs": ["Собрать рабочий план действий по вводным пользователя."],
                        "bullets": [],
                    },
                    {
                        "heading": "Вводные",
                        "paragraphs": [source_text],
                        "bullets": [],
                    },
                    {
                        "heading": "Этапы работ",
                        "paragraphs": [],
                        "bullets": [
                            "Уточнить задачу и ожидаемый результат.",
                            "Разбить работу на этапы.",
                            "Определить сроки и контрольные точки.",
                            "Выполнить работу.",
                            "Проверить результат и закрыть задачу.",
                        ],
                    },
                ],
            }

        if doc_type == "meeting_summary":
            return {
                "title": title,
                "meta": ["Документ создан в демо-режиме без LLM."],
                "sections": [
                    {
                        "heading": "Краткое резюме",
                        "paragraphs": [source_text],
                        "bullets": [],
                    },
                    {
                        "heading": "Договорённости",
                        "paragraphs": [],
                        "bullets": [
                            "Зафиксировать ключевые решения.",
                            "Назначить ответственных.",
                            "Определить сроки.",
                        ],
                    },
                    {
                        "heading": "Следующий шаг",
                        "paragraphs": ["Подтвердить договорённости и перейти к выполнению задач."],
                        "bullets": [],
                    },
                ],
            }

        return {
            "title": title,
            "meta": ["Документ создан в демо-режиме без LLM."],
            "sections": [
                {
                    "heading": "Вводные",
                    "paragraphs": [source_text],
                    "bullets": [],
                },
                {
                    "heading": "Чек-лист действий",
                    "paragraphs": [],
                    "bullets": [
                        "Проверить вводные.",
                        "Уточнить недостающие данные.",
                        "Выполнить основные действия.",
                        "Проверить качество результата.",
                        "Зафиксировать финальный статус.",
                    ],
                },
            ],
        }
