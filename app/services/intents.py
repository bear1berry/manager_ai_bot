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
    - не тратить токены на простую классификацию;
    - быстро выбрать лучший режим ответа;
    - не ломать ручные быстрые режимы.

    Возвращает mode, который дальше понимает LLMService.complete().
    """
    clean = text.strip()
    lower = clean.lower()

    if not lower:
        return IntentResult(
            mode="assistant",
            title="Обычный ассистент",
            confidence=0.1,
            reason="Пустой текст",
        )

    client_markers = [
        "клиент пишет",
        "клиент написал",
        "клиент говорит",
        "что ответить",
        "как ответить",
        "ответь клиенту",
        "возражение",
        "дорого",
        "дешевле",
        "претензия",
        "недоволен",
        "недовольна",
        "переписка",
        "сообщение клиенту",
        "письмо клиенту",
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
        "мысли",
        "в голове",
        "сумбур",
        "много всего",
        "не могу структурировать",
        "разобрать ситуацию",
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
    ]

    project_markers = [
        "что у нас по",
        "по проекту",
        "по клиенту",
        "напомни по",
        "иванова",
        "дедлайн",
        "бюджет",
        "смета",
        "договоренность",
        "договорённость",
    ]

    scores = {
        "client_reply": _score(lower, client_markers),
        "chaos": _score(lower, chaos_markers),
        "plan": _score(lower, plan_markers),
        "commercial_offer": _score(lower, document_markers),
        "assistant": _score(lower, project_markers) * 0.7,
    }

    best_mode = max(scores, key=scores.get)
    best_score = scores[best_mode]

    if best_score <= 0:
        return IntentResult(
            mode="assistant",
            title="Обычный ассистент",
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
        return "Думаю и собираю ответ в рабочую структуру 🧠"

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


def _confidence(score: float) -> float:
    if score >= 3:
        return 0.9
    if score >= 2:
        return 0.75
    if score >= 1:
        return 0.6
    return 0.35
