"""Per-watch alert modes, snooze and quiet-hour behaviour."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from config import Settings
from models import AVAILABLE, Showtime, WatchEvent
from watcher import (
    BOOKING_OPENED,
    MODE_ALL,
    MODE_OPENING,
    MODE_SEATS,
    NEW_DATE_OPENED,
    NEW_SHOWTIMES,
    SEATS_AVAILABLE,
    alert_allowed,
    in_quiet_hours,
)


def _event(date: str = "2026-01-06", kind: str = BOOKING_OPENED) -> WatchEvent:
    return WatchEvent(
        kind=kind,
        showtime=Showtime(
            provider="vox",
            branch_id="almaza",
            date=date,
            movie_id="HO1",
            movie_name="Avengers",
            time="10:45",
            hall_type="MAX",
            status=AVAILABLE,
            seats_available=4,
        ),
    )


def _quiet_settings() -> Settings:
    return replace(Settings(), timezone="UTC", quiet_start=23, quiet_end=8)


def test_alert_mode_filters_event_kinds():
    assert alert_allowed(MODE_ALL, BOOKING_OPENED)
    assert alert_allowed(MODE_ALL, SEATS_AVAILABLE)
    assert alert_allowed(MODE_ALL, NEW_SHOWTIMES)
    assert alert_allowed(MODE_ALL, NEW_DATE_OPENED)

    assert alert_allowed(MODE_SEATS, SEATS_AVAILABLE)
    assert not alert_allowed(MODE_SEATS, BOOKING_OPENED)
    assert not alert_allowed(MODE_SEATS, NEW_SHOWTIMES)
    assert not alert_allowed(MODE_SEATS, NEW_DATE_OPENED)

    assert alert_allowed(MODE_OPENING, BOOKING_OPENED)
    assert alert_allowed(MODE_OPENING, NEW_DATE_OPENED)
    assert not alert_allowed(MODE_OPENING, SEATS_AVAILABLE)
    assert not alert_allowed(MODE_OPENING, NEW_SHOWTIMES)


def test_quiet_hours_apply_to_watches_by_default():
    # 02:00 UTC is inside 23:00 -> 08:00.
    now = datetime(2026, 1, 1, 2, 0, tzinfo=UTC).timestamp()
    watch = {"quiet_watches": 1, "quiet_start": None, "quiet_end": None}
    assert in_quiet_hours(watch, _event("2026-01-06"), now, _quiet_settings())


def test_urgent_screenings_bypass_quiet_hours():
    now = datetime(2026, 1, 1, 2, 0, tzinfo=UTC).timestamp()
    watch = {"quiet_watches": 1, "quiet_start": None, "quiet_end": None}
    settings = _quiet_settings()
    assert not in_quiet_hours(watch, _event("2026-01-01"), now, settings)
    assert not in_quiet_hours(watch, _event("2026-01-02"), now, settings)


def test_user_can_opt_out_of_watch_quiet_hours():
    now = datetime(2026, 1, 1, 2, 0, tzinfo=UTC).timestamp()
    watch = {"quiet_watches": 0, "quiet_start": None, "quiet_end": None}
    assert not in_quiet_hours(watch, _event("2026-01-06"), now, _quiet_settings())


async def test_watch_stores_mode_booking_url_and_snooze(db):
    user = await db.get_or_create_user(900)
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
        booking_url="https://example/booking/1",
        alert_mode="seats",
    )
    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["alert_mode"] == "seats"
    assert row["booking_url"] == "https://example/booking/1"
    assert row["snoozed_until"] is None

    assert await db.set_watch_alert_mode(watch_id, int(user["id"]), "opening")
    row = await db.get_watch(watch_id)
    assert row is not None and row["alert_mode"] == "opening"

    until = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    assert await db.snooze_watch(watch_id, int(user["id"]), until)
    due = await db.list_due_snoozes(until)
    assert [item["id"] for item in due] == [watch_id]
    assert due[0]["telegram_id"] == 900
    assert due[0]["quiet_watches"] == 1

    await db.clear_watch_snooze(watch_id)
    assert await db.list_due_snoozes(until) == []


async def test_quiet_watches_can_be_disabled_per_user(db):
    user = await db.get_or_create_user(901)
    await db.update_user_settings(int(user["id"]), quiet_watches=0)
    row = await db.get_user(901)
    assert row is not None and row["quiet_watches"] == 0


async def test_required_seats_default_and_owner_only_update(db):
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
    )
    row = await db.get_watch(watch_id)
    assert row is not None and row["required_seats"] == 1

    assert await db.set_watch_required_seats(watch_id, int(user["id"]), 4)
    row = await db.get_watch(watch_id)
    assert row is not None and row["required_seats"] == 4

    stranger = await db.get_or_create_user(904)
    assert not await db.set_watch_required_seats(watch_id, int(stranger["id"]), 2)
    row = await db.get_watch(watch_id)
    assert row is not None and row["required_seats"] == 4


async def test_movie_scope_watch_uses_sentinel_time_and_hall(db):
    user = await db.get_or_create_user(902)
    watch_id = await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="2026-12-16",
        movie_id="HO1",
        movie_name="Avengers",
        showtime="*",
        hall_type="*",
        watch_limit=10,
        scope="movie",
    )
    row = await db.get_watch(watch_id)
    assert row is not None
    assert row["scope"] == "movie"
    assert row["showtime"] == "*"
    assert row["hall_type"] == "*"

    # Default scope stays per-showtime for older rows.
    other = await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="2026-12-16",
        movie_id="HO2",
        movie_name="Other",
        showtime="10:45",
        hall_type="MAX",
        watch_limit=10,
    )
    default_row = await db.get_watch(other)
    assert default_row is not None and default_row["scope"] == "showtime"
