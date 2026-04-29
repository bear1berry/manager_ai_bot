from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    mode: str
    title: str
    confidence: float
    reason: str


def detect_intent(text: str) -> IntentResult:
    """
    Лёгкий локальный intent-router без внешнего LLM.

    Задача:
    - быстро понять сценарий запроса;
    - не тратить токены на классификацию;
    - автоматически выбирать лучший режим ответа;
    - не ломать ручные быстрые режимы.
    """
    clean = text.strip()
    lower = clean.lower()

    if not lower:
        return IntentResult(
            mode="assistant",
            title="Универсальный",
            confidence=0.1,
            reason="Пустой текст",
        )

    client_markers = [
        "клиент пишет",
        "клиент написал",
        "клиент говорит",
        "клиент спрашивает",
        "что ответить",
        "как ответить",
        "ответь клиенту",
        "ответ клиенту",
        "возражение",
        "дорого",
        "дешевле",
        "скидку",
        "претензия",
        "недоволен",
        "недовольна",
        "переписка",
        "сообщение клиенту",
        "письмо клиенту",
        "отказ клиенту",
        "вернуть клиента",
        "клиент пропал",
        "закрыть сделку",
        "продажа",
        "продажи",
    ]

    chaos_markers = [
        "каша",
        "хаос",
        "не понимаю",
        "не знаю с чего",
        "не знаю, с чего",
        "запутался",
        "запуталась",
        "разложи",
        "разбери",
        "разобрать",
        "мысли",
        "в голове",
        "сумбур",
        "много всего",
        "не могу структурировать",
        "разобрать ситуацию",
        "разложи по полкам",
        "не вижу порядок",
        "не понимаю что делать",
        "разгреби",
        "структурируй",
    ]

    plan_markers = [
        "сделай план",
        "план действий",
        "что делать",
        "по шагам",
        "пошагово",
        "на неделю",
        "за неделю",
        "за месяц",
        "roadmap",
        "дорожная карта",
        "как запустить",
        "как сделать",
        "этапы",
        "сроки",
        "дедлайн",
        "mvp",
        "план на",
        "распиши",
        "разбей на этапы",
        "чекпоинты",
        "контрольные точки",
    ]

    product_markers = [
        "продукт",
        "продуктовый",
        "product",
        "product manager",
        "pm",
        "целевая аудитория",
        "целевая аудитория",
        "ца",
        "mvp",
        "гипотеза",
        "гипотезы",
        "метрика",
        "метрики",
        "retention",
        "activation",
        "conversion",
        "конверсия",
        "воронка",
        "пользовательский сценарий",
        "сценарий использования",
        "user story",
        "user stories",
        "боль пользователя",
        "ценность",
        "value proposition",
        "позиционирование",
        "упаковка продукта",
        "roadmap",
        "фича",
        "фичи",
        "feature",
        "функционал",
        "запуск продукта",
        "первые пользователи",
        "платный сценарий",
        "подписка",
        "монетизация",
        "сегмент",
        "сегменты",
        "рынок",
        "проверить спрос",
        "валидировать",
        "валидация",
    ]

    strategy_markers = [
        "стратегия",
        "стратег",
        "стратегически",
        "как продвигать",
        "продвижение",
        "рост",
        "growth",
        "первые пользователи",
        "первые клиенты",
        "платные пользователи",
        "без бюджета",
        "каналы продвижения",
        "каналы продаж",
        "конкуренты",
        "конкуренция",
        "сильный ход",
        "сильные ходы",
        "нестандартный ход",
        "позиционирование",
        "риски запуска",
        "план на 30 дней",
        "go to market",
        "gtm",
        "вывести на рынок",
        "захватить",
        "масштабировать",
        "масштабирование",
        "лидерство",
        "преимущество",
        "точка входа",
        "рычаг роста",
        "прорыв",
        "удар",
        "план удара",
    ]

    document_markers = [
        "кп",
        "коммерческое предложение",
        "документ",
        "pdf",
        "docx",
        "резюме встречи",
        "чек-лист",
        "чеклист",
        "план работ",
        "собери документ",
        "сделай документ",
        "оформи в документ",
        "сформируй файл",
    ]

    project_markers = [
        "что у нас по",
        "по проекту",
        "по клиенту",
        "напомни по",
        "дедлайн",
        "бюджет",
        "смета",
        "договоренность",
        "договорённость",
        "контекст проекта",
        "проектная память",
        "задача по проекту",
    ]

    scores = {
        "client_reply": _score(lower, client_markers),
        "chaos": _score(lower, chaos_markers),
        "plan": _score(lower, plan_markers),
        "product": _score(lower, product_markers),
        "strategy": _score(lower, strategy_markers),
        "commercial_offer": _score(lower, document_markers),
        "assistant": _score(lower, project_markers) * 0.7,
    }

    scores = _apply_context_boosts(lower=lower, scores=scores)

    best_mode = max(scores, key=scores.get)
    best_score = scores[best_mode]

    if best_score <= 0:
        return IntentResult(
            mode="assistant",
            title="Универсальный",
            confidence=0.35,
            reason="Явные маркеры сценария не найдены",
        )

    if best_mode == "client_reply":
        return IntentResult(
            mode="client_reply",
            title="Ответ клиенту",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки клиентской переписки или возражения",
        )

    if best_mode == "chaos":
        return IntentResult(
            mode="chaos",
            title="Разбор хаоса",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки хаотичных вводных",
        )

    if best_mode == "plan":
        return IntentResult(
            mode="plan",
            title="План действий",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки запроса на план или roadmap",
        )

    if best_mode == "product":
        return IntentResult(
            mode="product",
            title="Продукт",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки продуктового запроса",
        )

    if best_mode == "strategy":
        return IntentResult(
            mode="strategy",
            title="Стратег",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки стратегического запроса",
        )

    if best_mode == "commercial_offer":
        return IntentResult(
            mode="commercial_offer",
            title="Документ / КП",
            confidence=_confidence(best_score),
            reason="В тексте есть признаки документа или коммерческого предложения",
        )

    return IntentResult(
        mode="assistant",
        title="Проектный вопрос",
        confidence=_confidence(best_score),
        reason="В тексте есть признаки проектного контекста",
    )


