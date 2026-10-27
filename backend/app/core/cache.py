from collections import OrderedDict
from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Coroutine, Generic, Optional, Tuple, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Internal cache entry storing payload and expiration deadline."""

    value: T
    created_at: float
    expires_at: float

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at


class InMemoryTtlCache:
    """Thread-safe, bounded in-memory LRU cache with time-to-live (TTL) expiry (ADR-03)."""

    def __init__(self, default_ttl_seconds: int = 3600, max_size: int = 100) -> None:
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._entries: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._lock = threading.Lock()

        # Telemetry counters
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @staticmethod
    def build_key(month: str, cutoff: str, extra: str = "") -> str:
        """Standardized cache key formatter for day-ahead analytics."""
        base = f"{month.strip()}:{cutoff.strip()}"
        return f"{base}:{extra.strip()}" if extra else base

    def get(self, key: str) -> Optional[Any]:
        """Retrieve an item if it exists and has not expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            now = time.time()
            if entry.is_expired(now):
                del self._entries[key]
                self._misses += 1
                return None

            # Mark recently used in LRU
            self._entries.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store an item in the cache with a specified or default TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.time()
        entry = CacheEntry(
            value=value,
            created_at=now,
            expires_at=now + ttl,
        )

        with self._lock:
            # If key already exists, remove it before re-inserting
            if key in self._entries:
                del self._entries[key]
            elif len(self._entries) >= self.max_size:
                # Evict oldest entry (LRU)
                self._entries.popitem(last=False)
                self._evictions += 1

            self._entries[key] = entry

    def invalidate(self, key: str) -> bool:
        """Explicitly invalidate a cached item."""
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries and reset counters."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def purge_expired(self) -> int:
        """Scan and remove all expired entries, returning the number purged."""
        now = time.time()
        purged = 0
        with self._lock:
            expired_keys = [k for k, entry in self._entries.items() if entry.is_expired(now)]
            for k in expired_keys:
                del self._entries[k]
                purged += 1
        return purged

    def get_stats(self) -> dict[str, Any]:
        """Return cache health and telemetry statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0
            return {
                "size": len(self._entries),
                "max_size": self.max_size,
                "default_ttl_seconds": self.default_ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": round(hit_ratio, 4),
                "evictions": self._evictions,
            }

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Coroutine[Any, Any, T]],
        ttl_seconds: Optional[int] = None,
    ) -> Tuple[T, bool]:
        """Return (cached_value, is_cache_hit). Computes and caches on miss."""
        cached = self.get(key)
        if cached is not None:
            return cached, True

        fresh_val = await compute_fn()
        self.set(key, fresh_val, ttl_seconds=ttl_seconds)
        return fresh_val, False


# Global default cache instance initialized with application settings
_cache_instance: Optional[InMemoryTtlCache] = None


def get_cache(default_ttl: int = 3600, max_size: int = 100) -> InMemoryTtlCache:
    """Retrieve or initialize the singleton in-memory cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = InMemoryTtlCache(default_ttl_seconds=default_ttl, max_size=max_size)
    return _cache_instance
