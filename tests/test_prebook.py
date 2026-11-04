"""Renaissance pre-book date discovery (dates beyond the ten-day strip)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from models import Movie
from providers.renaissance import RenaissanceProvider, _merge_dates

BRANCH_HTML = """
<html><body>
<div class="eventsDays"><ul>
  <li><a href="https://rnscinemas.com/en/cinemas/madinty/04-11-2026">04 Nov</a></li>
  <li><a href="https://rnscinemas.com/en/cinemas/madinty/13-11-2026">13 Nov</a></li>
</ul></div>
</body></html>
"""

MOVIE_HTML = """
<html><body>
<div class="eventsDays"><ul>
  <li><a href="https://rnscinemas.com/en/movie/avengers/01-11-2026">past</a></li>
  <li><a href="https://rnscinemas.com/en/movie/avengers/16-12-2026">16 Dec</a></li>
  <li><a href="https://rnscinemas.com/en/movie/avengers/17-12-2026">17 Dec</a></li>
</ul></div>
<a href="https://rnscinemas.com/en/booking/x" data-booking-url="https://rnscinemas.com/en/booking/x"></a>
</body></html>
"""


class _FakeHttp:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    async def get(self, url, key, ttl, force_refresh=False, target_key=None, allow_stale=True):
        class _Result:
            text = self.pages.get(url, "")

        return _Result()

    async def report_failure(self, *args, **kwargs):
        return None


def _provider(cache, settings, pages: dict[str, str]) -> RenaissanceProvider:
    provider = RenaissanceProvider(_FakeHttp(pages), cache, settings)

    async def _coming_soon(force_refresh: bool = False):
        return [Movie("avengers", "Avengers: Doomsday", "avengers", "renaissance")]

    provider.get_coming_soon = _coming_soon
    return provider


def test_merge_dates_is_a_sorted_union():
    assert _merge_dates(["2026-11-05", "2026-11-04"], ["2026-11-05", "2026-12-16"]) == [
        "2026-11-04",
        "2026-11-05",
        "2026-12-16",
    ]
    assert _merge_dates([], []) == []


@pytest.mark.asyncio
async def test_refresh_prebook_dates_filters_past_and_stores_union(cache, test_settings):
    provider = _provider(
        cache,
        test_settings,
        {"https://rnscinemas.com/en/movie/avengers": MOVIE_HTML},
    )
    with patch("providers.renaissance.today_iso", return_value="2026-11-04"):
        await provider.refresh_prebook_dates()
    assert await provider._prebook_dates() == ["2026-12-16", "2026-12-17"]


@pytest.mark.asyncio
async def test_refresh_prebook_skips_unbookable_movies(cache, test_settings):
    no_showings = """
    <html><body>
    <div class="eventsDays"><ul>
      <li><a href="https://rnscinemas.com/en/movie/avengers/20-12-2026">20 Dec</a></li>
    </ul></div>
    <h3>No Showings Available</h3>
    </body></html>
    """
    provider = _provider(
        cache,
        test_settings,
        {"https://rnscinemas.com/en/movie/avengers": no_showings},
    )
    with patch("providers.renaissance.today_iso", return_value="2026-11-04"):
        await provider.refresh_prebook_dates()
    assert await provider._prebook_dates() == []


@pytest.mark.asyncio
async def test_get_dates_merges_prebook_with_strip(cache, test_settings):
    provider = _provider(
        cache,
        test_settings,
        {
            "https://rnscinemas.com/en/cinemas/madinty": BRANCH_HTML,
            "https://rnscinemas.com/en/movie/avengers": MOVIE_HTML,
        },
    )
    with patch("providers.renaissance.today_iso", return_value="2026-11-04"):
        await provider.refresh_prebook_dates()
    dates = await provider.get_dates("madinty")
    assert dates == ["2026-11-04", "2026-11-13", "2026-12-16", "2026-12-17"]


@pytest.mark.asyncio
async def test_get_dates_without_prebook_is_unchanged(cache, test_settings):
    provider = _provider(
        cache,
        test_settings,
        {"https://rnscinemas.com/en/cinemas/madinty": BRANCH_HTML},
    )
    dates = await provider.get_dates("madinty")
    assert dates == ["2026-11-04", "2026-11-13"]
