"""Cross-cinema window watches (all cinemas, morning/evening)."""

from __future__ import annotations

import pytest

from db import WatchLimitReached
from handlers.watches import _window_match
from models import AVAILABLE, NOT_AVAILABLE, Showtime
from watcher import BOOKING_OPENED, compute_watch_events


def _showtime(status: str, time: str, mid: str = "HO1") -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="almaza",
        date="2026-12-16",
        movie_id=mid,
        movie_name="Avengers",
        time=time,
        hall_type="MAX",
        status=status,
    )


def _window_watch(window: str) -> dict:
    return {
        "id": 1,
        "showtime": window,
        "hall_type": "*",
        "movie_id": "HO1",
        "scope": "movie",
        "time_window": window,
    }


def test_window_match_split_at_cutoff() -> None:
    assert _window_match(_showtime(AVAILABLE, "16:59"), "morning", 17)
    assert not _window_match(_showtime(AVAILABLE, "17:00"), "morning", 17)
    assert _window_match(_showtime(AVAILABLE, "17:00"), "evening", 17)
    assert not _window_match(_showtime(AVAILABLE, "09:00"), "evening", 17)


def test_morning_window_filters_evening_showtime() -> None:
    previous = [_showtime(NOT_AVAILABLE, "10:45"), _showtime(NOT_AVAILABLE, "20:00")]
    current = [_showtime(AVAILABLE, "10:45"), _showtime(AVAILABLE, "20:00")]
    events = compute_watch_events(previous, current, [_window_watch("morning")], 17)
    assert [(e[1].kind, e[1].times) for e in events] == [(BOOKING_OPENED, ("10:45",))]


def test_evening_window_filters_morning_showtime() -> None:
    previous = [_showtime(NOT_AVAILABLE, "10:45"), _showtime(NOT_AVAILABLE, "20:00")]
    current = [_showtime(AVAILABLE, "10:45"), _showtime(AVAILABLE, "20:00")]
    events = compute_watch_events(previous, current, [_window_watch("evening")], 17)
    assert [(e[1].kind, e[1].times) for e in events] == [(BOOKING_OPENED, ("20:00",))]


@pytest.mark.asyncio
async def test_group_counts_as_one_watch(db):
    user = await db.get_or_create_user(1, watch_limit=2)
    ids = await db.add_watch_group(
        int(user["id"]),
        2,
        [
            {
                "provider": "vox",
                "branch_id": "a",
                "branch_name": "A",
                "date": "2026-12-16",
                "movie_id": "m",
                "movie_name": "M",
                "showtime": "morning",
                "hall_type": "*",
                "scope": "movie",
                "group_id": "g",
                "time_window": "morning",
            },
            {
                "provider": "vox",
                "branch_id": "b",
                "branch_name": "B",
                "date": "2026-12-16",
                "movie_id": "m",
                "movie_name": "M",
                "showtime": "morning",
                "hall_type": "*",
                "scope": "movie",
                "group_id": "g",
                "time_window": "morning",
            },
        ],
    )
    assert len(ids) == 2
    assert await db.count_active_watches(int(user["id"])) == 1


@pytest.mark.asyncio
async def test_group_respects_watch_limit(db):
    user = await db.get_or_create_user(1, watch_limit=2)
    await db.add_watch(
        int(user["id"]), "vox", "a", "A", "2026-12-16", "m1", "M1", "10:45", "MAX", 2
    )
    await db.add_watch(
        int(user["id"]), "vox", "a", "A", "2026-12-16", "m2", "M2", "11:00", "MAX", 2
    )
    assert await db.count_active_watches(int(user["id"])) == 2
    with pytest.raises(WatchLimitReached):
        await db.add_watch_group(
            int(user["id"]),
            2,
            [
                {
                    "provider": "vox",
                    "branch_id": "b",
                    "branch_name": "B",
                    "date": "2026-12-16",
                    "movie_id": "m3",
                    "movie_name": "M3",
                    "showtime": "morning",
                    "hall_type": "*",
                    "scope": "movie",
                    "group_id": "g",
                    "time_window": "morning",
                }
            ],
        )


@pytest.mark.asyncio
async def test_movie_waits_table_is_dropped_on_init(db):
    await db.execute(
        "CREATE TABLE IF NOT EXISTS movie_waits "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT)"
    )
    await db.execute("INSERT INTO movie_waits (user_id, title) VALUES (1, 'test')")
    await db.init_schema()
    tables = await db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='movie_waits'"
    )
    assert tables == []


def test_window_keyboard_hides_zero_counts() -> None:
    from keyboards import window_keyboard

    callbacks = {
        button.callback_data for row in window_keyboard(0, 3).inline_keyboard for button in row
    }
    assert "win:morning" not in callbacks
    assert "win:evening" in callbacks

    callbacks = {
        button.callback_data for row in window_keyboard(2, 0).inline_keyboard for button in row
    }
    assert "win:morning" in callbacks
    assert "win:evening" not in callbacks


def test_window_cutoff_text_uses_setting() -> None:
    from i18n import ar, en

    assert ar.window_cutoff_text(17) == "5 م"
    assert ar.window_cutoff_text(12) == "12 م"
    assert ar.window_cutoff_text(0) == "12 ص"
    assert en.window_cutoff_text(17) == "5 PM"
    assert en.window_cutoff_text(12) == "12 PM"
    assert en.window_cutoff_text(0) == "12 AM"
    assert "5 م" in ar.window_label("morning", 17)
    assert "5 PM" in en.window_label("evening", 17)
