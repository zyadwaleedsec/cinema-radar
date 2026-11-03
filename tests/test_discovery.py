"""Discovery baselines, flap handling and Coming Soon releases."""

from __future__ import annotations

import json

import pytest

from broadcaster import Broadcaster
from db import utc_now_iso
from discovery import DiscoveryJob
from models import (
    AVAILABLE,
    Branch,
    BranchOverview,
    DiscoveryEvent,
    Movie,
    Showtime,
)
from notifier import TelegramSender


def make_overview(movies, date="2026-12-16", branch=None) -> BranchOverview:
    branch = branch or Branch("almaza", "Almaza", "vox")
    shows = tuple(
        Showtime(
            provider="vox",
            branch_id=branch.id,
            date=date,
            movie_id=m.id,
            movie_name=m.name,
            time="10:45",
            hall_type="MAX",
            status=AVAILABLE,
            booking_url=f"https://example/booking/{m.id}",
            showtime_id=f"{m.id}-1",
        )
        for m in movies
    )
    return BranchOverview(
        branch=branch,
        dates=(date,),
        movies=tuple(movies),
        showtimes=shows,
        fetched_date=date,
    )


class FakeProvider:
    name = "vox"

    def __init__(self, current: BranchOverview) -> None:
        self.current = current
        self.confirm = current
        self.calls = 0

    async def get_branches(self, force_refresh=False):
        return [self.current.branch]

    async def get_branch_overview(self, branch_id, force_refresh=False):
        if force_refresh:
            self.calls += 1
            return self.current
        return self.confirm


class FakeProviders:
    def __init__(self, provider):
        self.provider = provider

    def get(self, name):
        return self.provider


class FakeBroadcaster:
    def __init__(self) -> None:
        self.events: list[DiscoveryEvent] = []

    async def enqueue_events(self, events):
        self.events.extend(events)


@pytest.mark.asyncio
async def test_discovery_baseline_new_movie_once_and_no_flap(db, cache, test_settings, clock):
    a = Movie("HO1", "Movie A", "movie-a")
    b = Movie("HO2", "Movie B", "movie-b")
    c = Movie("HO3", "Movie C", "movie-c")
    provider = FakeProvider(make_overview([a]))
    broadcaster = FakeBroadcaster()
    job = DiscoveryJob(
        test_settings,
        db,
        cache,
        FakeProviders(provider),
        broadcaster=broadcaster,
        clock=clock,
        sleep=clock.sleep,
    )

    assert await job.run_once(now=clock()) == 0
    assert provider.calls == 1
    assert broadcaster.events == []

    # Same interval: no upstream request.
    assert await job.run_once(now=clock()) == 0
    assert provider.calls == 1

    # A new movie appears -> exactly one NEW_MOVIE.
    clock.advance(101)
    provider.current = make_overview([a, b])
    provider.confirm = provider.current
    assert await job.run_once(now=clock()) == 1
    assert provider.calls == 2
    assert len(broadcaster.events) == 1
    assert broadcaster.events[0].kind == "NEW_MOVIE"
    assert broadcaster.events[0].movie.id == "HO2"

    # The same event is never published twice.
    clock.advance(101)
    assert await job.run_once(now=clock()) == 0
    assert provider.calls == 3
    assert len(broadcaster.events) == 1

    # Flapping: C appears in the first read but is gone on confirmation.
    clock.advance(101)
    provider.current = make_overview([a, b, c])
    provider.confirm = make_overview([a, b])
    assert await job.run_once(now=clock()) == 0
    assert len(broadcaster.events) == 1

    # Within the flap window it is ignored.
    clock.advance(101)
    provider.current = make_overview([a, b, c])
    provider.confirm = provider.current
    assert await job.run_once(now=clock()) == 0
    assert len(broadcaster.events) == 1

    # After the flap window it is a real event again.
    clock.advance(test_settings.discovery_flap_window + 1)
    assert await job.run_once(now=clock()) == 1
    assert len(broadcaster.events) == 2


class FakeUpcomingProvider(FakeProvider):
    def __init__(self, current, coming):
        super().__init__(current)
        self.coming = list(coming)

    async def get_coming_soon(self, force_refresh=False):
        return list(self.coming)

    async def get_movie_details(self, movie, force_refresh=False):
        return movie


