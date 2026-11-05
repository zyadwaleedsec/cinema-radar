"""The watcher-count line appears only once a movie has an audience."""

from __future__ import annotations

import handlers.watches as watches
from config import Settings


async def _watch(db, user_id: int, movie_id: str = "HO1", showtime: str = "10:45") -> int:
    return await db.add_watch(
        user_id,
        provider="vox",
        branch_id="almaza",
        branch_name="Almaza",
        date="2026-12-20",
        movie_id=movie_id,
        movie_name="Avengers",
        showtime=showtime,
        hall_type="IMAX",
        watch_limit=10,
    )


async def test_count_movie_watchers_counts_distinct_active_users(db):
    first = await db.get_or_create_user(1, watch_limit=10)
    second = await db.get_or_create_user(2, watch_limit=10)
    third = await db.get_or_create_user(3, watch_limit=10)

    await _watch(db, int(first["id"]))
    await _watch(db, int(first["id"]), showtime="14:00")
    await _watch(db, int(second["id"]))
    await _watch(db, int(second["id"]), movie_id="OTHER")

    assert await db.count_movie_watchers("vox", "HO1") == 2

    await _watch(db, int(third["id"]))
    assert await db.count_movie_watchers("vox", "HO1") == 3

    watch_id = await _watch(db, int(third["id"]), movie_id="SECOND")
    await db.deactivate_watch(watch_id)
    assert await db.count_movie_watchers("vox", "HO1") == 3

    third_watch = await db.fetchone(
        "SELECT id FROM watches WHERE user_id = ? AND movie_id = 'HO1'", (int(third["id"]),)
    )
    await db.deactivate_watch(int(third_watch["id"]))
    assert await db.count_movie_watchers("vox", "HO1") == 2


async def test_detail_payload_hides_the_line_below_the_threshold(db):
    settings = Settings()
    watch = {
        "id": 7,
        "branch_name": "Almaza",
        "date": "2026-12-20",
        "movie_name": "Avengers",
        "showtime": "10:45",
        "hall_type": "IMAX",
        "alert_mode": "all",
        "snoozed_until": None,
        "scope": "showtime",
        "provider": "vox",
        "required_seats": 1,
        "movie_id": "HO1",
    }

    text, _ = await watches._watch_detail_payload(watch, settings, watchers=None)
    assert "بيتابعوا" not in text

    text, _ = await watches._watch_detail_payload(watch, settings, watchers=3)
    assert "👥 3" in text


class FakeMetadata:
    def __init__(self, aliases: list[str]) -> None:
        self._aliases = aliases

    async def aliases(self, query: str) -> list[str]:
        return self._aliases


async def test_arabic_alias_search_matches_english_provider_titles():
    movies = [
        {"id": "1", "name": "Avengers"},
        {"id": "2", "name": "Dune"},
    ]

    matches = await watches._arabic_alias_matches("منتقمون", movies, FakeMetadata(["Avengers"]))

    assert [movie["id"] for movie in matches] == ["1"]


async def test_arabic_alias_search_ignores_loose_matches():
    movies = [{"id": "1", "name": "Dune"}]

    matches = await watches._arabic_alias_matches(
        "منتقمون", movies, FakeMetadata(["Something Else"])
    )

    assert matches == []
