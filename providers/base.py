"""Provider contract.  VOX is first; other cinemas can be added without
touching the watcher, discovery or bot layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from models import Branch, BranchOverview, Movie, Showtime


class UpstreamFormatError(RuntimeError):
    """The provider returned a page we could not understand."""


#: Human-readable brand names, shown in the cinema picker and watch badges.
PROVIDER_DISPLAY = {
    "vox": "VOX",
    "renaissance": "Renaissance",
}


class CinemaProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_branches(self, force_refresh: bool = False) -> list[Branch]: ...

    @abstractmethod
    async def get_dates(self, branch_id: str, force_refresh: bool = False) -> list[str]: ...

    @abstractmethod
    async def get_movies(
        self, branch_id: str, date: str, force_refresh: bool = False
    ) -> list[Movie]: ...

    @abstractmethod
    async def get_showtimes(
        self,
        branch_id: str,
        date: str,
        movie_id: str | None = None,
        force_refresh: bool = False,
        ttl: float | None = None,
    ) -> list[Showtime]: ...

    async def get_coming_soon(self, force_refresh: bool = False) -> list[Movie]:
        """Movies announced for a future release.  Optional providers return []."""

        return []

    async def get_movie_details(self, movie: Movie, force_refresh: bool = False) -> Movie:
        """Poster, duration, rating and language.  Optional providers keep *movie*."""

        return movie

    async def get_movie_poster(self, movie: Movie) -> str | None:
        """Return official (TMDB-hosted) artwork for a listing, if available."""

        return movie.poster_url

    async def get_branch_overview(
        self, branch_id: str, force_refresh: bool = False
    ) -> BranchOverview:
        branches = await self.get_branches(force_refresh=force_refresh)
        branch = next((b for b in branches if b.id == branch_id), Branch(branch_id, branch_id))
        dates = await self.get_dates(branch_id, force_refresh=force_refresh)
        movies: list[Movie] = []
        showtimes: list[Showtime] = []
        if dates:
            movies = await self.get_movies(branch_id, dates[0], force_refresh=force_refresh)
            showtimes = await self.get_showtimes(branch_id, dates[0], force_refresh=force_refresh)
        return BranchOverview(
            branch=branch,
            dates=tuple(dates),
            movies=tuple(movies),
            showtimes=tuple(showtimes),
            fetched_date=dates[0] if dates else None,
        )


class ProviderRegistry:
    def __init__(self, providers: Iterable[CinemaProvider]) -> None:
        self._providers = {p.name: p for p in providers}

    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def __contains__(self, name: object) -> bool:
        return name in self._providers

    def get(self, name: str) -> CinemaProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {name}") from exc