@pytest.mark.asyncio
async def test_coming_soon_release_is_one_upcoming_event(db, cache, test_settings, clock):
    a = Movie("HO1", "Movie A", "movie-a")
    soon = Movie(
        "HO2",
        "Coming B",
        "coming-b",
        poster_url="https://assets/coming-b.jpg",
        duration_minutes=120,
        rating="PG",
        language="English",
    )
    provider = FakeUpcomingProvider(make_overview([a]), [soon])
    broadcaster = FakeBroadcaster()
    job = DiscoveryJob(
        test_settings,
        db,
        cache,
        FakeProviders(provider),
        broadcaster=broadcaster,
        clock=clock,
        sleep=clock.sleep,
    )

    # First pass stores the branch and Coming Soon baselines.
    assert await job.run_once(now=clock()) == 0
    assert broadcaster.events == []

    # The upcoming title gets real showtimes -> release alert instead of a
    # second NEW_MOVIE alert for the same film.
    clock.advance(test_settings.coming_soon_interval + 1)
    clock.advance(test_settings.discovery_interval + 1)
    provider.current = make_overview([a, soon])
    provider.confirm = provider.current
    assert await job.run_once(now=clock()) == 1
    assert [event.kind for event in broadcaster.events] == ["UPCOMING_MOVIE"]
    event = broadcaster.events[0]
    assert event.movie.id == "HO2"
    assert event.movie.duration_minutes == 120
    assert event.event_key == "UPCOMING_MOVIE:HO2"

    # Already released -> never repeat.
    clock.advance(test_settings.coming_soon_interval + 1)
    clock.advance(test_settings.discovery_interval + 1)
    assert await job.run_once(now=clock()) == 0
    assert len(broadcaster.events) == 1


@pytest.mark.asyncio
async def test_coming_soon_title_already_showing_is_not_a_release(db, cache, test_settings, clock):
    soon = Movie("HO2", "Already Showing", "already-showing")
    provider = FakeUpcomingProvider(make_overview([soon]), [soon])
    broadcaster = FakeBroadcaster()
    job = DiscoveryJob(
        test_settings,
        db,
        cache,
        FakeProviders(provider),
        broadcaster=broadcaster,
        clock=clock,
        sleep=clock.sleep,
    )

    assert await job.run_once(now=clock()) == 0
    clock.advance(test_settings.coming_soon_interval + 1)
    clock.advance(test_settings.discovery_interval + 1)
    assert await job.run_once(now=clock()) == 0
    assert broadcaster.events == []


@pytest.mark.asyncio
async def test_watch_stores_movie_details(db):
    user = await db.get_or_create_user(903)
    watch_id = await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="2026-12-16",
        movie_id="HO1",
        movie_name="Avengers",
        showtime="10:45",
        hall_type="MAX",
        watch_limit=10,
        poster_url="https://assets/avengers.jpg",
        duration_minutes=150,
        rating="PG-13",
        language="English",
    )
    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["poster_url"] == "https://assets/avengers.jpg"
    assert row["duration_minutes"] == 150
    assert row["rating"] == "PG-13"
    assert row["language"] == "English"


class FakeBot:
    def __init__(self, clock):
        self.clock = clock
        self.times: list[float] = []

    async def send_message(self, **kwargs):
        self.times.append(self.clock())
        return None


@pytest.mark.asyncio
async def test_5000_subscribers_respect_telegram_rate(db, test_settings, clock):
    now = utc_now_iso()
    await db.executemany(
        "INSERT INTO users (telegram_id, watch_limit, created_at) VALUES (?, 10, ?)",
        [(20_000 + i, now) for i in range(5000)],
    )
    await db.executemany(
        """
        INSERT INTO subscriptions (user_id, branch_ids, event_types, hall_type, active, created_at)
        VALUES (?, '[]', '["NEW_MOVIE"]', NULL, 1, ?)
        """,
        [(i + 1, now) for i in range(5000)],
    )
    bot = FakeBot(clock)
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)
    broadcaster = Broadcaster(test_settings, db, sender, clock=clock)
    event = DiscoveryEvent(
        kind="NEW_MOVIE",
        branch=Branch("almaza", "Almaza", "vox"),
        movie=Movie("HO9", "New Movie", "new-movie"),
        date="2026-12-16",
        event_key="NEW_MOVIE:almaza:HO9",
    )
    sent = await broadcaster.process([event], now=clock())
    assert sent == 5000
    assert len(bot.times) == 5000

    # No one-second window contains more than 25 sends.
    start = 0
    for end in range(len(bot.times)):
        while bot.times[end] - bot.times[start] >= 1.0:
            start += 1
        assert end - start + 1 <= 25


async def test_existing_all_types_subscription_is_upgraded(db):
    old = '["NEW_MOVIE","NEW_DATE_OPENED","NEW_SHOWTIMES"]'
    user = await db.get_or_create_user(904)
    await db.upsert_subscription(int(user["id"]), [], [], None, True)
    await db.execute(
        "UPDATE subscriptions SET event_types = ? WHERE user_id = ?",
        (old, user["id"]),
    )

    await db.init_schema()

    sub = await db.get_subscription(int(user["id"]))
    assert sub is not None
    assert "UPCOMING_MOVIE" in json.loads(sub["event_types"])


async def test_deliberate_subset_is_not_upgraded(db):
    await db.get_or_create_user(905)
    user = await db.get_user(905)
    assert user is not None
    await db.upsert_subscription(int(user["id"]), [], ["NEW_MOVIE", "NEW_SHOWTIMES"], None, True)

    await db.init_schema()

    sub = await db.get_subscription(int(user["id"]))
    assert sub is not None
    assert "UPCOMING_MOVIE" not in json.loads(sub["event_types"])
