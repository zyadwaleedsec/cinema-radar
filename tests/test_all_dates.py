"""All-dates (same branch) watches: storage, expansion and new-date alerts."""

from __future__ import annotations

from models import AVAILABLE, NOT_AVAILABLE, Showtime
from scheduler import Scheduler
from watcher import NEW_DATE_OPENED, Watcher


class FakeProvider:
    name = "vox"

    def __init__(self, dates: list[str], showtimes: dict[str, list[Showtime]]) -> None:
        self.dates = dates
        self.showtimes = showtimes
        self.calls = 0

    async def get_dates(self, branch_id):
        return list(self.dates)

    async def get_showtimes(self, branch_id, date, movie_id=None, force_refresh=False, ttl=None):
        self.calls += 1
        return list(self.showtimes.get(date, []))


class FakeHttp:
    slowdown_factor = 1.0

    def target_multiplier(self, key):
        return 1.0


class FakeProviders:
    def __init__(self, provider):
        self.provider = provider

    def get(self, name):
        return self.provider


class FakeNotifier:
    def __init__(self):
        self.events = []

    async def send_watch_alert(self, watch, event):
        self.events.append(event)


def _showtime(date: str, status: str = AVAILABLE, hall: str = "MAX") -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="almaza",
        date=date,
        movie_id="HO1",
        movie_name="Avengers",
        time="10:45",
        hall_type=hall,
        status=status,
        seats_available=4 if status == AVAILABLE else None,
        booking_url="https://example/booking/1",
        showtime_id=f"{date}-1",
    )


async def _add_all_dates_watch(db, hall: str = "*") -> int:
    user = await db.get_or_create_user(950, watch_limit=10)
    return await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="*",
        movie_id="HO1",
        movie_name="Avengers",
        showtime="*",
        hall_type=hall,
        watch_limit=10,
        scope="movie_all_dates",
    )


def _watcher(settings, db, cache, clock, provider, notifier):
    return Watcher(
        settings,
        db,
        cache,
        Scheduler(settings, clock),
        FakeProviders(provider),
        FakeHttp(),
        notifier=notifier,
        clock=clock,
        sleep=clock.sleep,
    )


async def test_all_dates_watch_is_stored_with_sentinels(db):
    watch_id = await _add_all_dates_watch(db)
    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["date"] == "*"
    assert row["showtime"] == "*"
    assert row["scope"] == "movie_all_dates"
    assert row["hall_type"] == "*"
    assert row["baseline_done"] == 0

    assert [item["id"] for item in await db.active_all_dates_watches()] == [watch_id]
    # Day-specific targets must not include the sentinel row.
    assert await db.active_watch_targets() == []


async def test_baselines_are_created_pruned_and_marked(db):
    watch_id = await _add_all_dates_watch(db)
    await db.set_watch_baseline(watch_id, "2026-12-20", AVAILABLE)
    await db.set_watch_baseline(watch_id, "2026-12-21", NOT_AVAILABLE)
    assert await db.count_watch_baselines(watch_id) == 2
    baseline = await db.get_watch_baseline(watch_id, "2026-12-20")
    assert baseline is not None and baseline["status"] == AVAILABLE

    await db.prune_watch_baselines("2026-12-21")
    assert await db.count_watch_baselines(watch_id) == 1

    await db.mark_watch_baseline_done(watch_id)
    row = await db.get_watch(watch_id)
    assert row is not None and row["baseline_done"] == 1


async def test_first_scan_is_silent_then_new_date_alerts_once(db, cache, test_settings, clock):
    d1, d2, d3 = "2026-12-20", "2026-12-21", "2026-12-22"
    provider = FakeProvider([d1, d2], {d1: [_showtime(d1)], d2: [_showtime(d2)]})
    notifier = FakeNotifier()
    watcher = _watcher(test_settings, db, cache, clock, provider, notifier)
    watch_id = await _add_all_dates_watch(db)

    # First full scan only records the baseline.
    assert await watcher.run_once(now=clock()) == 0
    assert notifier.events == []
    assert len(watcher.scheduler) == 2
    assert await db.count_watch_baselines(watch_id) == 2

    # A later tick flips baseline_done after the baseline exists.
    clock.advance(100)
    await watcher.sync_targets()
    row = await db.get_watch(watch_id)
    assert row is not None and row["baseline_done"] == 1

    # A brand new bookable date produces exactly one NEW_DATE_OPENED alert.
    provider.dates = [d1, d2, d3]
    provider.showtimes[d3] = [_showtime(d3)]
    clock.advance(2000)
    sent = await watcher.run_once(now=clock())
    assert sent == 1
    assert [event.kind for event in notifier.events] == [NEW_DATE_OPENED]
    assert notifier.events[0].showtime.date == d3
    assert await db.count_watch_baselines(watch_id) == 3

    # Re-running after the baseline was committed stays quiet (dedupe).
    clock.advance(2000)
    assert await watcher.run_once(now=clock()) == 0
    assert len(notifier.events) == 1


async def test_all_dates_alert_respects_selected_format(db, cache, test_settings, clock):
    date = "2026-12-20"
    provider = FakeProvider([date], {date: [_showtime(date, NOT_AVAILABLE, "MAX")]})
    notifier = FakeNotifier()
    watcher = _watcher(test_settings, db, cache, clock, provider, notifier)
    await _add_all_dates_watch(db, hall="IMAX")

    assert await watcher.run_once(now=clock()) == 0
    clock.advance(100)
    await watcher.sync_targets()

    # Only a MAX session is on sale: an IMAX-only watch must stay quiet.
    provider.showtimes[date] = [_showtime(date, AVAILABLE, "MAX")]
    clock.advance(2000)
    assert await watcher.run_once(now=clock()) == 0
    assert notifier.events == []

    # The IMAX session opening on the same day is the alert that matters.
    provider.showtimes[date] = [
        _showtime(date, AVAILABLE, "MAX"),
        _showtime(date, AVAILABLE, "IMAX"),
    ]
    notifier.events.clear()
    clock.advance(2000)
    assert await watcher.run_once(now=clock()) == 1
    assert notifier.events[0].showtime.hall_type == "IMAX"
