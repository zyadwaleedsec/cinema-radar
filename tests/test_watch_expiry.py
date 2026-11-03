"""Watch lifecycle: automatic expiry, grouped notices and hard deletion."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from db import Database
from models import AVAILABLE, Showtime
from scheduler import Scheduler
from timeutil import day_end_iso, expiry_iso
from watcher import Watcher

PAST = "2000-01-01T00:00:00+00:00"
FUTURE = "2999-01-01T00:00:00+00:00"


class FakeProvider:
    name = "vox"

    def __init__(self, dates: list[str], showtimes: dict[str, list[Showtime]]) -> None:
        self.dates = dates
        self.showtimes = showtimes

    async def get_dates(self, branch_id):
        return list(self.dates)

    async def get_showtimes(self, branch_id, date, movie_id=None, force_refresh=False, ttl=None):
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
    def __init__(self, fail_times: int = 0) -> None:
        self.messages: list[tuple[int, list[dict]]] = []
        self.fail_times = fail_times

    async def send_watch_alert(self, watch, event):
        pass

    async def send_watch_expired(self, telegram_id, watches):
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("Telegram is down")
        self.messages.append((telegram_id, list(watches)))


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


async def _add_watch(
    db,
    telegram_id: int = 970,
    *,
    expires_at: str | None = None,
    date: str = "2999-01-01",
    time: str = "10:45",
    scope: str = "showtime",
    hall: str = "MAX",
) -> int:
    user = await db.get_or_create_user(telegram_id, watch_limit=10)
    return await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date=date,
        movie_id="HO1",
        movie_name="Avengers",
        showtime=time if scope == "showtime" else "*",
        hall_type=hall,
        watch_limit=10,
        scope=scope,
        expires_at=expires_at,
    )


def _showtime(date: str, time: str = "10:45", hall: str = "MAX") -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="almaza",
        date=date,
        movie_id="HO1",
        movie_name="Avengers",
        time=time,
        hall_type=hall,
        status=AVAILABLE,
        seats_available=4,
    )


async def test_legacy_watches_table_is_upgraded_in_place(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            is_supporter INTEGER NOT NULL DEFAULT 0,
            watch_limit INTEGER NOT NULL DEFAULT 10,
            notify_cancellations INTEGER NOT NULL DEFAULT 1,
            quiet_start INTEGER,
            quiet_end INTEGER,
            onboarded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            date TEXT NOT NULL,
            movie_id TEXT NOT NULL,
            movie_name TEXT NOT NULL,
            showtime TEXT NOT NULL,
            hall_type TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        INSERT INTO users (telegram_id, created_at)
        VALUES (1, '2026-01-01T00:00:00+00:00');
        INSERT INTO watches
            (user_id, provider, branch_id, branch_name, date, movie_id,
             movie_name, showtime, hall_type, active, created_at)
        VALUES
            (1, 'vox', 'b', 'B', '2026-12-01', 'm', 'M', '10:45',
             'MAX', 0, '2026-01-01T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    database = Database(str(path))
    await database.connect()
    try:
        await database.init_schema()
        row = await database.fetchone(
            "SELECT active, deactivated_at, expiry_notified, imax_status FROM watches"
        )
        assert row is not None
        assert row["active"] == 0
        assert row["deactivated_at"] is not None
        assert row["expiry_notified"] == 1
        assert row["imax_status"] is None
        assert await database.get_imax_override("m") is None
    finally:
        await database.close()


async def test_due_watches_close_and_send_one_grouped_message(db, cache, test_settings, clock):
    first = await _add_watch(db, expires_at=PAST)
    second = await _add_watch(db, expires_at=PAST, time="22:00")
    future = await _add_watch(db, expires_at=FUTURE, time="18:00")
    notifier = FakeNotifier()
    watcher = _watcher(test_settings, db, cache, clock, FakeProvider([], {}), notifier)

    await watcher.sync_targets()

    assert len(notifier.messages) == 1
    telegram_id, watches = notifier.messages[0]
    assert telegram_id == 970
    assert [int(watch["id"]) for watch in watches] == [first, second]

    for watch_id in (first, second):
        row = await db.get_watch(watch_id)
        assert row is not None
        assert row["active"] == 0
        assert row["deactivated_at"] is not None
        assert row["expiry_notified"] == 1

    remaining = await db.get_watch(future)
    assert remaining is not None and remaining["active"] == 1

    # The notice is sent exactly once.
    await watcher.sync_targets()
    assert len(notifier.messages) == 1


async def test_failed_notice_is_retried_on_the_next_cycle(db, cache, test_settings, clock):
    watch_id = await _add_watch(db, expires_at=PAST)
    notifier = FakeNotifier(fail_times=1)
    watcher = _watcher(test_settings, db, cache, clock, FakeProvider([], {}), notifier)

    await watcher.sync_targets()
    assert notifier.messages == []
    row = await db.get_watch(watch_id)
    assert row is not None and row["active"] == 0 and row["expiry_notified"] == 0

    clock.advance(60)
    await watcher.sync_targets()
    assert len(notifier.messages) == 1
    row = await db.get_watch(watch_id)
    assert row is not None and row["expiry_notified"] == 1


async def test_manual_removal_is_silent_and_deleted_after_retention(
    db, cache, test_settings, clock
):
    watch_id = await _add_watch(db, expires_at=FUTURE)
    await db.set_watch_baseline(watch_id, "2999-01-01", AVAILABLE)

    assert await db.deactivate_watch(watch_id) is True
    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["active"] == 0
    assert row["deactivated_at"] is not None
    assert row["expiry_notified"] == 1

    notifier = FakeNotifier()
    watcher = _watcher(test_settings, db, cache, clock, FakeProvider([], {}), notifier)
    await watcher.sync_targets()
    assert notifier.messages == []

    # Manual removal stores real time; align it with the fake clock so the
    # retention assertion exercises the configured window.
    clock.advance(timedelta(days=test_settings.watch_retention_days + 1).total_seconds())
    old = datetime.fromtimestamp(
        clock() - (test_settings.watch_retention_days + 1) * 86400, tz=UTC
    ).isoformat(timespec="seconds")
    await db.execute("UPDATE watches SET deactivated_at = ? WHERE id = ?", (old, watch_id))
    await watcher.sync_targets()

    assert await db.get_watch(watch_id) is None
    assert await db.count_watch_baselines(watch_id) == 0


async def test_movie_watch_expiry_tracks_the_latest_showtime(db, cache, test_settings, clock):
    date = "2999-01-02"
    provider = FakeProvider(
        [date],
        {
            date: [
                _showtime(date, "14:00"),
                _showtime(date, "22:00", "IMAX"),
            ]
        },
    )
    watch_id = await _add_watch(db, date=date, time="*", scope="movie", hall="*", expires_at=None)
    watcher = _watcher(test_settings, db, cache, clock, provider, FakeNotifier())

    await watcher.run_once(now=clock())

    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["expires_at"] == expiry_iso(date, "22:00", test_settings.timezone)


async def test_all_dates_expiry_follows_the_last_available_day(db, cache, test_settings, clock):
    first_date, last_date = "2999-01-02", "2999-01-20"
    provider = FakeProvider(
        [first_date, last_date],
        {first_date: [_showtime(first_date)], last_date: [_showtime(last_date)]},
    )
    watch_id = await _add_watch(
        db, date="*", time="*", scope="movie_all_dates", hall="*", expires_at=None
    )
    watcher = _watcher(test_settings, db, cache, clock, provider, FakeNotifier())

    await watcher.sync_targets()

    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["expires_at"] == day_end_iso(last_date, test_settings.timezone)
