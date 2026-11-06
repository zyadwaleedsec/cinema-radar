"""Premiere Cinemas API parsing and provider regression tests."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from http_client import FetchResult, UpstreamError
from providers.premiere import (
    PremiereProvider,
    normalize_time,
    parse_coming_soon,
    parse_movies,
    parse_showtimes,
)

LISTING = [
    {
        "movie_unique_identifier": "6901.192",
        "movie_id": 294,
        "movie_title": "Wala Kan Ala El-Bal",
        "movie_experience": "PREMIUM",
        "mf_name": "2D",
        "movie_plot": "A romantic comedy in Luxor.",
        "movie_runtime": 91,
        "lang_name": "Arabic",
        "schdeuled_cinema_list": "1,3",
        "show_dates": "2026-11-06,2026-11-07,2026-11-08",
        "ratings": [{"rating_id": 4, "rating": "All Ages"}],
        "trailer_links": [],
    },
    {
        "movie_unique_identifier": "6125.569",
        "movie_id": 313,
        "movie_title": "Hadoota",
        "movie_experience": "PREMIUM",
        "mf_name": "2D",
        "movie_plot": "A comedy.",
        "movie_runtime": 115,
        "lang_name": "Arabic",
        "schdeuled_cinema_list": "1,2",
        "show_dates": "2026-11-11,2026-11-12,2026-11-13",
        "ratings": [{"rating_id": 4, "rating": "All Ages"}],
        "trailer_links": [],
    },
    {
        "movie_unique_identifier": "9999.001",
        "movie_id": 999,
        "movie_title": "The Cat in the Hat",
        "movie_experience": "Standard",
        "mf_name": "2D",
        "movie_plot": "A family adventure.",
        "movie_runtime": 90,
        "lang_name": "English",
        "schdeuled_cinema_list": "2",
        "show_dates": "2026-11-06",
        "ratings": [{"rating_id": 4, "rating": "All Ages"}],
        "trailer_links": ["https://www.youtube.com/watch?v=cat"],
    },
]

SHOWTIMES = {
    "status": True,
    "Records": [
        {
            "cinema_id": 1,
            "cinema_name": "Nile Cinema",
            "cinemaShowTimes": [
                {
                    "md_id": 6041,
                    "movieDetailsData": [
                        {
                            "movie_unique_identifier": "6901.192",
                            "movie_title": "Wala Kan Ala El-Bal",
                            "mf_name": "2D",
                            "movie_experience": "PREMIUM",
                            "cinema_id": 1,
                            "screen_name": "SCREEN 5",
                            "ss_id": 22417,
                            "ss_start_date": "2026-11-06",
                            "ss_actual_start_date": "2026-11-06",
                            "ss_start_time": "15:30",
                            "ss_actual_end_date": "2026-11-06",
                        },
                        {
                            "movie_unique_identifier": "6901.192",
                            "movie_title": "Wala Kan Ala El-Bal",
                            "mf_name": "2D",
                            "movie_experience": "PREMIUM",
                            "cinema_id": 1,
                            "screen_name": "SCREEN 5",
                            "ss_id": 22446,
                            "ss_start_date": "2026-11-06",
                            "ss_actual_start_date": "2026-11-07",
                            "ss_start_time": "00:30",
                            "ss_actual_end_date": "2026-11-07",
                        },
                    ],
                },
                {
                    "md_id": 6042,
                    "movieDetailsData": [
                        {
                            "movie_unique_identifier": "6901.192",
                            "movie_title": "Wala Kan Ala El-Bal",
                            "mf_name": "2D",
                            "movie_experience": "LUXE",
                            "cinema_id": 1,
                            "screen_name": "SCREEN 2",
                            "ss_id": 22341,
                            "ss_start_date": "2026-11-06",
                            "ss_actual_start_date": "2026-11-06",
                            "ss_start_time": "16:30",
                            "ss_actual_end_date": "2026-11-06",
                        }
                    ],
                },
            ],
        },
        {
            "cinema_id": 3,
            "cinema_name": "Galaxy elManial",
            "cinemaShowTimes": [
                {
                    "md_id": 900,
                    "movieDetailsData": [
                        {
                            "movie_unique_identifier": "6901.192",
                            "movie_title": "Wala Kan Ala El-Bal",
                            "mf_name": "2D",
                            "movie_experience": "CineComfort",
                            "cinema_id": 3,
                            "screen_name": "Screen 2",
                            "ss_id": 10062,
                            "ss_start_date": "2026-11-06",
                            "ss_actual_start_date": "2026-11-06",
                            "ss_start_time": "16:00",
                            "ss_actual_end_date": "2026-11-06",
                        }
                    ],
                }
            ],
        },
    ],
}

HOME = (
    '<html><script src="/_next/static/chunks/app/%5Blang%5D/layout-abc123.js"></script>'
    "</html>"
)
BUNDLE = 'const token="eyJhbGciOiJIUzI1NiJ9.eyJ0b2tlbiI6ImFiYyJ9.c2lnbmF0dXJl";'


class FakeHttp:
    def __init__(self, api_payload: dict | None = None) -> None:
        self.api_payload = SHOWTIMES if api_payload is None else api_payload
        self.calls: list[dict] = []
        self.failures: list[tuple] = []

    async def get(
        self,
        url,
        key,
        ttl,
        force_refresh=False,
        conditional=True,
        target_key=None,
        allow_stale=True,
        headers=None,
    ):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers or {}),
                "target_key": target_key,
            }
        )
        if url == "https://premiere-cinemas.com/":
            text = HOME
        elif "layout-abc123.js" in url:
            text = BUNDLE
        elif "get-now-showing-movies" in url:
            text = json.dumps({"status": True, "Records": {"data": LISTING}})
        else:
            text = json.dumps(self.api_payload)
        return FetchResult(text=text, status_code=200)

    async def report_failure(self, reason, target_key=None, url=None):
        self.failures.append((reason, target_key, url))


def test_normalize_time_handles_24h_and_am_pm():
    assert normalize_time("15:30") == "15:30"
    assert normalize_time("3:30 PM") == "15:30"
    assert normalize_time("12:05 AM") == "00:05"
    assert normalize_time("nonsense") is None


def test_parse_movies_uses_the_api_unique_identifier():
    movies = parse_movies(LISTING)
    assert [movie.id for movie in movies] == ["6901.192", "6125.569", "9999.001"]
    current = movies[0]
    assert current.name == "Wala Kan Ala El-Bal"
    assert current.duration_minutes == 91
    assert current.language == "Arabic"
    assert current.rating == "All Ages"
    assert current.poster_url is None


def test_parse_coming_soon_starts_at_the_first_screening_day():
    movies = parse_coming_soon(LISTING, "2026-11-06")
    assert [movie.name for movie in movies] == ["Hadoota"]
    assert movies[0].release_date == "2026-11-11"


def test_parse_showtimes_keeps_raw_experiences_and_actual_dates():
    shows = parse_showtimes(SHOWTIMES)
    by_id = {show.showtime_id: show for show in shows}
    assert set(by_id) == {"22417", "22446", "22341", "10062"}

    premium = by_id["22417"]
    assert premium.branch_id == "1"
    assert premium.hall_type == "PREMIUM"
    assert premium.status == "AVAILABLE"
    assert premium.seats_available is None
    assert premium.date == "2026-11-06"
    assert premium.movie_id == "6901.192"

    after_midnight = by_id["22446"]
    assert after_midnight.time == "00:30"
    assert after_midnight.date == "2026-11-07"

    assert by_id["22341"].hall_type == "LUXE"
    assert by_id["10062"].hall_type == "CineComfort"


async def _provider(cache, test_settings, fake_http):
    settings = replace(test_settings, premiere_showtimes_ttl=600, premiere_snapshot_ttl=600)
    return PremiereProvider(fake_http, cache, settings)


async def test_get_showtimes_fetches_once_and_filters_the_branch(cache, test_settings):
    http = FakeHttp()
    provider = await _provider(cache, test_settings, http)
    shows = await provider.get_showtimes("1", "2026-11-06", "6901.192")
    assert {show.showtime_id for show in shows} == {"22417", "22446", "22341"}
    api_calls = [call for call in http.calls if "mifcentral-api" in call["url"]]
    assert len(api_calls) == 1
    assert api_calls[0]["headers"]["Authorization"].startswith("Bearer ")
    assert "x-web-security" not in api_calls[0]["headers"]

    token_calls = [
        call
        for call in http.calls
        if call["url"].startswith("https://premiere-cinemas.com")
    ]
    assert token_calls
    assert {call["target_key"] for call in token_calls} == {"premiere:token"}

    # The second branch is served from the same all-branch response.
    other = await provider.get_showtimes("3", "2026-11-06", "6901.192")
    assert [show.showtime_id for show in other] == ["10062"]
    assert len([call for call in http.calls if "mifcentral-api" in call["url"]]) == 1


async def test_get_showtimes_resolves_a_legacy_numeric_movie_id(cache, test_settings):
    http = FakeHttp()
    provider = await _provider(cache, test_settings, http)
    shows = await provider.get_showtimes("1", "2026-11-06", "294")
    assert shows
    api_calls = [call for call in http.calls if "get-movie-show-times" in call["url"]]
    assert "6901.192" in api_calls[0]["url"]


async def test_encrypted_response_latches_the_provider_off(cache, test_settings):
    http = FakeHttp({"encryptedData": "abc", "status": True})
    provider = await _provider(cache, test_settings, http)
    with pytest.raises(UpstreamError):
        await provider.get_showtimes("1", "2026-11-06", "6901.192")
    assert provider._encrypted is True
    assert len(http.failures) == 1
    api_calls = len([call for call in http.calls if "mifcentral-api" in call["url"]])

    with pytest.raises(UpstreamError):
        await provider.get_showtimes("1", "2026-11-06", "6901.192")
    assert len([call for call in http.calls if "mifcentral-api" in call["url"]]) == api_calls


def test_premiere_formats_stay_raw():
    from models import format_key

    assert format_key("LUXE") == "LUXE"
    assert format_key("CineComfort") == "CINECOMFORT"
    assert format_key("Plus") == "PLUS"
    assert format_key("MX4D") == "MX4D"
