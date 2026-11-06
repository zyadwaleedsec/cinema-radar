"""Provider contract.  VOX is first; other cinemas can be added without
touching the watcher, discovery or bot layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from models import CANONICAL_FORMATS, Branch, BranchOverview, Movie, Showtime


class UpstreamFormatError(RuntimeError):
    """The provider returned a page we could not understand."""


#: Human-readable brand names, shown in the cinema picker and watch badges.
PROVIDER_DISPLAY = {
    "vox": "VOX",
    "renaissance": "Renaissance",
    "premiere": "Premiere",
}

#: Screening formats each cinema actually sells.  The discovery settings
#: filter must never offer IMAX to a Renaissance-only subscriber, or 4DX to a
#: VOX branch that does not have one.  Keys are canonical
#: :data:`models.CANONICAL_FORMATS` values; the parser in each provider is the
#: source of truth for this list.
PROVIDER_FORMATS: dict[str, tuple[str, ...]] = {
    "vox": (
        "IMAX",
        "SCREENX",
        "PREMIUM",
        "STANDARD",
        "DOLBY",
        "4DX",
        "GOLD",
        "KIDS",
        "ONYX",
        "MAX",
        "VIP",
        "3D",
        "2D",
    ),
    "renaissance": (
        "STANDARD",
        "PREMIUM",
        "SPECIAL",
        "VIP",
        "DBOX",
        "BALCONE",
        "3D",
        "2D",
    ),
    # Premiere publishes the experience exactly as the cinema names it.  Its
    # LUXE / CineComfort / Plus rooms are not VOX concepts, so they are never
    # mapped to VIP or PREMIUM.
    "premiere": (
        "PREMIUM",
        "LUXE",
        "MAX",
        "MX4D",
        "STANDARD",
        "CINECOMFORT",
        "PLUS",
        "3D",
        "2D",
    ),
}


def providers_for_branches(branch_ids: object, enabled_providers: object) -> set[str]:
    """Cinemas covered by a subscription's branch filter.

    Empty ``branch_ids`` means "every enabled cinema".  Legacy bare branch ids
    are treated as the default provider (they predate multi-cinema support).
    Unknown values fall back to every enabled cinema so the filter is never
    empty.
    """

    enabled = {str(name) for name in (enabled_providers or ()) if str(name) in PROVIDER_FORMATS}
    if not enabled:
        enabled = set(PROVIDER_FORMATS)
    values = [str(item).strip() for item in (branch_ids or ()) if str(item).strip()]
    if not values:
        return enabled
    chosen = set()
    for item in values:
        prefix = item.split(":", 1)[0] if ":" in item else "vox"
        if prefix in PROVIDER_FORMATS and prefix in enabled:
            chosen.add(prefix)
    return chosen or enabled


def available_formats(branch_ids: object, enabled_providers: object) -> tuple[str, ...]:
    """Canonical formats offered by the selected cinemas, in display order."""

    chosen = providers_for_branches(branch_ids, enabled_providers)
    allowed: set[str] = set()
    for name in chosen:
        allowed.update(PROVIDER_FORMATS.get(name, ()))
    return tuple(key for key in CANONICAL_FORMATS if key in allowed)


class CinemaProvider(ABC):
    name: str = "base"

    #: True when the upstream showtimes endpoint is per movie rather than a
    #: whole branch/day page.  The watcher then passes ``movie_id`` and does
    #: not coalesce two different movies into the same in-flight request.
    showtimes_per_movie: bool = False

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
