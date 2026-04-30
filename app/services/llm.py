from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings
from app.services.costs import estimate_llm_usage, record_llm_usage
from app.services.model_router import ModelRoute, choose_model_route
from app.storage.db import connect_db
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
        user_id: int | None = None,
        telegram_id: int | None = None,
        chat_id: int | None = None,
        feature: str = "chat",
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

        route = choose_model_route(
            settings=self.settings,
            user_text=user_text,
            mode=mode,
            purpose=feature,
        )

        try:
            answer = await self._request_text(
                messages=messages,
                max_tokens=route.max_tokens,
                temperature=route.temperature,
                model=route.model,
            )
            await self._record_usage_safe(
                messages=messages,
                answer=answer,
                route=route,
                model=route.model,
                user_id=user_id,
                telegram_id=telegram_id,
                chat_id=chat_id,
                feature=feature,
                mode=mode,
                status="ok",
            )
            return answer
        except Exception as first_exc:
            logger.exception("LLM request failed on model=%s", route.model)

            if route.fallback_model and route.fallback_model != route.model:
                try:
                    answer = await self._request_text(
                        messages=messages,
                        max_tokens=route.max_tokens,
                        temperature=route.temperature,
                        model=route.fallback_model,
                    )
                    await self._record_usage_safe(
                        messages=messages,
                        answer=answer,
                        route=route,
                        model=route.fallback_model,
                        user_id=user_id,
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        feature=feature,
                        mode=mode,
                        status="fallback_ok",
                        error=str(first_exc),
                    )
                    return answer
                except Exception as fallback_exc:
                    logger.exception("LLM fallback request failed on model=%s", route.fallback_model)
                    await self._record_usage_safe(
                        messages=messages,
                        answer="",
                        route=route,
                        model=route.fallback_model,
                        user_id=user_id,
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        feature=feature,
                        mode=mode,
                        status="failed",
                        error=str(fallback_exc),
                    )
            else:
                await self._record_usage_safe(
                    messages=messages,
                    answer="",
                    route=route,
                    model=route.model,
                    user_id=user_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    feature=feature,
                    mode=mode,
                    status="failed",
                    error=str(first_exc),
                )

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
        user_id: int | None = None,
        telegram_id: int | None = None,
        chat_id: int | None = None,
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

        route = choose_model_route(
            settings=self.settings,
            user_text=source_text,
            mode=doc_type,
            purpose="document",
        )

        try:
            raw = await self._request_text(
                messages=messages,
                max_tokens=route.max_tokens,
                temperature=route.temperature,
                model=route.model,
            )
            await self._record_usage_safe(
                messages=messages,
                answer=raw,
                route=route,
                model=route.model,
                user_id=user_id,
                telegram_id=telegram_id,
                chat_id=chat_id,
                feature="document",
                mode=doc_type,
                status="ok",
            )

            data = self._parse_json_object(raw)
            normalized = self._normalize_document_data(data=data, fallback_title=title)

            if not normalized["sections"]:
                raise ValueError("LLM document has empty sections")

            return normalized
        except Exception as first_exc:
            logger.exception("LLM document generation failed on model=%s", route.model)

            if route.fallback_model and route.fallback_model != route.model:
                try:
                    raw = await self._request_text(
                        messages=messages,
                        max_tokens=route.max_tokens,
                        temperature=route.temperature,
                        model=route.fallback_model,
                    )
                    await self._record_usage_safe(
                        messages=messages,
                        answer=raw,
                        route=route,
                        model=route.fallback_model,
                        user_id=user_id,
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        feature="document",
                        mode=doc_type,
                        status="fallback_ok",
                        error=str(first_exc),
                    )
                    data = self._parse_json_object(raw)
                    normalized = self._normalize_document_data(data=data, fallback_title=title)
                    if normalized["sections"]:
                        return normalized
                except Exception as fallback_exc:
                    logger.exception("LLM document fallback failed")
                    await self._record_usage_safe(
                        messages=messages,
                        answer="",
                        route=route,
                        model=route.fallback_model,
                        user_id=user_id,
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        feature="document",
                        mode=doc_type,
                        status="failed",
                        error=str(fallback_exc),
                    )

            return self._fallback_document_data(title=title, source_text=source_text, doc_type=doc_type)

    async def _request_text(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> str:
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"

        payload = {
            "model": model,
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

    async def _record_usage_safe(
        self,
        *,
        messages: list[dict[str, str]],
        answer: str,
        route: ModelRoute,
        model: str,
        user_id: int | None,
        telegram_id: int | None,
        chat_id: int | None,
        feature: str,
        mode: str,
        status: str,
        error: str | None = None,
    ) -> None:
        try:
            usage = estimate_llm_usage(
                model=model,
                messages=messages,
                output_text=answer,
            )

            async with await connect_db(self.settings.database_path) as db:
                await record_llm_usage(
                    db,
                    user_id=user_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    feature=feature,
                    mode=mode,
                    provider="openai-compatible",
                    model=model,
                    route_tier=route.tier,
                    route_reason=route.reason,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    estimated_cost_usd=usage.estimated_cost_usd,
                    status=status,
                    error=error,
                )
        except Exception:
            logger.exception("Failed to record LLM usage")

    @staticmethod
    def _build_user_prompt(user_text: str, mode: str) -> str:
        mode_prompts = {
            "client_reply": (
                "Сделай профессиональный ответ клиенту.\n\n"
                "Требования:\n"
                "- текст должен быть готов к отправке;\n"
                "- тон спокойный, уверенный, без оправданий;\n"
                "- без канцелярита и воды;\n"
                "- если есть риск конфликта — снизь напряжение;\n"
                "- если клиент возражает по цене — покажи ценность, а не защищайся.\n\n"
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
                "Требования:\n"
                "- найди главную суть;\n"
                "- отдели факты от эмоций и предположений;\n"
                "- покажи риски;\n"
                "- собери порядок действий;\n"
                "- в конце дай один самый важный следующий шаг.\n\n"
                "Структура ответа:\n"
                "**Суть**\n"
                "**Что важно**\n"
                "**Риски**\n"
                "**План действий**\n"
                "**Следующий шаг**"
            ),
            "plan": (
                "Сделай рабочий план действий.\n\n"
                "Требования:\n"
                "- план должен быть реалистичным;\n"
                "- шаги должны идти по порядку;\n"
                "- добавь контрольные точки;\n"
                "- обозначь риски и как их снизить;\n"
                "- не растягивай ответ без необходимости.\n\n"
                "Структура ответа:\n"
                "**Цель**\n"
                "**План по шагам**\n"
                "**Контрольные точки**\n"
                "**Риски**\n"
                "**Что сделать первым**"
            ),
            "product": (
                "Работай как сильный Product Manager.\n\n"
                "Твоя задача — превратить сырую идею или проблему в продуктовую структуру.\n\n"
                "Всегда думай через:\n"
                "- целевую аудиторию;\n"
                "- боль пользователя;\n"
                "- ценность продукта;\n"
                "- сценарии использования;\n"
                "- MVP;\n"
                "- гипотезы;\n"
                "- метрики;\n"
                "- риски;\n"
                "- следующий эксперимент.\n\n"
                "Не распыляйся. Дай практичный продуктовый разбор.\n\n"
                "Структура ответа:\n"
                "**Суть продукта**\n"
                "**Кому это нужно**\n"
                "**Боль пользователя**\n"
                "**Ценность**\n"
                "**MVP**\n"
                "**Гипотезы для проверки**\n"
                "**Метрики**\n"
                "**Риски**\n"
                "**Следующий шаг**"
            ),
            "strategy": (
                "Работай как стратег: трезво, жёстко, практично, с фокусом на выигрыш.\n\n"
                "Твоя задача — найти сильные ходы, приоритеты и план действий.\n\n"
                "Всегда анализируй:\n"
                "- цель;\n"
                "- текущую позицию;\n"
                "- ресурсы;\n"
                "- ограничения;\n"
                "- рычаги роста;\n"
                "- нестандартные ходы;\n"
                "- риски;\n"
                "- что даст максимальный эффект быстрее всего.\n\n"
                "Не фантазируй без опоры. Если делаешь допущение — пометь его.\n\n"
                "Структура ответа:\n"
                "**Цель**\n"
                "**Текущая позиция**\n"
                "**Главный рычаг**\n"
                "**Сильные ходы**\n"
                "**Что не делать**\n"
                "**Риски**\n"
                "**План удара**\n"
                "**Первое действие**"
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
                "Ты работаешь в режиме «Универсальный».\n\n"
                "Это главный режим продукта. Он должен уверенно закрывать почти любые запросы пользователя: "
                "рабочие, личные, продуктовые, текстовые, стратегические, учебные, аналитические, организационные, "
                "творческие и технические.\n\n"
                "Главная задача:\n"
                "- быстро понять, что пользователь реально хочет получить;\n"
                "- выбрать лучший формат ответа без лишних уточнений;\n"
                "- дать полезный результат, который можно применить сразу;\n"
                "- показать, что бот умеет больше, чем документы и проекты.\n\n"
                "Стиль ответа:\n"
                "- русский язык;\n"
                "- короткие заголовки;\n"
                "- жирное выделение важных смыслов;\n"
                "- списки через тире;\n"
                "- без воды;\n"
                "- уверенно, практично, спокойно;\n"
                "- в конце почти всегда дай блок «Что сделать дальше».\n\n"
                "Базовая структура, если формат не очевиден:\n"
                "**Суть**\n"
                "**Разбор**\n"
                "**Лучшее решение**\n"
                "**Риски**\n"
                "**Что сделать дальше**"
            ),
        }

        prompt = mode_prompts.get(mode, mode_prompts["assistant"])

        quality_note = (
            "\n\nГлобальный стандарт качества:\n"
            "- сначала ответь на реальный запрос пользователя;\n"
            "- не лей воду;\n"
            "- отделяй факты от предположений;\n"
            "- если данных мало — скажи честно;\n"
            "- если есть web-контекст — не выдумывай актуальные факты вне него;\n"
            "- в конце дай практичный следующий шаг, если это уместно."
        )

        return f"{prompt}{quality_note}\n\nВводные пользователя:\n{user_text}"

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
            "🧠 **Универсальный режим готов к работе**\n\n"
            "**Сейчас**\n"
            "LLM API не подключён, поэтому я работаю в демо-режиме.\n\n"
            "**Что я могу закрывать после подключения API**\n"
            "— разбор рабочих задач;\n"
            "— тексты и ответы клиентам;\n"
            "— планы действий;\n"
            "— продуктовые гипотезы;\n"
            "— стратегические разборы;\n"
            "— идеи и упаковку;\n"
            "— анализ ситуаций;\n"
            "— документы и структуру;\n"
            "— обучение и объяснения.\n\n"
            "**Что я понял из запроса**\n"
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
