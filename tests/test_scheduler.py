"""Per-target scheduling and request coalescing."""

from __future__ import annotations

import pytest

from models import AVAILABLE, Showtime
from scheduler import Scheduler
from watcher import Watcher


class FakeProvider:
    name = "vox"

    def __init__(self) -> None:
        self.calls = 0

    async def get_showtimes(self, branch_id, date, movie_id=None, force_refresh=False, ttl=None):
        self.calls += 1
        return [
            Showtime(
                provider="vox",
                branch_id=branch_id,
                date=date,
                movie_id="HO1",
                movie_name="Movie",
                time="10:45",
                hall_type="MAX",
                status=AVAILABLE,
                booking_url="https://example/booking/1",
                showtime_id=f"{date}-1",
            )
        ]


class FakeHttp:
    slowdown_factor = 1.0

    def target_multiplier(self, key):
        return 1.0


class FakeProviders:
    def __init__(self, provider):
        self.provider = provider

    def get(self, name):
        return self.provider


class FakeDates:
    def __init__(self, dates):
        self.dates = dates
        self.calls = 0

    async def get_dates(self, branch_id):
        self.calls += 1
        return self.dates


class FakeDatesProviders:
    def __init__(self, providers):
        self._providers = providers

    def get(self, name):
        return self._providers[name]


class FakeNotifier:
    def __init__(self):
        self.sent = 0

    async def send_watch_alert(self, watch, event):
        self.sent += 1


@pytest.mark.asyncio
async def test_1000_watchers_20_targets_make_20_requests(db, cache, test_settings, clock):
    provider = FakeProvider()
    http = FakeHttp()
    scheduler = Scheduler(test_settings, clock)
    notifier = FakeNotifier()
    watcher = Watcher(
        test_settings,
        db,
        cache,
        scheduler,
        FakeProviders(provider),
        http,
        notifier=notifier,
        clock=clock,
        sleep=clock.sleep,
    )

    # 50 users x 20 targets = 1000 watchers.
    for u in range(50):
        user = await db.get_or_create_user(10_000 + u, watch_limit=25)
        for d in range(20):
            date = f"2026-12-{1 + d:02d}"
            await db.add_watch(
                user_id=int(user["id"]),
                provider="vox",
                branch_id="almaza",
                branch_name="Almaza",
                date=date,
                movie_id="HO1",
                movie_name="Movie",
                showtime="10:45",
                hall_type="MAX",
                watch_limit=25,
            )

    await watcher.sync_targets()
    assert len(scheduler) == 20
    clock.advance(1000)
    sent = await watcher.run_once(now=clock())
    assert sent == 0
    assert provider.calls == 20
    assert notifier.sent == 0
    assert len(scheduler) == 20


async def test_run_once_reconciles_at_the_configured_cadence(db, cache, test_settings, clock):
    scheduler = Scheduler(test_settings, clock)
    watcher = Watcher(
        test_settings,
        db,
        cache,
        scheduler,
        FakeProviders(FakeProvider()),
        FakeHttp(),
        notifier=FakeNotifier(),
        clock=clock,
        sleep=clock.sleep,
    )
    calls = 0
    sync = watcher.sync_targets

    async def counting_sync():
        nonlocal calls
        calls += 1
        return await sync()

    watcher.sync_targets = counting_sync

    await watcher.run_once(now=clock())
    assert calls == 1

    # A one-second tick must not re-scan the whole watch table.
    clock.advance(test_settings.watcher_tick)
    await watcher.run_once(now=clock())
    assert calls == 1

    clock.advance(test_settings.watcher_sync_interval)
    await watcher.run_once(now=clock())
    assert calls == 2


async def test_branch_dates_cache_is_scoped_by_provider(db, cache, test_settings, clock):
    vox = FakeDates(["2026-12-01"])
    renaissance = FakeDates(["2026-12-02"])
    watcher = Watcher(
        test_settings,
        db,
        cache,
        Scheduler(test_settings, clock),
        FakeDatesProviders({"vox": vox, "renaissance": renaissance}),
        FakeHttp(),
        clock=clock,
        sleep=clock.sleep,
    )

    assert await watcher._branch_dates("vox", "same-id") == ["2026-12-01"]
    assert await watcher._branch_dates("renaissance", "same-id") == ["2026-12-02"]
    assert vox.calls == 1 and renaissance.calls == 1