def status_text(intent: IntentResult, has_project_context: bool) -> str:
    if has_project_context:
        return (
            "🧠 Нашёл проектный контекст.\n"
            f"Сценарий: **{intent.title}**.\n"
            "Отвечаю с учётом памяти."
        )

    if intent.mode == "assistant":
        return "🧠 Думаю и собираю ответ в рабочую структуру."

    if intent.mode == "product":
        return (
            "🧩 Определил сценарий: **Продукт**\n\n"
            "Собираю продуктовый разбор: ЦА, боль, ценность, MVP, гипотезы и следующий шаг."
        )

    if intent.mode == "strategy":
        return (
            "🔥 Определил сценарий: **Стратег**\n\n"
            "Ищу сильные ходы, риски, рычаги роста и первый ударный шаг."
        )

    if intent.mode == "client_reply":
        return (
            "✍️ Определил сценарий: **Ответ клиенту**\n\n"
            "Собираю готовый текст: спокойно, уверенно, без оправданий."
        )

    if intent.mode == "chaos":
        return (
            "🧾 Определил сценарий: **Разбор хаоса**\n\n"
            "Отделяю суть от шума и собираю порядок действий."
        )

    if intent.mode == "plan":
        return (
            "📌 Определил сценарий: **План действий**\n\n"
            "Собираю шаги, контрольные точки и риски."
        )

    return (
        f"🧭 Определил сценарий: **{intent.title}**\n\n"
        "Собираю ответ в подходящей структуре."
    )


def _score(text: str, markers: list[str]) -> float:
    score = 0.0

    for marker in markers:
        if marker in text:
            score += 1.0

    if "?" in text:
        score += 0.15

    if len(text) > 350:
        score += 0.25

    return score


def _apply_context_boosts(lower: str, scores: dict[str, float]) -> dict[str, float]:
    """
    Небольшие поправки, чтобы близкие сценарии не путались.
    Например:
    - MVP может быть и планом, и продуктом, но если рядом есть ЦА/ценность — это продукт.
    - первые пользователи могут быть и продуктом, и стратегией, но если есть продвижение/рост — это стратегия.
    """
    boosted = dict(scores)

    product_context = [
        "ца",
        "целевая аудитория",
        "боль",
        "ценность",
        "mvp",
        "гипотеза",
        "метрики",
        "пользователь",
        "сценарий",
        "монетизация",
    ]

    strategy_context = [
        "продвигать",
        "продвижение",
        "рост",
        "без бюджета",
        "конкуренты",
        "каналы",
        "первые пользователи",
        "первые клиенты",
        "вывести",
        "рынок",
    ]

    if _has_any(lower, product_context):
        boosted["product"] += 0.45

    if _has_any(lower, strategy_context):
        boosted["strategy"] += 0.45

    if "roadmap" in lower or "дорожная карта" in lower:
        if _has_any(lower, product_context):
            boosted["product"] += 0.35
        else:
            boosted["plan"] += 0.35

    if "первые пользователи" in lower or "первые клиенты" in lower:
        boosted["strategy"] += 0.35

    if "клиент пишет" in lower or "что ответить" in lower or "как ответить" in lower:
        boosted["client_reply"] += 0.7

    if "сделай план" in lower or "по шагам" in lower or "пошагово" in lower:
        boosted["plan"] += 0.5

    if "разбери идею" in lower:
        boosted["product"] += 0.45

    if "сильный ход" in lower or "план удара" in lower:
        boosted["strategy"] += 0.7

    return boosted


def _has_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def _confidence(score: float) -> float:
    if score >= 4:
        return 0.95
    if score >= 3:
        return 0.9
    if score >= 2:
        return 0.75
    if score >= 1:
        return 0.6
    return 0.35
