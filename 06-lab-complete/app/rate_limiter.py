"""Redis-backed sliding-window rate limiting."""
import time
import uuid

from fastapi import HTTPException

from .config import settings
from .storage import storage


def check_rate_limit(user_id: str) -> None:
    window_seconds = 60
    now = time.time()
    key = f"rate:{user_id}"

    storage.zremrangebyscore(key, 0, now - window_seconds)
    current = storage.zcard(key)

    if current >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "window_seconds": window_seconds,
            },
            headers={"Retry-After": str(window_seconds)},
        )

    storage.zadd(key, f"{now}:{uuid.uuid4().hex}", now)
    storage.expire(key, window_seconds)
