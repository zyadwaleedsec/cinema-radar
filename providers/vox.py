"""VOX Cinemas Egypt provider.

Research notes (see README for the full write-up)
--------------------------------------------------
VOX Egypt (https://egy.voxcinemas.com) is server-rendered HTML.  There is no
public JSON showtimes API in the web app; the useful pages are:

* ``/cinemas``                         -> branch list
* ``/showtimes?c=<branch>``            -> date strip + first on-sale day
* ``/showtimes?c=<branch>&d=YYYYMMDD`` -> every movie/session for one day
* ``/booking/<session-id>``            -> booking page (we never fetch it)

The day page is the whole-branch+day endpoint we prefer: one request returns
every movie and session, and VOX marks bookable sessions with a real
``/booking/...`` link.  We deliberately never open booking or seat-map pages;
availability is derived from the public showtimes markup.  The parser is
isolated below so a markup change is easy to repair.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date as date_cls
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from cache import (
    Cache,
    branches_key,
    coming_soon_key,
    dates_key,
    movie_details_key,
    movies_key,
    overview_key,
    showtimes_key,
)
from config import Settings
from http_client import HttpClient, UpstreamError
from models import (
    AVAILABLE,
    NOT_AVAILABLE,
    SOLD_OUT,
    Branch,
    BranchOverview,
    Movie,
    Showtime,
)
from providers.base import CinemaProvider, UpstreamFormatError

logger = logging.getLogger(__name__)

BASE_URL = "https://egy.voxcinemas.com"


def _url_part(value: object) -> str:
    """Quote an upstream-derived path/query value for one URL segment."""

    return quote(str(value), safe="")


_MOVIE_HREF = re.compile(r"/movies/([^/?#]+)")
_SHOWTIME_MOVIE_HREF = re.compile(r"[?&]m=([^&#]+)")
_BOOKING_HREF = re.compile(r"/booking/([^/?#]+)")
_DATE_PARAM = re.compile(r"[?&]d=(\d{8})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?|ص|م)?", re.IGNORECASE)
_SEATS_RE = re.compile(r"(\d+)\s*(?:seats?|كرسي|كراسي)", re.IGNORECASE)
_MOVIE_ID_RE = re.compile(r"\bHO\d{6,}\b")
_RELEASE_DATE_RE = re.compile(
    r"release\s+date\s*:?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", re.IGNORECASE
)
_ISO_DURATION_RE = re.compile(r"^P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?", re.IGNORECASE)
_RATINGS = ("NC-17", "PG-13", "PG", "G", "R", "15+", "12+", "18+", "TBC")

_FORMAT_DISPLAY = {
    "SCREENX": "ScreenX",
    "THEATRE": "Theatre",
    "PREMIUM": "Premium",
    "STANDARD": "Standard",
    "DOLBY": "Dolby",
    "IMAX": "IMAX",
    "4DX": "4DX",
    "GOLD": "Gold",
    "KIDS": "Kids",
    "ONYX": "Onyx",
    "MAX": "MAX",
    "VIP": "VIP",
    "3D": "3D",
    "2D": "2D",
}
_FORMATS = tuple(_FORMAT_DISPLAY)

_FALLBACK_BRANCHES = (
    Branch("city-centre-almaza", "سيتي سنتر الماظة", "vox"),
    Branch("mall-of-egypt", "مول مصر", "vox"),
    Branch("city-centre-alexandria", "سيتي سنتر اسكندرية", "vox"),
)


def to_vox_date(iso_date: str) -> str:
    try:
        return date_cls.fromisoformat(iso_date).strftime("%Y%m%d")
    except (TypeError, ValueError):
        return iso_date.replace("-", "")


def _raw_key(key: str) -> str:
    """Raw HTML and parsed JSON must never share a cache slot."""

    return f"raw:{key}"


def from_vox_date(raw: str) -> str:
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except (TypeError, ValueError):
        return raw


def normalize_time(raw: str) -> str | None:
    match = _TIME_RE.search(raw or "")
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = (match.group(3) or "").lower().replace(".", "")
    if suffix in {"pm", "م"} and hour < 12:
        hour += 12
    if suffix in {"am", "ص"} and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


@dataclass(frozen=True)
class _MovieContext:
    movie_id: str
    name: str
    slug: str


class VoxProvider(CinemaProvider):
    name = "vox"

    def __init__(
        self,
        http: HttpClient,
        cache: Cache,
        settings: Settings,
        posters: Any | None = None,
    ) -> None:
        self.http = http
        self.cache = cache
        self.settings = settings
        self.posters = posters
        self.base_url = settings.http_base_url.rstrip("/")

    async def get_movie_poster(self, movie: Movie) -> str | None:
        if self.posters is None:
            return None
        return await self.posters.url(movie.name)

    async def _official_poster(self, movie: Movie) -> Movie:
        """Replace any cinema-scraped artwork with the TMDB poster."""

        return replace(movie, poster_url=await self.get_movie_poster(movie))

    # ------------------------------------------------------------------ public
    async def get_branches(self, force_refresh: bool = False) -> list[Branch]:
        key = branches_key(self.name)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_static_ttl)
            if cached:
                return [Branch(**item) for item in cached]
        try:
            html = await self._fetch(
                f"{self.base_url}/cinemas",
                _raw_key(key),
                self.settings.cache_static_ttl,
                force_refresh,
            )
            branches = parse_branches(html)
        except Exception:
            logger.exception("Could not fetch VOX branches; using fallback list")
            branches = list(_FALLBACK_BRANCHES)
        if not branches:
            branches = list(_FALLBACK_BRANCHES)
        await self.cache.put_json(
            key, [b.__dict__ for b in branches], self.settings.cache_static_ttl
        )
        return branches

    async def get_dates(self, branch_id: str, force_refresh: bool = False) -> list[str]:
        key = dates_key(self.name, branch_id)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return list(cached)
        url = f"{self.base_url}/showtimes?c={_url_part(branch_id)}"
        try:
            html = await self._fetch(
                url, _raw_key(key), self.settings.cache_listings_ttl, force_refresh
            )
            dates = parse_dates(html)
        except Exception:
            logger.exception("Could not fetch VOX dates for %s", branch_id)
            dates = []
        await self.cache.put_json(key, dates, self.settings.cache_listings_ttl)
        return dates

    async def get_movies(
        self, branch_id: str, date: str, force_refresh: bool = False
    ) -> list[Movie]:
        key = movies_key(self.name, branch_id, date)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return _without_scraped_posters([Movie(**item) for item in cached])
        try:
            html = await self._day_html(branch_id, date, force_refresh)
            movies = parse_movies(html)
            if not movies:
                # Some VOX layouts do not link the movie title to /movies/.
                # The sessions still carry the movie id/name, so derive the
                # movie list from them instead of showing "no movies".
                movies = _movies_from_showtimes(parse_showtimes(html, branch_id, date))
        except Exception:
            logger.exception("Could not fetch VOX movies for %s %s", branch_id, date)
            stale = await self.cache.get_json(key, allow_stale=True)
            movies = [Movie(**item) for item in stale] if stale else []
        movies = _without_scraped_posters(movies)
        await self.cache.put_json(
            key, [m.__dict__ for m in movies], self.settings.cache_listings_ttl
        )
        return movies

    async def get_coming_soon(self, force_refresh: bool = False) -> list[Movie]:
        key = coming_soon_key(self.name)
        ttl = self.settings.cache_coming_soon_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached is not None:
                return _without_scraped_posters([Movie(**item) for item in cached])
        try:
            html = await self._fetch(
                f"{self.base_url}/movies/comingsoon", _raw_key(key), ttl, force_refresh
            )
            movies = parse_coming_soon(html)
        except Exception:
            logger.exception("Could not fetch VOX coming soon")
            stale = await self.cache.get_json(key, allow_stale=True)
            # Do not cache an empty/failed result: a later retry must be able to
            # rebuild a correct baseline instead of waiting for the TTL.
            return _without_scraped_posters([Movie(**item) for item in stale]) if stale else []
        movies = _without_scraped_posters(movies)
        await self.cache.put_json(key, [m.__dict__ for m in movies], ttl)
        return movies

    async def get_movie_details(self, movie: Movie, force_refresh: bool = False) -> Movie:
        slug = (movie.slug or movie.id or "").strip()
        if not slug or slug in {".", ".."} or "/" in slug or "\\" in slug:
            return movie
        key = movie_details_key(self.name, slug)
        ttl = self.settings.cache_movie_details_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached:
                merged = {**movie.__dict__}
                merged.update({k: v for k, v in cached.items() if v not in (None, "")})
                return await self._official_poster(Movie(**merged))
        try:
            html = await self._fetch(
                f"{self.base_url}/movies/{_url_part(slug)}", _raw_key(key), ttl, force_refresh
            )
            details = parse_movie_details(html, movie)
        except Exception:
            logger.warning("Could not fetch VOX movie details for %s", slug)
            return await self._official_poster(movie)
        details = await self._official_poster(details)
        await self.cache.put_json(
            key,
            {
                "id": details.id,
                "name": details.name,
                "slug": details.slug,
                "provider": details.provider,
                "poster_url": details.poster_url,
                "duration_minutes": details.duration_minutes,
                "rating": details.rating,
                "language": details.language,
                "synopsis": details.synopsis,
                "trailer_url": details.trailer_url,
            },
            ttl,
        )
        return details

    async def get_showtimes(
        self,
        branch_id: str,
        date: str,
        movie_id: str | None = None,
        force_refresh: bool = False,
        ttl: float | None = None,
    ) -> list[Showtime]:
        key = showtimes_key(self.name, branch_id, date)
        ttl = self.settings.cache_showtimes_ttl if ttl is None else ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached is not None:
                showtimes = [Showtime.from_dict(item) for item in cached]
                return self._filter(showtimes, movie_id)
        strict = bool(force_refresh)
        try:
            html = await self._day_html(branch_id, date, force_refresh, strict=strict)
            soup = BeautifulSoup(html, "lxml")
            showtimes = parse_showtimes(soup, branch_id, date)
            movies = parse_movies(soup)
            if movies:
                await self.cache.put_json(
                    movies_key(self.name, branch_id, date),
                    [m.__dict__ for m in movies],
                    self.settings.cache_listings_ttl,
                )
            dates = parse_dates(soup)
            if dates:
                await self.cache.put_json(
                    dates_key(self.name, branch_id), dates, self.settings.cache_listings_ttl
                )
        except UpstreamError:
            if strict:
                raise
            logger.warning("Could not fetch VOX showtimes for %s %s", branch_id, date)
            stale = await self.cache.get_json(key, allow_stale=True)
            showtimes = [Showtime.from_dict(item) for item in stale] if stale else []
        except Exception as exc:
            logger.exception("Could not parse VOX showtimes for %s %s", branch_id, date)
            if strict:
                await self.http.report_failure("parse", f"{self.name}:{branch_id}:{date}")
                raise UpstreamError(
                    f"Parse error: {exc}",
                    reason="parse",
                    url=f"{self.base_url}/showtimes?c={_url_part(branch_id)}",
                ) from exc
            stale = await self.cache.get_json(key, allow_stale=True)
            showtimes = [Showtime.from_dict(item) for item in stale] if stale else []
        # Never overwrite a good snapshot with an empty/failed parse: menus may
        # still want the last known data with an age label.
        if showtimes:
            await self.cache.put_json(key, [s.to_dict() for s in showtimes], ttl)
        return self._filter(showtimes, movie_id)

    async def get_branch_overview(
        self, branch_id: str, force_refresh: bool = False
    ) -> BranchOverview:
        key = overview_key(self.name, branch_id)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached:
                return self._overview_from_dict(cached)
        url = f"{self.base_url}/showtimes?c={_url_part(branch_id)}"
        strict = bool(force_refresh)
        try:
            html = await self._fetch(
                url,
                _raw_key(key),
                self.settings.cache_listings_ttl,
                force_refresh,
                strict=strict,
                target_key=f"{self.name}:{branch_id}",
            )
        except UpstreamError:
            if strict:
                raise
            logger.warning("Could not fetch VOX overview for %s", branch_id)
            cached = await self.cache.get_json(key, allow_stale=True)
            if cached:
                return self._overview_from_dict(cached)
            branches = await self.get_branches()
            branch = next((b for b in branches if b.id == branch_id), Branch(branch_id, branch_id))
            return BranchOverview(branch=branch)
        except Exception as exc:
            logger.exception("Could not parse VOX overview for %s", branch_id)
            if strict:
                await self.http.report_failure("parse", f"{self.name}:{branch_id}")
                raise UpstreamError(f"Parse error: {exc}", reason="parse", url=url) from exc
            cached = await self.cache.get_json(key, allow_stale=True)
            if cached:
                return self._overview_from_dict(cached)
            return BranchOverview(branch=Branch(branch_id, branch_id))

        branches = await self.get_branches()
        branch = next((b for b in branches if b.id == branch_id), Branch(branch_id, branch_id))
        soup = BeautifulSoup(html, "lxml")
        dates = parse_dates(soup)
        movies = _without_scraped_posters(parse_movies(soup))
        primary = dates[0] if dates else date_cls.today().isoformat()
        showtimes = parse_showtimes(soup, branch_id, primary)
        overview = BranchOverview(
            branch=branch,
            dates=tuple(dates),
            movies=tuple(movies),
            showtimes=tuple(showtimes),
            fetched_date=primary,
        )
        await self.cache.put_json(
            key, self._overview_to_dict(overview), self.settings.cache_listings_ttl
        )
        if dates:
            await self.cache.put_json(
                dates_key(self.name, branch_id), dates, self.settings.cache_listings_ttl
            )
        if movies:
            await self.cache.put_json(
                movies_key(self.name, branch_id, primary),
                [m.__dict__ for m in movies],
                self.settings.cache_listings_ttl,
            )
        if showtimes:
            await self.cache.put_json(
                showtimes_key(self.name, branch_id, primary),
                [s.to_dict() for s in showtimes],
                self.settings.cache_showtimes_ttl,
            )
        return overview

    # ----------------------------------------------------------------- helpers
    async def _fetch(
        self,
        url: str,
        key: str,
        ttl: float,
        force_refresh: bool,
        *,
        strict: bool = False,
        target_key: str | None = None,
    ) -> str:
        result = await self.http.get(
            url,
            key,
            ttl,
            force_refresh=force_refresh,
            target_key=target_key,
            allow_stale=not strict,
        )
        if not result.text:
            await self.http.report_failure("empty", target_key, url)
            raise UpstreamFormatError(f"Empty response from {url}")
        return result.text

    async def _day_html(
        self,
        branch_id: str,
        date: str,
        force_refresh: bool,
        *,
        strict: bool = False,
    ) -> str:
        key = showtimes_key(self.name, branch_id, date)
        url = f"{self.base_url}/showtimes?c={_url_part(branch_id)}&d={_url_part(to_vox_date(date))}"
        return await self._fetch(
            url,
            _raw_key(key),
            self.settings.cache_showtimes_ttl,
            force_refresh,
            strict=strict,
            target_key=f"{self.name}:{branch_id}:{date}",
        )

    @staticmethod
    def _filter(showtimes: Iterable[Showtime], movie_id: str | None) -> list[Showtime]:
        if not movie_id:
            return list(showtimes)
        return [s for s in showtimes if s.movie_id == movie_id]

    @staticmethod
    def _overview_to_dict(overview: BranchOverview) -> dict[str, Any]:
        return {
            "branch": overview.branch.__dict__,
            "dates": list(overview.dates),
            "movies": [m.__dict__ for m in _without_scraped_posters(overview.movies)],
            "showtimes": [s.to_dict() for s in overview.showtimes],
            "fetched_date": overview.fetched_date,
        }

    @staticmethod
    def _overview_from_dict(data: dict[str, Any]) -> BranchOverview:
        return BranchOverview(
            branch=Branch(**data["branch"]),
            dates=tuple(data.get("dates", ())),
            movies=tuple(_without_scraped_posters([Movie(**m) for m in data.get("movies", ())])),
            showtimes=tuple(Showtime.from_dict(s) for s in data.get("showtimes", ())),
            fetched_date=data.get("fetched_date"),
        )


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable without network access)
# ---------------------------------------------------------------------------


def parse_branches(html: str) -> list[Branch]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Branch] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        match = re.search(r"/cinemas/([^/?#]+)", href)
        if not match:
            continue
        slug = match.group(1)
        if slug in {"all", "search"}:
            continue
        name = _clean_text(anchor.get_text(" ")) or _attr(anchor, "title")
        if not name:
            image = anchor.find("img")
            name = _attr(image, "alt") if image else ""
        if not name:
            parent_heading = anchor.find_previous(["h2", "h3", "h4"])
            name = _clean_text(parent_heading.get_text(" ")) if parent_heading else ""
        name = name or slug.replace("-", " ").title()
        found.setdefault(slug, Branch(slug, name, "vox", urljoin(BASE_URL, href)))
    return list(found.values())


def parse_dates(html: str | BeautifulSoup) -> list[str]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")
    dates: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        for match in _DATE_PARAM.finditer(anchor["href"]):
            dates.add(from_vox_date(match.group(1)))
    for node in soup.find_all(attrs={"data-date": True}):
        value = str(node.get("data-date", ""))
        if re.fullmatch(r"\d{8}", value):
            dates.add(from_vox_date(value))
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dates.add(value)
    for node in soup.find_all(attrs={"data-value": True}):
        value = str(node.get("data-value", ""))
        if re.fullmatch(r"\d{8}", value):
            dates.add(from_vox_date(value))
    # The currently selected day is rendered as a <span>, not a link, but the
    # page's own form carries it in a hidden input.
    for node in soup.find_all("input", attrs={"name": "d", "value": True}):
        value = str(node.get("value", ""))
        if re.fullmatch(r"\d{8}", value):
            dates.add(from_vox_date(value))
    return sorted(dates)


_NAV_SLUGS = {"whatson", "comingsoon", "cinemas", "offers", "experiences", "giftcards"}
_GENERIC_NAMES = {"info", "details", "more", "book", "book now", "tickets", "read more"}


def _movie_title(container: Any, anchor: Any = None) -> str:
    """Pick the real movie title, never a generic link label like "Info"."""

    for scope in (container, anchor.parent if anchor is not None else None):
        if scope is None or not hasattr(scope, "find"):
            continue
        heading = scope.find(["h2", "h3", "h4"])
        if heading is not None:
            name = _clean_text(heading.get_text(" "))
            if name and name.lower() not in _GENERIC_NAMES:
                return name
    if anchor is not None:
        image = anchor.find("img")
        for value in (
            _attr(anchor, "title"),
            _attr(image, "alt"),
            _clean_text(anchor.get_text(" ")),
        ):
            if value and value.lower() not in _GENERIC_NAMES:
                return value
    return ""


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _movie_identity(article: Any, fallback_slug: str = "") -> tuple[str, str, str]:
    slug = _attr(article, "data-slug") or _attr(article, "data-identifier") or fallback_slug
    name = _movie_title(article)
    movie_id = (
        _attr(article, "data-movie-id")
        or _attr(article, "data-movie")
        or _attr(article, "data-identifier")
        or slug
    )
    if not slug and name:
        slug = _slugify(name)
    if not movie_id:
        movie_id = slug
    return movie_id, name, slug


def parse_movies(html: str | BeautifulSoup) -> list[Movie]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")
    found: dict[str, Movie] = {}

    # Current VOX layout: one <article class="movie-compare"> per movie.
    for article in soup.select("article.movie-compare, article[data-slug]"):
        movie_id, name, slug = _movie_identity(article)
        if not (movie_id or slug or name):
            continue
        if (slug or "").lower() in _NAV_SLUGS:
            continue
        found.setdefault(
            movie_id,
            Movie(
                movie_id,
                name or slug.replace("-", " ").title(),
                slug or movie_id,
                "vox",
                _poster(article),
            ),
        )
    if found:
        return list(found.values())

    # Generic fallback for other layouts / movie listing pages.
    for anchor in soup.find_all("a", href=True):
        match = _MOVIE_HREF.search(anchor["href"]) or _SHOWTIME_MOVIE_HREF.search(anchor["href"])
        if not match:
            continue
        slug = match.group(1)
        if not slug or slug.lower() in _NAV_SLUGS:
            continue
        container = anchor.find_parent("article") or _nearest_container(anchor)
        name = _movie_title(container, anchor) or slug.replace("-", " ").title()
        movie_id = _movie_id(container, slug) or slug
        found.setdefault(
            movie_id,
            Movie(movie_id, name, slug, "vox", _poster(container)),
        )
    return list(found.values())


def parse_coming_soon(html: str) -> list[Movie]:
    """Parse ``/movies/comingsoon``.

    VOX uses the same movie cards as the regular listing page, so the shared
    parser does most of the work.  The extra pass only covers layouts where the
    poster card is not wrapped in ``article.movie-compare``.
    """

    soup = BeautifulSoup(html, "lxml")
    movies = parse_movies(soup)
    if not movies:
        found: dict[str, Movie] = {}
        for anchor in soup.find_all("a", href=_MOVIE_HREF):
            match = _MOVIE_HREF.search(anchor["href"])
            if not match:
                continue
            slug = match.group(1)
            if not slug or slug.lower() in _NAV_SLUGS:
                continue
            container = anchor.find_parent("article") or _nearest_container(anchor)
            name = _movie_title(container, anchor) or slug.replace("-", " ").title()
            found.setdefault(
                slug,
                Movie(slug, name, slug, "vox", _poster(container)),
            )
        movies = list(found.values())
    return _with_release_dates(movies, soup)


def _release_date(container: Any) -> str | None:
    """The ``Release Date: 17 December 2026`` line on a coming-soon card."""

    if container is None or not hasattr(container, "get_text"):
        return None
    match = _RELEASE_DATE_RE.search(container.get_text(" ", strip=True))
    if not match:
        return None
    raw = " ".join(match.group(1).split())
    for pattern in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _with_release_dates(movies: list[Movie], soup: BeautifulSoup) -> list[Movie]:
    """Attach the release date each coming-soon card publishes."""

    releases: dict[str, str] = {}
    for article in soup.find_all("article"):
        slug = _attr(article, "data-slug")
        if not slug:
            continue
        release = _release_date(article)
        if release:
            releases[slug] = release
    if not releases:
        return movies
    return [
        replace(movie, release_date=releases[movie.slug]) if movie.slug in releases else movie
        for movie in movies
    ]


def parse_movie_details(html: str, fallback: Movie | None = None) -> Movie:
    """Read poster, duration, age rating and language from a movie page.

    VOX exposes most of this in JSON-LD, with the rest in ordinary headings and
    tags.  Every field falls back to what the listing page already gave us, so a
    partly-changed page still yields a useful alert instead of an exception.
    """

    soup = BeautifulSoup(html, "lxml")
    data = _jsonld_movie(soup)
    name = (
        _clean_text(data.get("name"))
        or _meta_content(soup, "og:title")
        or _first_heading(soup)
        or (fallback.name if fallback else "")
    )
    name = _strip_site_suffix(name)
    poster = (
        _jsonld_image(data.get("image"))
        or _meta_content(soup, "og:image")
        or _poster(soup)
        or (fallback.poster_url if fallback else None)
    )
    duration = (
        _duration_minutes(data.get("duration"))
        or _duration_from_text(soup.get_text(" ", strip=True))
        or (fallback.duration_minutes if fallback else None)
    )
    rating = (
        _clean_text(data.get("contentRating"))
        or _rating_from_text(soup.get_text(" ", strip=True))
        or (fallback.rating if fallback else None)
    )
    language = (
        _language_label(data.get("inLanguage"))
        or _language_from_soup(soup)
        or (fallback.language if fallback else None)
    )
    synopsis = (
        _clean_text(data.get("description"))
        or _meta_content(soup, "og:description")
        or _meta_content(soup, "description")
        or (fallback.synopsis if fallback else "")
    )
    trailer = (
        _trailer_url(data.get("trailer"))
        or _trailer_url(data.get("video"))
        or _trailer_from_soup(soup)
        or (fallback.trailer_url if fallback else None)
    )
    base = fallback or Movie(id=poster or name, name=name, slug="")
    return replace(
        base,
        name=name or base.name,
        poster_url=poster or base.poster_url,
        duration_minutes=duration,
        rating=rating,
        language=language,
        synopsis=(synopsis[:600] or None) if synopsis else base.synopsis,
        trailer_url=trailer or base.trailer_url,
    )


def _movies_from_showtimes(showtimes: Iterable[Showtime]) -> list[Movie]:
    """Build a movie list from sessions when movie anchors are absent."""

    found: dict[str, Movie] = {}
    for showtime in showtimes:
        found.setdefault(
            showtime.movie_id,
            Movie(
                id=showtime.movie_id,
                name=showtime.movie_name,
                slug=showtime.movie_id,
                provider="vox",
            ),
        )
    return list(found.values())


def parse_showtimes(html: str | BeautifulSoup, branch_id: str, default_date: str) -> list[Showtime]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")
    sessions: dict[str, Showtime] = {}

    # Current VOX layout: each movie is an <article class="movie-compare">,
    # sessions live in <ol class="showtimes"> and every session is either an
    # <a href="/booking/..."> (bookable) or a <span class="... unavailable">
    # (not on sale / sold out).  Both matter: a watch must exist before the
    # booking link appears.
    for article in soup.select("article.movie-compare, article[data-slug]"):
        movie_id, name, slug = _movie_identity(article)
        if not movie_id or (slug or "").lower() in _NAV_SLUGS:
            continue
        for element in article.select(
            "ol.showtimes .action.showtime, "
            "ol.showtimes a[href*='/booking/'], "
            "ol.showtimes span.showtime"
        ):
            item = element.find_parent("li")
            if item is None:
                continue
            time_value = normalize_time(element.get_text(" "))
            if not time_value:
                continue
            href = element.get("href") or ""
            booking_url = urljoin(BASE_URL, href) if "/booking/" in href else None
            showtime_id = _attr(item, "data-id") or _attr(element, "data-id")
            if not showtime_id:
                booking_match = _BOOKING_HREF.search(href)
                showtime_id = booking_match.group(1) if booking_match else ""
            showtime = Showtime(
                provider="vox",
                branch_id=branch_id,
                date=_session_date(href, default_date),
                movie_id=movie_id,
                movie_name=name or movie_id,
                time=time_value,
                hall_type=_hall_for_session(item, element),
                status=_session_status(element, booking_url is not None),
                seats_available=_seat_count(element, item),
                booking_url=booking_url,
                showtime_id=showtime_id,
            )
            sessions.setdefault(showtime.key + "|" + movie_id, showtime)

    if sessions:
        return sorted(sessions.values(), key=lambda s: (s.movie_name, s.time, s.hall_type))

    # Fallback for older/other layouts: only bookable sessions are visible.
    booking_anchors = soup.find_all("a", href=_BOOKING_HREF)
    for anchor in booking_anchors:
        href = anchor["href"]
        booking_match = _BOOKING_HREF.search(href)
        if not booking_match:
            continue
        container = _nearest_container(anchor)
        context = _movie_context(anchor, container)
        if context is None:
            continue
        raw_time = _session_time(anchor, container)
        if not raw_time:
            continue
        showtime_id = booking_match.group(1)
        hall = _hall_type(anchor, container)
        status = _status(anchor, container, has_booking=True)
        seats = _seat_count(anchor, container)
        date_value = _session_date(href, default_date)
        showtime = Showtime(
            provider="vox",
            branch_id=branch_id,
            date=date_value,
            movie_id=context.movie_id,
            movie_name=context.name,
            time=raw_time,
            hall_type=hall,
            status=status,
            seats_available=seats,
            booking_url=urljoin(BASE_URL, href),
            showtime_id=showtime_id,
        )
        sessions.setdefault(showtime.key + "|" + context.movie_id, showtime)

    if not booking_anchors:
        # Fallback for pages that list sessions without a booking link yet.
        candidates = soup.find_all(
            lambda tag: (
                tag.name in {"a", "button", "li", "div", "span"}
                and any(
                    token in " ".join(tag.get("class", [])).lower()
                    for token in ("session", "showtime", "performance")
                )
            )
        )
        for node in candidates:
            raw_time = _session_time(node, node)
            if not raw_time:
                continue
            context = _movie_context(node, _nearest_container(node))
            if context is None:
                continue
            hall = _hall_type(node, node)
            showtime = Showtime(
                provider="vox",
                branch_id=branch_id,
                date=default_date,
                movie_id=context.movie_id,
                movie_name=context.name,
                time=raw_time,
                hall_type=hall,
                status=_status(node, node, has_booking=False),
                seats_available=_seat_count(node, node),
            )
            sessions.setdefault(showtime.key + "|" + context.movie_id, showtime)

    if not sessions and not _looks_like_no_showtimes(soup):
        text = soup.get_text(" ", strip=True)
        if len(text) > 200 and ("showtimes" in text.lower() or "movies" in text.lower()):
            # A real page with no sessions is fine; a page that looks nothing
            # like VOX is not.  Callers fall back to cache on the exception.
            logger.debug("No sessions parsed for %s %s", branch_id, default_date)
    return sorted(sessions.values(), key=lambda s: (s.movie_name, s.time, s.hall_type))


# ---------------------------------------------------------------------------
# Parsing internals
# ---------------------------------------------------------------------------


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _attr(node: Any, name: str) -> str:
    if node is None:
        return ""
    try:
        return _clean_text(node.get(name) or "")
    except Exception:
        return ""


def _nearest_container(node: Any) -> Any:
    current = node
    for _ in range(6):
        if current is None:
            return node
        if getattr(current, "name", None) in {"article", "section", "li"}:
            return current
        current = current.parent
    return node


def _movie_context(element: Any, container: Any) -> _MovieContext | None:
    current = element
    for _ in range(8):
        if current is None:
            break
        movie_id = _attr(current, "data-movie-id") or _attr(current, "data-movie")
        movie_name = _attr(current, "data-movie-name")
        slug_attr = _attr(current, "data-slug") or _attr(current, "data-identifier")
        link = current.find("a", href=_MOVIE_HREF) or current.find("a", href=_SHOWTIME_MOVIE_HREF)
        slug = slug_attr
        if link is not None:
            match = _MOVIE_HREF.search(link["href"]) or _SHOWTIME_MOVIE_HREF.search(link["href"])
            slug = (match.group(1) if match else "") or slug_attr
        if slug or movie_id:
            # Prefer the real <h2> title over generic link labels such as
            # "Info", which VOX puts inside the movie hero.
            name = movie_name or _movie_title(current, link)
            if not name and container is not None:
                name = _movie_title(container)
            return _MovieContext(
                movie_id=movie_id or _movie_id(current, slug) or slug,
                name=name or slug.replace("-", " ").title() or "فيلم",
                slug=slug,
            )
        current = current.parent

    # Last resort: nearest previous movie link in the document.
    if container is not None:
        previous = container.find_previous("a", href=_MOVIE_HREF)
        if previous is not None:
            match = _MOVIE_HREF.search(previous["href"])
            slug = match.group(1) if match else ""
            name = _movie_title(container) or slug.replace("-", " ").title()
            return _MovieContext(_movie_id(container, slug) or slug, name or "فيلم", slug)
    return None


def _movie_id(container: Any, slug: str) -> str:
    if container is None:
        return slug
    for name in ("data-movie-id", "data-movie", "data-id"):
        value = _attr(container, name)
        if value and (value.startswith("HO") or name == "data-movie-id"):
            return value
    match = _MOVIE_ID_RE.search(str(container)[:20000])
    if match:
        return match.group(0)
    return slug


def _without_scraped_posters(movies: Iterable[Movie]) -> list[Movie]:
    """Drop cinema-hosted artwork; official posters come from TMDB only."""

    return [replace(movie, poster_url=None) for movie in movies]


def _poster(container: Any) -> str | None:
    if container is None:
        return None
    image = container.find("img")
    if image is None:
        return None
    src = _attr(image, "src") or _attr(image, "data-src")
    if not src:
        return None
    return urljoin(BASE_URL, src)


def _jsonld_movie(soup: BeautifulSoup) -> dict[str, Any]:
    """Return the first JSON-LD ``Movie`` object on the page."""

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        stack: list[Any] = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            elif isinstance(graph, dict):
                stack.append(graph)
            types = item.get("@type")
            if types == "Movie" or (isinstance(types, list) and "Movie" in types):
                return item
    return {}


def _meta_content(soup: BeautifulSoup, key: str) -> str:
    node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return _attr(node, "content")


def _first_heading(soup: BeautifulSoup) -> str:
    node = soup.find("h1") or soup.find("h2")
    return _clean_text(node.get_text(" ")) if node is not None else ""


def _strip_site_suffix(name: str) -> str:
    for separator in (" | ", " – ", " - "):
        if separator in name:
            head = name.split(separator, 1)[0].strip()
            if head:
                return head
    return name


def _jsonld_image(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            found = _jsonld_image(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        return _jsonld_image(value.get("url") or value.get("contentUrl"))
    return None


def _duration_minutes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    text = str(value).strip()
    if not text:
        return None
    if text.upper().startswith("P"):
        match = _ISO_DURATION_RE.match(text)
        if match:
            total = int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
            return total or None
    return _duration_from_text(text)


def _duration_from_text(text: str) -> int | None:
    if not text:
        return None
    hours = re.search(r"(\d+)\s*(?:h|hr|hrs|hours?|ساعة|ساعات)\b", text, re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*(?:m|min|mins|minutes?|دقيقة|دقائق)\b", text, re.IGNORECASE)
    if hours or minutes:
        return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)
    return None


def _rating_from_text(text: str) -> str | None:
    for token in _RATINGS:
        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])",
            text or "",
            re.IGNORECASE,
        ):
            return token
    return None


_LANGUAGES = {
    "en": "English",
    "eng": "English",
    "english": "English",
    "الإنجليزية": "الإنجليزية",
    "الانجليزية": "الإنجليزية",
    "انجليزي": "English",
    "ar": "العربية",
    "ara": "العربية",
    "arabic": "العربية",
    "العربية": "العربية",
    "عربي": "العربية",
    "fr": "Français",
    "fre": "Français",
    "fra": "Français",
    "french": "Français",
    "الفرنسية": "الفرنسية",
    "hi": "Hindi",
    "hin": "Hindi",
    "hindi": "Hindi",
    "الهندية": "الهندية",
    "ur": "Urdu",
    "urdu": "Urdu",
}


def _language_label(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            found = _language_label(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        return _language_label(value.get("name") or value.get("alternateName"))
    text = _clean_text(str(value or ""))
    if not text:
        return None
    return _LANGUAGES.get(text.lower()) or _LANGUAGES.get(text)


def _language_from_soup(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    for label in ("Language", "اللغة", "Dialect", "اللهجة"):
        match = re.search(
            rf"{label}\s*[:\-–]?\s*([A-Za-z\u0600-\u06FF ]{{2,30}})",
            text,
            re.IGNORECASE,
        )
        if match:
            found = _language_label(match.group(1).strip())
            if found:
                return found
    for node in soup.select("[data-language], .tag, .language"):
        value = _attr(node, "data-language") or _clean_text(node.get_text(" "))
        found = _language_label(value)
        if found:
            return found
    return None


def _safe_http_url(value: object) -> str | None:
    text = _clean_text(str(value or ""))
    if not text:
        return None
    absolute = urljoin(BASE_URL, text)
    if not absolute.lower().startswith(("http://", "https://")):
        return None
    return absolute


def _normalise_trailer(url: str) -> str:
    """Turn YouTube embed/short links into a normal watch link."""

    match = re.search(
        r"(?:youtube\.com/(?:embed/|shorts/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{6,})",
        url,
    )
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url


def _trailer_url(value: Any) -> str | None:
    if isinstance(value, str):
        found = _safe_http_url(value)
        return _normalise_trailer(found) if found else None
    if isinstance(value, list):
        for item in value:
            found = _trailer_url(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        for key in ("contentUrl", "embedUrl", "url"):
            found = _trailer_url(value.get(key))
            if found:
                return found
    return None


def _trailer_from_soup(soup: BeautifulSoup) -> str | None:
    for key in ("og:video", "og:video:url", "twitter:player"):
        found = _safe_http_url(_meta_content(soup, key))
        if found:
            return _normalise_trailer(found)
    for node in soup.find_all(["iframe", "a"]):
        url = _safe_http_url(node.get("src") or node.get("href") or "")
        if url and any(host in url for host in ("youtube.", "youtu.be", "vimeo.")):
            return _normalise_trailer(url)
    return None


def _session_time(element: Any, container: Any) -> str | None:
    for node in (element, container):
        if node is None:
            continue
        for name in ("data-time", "data-start", "data-showtime"):
            value = _attr(node, name)
            if value:
                parsed = normalize_time(value)
                if parsed:
                    return parsed
        time_node = node.find("time") if hasattr(node, "find") else None
        if time_node is not None:
            parsed = normalize_time(time_node.get_text(" "))
            if parsed:
                return parsed
    for node in (element, container):
        if node is None:
            continue
        parsed = normalize_time(node.get_text(" "))
        if parsed:
            return parsed
    return None


def _hall_for_session(item: Any, element: Any) -> str:
    """Find the hall label (e.g. <strong>IMAX</strong>) that groups a session."""

    current = item.parent if item is not None else None
    for _ in range(6):
        if current is None or getattr(current, "name", None) in {
            "article",
            "section",
            "body",
            "main",
        }:
            break
        strong = current.find("strong", recursive=False)
        if strong is not None:
            found = _format_from_text(strong.get_text(" "))
            if found:
                return found
        current = current.parent
    return _hall_type(element, item)


def _session_status(element: Any, has_booking: bool) -> str:
    classes = " ".join(element.get("class", []) if hasattr(element, "get") else []).lower()
    aria = str(element.get("aria-disabled", "")).lower() if hasattr(element, "get") else ""
    haystack = f"{classes} {aria}"
    if any(token in haystack for token in ("sold", "full")):
        return SOLD_OUT
    if any(token in haystack for token in ("unavailable", "disabled", "not-available")):
        # VOX only renders a session once its day is on sale.  A grey
        # "unavailable" session therefore means every seat is booked, not
        # that booking has not opened yet.  A day with no sessions at all is
        # the "not open yet" case, and is handled at the day/movie level.
        return SOLD_OUT
    return AVAILABLE if has_booking else NOT_AVAILABLE


def _hall_type(element: Any, container: Any) -> str:
    for node in (element, container):
        if node is None:
            continue
        for name in ("data-format", "data-hall", "data-experience", "data-screen"):
            value = _attr(node, name)
            if value:
                return _normalise_format(value)
        classes = " ".join(node.get("class", []) if hasattr(node, "get") else [])
        found = _format_from_text(classes)
        if found:
            return found
        found = _format_from_text(node.get_text(" "))
        if found:
            return found
    return "Standard"


def _normalise_format(value: str) -> str:
    upper = value.upper()
    for token in _FORMATS:
        if token in upper:
            return _FORMAT_DISPLAY.get(token, token.title())
    return value.strip().title() or "Standard"


def _format_from_text(text: str) -> str | None:
    upper = (text or "").upper()
    for token in _FORMATS:
        if re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", upper):
            return _FORMAT_DISPLAY.get(token, token.title())
    return None


def _status(element: Any, container: Any, has_booking: bool) -> str:
    for node in (element, container):
        if node is None:
            continue
        value = _attr(node, "data-status").upper()
        if value:
            if "SOLD" in value or "FULL" in value:
                return SOLD_OUT
            if "AVAILABLE" in value or "BOOK" in value:
                return AVAILABLE
            if "NOT" in value or "UNAVAILABLE" in value:
                return NOT_AVAILABLE
        classes = " ".join(node.get("class", []) if hasattr(node, "get") else []).lower()
        text = node.get_text(" ").lower() if hasattr(node, "get_text") else ""
        haystack = f"{classes} {text}"
        if any(token in haystack for token in ("sold out", "sold-out", "full", "كامل", "نفد")):
            return SOLD_OUT
        if any(
            token in haystack for token in ("unavailable", "disabled", "not bookable", "لسه مفتحش")
        ):
            return NOT_AVAILABLE
    return AVAILABLE if has_booking else NOT_AVAILABLE


def _seat_count(element: Any, container: Any) -> int | None:
    for node in (element, container):
        if node is None:
            continue
        for name in ("data-seats", "data-seats-available", "data-available"):
            value = _attr(node, name)
            if value.isdigit():
                return int(value)
    for node in (element, container):
        if node is None:
            continue
        match = _SEATS_RE.search(node.get_text(" ") if hasattr(node, "get_text") else "")
        if match:
            return int(match.group(1))
    return None


def _session_date(href: str, default: str) -> str:
    match = _DATE_PARAM.search(href)
    return from_vox_date(match.group(1)) if match else default


def _looks_like_no_showtimes(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ", strip=True).lower()
    return any(
        phrase in text
        for phrase in (
            "no showtimes",
            "no sessions",
            "no movies",
            "لا توجد حفلات",
            "لا توجد عروض",
        )
    )
