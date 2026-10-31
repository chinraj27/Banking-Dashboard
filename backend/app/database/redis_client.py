"""Redis wrapper (cache + sessions) with an in-memory fallback when Redis is not configured."""
import json
import logging
import time
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, url: str):
        self._mem: dict[str, tuple[float | None, str]] = {}
        self._r = None
        if url:
            try:
                import redis

                client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
                client.ping()
                self._r = client
            except Exception as exc:  # fail soft: the app must work without a cache
                log.warning("Redis unavailable, using in-memory cache: %s", exc)

    @property
    def backend(self) -> str:
        return "redis" if self._r is not None else "memory"

    def ping(self) -> bool:
        try:
            return bool(self._r.ping()) if self._r is not None else True
        except Exception:
            return False

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if self._r is not None:
            try:
                self._r.set(key, value, ex=ttl)
                return
            except Exception as exc:
                log.warning("Redis set failed: %s", exc)
        self._mem[key] = (time.time() + ttl if ttl else None, value)

    def get(self, key: str) -> str | None:
        if self._r is not None:
            try:
                return self._r.get(key)
            except Exception as exc:
                log.warning("Redis get failed: %s", exc)
        item = self._mem.get(key)
        if not item:
            return None
        expires, value = item
        if expires is not None and expires < time.time():
            self._mem.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> None:
        if self._r is not None:
            try:
                self._r.delete(key)
            except Exception as exc:
                log.warning("Redis delete failed: %s", exc)
        self._mem.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        if self._r is not None:
            try:
                for key in self._r.scan_iter(match=f"{prefix}*"):
                    self._r.delete(key)
            except Exception as exc:
                log.warning("Redis delete_prefix failed: %s", exc)
        for key in [k for k in self._mem if k.startswith(prefix)]:
            self._mem.pop(key, None)

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        return json.loads(raw) if raw is not None else None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.set(key, json.dumps(value, default=str), ttl or settings.cache_ttl_seconds)


cache = Cache(settings.redis_url)
