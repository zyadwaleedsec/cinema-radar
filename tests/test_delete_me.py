"""Account deletion must remove every personal row."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_delete_me_removes_all_rows(db, test_settings):
    user = await db.get_or_create_user(900, watch_limit=test_settings.free_watch_limit)
    uid = int(user["id"])
    await db.add_watch(
        user_id=uid,
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="2026-12-16",
        movie_id="HO1",
        movie_name="Movie",
        showtime="10:45",
        hall_type="MAX",
        watch_limit=10,
    )
    await db.upsert_subscription(uid, ["almaza"], ["NEW_MOVIE"], "MAX", True)
    await db.add_feedback(uid, "someone", "great bot")
    await db.create_donation(uid, "vodafone_cash", 100, "received", "proof", file_id="file-1")

    assert await db.delete_user(900) is True

    assert await db.get_user(900) is None
    assert await db.list_watches(uid, active_only=False) == []
    assert await db.get_subscription(uid) is None
    assert await db.scalar("SELECT COUNT(*) FROM feedback", default=0) == 0
    assert await db.fetchall("SELECT * FROM donations") == []
