"""Localised TMDB metadata: matching stays English, display follows the UI."""

from __future__ import annotations

from metadata import TmdbMetadataService, display_language
from tmdb import ARABIC_LANGUAGE, ENGLISH_LANGUAGE, TmdbMovie


class FakeClient:
    enabled = True

    def __init__(self) -> None:
        self.details_calls: list[tuple[int, str]] = []
        self.search_calls: list[tuple[str, str]] = []
        self.fail_details = False

    async def resolve(self, title: str, year: int | None = None) -> TmdbMovie | None:
        return TmdbMovie(title, year, "/poster.jpg", 42, title, "An English overview")

    async def details(self, tmdb_id: int, language: str = ARABIC_LANGUAGE) -> TmdbMovie | None:
        self.details_calls.append((tmdb_id, language))
        if self.fail_details:
            raise RuntimeError("tmdb down")
        return TmdbMovie("فيلم عربي", 2026, "/ar.jpg", tmdb_id, "Original", "ملخص عربي")

    async def search(
        self, query: str, language: str = ENGLISH_LANGUAGE, limit: int = 20
    ) -> list[TmdbMovie]:
        self.search_calls.append((query, language))
        return [
            TmdbMovie("فيلم عربي", 2026, None, 7, "English Title", None),
            TmdbMovie("اسم تاني", 2025, None, 8, "English Title", None),
        ]


def test_display_language_only_localises_arabic():
    assert display_language("ar") == ARABIC_LANGUAGE
    assert display_language("ar-EG") == ARABIC_LANGUAGE
    assert display_language("en") is None
    assert display_language(None) is None


async def test_localize_returns_arabic_title_and_overview():
    client = FakeClient()
    service = TmdbMetadataService(client)

    movie = await service.localize("English Title", language=ARABIC_LANGUAGE)

    assert movie is not None
    assert movie.title == "فيلم عربي"
    assert movie.overview == "ملخص عربي"
    assert client.details_calls == [(42, ARABIC_LANGUAGE)]


async def test_localize_falls_back_when_details_fail():
    client = FakeClient()
    client.fail_details = True
    service = TmdbMetadataService(client)

    movie = await service.localize("English Title", language=ARABIC_LANGUAGE)

    assert movie is not None
    assert movie.title == "English Title"
    assert movie.overview == "An English overview"


async def test_english_never_calls_tmdb():
    client = FakeClient()
    service = TmdbMetadataService(client)

    assert await service.localize("English Title", language=None) is None
    assert client.details_calls == []


async def test_aliases_include_original_and_localized_titles_once():
    client = FakeClient()
    service = TmdbMetadataService(client)

    aliases = await service.aliases("فيلم")

    assert aliases == ["English Title", "فيلم عربي", "اسم تاني"]
    assert client.search_calls == [("فيلم", ARABIC_LANGUAGE)]


async def test_disabled_client_is_a_no_op():
    client = FakeClient()
    client.enabled = False
    service = TmdbMetadataService(client)

    assert await service.localize("x") is None
    assert await service.aliases("x") == []
