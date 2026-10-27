import asyncio
import time
import pytest

from app.core.cache import InMemoryTtlCache, get_cache


def test_cache_build_key() -> None:
    key1 = InMemoryTtlCache.build_key("2026-01", "12:00")
    assert key1 == "2026-01:12:00"

    key2 = InMemoryTtlCache.build_key("2026-01", "12:00", extra="page=1")
    assert key2 == "2026-01:12:00:page=1"


def test_cache_set_and_get_hit() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=10)
    cache.set("key1", {"generation": 12500})

    val = cache.get("key1")
    assert val == {"generation": 12500}

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["size"] == 1
    assert stats["hit_ratio"] == 1.0


def test_cache_miss_on_absent_key() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=10)
    val = cache.get("nonexistent")
    assert val is None

    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 1
    assert stats["hit_ratio"] == 0.0


def test_cache_ttl_expiry() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=1, max_size=10)
    # Set with 0.05s TTL
    cache.set("temp_key", "temporary_value", ttl_seconds=0.05)

    # Immediate access succeeds
    assert cache.get("temp_key") == "temporary_value"

    # Wait for expiration
    time.sleep(0.07)

    # Subsequent access fails and marks miss
    assert cache.get("temp_key") is None
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_cache_lru_eviction() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=3)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")

    assert cache.get_stats()["size"] == 3

    # Add 4th key -> oldest (k1) must be evicted
    cache.set("k4", "v4")

    assert cache.get("k1") is None  # Evicted
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"
    assert cache.get("k4") == "v4"

    stats = cache.get_stats()
    assert stats["evictions"] == 1
    assert stats["size"] == 3


def test_cache_lru_access_preserves_accessed_key() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=3)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")

    # Access k1 to make it most recently used
    assert cache.get("k1") == "v1"

    # Add 4th key -> k2 should be evicted (not k1)
    cache.set("k4", "v4")

    assert cache.get("k1") == "v1"  # Retained
    assert cache.get("k2") is None  # Evicted
    assert cache.get("k4") == "v4"


def test_cache_invalidate_and_clear() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=10)
    cache.set("k1", "v1")
    cache.set("k2", "v2")

    assert cache.invalidate("k1") is True
    assert cache.invalidate("k1") is False  # Already gone
    assert cache.get("k1") is None
    assert cache.get("k2") == "v2"

    cache.clear()
    assert cache.get("k2") is None
    assert cache.get_stats()["size"] == 0


def test_cache_purge_expired() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=10, max_size=10)
    cache.set("k_live", "live", ttl_seconds=60)
    cache.set("k_expire1", "exp1", ttl_seconds=0.02)
    cache.set("k_expire2", "exp2", ttl_seconds=0.02)

    time.sleep(0.04)
    purged_count = cache.purge_expired()
    assert purged_count == 2
    assert cache.get_stats()["size"] == 1
    assert cache.get("k_live") == "live"


def test_cache_get_or_compute() -> None:
    cache = InMemoryTtlCache(default_ttl_seconds=60, max_size=10)
    compute_count = 0

    async def run_test() -> None:
        nonlocal compute_count

        async def compute_heavy_data() -> dict:
            nonlocal compute_count
            compute_count += 1
            return {"computed": "yes", "count": compute_count}

        # First call: computes and returns hit=False
        data1, hit1 = await cache.get_or_compute("calc_key", compute_heavy_data)
        assert data1 == {"computed": "yes", "count": 1}
        assert hit1 is False
        assert compute_count == 1

        # Second call: cached and returns hit=True without recomputing
        data2, hit2 = await cache.get_or_compute("calc_key", compute_heavy_data)
        assert data2 == {"computed": "yes", "count": 1}
        assert hit2 is True
        assert compute_count == 1  # Never incremented again

    asyncio.run(run_test())
