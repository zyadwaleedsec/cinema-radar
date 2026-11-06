"""A coming-soon title's date picker starts at its first screening day."""

from __future__ import annotations

import handlers.watches as watches
from models import Movie
from providers.vox import parse_coming_soon


class _ComingSoonProvider:
    name = "vox"

    def __init__(self, movies):
        self._movies = movies

    async def get_coming_soon(self, force_refresh: bool = False):
        return self._movies


class _Providers:
    def __init__(self, provider):
        self._provider = provider

    def names(self):
        return (self._provider.name,)

    def get(self, name):
        return self._provider


DATES = ["2026-11-06", "2026-11-07", "2026-12-16", "2026-12-17", "2026-12-23"]


def _dune_provider():
    return _ComingSoonProvider(
        [
            Movie(
                "dune-part-three",
                "Dune: Part Three",
                "dune-part-three",
                "vox",
                release_date="2026-12-17",
            )
        ]
    )


async def test_dates_start_at_the_release_date():
    providers = _Providers(_dune_provider())

    dates = await watches._dates_from_release(DATES, "Dune", providers, None)

    assert dates == ["2026-12-17", "2026-12-23"]


async def test_dates_stay_sorted_and_keep_later_days_only():
    providers = _Providers(_dune_provider())

    dates = await watches._dates_from_release(DATES, "dune part three", providers, None)

    assert dates and dates[0] >= "2026-12-17"


async def test_date_strip_before_release_yields_no_bookable_day():
    providers = _Providers(_dune_provider())

    dates = await watches._dates_from_release(["2026-11-06", "2026-11-07"], "Dune", providers, None)

    assert dates == []


async def test_query_without_a_coming_soon_match_is_untouched():
    providers = _Providers(_dune_provider())

    dates = await watches._dates_from_release(DATES, "Godzilla", providers, None)

    assert dates == DATES


async def test_coming_soon_without_a_release_date_is_ignored():
    providers = _Providers(_ComingSoonProvider([Movie("hexed", "Hexed", "hexed", "vox")]))

    dates = await watches._dates_from_release(DATES, "Hexed", providers, None)

    assert dates == DATES


async def test_provider_errors_fall_back_to_the_full_date_list():
    class _BrokenProvider:
        name = "vox"

        async def get_coming_soon(self, force_refresh: bool = False):
            raise RuntimeError("down")

    dates = await watches._dates_from_release(DATES, "Dune", _Providers(_BrokenProvider()), None)

    assert dates == DATES


def test_coming_soon_parser_reads_the_release_date_line():
    html = """
    <html><body>
      <article class="movie-summary" data-slug="dune-part-three" data-title="Dune: Part Three">
        <a href="/movies/dune-part-three">
          <img class="poster" src="https://assets.voxcinemas.com/posters/dune.jpg" alt="Dune: Part Three">
        </a>
        <div>
          <h3><a href="/movies/dune-part-three">Dune: Part Three</a></h3>
          <p>
            <strong>Release Date:</strong> 17 December 2026<br />
            <strong>Language:</strong> English
          </p>
        </div>
      </article>
      <article class="movie-summary" data-slug="jumanji-open-world" data-title="Jumanji: Open World">
        <div>
          <h3><a href="/movies/jumanji-open-world">Jumanji: Open World</a></h3>
          <p><strong>Release Date:</strong> 24 December 2026</p>
        </div>
      </article>
      <article class="movie-summary" data-slug="undated" data-title="Undated">
        <div><h3><a href="/movies/undated">Undated</a></h3></div>
      </article>
    </body></html>
    """

    movies = {movie.slug: movie for movie in parse_coming_soon(html)}

    assert movies["dune-part-three"].release_date == "2026-12-17"
    assert movies["jumanji-open-world"].release_date == "2026-12-24"
    assert movies["undated"].release_date is None


def test_listing_pages_do_not_gain_a_release_date():
    html = """
    <article class="movie-compare" data-slug="clayface" data-identifier="clayface">
      <div><h3><a href="/movies/clayface">Clayface</a></h3></div>
    </article>
    """

    (movie,) = parse_coming_soon(html)

    assert movie.name == "Clayface"
    assert movie.release_date is None
