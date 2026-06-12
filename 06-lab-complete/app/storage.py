"""Redis-backed storage with local fallback for development."""
import json
import logging
from collections import defaultdict
from typing import Any

import redis

from .config import settings

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self):
        self.client: redis.Redis | None = None
        self.memory: dict[str, Any] = {}
        self.memory_lists: dict[str, list[str]] = defaultdict(list)
        self._connect()

    def _connect(self) -> None:
        if not settings.redis_url:
            logger.warning("REDIS_URL not set - using in-memory fallback")
            return
        try:
            self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self.client.ping()
            logger.info("Connected to Redis")
        except Exception as exc:
            logger.warning("Redis unavailable - using in-memory fallback: %s", exc)
            self.client = None

    @property
    def using_redis(self) -> bool:
        return self.client is not None

    def ping(self) -> bool:
        if not self.client:
            return True
        self.client.ping()
        return True

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        if self.client:
            self.client.zremrangebyscore(key, min_score, max_score)
            return
        self.memory_lists[key] = [
            raw for raw in self.memory_lists[key]
            if not (min_score <= json.loads(raw)["score"] <= max_score)
        ]

    def zcard(self, key: str) -> int:
        if self.client:
            return int(self.client.zcard(key))
        return len(self.memory_lists[key])

    def zadd(self, key: str, member: str, score: float) -> None:
        if self.client:
            self.client.zadd(key, {member: score})
            return
        self.memory_lists[key].append(json.dumps({"member": member, "score": score}))

    def expire(self, key: str, seconds: int) -> None:
        if self.client:
            self.client.expire(key, seconds)

    def get_float(self, key: str) -> float:
        if self.client:
            return float(self.client.get(key) or 0)
        return float(self.memory.get(key, 0))

    def incr_float(self, key: str, amount: float) -> float:
        if self.client:
            return float(self.client.incrbyfloat(key, amount))
        self.memory[key] = self.get_float(key) + amount
        return float(self.memory[key])

    def rpush_json(self, key: str, value: dict[str, Any]) -> None:
        raw = json.dumps(value, ensure_ascii=False)
        if self.client:
            self.client.rpush(key, raw)
            return
        self.memory_lists[key].append(raw)

    def lrange_json(self, key: str, start: int = 0, end: int = -1) -> list[dict[str, Any]]:
        if self.client:
            values = self.client.lrange(key, start, end)
        else:
            values = self.memory_lists[key][start:] if end == -1 else self.memory_lists[key][start:end + 1]
        return [json.loads(raw) for raw in values]

    def ltrim(self, key: str, start: int, end: int) -> None:
        if self.client:
            self.client.ltrim(key, start, end)
            return
        values = self.memory_lists[key]
        self.memory_lists[key] = values[start:] if end == -1 else values[start:end + 1]


storage = Storage()
