import os
import time
import json
import threading
from typing import Any, Callable, Optional

# Optional Redis backend selection via USE_REDIS_CACHE=1 and REDIS_URL

class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, Any]] = {}

    def _now(self) -> float:
        return time.time()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < self._now():
                self._cache.pop(key, None)
                # Increment expired metric
                try:
                    global _cache_expired
                    _cache_expired += 1
                except Exception:
                    pass
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            self._cache[key] = (self._now() + ttl_seconds, value)

    def invalidate(self, prefix_or_key: str) -> None:
        with self._lock:
            if prefix_or_key in self._cache:
                self._cache.pop(prefix_or_key, None)
                return
            to_delete = [k for k in self._cache.keys() if k.startswith(prefix_or_key)]
            for k in to_delete:
                self._cache.pop(k, None)


class _RedisBackend:
    def __init__(self, url: str) -> None:
        import redis  # type: ignore

        # decode_responses=True gives str for values; we'll JSON serialize
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[Any]:
        val = self._client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            # Fallback: string repr
            payload = json.dumps(str(value))
        self._client.setex(key, ttl_seconds, payload)

    def invalidate(self, prefix_or_key: str) -> None:
        # Delete exact key if present; otherwise scan by prefix
        if self._client.delete(prefix_or_key):
            return
        pattern = f"{prefix_or_key}*"
        pipe = self._client.pipeline(transaction=False)
        # Use scan_iter to avoid blocking
        for k in self._client.scan_iter(pattern):
            pipe.delete(k)
        pipe.execute()


_CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
_USE_REDIS = os.getenv("USE_REDIS_CACHE") == "1"
_LOG_CACHE = os.getenv("LOG_CACHE") == "1"
_metrics_lock = threading.RLock()
_cache_hits = 0
_cache_misses = 0
_cache_expired = 0
_backend: Any

if _USE_REDIS:
    try:
        _backend = _RedisBackend(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    except Exception:
        # Fallback to memory if Redis not available
        _backend = _MemoryBackend()
else:
    _backend = _MemoryBackend()


def cache_get(key: str) -> Optional[Any]:
    if not _CACHE_ENABLED:
        return None
    try:
        value = _backend.get(key)
        with _metrics_lock:
            if value is not None:
                global _cache_hits
                _cache_hits += 1
                if _LOG_CACHE:
                    print(f"[cache] hit key={key}")
            else:
                global _cache_misses
                _cache_misses += 1
                if _LOG_CACHE:
                    print(f"[cache] miss key={key}")
        return value
    except Exception as e:
        return None


def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    if not _CACHE_ENABLED:
        return
    try:
        _backend.set(key, value, ttl_seconds)
        if _LOG_CACHE:
            print(f"[cache] set key={key} ttl={ttl_seconds}")
    except Exception:
        pass


def cache_invalidate(prefix_or_key: str) -> None:
    try:
        _backend.invalidate(prefix_or_key)
        if _LOG_CACHE:
            print(f"[cache] invalidate pattern={prefix_or_key}")
    except Exception:
        pass


def cache_memo(key: str, ttl_seconds: int, producer: Callable[[], Any]) -> Any:
    cached = cache_get(key)
    if cached is not None:
        return cached
    value = producer()
    cache_set(key, value, ttl_seconds)
    return value


def cache_metrics() -> dict[str, int]:
    with _metrics_lock:
        return {
            "hits": _cache_hits,
            "misses": _cache_misses,
            "expired": _cache_expired,
        }

