"""Free and supporter watch limits, plus the one-off trimming migration."""

from __future__ import annotations

import pytest

from db import WatchLimitReached


async def add(db, user, index: int, limit: int, day: int = 16):
    return await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date=f"2026-12-{day:02d}",
        movie_id=f"HO{index}",
        movie_name=f"Movie {index}",
        showtime="10:45",
        hall_type="MAX",
        watch_limit=limit,
    )


@pytest.mark.asyncio
async def test_free_user_limit(db, test_settings):
    user = await db.get_or_create_user(700, watch_limit=test_settings.free_watch_limit)
    for i in range(test_settings.free_watch_limit):
        await add(db, user, i, test_settings.free_watch_limit)
    with pytest.raises(WatchLimitReached):
        await add(db, user, 99, test_settings.free_watch_limit)


@pytest.mark.asyncio
async def test_supporter_can_add_more(db, test_settings):
    user = await db.get_or_create_user(701, watch_limit=test_settings.free_watch_limit)
    for i in range(test_settings.free_watch_limit):
        await add(db, user, i, test_settings.free_watch_limit)
    await db.set_user_supporter(701, True, test_settings.supporter_watch_limit)
    user = await db.get_user(701)
    assert user is not None
    for i in range(test_settings.free_watch_limit, test_settings.supporter_watch_limit):
        await add(db, user, i, int(user["watch_limit"]), day=17 + i)
    assert await db.count_active_watches(int(user["id"])) == test_settings.supporter_watch_limit
    with pytest.raises(WatchLimitReached):
        await add(db, user, 99, int(user["watch_limit"]))


@pytest.mark.asyncio
async def test_trim_keeps_the_soonest_watches(db, test_settings):
    user = await db.get_or_create_user(702, watch_limit=10)
    # Ten active watches, deliberately spread over different dates.
    for i in range(10):
        await add(db, user, i, 10, day=16 + i)

    trimmed = await db.trim_watches_to_limits(
        test_settings.free_watch_limit, test_settings.supporter_watch_limit
    )

    assert trimmed == [
        {
            "telegram_id": 702,
            "removed": 8,
            "limit": test_settings.free_watch_limit,
        }
    ]
    remaining = await db.list_watches(int(user["id"]))
    assert len(remaining) == test_settings.free_watch_limit
    assert [w["date"] for w in remaining] == ["2026-12-16", "2026-12-17"]
    updated = await db.get_user(702)
    assert updated is not None
    assert updated["watch_limit"] == test_settings.free_watch_limit
