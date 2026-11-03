"""Cache pruning and the bounded stale-read window."""

from __future__ import annotations

from cache import Cache


class StepClock:
    def __init__(self, value: float = 1_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


async def test_sweep_drops_entries_expired_past_the_stale_window(db):
    clock = StepClock()
    cache = Cache(db, now=clock, max_stale=100.0)

    await cache.put("old", "x", ttl=10.0)
    clock.value += 200.0
    await cache.put("recent", "y", ttl=10.0)

    assert await cache.sweep() == 1
    assert await cache.get("old") is None
    assert await cache.get("recent") is not None
    assert await db.scalar("SELECT COUNT(*) FROM state_cache", default=0) == 1


async def test_load_prunes_rows_that_expired_long_ago(db):
    await db.set_cache_row(
        key="ancient",
        payload="x",
        etag=None,
        last_modified=None,
        body_hash=None,
        fetched_at=0.0,
        ttl=10.0,
    )
    cache = Cache(db, now=StepClock(), max_stale=100.0)

    assert await cache.load() == 0
    assert await db.scalar("SELECT COUNT(*) FROM state_cache", default=0) == 0


async def test_stale_reads_respect_the_stale_window(db):
    clock = StepClock()
    cache = Cache(db, now=clock, max_stale=100.0)
    await cache.put("key", "x", ttl=10.0)

    clock.value += 50.0  # expired, but still inside the grace window
    assert await cache.get("key", allow_stale=True) is not None

    clock.value += 100.0  # now far past the grace window
    assert await cache.get("key", allow_stale=True) is None
