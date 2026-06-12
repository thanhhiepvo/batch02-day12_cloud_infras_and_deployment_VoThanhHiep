"""Cost guard — monthly budget per user, Redis-backed when available."""
import time
import logging

from fastapi import HTTPException

from app.config import settings
from app.session import USE_REDIS, _redis

logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

_memory_cost: dict[str, float] = {}
_memory_month: dict[str, str] = {}


def _current_month() -> str:
    return time.strftime("%Y-%m")


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    )


def check_budget(user_id: str) -> None:
    month = _current_month()
    budget = settings.monthly_budget_usd

    if USE_REDIS and _redis is not None:
        key = f"budget:{user_id}:{month}"
        spent = float(_redis.get(key) or 0)
        if spent >= budget:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(spent, 4),
                    "budget_usd": budget,
                },
            )
        return

    if _memory_month.get(user_id) != month:
        _memory_month[user_id] = month
        _memory_cost[user_id] = 0.0
    if _memory_cost.get(user_id, 0.0) >= budget:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(_memory_cost[user_id], 4),
                "budget_usd": budget,
            },
        )


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> float:
    cost = _estimate_cost(input_tokens, output_tokens)
    month = _current_month()

    if USE_REDIS and _redis is not None:
        key = f"budget:{user_id}:{month}"
        new_total = _redis.incrbyfloat(key, cost)
        _redis.expire(key, 32 * 24 * 3600)
        logger.info("Usage user=%s month=%s cost=$%.4f total=$%.4f", user_id, month, cost, new_total)
        return float(new_total)

    if _memory_month.get(user_id) != month:
        _memory_month[user_id] = month
        _memory_cost[user_id] = 0.0
    _memory_cost[user_id] += cost
    logger.info("Usage user=%s month=%s cost=$%.4f total=$%.4f", user_id, month, cost, _memory_cost[user_id])
    return _memory_cost[user_id]
