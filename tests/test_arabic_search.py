"""Arabic queries resolve to the English titles cinemas actually list."""

from __future__ import annotations

import handlers.watches as watches


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
