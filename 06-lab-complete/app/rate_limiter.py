"""Rate limiting — Redis sliding window when available, in-memory fallback."""
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings
from app.session import USE_REDIS, _redis

_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(user_id: str) -> None:
    limit = settings.rate_limit_per_minute
    window_seconds = 60
    now = time.time()

    if USE_REDIS and _redis is not None:
        key = f"ratelimit:{user_id}"
        window_start = now - window_seconds
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        _, _, count, _ = pipe.execute()
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
        return

    window = _rate_windows[user_id]
    while window and window[0] < now - window_seconds:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} req/min",
            headers={"Retry-After": "60"},
        )
    window.append(now)
