from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import Settings

ModelTier = Literal["fast", "main", "heavy"]


@dataclass(frozen=True)
class ModelRoute:
    tier: ModelTier
    model: str
    fallback_model: str
    max_tokens: int
    temperature: float
    reason: str


HEAVY_MODES = {
    "product",
    "strategy",
    "commercial_offer",
    "meeting_summary",
    "work_plan",
    "checklist",
}

FAST_MARKERS = [
    "коротко",
    "кратко",
    "быстро",
    "в двух словах",
    "что такое",
    "объясни простыми словами",
]


def choose_model_route(
    *,
    settings: Settings,
    user_text: str,
    mode: str,
    purpose: str = "chat",
) -> ModelRoute:
    text = " ".join(user_text.lower().strip().split())
    length = len(text)

    if purpose in {"document", "deep_research"}:
        return ModelRoute(
            tier="heavy",
            model=settings.llm_heavy_model or settings.llm_model,
            fallback_model=settings.llm_fallback_model or settings.llm_model,
            max_tokens=2800 if purpose == "document" else 3200,
            temperature=0.25 if purpose == "document" else 0.3,
            reason=f"purpose:{purpose}",
        )

    if mode in HEAVY_MODES or length > 2500:
        return ModelRoute(
            tier="heavy",
            model=settings.llm_heavy_model or settings.llm_model,
            fallback_model=settings.llm_fallback_model or settings.llm_model,
            max_tokens=2600,
            temperature=0.3,
            reason="heavy_mode_or_long_input",
        )

    if length <= 220 or any(marker in text for marker in FAST_MARKERS):
        return ModelRoute(
            tier="fast",
            model=settings.llm_fast_model or settings.llm_model,
            fallback_model=settings.llm_fallback_model or settings.llm_model,
            max_tokens=1200,
            temperature=0.25,
            reason="short_or_fast_marker",
        )

    return ModelRoute(
        tier="main",
        model=settings.llm_model,
        fallback_model=settings.llm_fallback_model or settings.llm_model,
        max_tokens=2200,
        temperature=0.35,
        reason="default_main",
    )
