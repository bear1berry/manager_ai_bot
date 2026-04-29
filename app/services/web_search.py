from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebSearchBundle:
    requested: bool
    enabled: bool
    provider: str
    query: str
    results: list[WebSearchResult]
    error: str | None = None

    @property
    def has_results(self) -> bool:
        return bool(self.results)


WEB_SEARCH_MARKERS = [
    "найди",
    "найти",
    "поищи",
    "поиск",
    "в интернете",
    "в сети",
    "загугли",
    "проверь",
    "проверить",
    "актуально",
    "актуальная",
    "актуальные",
    "актуальный",
    "свежие данные",
    "свежая информация",
    "что нового",
    "новости",
    "сейчас",
    "на сегодня",
    "по состоянию на",
    "последние изменения",
    "официальная документация",
    "документация",
    "релиз",
    "release",
    "api",
    "цены",
    "стоимость",
    "курс",
    "закон",
    "приказ",
    "постановление",
    "конкуренты",
    "рынок",
    "telegram bot api",
    "telegram stars",
    "mini app",
    "mini apps",
]

NO_WEB_MARKERS = [
    "без поиска",
    "не ищи",
    "не надо искать",
    "не используй интернет",
    "без интернета",
]


class WebSearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def should_search(self, text: str) -> bool:
        lower = text.lower()

        if any(marker in lower for marker in NO_WEB_MARKERS):
            return False

        return any(marker in lower for marker in WEB_SEARCH_MARKERS)

    async def search_if_needed(self, text: str) -> WebSearchBundle:
        requested = self.should_search(text)

        if not requested:
            return WebSearchBundle(
                requested=False,
                enabled=self.settings.web_search_enabled,
                provider=self.settings.web_search_provider,
                query="",
                results=[],
            )

        query = self._build_query(text)

        if not self.settings.web_search_enabled:
            return WebSearchBundle(
                requested=True,
                enabled=False,
                provider=self.settings.web_search_provider,
                query=query,
                results=[],
                error="WEB_SEARCH_ENABLED=false",
            )

        try:
            if self.settings.web_search_provider == "tavily":
                results = await self._search_tavily(query)
            elif self.settings.web_search_provider == "serper":
                results = await self._search_serper(query)
            elif self.settings.web_search_provider == "brave":
                results = await self._search_brave(query)
            else:
                results = []

            return WebSearchBundle(
                requested=True,
                enabled=True,
                provider=self.settings.web_search_provider,
                query=query,
                results=results,
                error=None if results else "Поиск не вернул результатов",
            )
        except Exception as exc:
            logger.exception("Web search failed")
            return WebSearchBundle(
                requested=True,
                enabled=True,
                provider=self.settings.web_search_provider,
                query=query,
                results=[],
                error=str(exc)[:500],
            )

    def build_context(self, bundle: WebSearchBundle) -> str:
        if not bundle.requested:
            return ""

        if not bundle.enabled:
            return (
                "Пользователь просил актуальные данные из сети, но web-поиск отключён в настройках.\n"
                "Ответь честно: без актуальной проверки, предложи включить WEB_SEARCH_ENABLED и API-ключ поиска.\n"
            )

        if not bundle.results:
            return (
                "Пользователь просил актуальные данные из сети, но поиск не вернул результатов.\n"
                f"Запрос поиска: {bundle.query}\n"
                f"Ошибка/статус: {bundle.error or 'нет результатов'}\n"
                "Ответь осторожно и не придумывай свежие факты.\n"
            )

        lines = [
            "Ниже web-контекст из поиска. Используй его как источник актуальных данных.",
            "Не выдумывай факты, которых нет в источниках.",
            "Если источники противоречат друг другу — прямо скажи.",
            "",
            f"Поисковый запрос: {bundle.query}",
            "",
            "Результаты поиска:",
        ]

        for index, result in enumerate(bundle.results, start=1):
            lines.append(
                f"{index}. {result.title}\n"
                f"URL: {result.url}\n"
                f"Фрагмент: {result.snippet}"
            )

        return "\n\n".join(lines)

    def format_sources_html(self, bundle: WebSearchBundle) -> str:
        if not bundle.requested or not bundle.results:
            return ""

        lines = ["🌐 <b>Источники</b>"]

        for index, result in enumerate(bundle.results, start=1):
            title = html.escape(result.title[:90])
            url = html.escape(result.url)
            lines.append(f"{index}. <a href=\"{url}\">{title}</a>")

        return "\n".join(lines)

    async def _search_tavily(self, query: str) -> list[WebSearchResult]:
        if not self.settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is empty")

        url = self.settings.tavily_base_url.rstrip("/") + "/search"

        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": self._max_results(),
            "include_answer": False,
            "include_raw_content": False,
        }

        async with httpx.AsyncClient(timeout=self.settings.web_search_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_results = data.get("results") or []
        return [
            self._normalize_result(
                title=item.get("title"),
                url=item.get("url"),
                snippet=item.get("content") or item.get("snippet"),
            )
            for item in raw_results
            if item.get("url")
        ][: self._max_results()]

    async def _search_serper(self, query: str) -> list[WebSearchResult]:
        if not self.settings.serper_api_key:
            raise RuntimeError("SERPER_API_KEY is empty")

        url = self.settings.serper_base_url.rstrip("/") + "/search"

        headers = {
            "X-API-KEY": self.settings.serper_api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "q": query,
            "num": self._max_results(),
        }

        async with httpx.AsyncClient(timeout=self.settings.web_search_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_results = data.get("organic") or []
        return [
            self._normalize_result(
                title=item.get("title"),
                url=item.get("link"),
                snippet=item.get("snippet"),
            )
            for item in raw_results
            if item.get("link")
        ][: self._max_results()]

    async def _search_brave(self, query: str) -> list[WebSearchResult]:
        if not self.settings.brave_api_key:
            raise RuntimeError("BRAVE_API_KEY is empty")

        url = self.settings.brave_base_url.rstrip("/") + "/res/v1/web/search"

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.settings.brave_api_key,
        }

        params = {
            "q": query,
            "count": self._max_results(),
            "search_lang": "ru",
            "country": "RU",
        }

        async with httpx.AsyncClient(timeout=self.settings.web_search_timeout_seconds) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        raw_results = (data.get("web") or {}).get("results") or []
        return [
            self._normalize_result(
                title=item.get("title"),
                url=item.get("url"),
                snippet=item.get("description"),
            )
            for item in raw_results
            if item.get("url")
        ][: self._max_results()]

    def _max_results(self) -> int:
        return max(1, min(int(self.settings.web_search_max_results), 8))

    @staticmethod
    def _build_query(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"@\w+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        for marker in NO_WEB_MARKERS:
            cleaned = cleaned.replace(marker, "")

        return cleaned[:500]

    @staticmethod
    def _normalize_result(title: str | None, url: str | None, snippet: str | None) -> WebSearchResult:
        return WebSearchResult(
            title=(title or "Источник").strip()[:180],
            url=(url or "").strip(),
            snippet=(snippet or "").strip()[:900],
        )
