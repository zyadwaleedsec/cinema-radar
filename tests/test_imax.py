"""IMAX snapshot matching, TMDB fallback and Arabic labels."""

from __future__ import annotations

from pathlib import Path

import strings
from imax import (
    CERTIFIED_DIGITAL,
    FULL_70MM,
    PARTIAL_70MM,
    UNKNOWN,
    ImaxFilm,
    ImaxService,
    normalize_title,
)

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "imax_films.json"


class FakeTmdb:
    def __init__(self, title: str | None = None, year: int | None = None) -> None:
        self.title = title
        self.year = year
        self.calls = 0

    async def resolve(self, title: str, year: int | None = None):
        self.calls += 1
        if self.title is None:
            return None
        from tmdb import TmdbMovie

        return TmdbMovie(self.title, self.year)


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    async def get_json(self, key: str, **_kwargs):
        return self.values.get(key)

    async def put_json(self, key: str, value: object, ttl: float, **_kwargs) -> None:
        self.values[key] = value


def _service(tmdb=None, cache=None) -> ImaxService:
    return ImaxService(
        [
            ImaxFilm("Oppenheimer", 2023, PARTIAL_70MM),
            ImaxFilm("Dune: Part Two", 2024, CERTIFIED_DIGITAL),
            ImaxFilm("The Dark Knight", 2008, PARTIAL_70MM),
            ImaxFilm("Avatar", 2009, FULL_70MM),
            ImaxFilm("Avatar", 2022, PARTIAL_70MM),
        ],
        tmdb=tmdb,
        cache=cache,
    )


def test_normalize_title_handles_case_punctuation_and_articles():
    assert normalize_title("The Dark Knight") == "dark knight"
    assert normalize_title("Fast & Furious") == "fast and furious"
    assert normalize_title("Dune: Part Two") == "dune part two"
    assert normalize_title("Amélie") == "amelie"
    assert normalize_title("  WALL·E  ") == "wall e"


def test_match_prefers_exact_year_then_nearby_year():
    service = _service()

    assert service.match("Oppenheimer", 2023) == ImaxFilm("Oppenheimer", 2023, PARTIAL_70MM)
    # VOX may be one year off because of regional release dates.
    assert service.match("Oppenheimer", 2024) == ImaxFilm("Oppenheimer", 2023, PARTIAL_70MM)
    assert service.match("Oppenheimer", 2020) is None


def test_match_without_year_uses_newest_listing():
    service = _service()
    assert service.match("Avatar") == ImaxFilm("Avatar", 2022, PARTIAL_70MM)


async def test_lookup_uses_tmdb_only_as_a_title_normaliser():
    tmdb = FakeTmdb(title="Oppenheimer", year=2023)
    service = _service(tmdb=tmdb)

    assert await service.lookup("Oppy (IMAX)") == PARTIAL_70MM
    assert tmdb.calls == 1

    # The result is memoised, so a second card does not call TMDB again.
    assert await service.lookup("Oppy (IMAX)") == PARTIAL_70MM
    assert tmdb.calls == 1


async def test_lookup_returns_unknown_and_caches_it():
    cache = FakeCache()
    service = _service(tmdb=FakeTmdb(), cache=cache)

    assert await service.lookup("A Completely Different Film", 2026) == UNKNOWN
    assert cache.values


async def test_admin_override_wins_for_future_lookups():
    tmdb = FakeTmdb()
    service = _service(tmdb=tmdb)

    assert await service.lookup("Oppenheimer") == PARTIAL_70MM
    service.remember("Oppenheimer", FULL_70MM)
    assert await service.lookup("Oppenheimer") == FULL_70MM


def test_bundled_snapshot_contains_known_imax_films():
    service = ImaxService.from_path(SNAPSHOT)

    assert service.match("Oppenheimer", 2023) is not None
    assert service.match("Dune: Part Two", 2024) is not None
    assert service.match("Interstellar", 2014) is not None


def test_imax_lines_cover_every_category():
    assert "بالكامل" in strings.imax_line(FULL_70MM)
    assert "أجزاء" in strings.imax_line(PARTIAL_70MM)
    assert "المعتمدة" in strings.imax_line(CERTIFIED_DIGITAL)
    assert "مش معروف" in strings.imax_line(UNKNOWN)
    assert strings.imax_line(None) == ""
