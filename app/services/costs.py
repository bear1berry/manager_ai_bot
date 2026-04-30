from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class LLMUsageEstimate:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


MODEL_PRICES_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    # input, output. Approximate placeholders for MVP cost analytics.
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    # Practical rough estimate for mixed Russian/English text.
    return max(1, math.ceil(len(text) / 4))


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(str(item.get("content") or "")) for item in messages)


def estimate_llm_usage(
    *,
    model: str,
    messages: list[dict[str, str]],
    output_text: str,
) -> LLMUsageEstimate:
    input_tokens = estimate_messages_tokens(messages)
    output_tokens = estimate_tokens(output_text)

    input_price, output_price = MODEL_PRICES_PER_1M_TOKENS.get(
        model,
        MODEL_PRICES_PER_1M_TOKENS["deepseek-chat"],
    )

    estimated_cost = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)

    return LLMUsageEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=round(estimated_cost, 8),
    )


async def record_llm_usage(
    db: aiosqlite.Connection,
    *,
    user_id: int | None,
    telegram_id: int | None,
    chat_id: int | None,
    feature: str,
    mode: str,
    provider: str,
    model: str,
    route_tier: str,
    route_reason: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    status: str,
    error: str | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO llm_usage_events (
            user_id,
            telegram_id,
            chat_id,
            feature,
            mode,
            provider,
            model,
            route_tier,
            route_reason,
            input_tokens,
            output_tokens,
            estimated_cost_usd,
            status,
            error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            telegram_id,
            chat_id,
            feature[:80],
            mode[:80],
            provider[:80],
            model[:120],
            route_tier[:40],
            route_reason[:200],
            int(input_tokens),
            int(output_tokens),
            float(estimated_cost_usd),
            status[:40],
            (error or "")[:1000] or None,
        ),
    )
    await db.commit()


async def llm_usage_stats_24h(db: aiosqlite.Connection) -> dict[str, Any]:
    cursor = await db.execute(
        """
        SELECT
            COUNT(*) AS requests,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
        FROM llm_usage_events
        WHERE created_at >= DATETIME('now', '-24 hours')
        """
    )
    row = await cursor.fetchone()

    cursor = await db.execute(
        """
        SELECT status, COUNT(*) AS cnt
        FROM llm_usage_events
        WHERE created_at >= DATETIME('now', '-24 hours')
        GROUP BY status
        """
    )
    status_rows = await cursor.fetchall()

    cursor = await db.execute(
        """
        SELECT route_tier, COUNT(*) AS cnt
        FROM llm_usage_events
        WHERE created_at >= DATETIME('now', '-24 hours')
        GROUP BY route_tier
        """
    )
    tier_rows = await cursor.fetchall()

    return {
        "requests": int(row["requests"] or 0) if row else 0,
        "input_tokens": int(row["input_tokens"] or 0) if row else 0,
        "output_tokens": int(row["output_tokens"] or 0) if row else 0,
        "estimated_cost_usd": float(row["estimated_cost_usd"] or 0) if row else 0.0,
        "statuses": {str(item["status"]): int(item["cnt"]) for item in status_rows},
        "tiers": {str(item["route_tier"]): int(item["cnt"]) for item in tier_rows},
    }


async def latest_llm_usage(db: aiosqlite.Connection, limit: int = 15) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """
        SELECT *
        FROM llm_usage_events
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return await cursor.fetchall()
