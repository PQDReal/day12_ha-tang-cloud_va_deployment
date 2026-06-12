"""Monthly per-user cost guard."""
from datetime import datetime, timezone

from fastapi import HTTPException

from .config import settings
from .storage import storage

PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS,
        6,
    )


def check_budget(user_id: str, estimated_cost: float) -> None:
    key = f"budget:{user_id}:{_month_key()}"
    current = storage.get_float(key)
    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "estimated_cost_usd": estimated_cost,
                "budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(user_id: str, cost: float) -> float:
    key = f"budget:{user_id}:{_month_key()}"
    total = storage.incr_float(key, cost)
    storage.expire(key, 32 * 24 * 3600)
    return round(total, 6)


def usage(user_id: str) -> dict:
    current = storage.get_float(f"budget:{user_id}:{_month_key()}")
    return {
        "user_id": user_id,
        "month": _month_key(),
        "cost_usd": round(current, 6),
        "budget_usd": settings.monthly_budget_usd,
        "budget_remaining_usd": max(0, round(settings.monthly_budget_usd - current, 6)),
        "budget_used_pct": round(current / settings.monthly_budget_usd * 100, 1),
    }
