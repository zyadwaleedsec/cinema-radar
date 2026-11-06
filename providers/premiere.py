"""Premiere Cinemas Egypt provider.

Premiere's public site is a Next.js application that talks to its own JSON API.
The API is protected by a bearer token that is embedded in the public layout
bundle, so no account or private key is involved.  The useful endpoints are:

* ``GET /api/v1/hybrid/get-now-showing-movies?lang_id=1``
  every film, its playable dates and the branches it plays at;
* ``GET /api/v1/hybrid/get-movie-show-times/<movie>?fromDate=YYYY-MM-DD&lang_id=1``
  every session for one film and day, grouped by branch.  One request covers
  all five branches, which is why this provider advertises
  :attr:`showtimes_per_movie`;
* ``GET /api/v1/hybrid/get-movie-show-dates/<movie>?cinema_id=N``
  the playable days for one film at one branch (not needed for the normal
  flow because the listing already carries dates).

The API returns plain JSON when ``x-web-security`` is omitted.  If it ever
starts returning ``{"encryptedData": ...}`` instead, the contract has changed:
the provider latches off, reports a parse failure once and raises, rather than
turning an outage into empty showtimes and false alerts.

Premiere publishes experience names as they are (``PREMIUM``, ``LUXE``,
``CineComfort``, ``Plus``, ``MAX``, ``MX4D``, ``Standard``); they are kept
verbatim.  There are no seat counts and no sold-out flag, so
``seats_available`` stays ``None`` and a listed session is ``AVAILABLE``.
Booking and seat-map pages are never opened.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import replace
from datetime import date as date_cls
from typing import Any
from urllib.parse import quote, urljoin

from cache import (
    Cache,
    branches_key,
    coming_soon_key,
    dates_key,
    day_snapshot_key,
    movie_details_key,
    movie_showtimes_key,
    movies_key,
    overview_key,
)
from config import Settings
from http_client import HttpClient, UpstreamError
from models import AVAILABLE, Branch, BranchOverview, Movie, Showtime
from providers.base import CinemaProvider
from timeutil import today_iso

logger = logging.getLogger(__name__)

BASE_URL = "https://premiere-cinemas.com"
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
LAYOUT_RE = re.compile(r"/_next/static/chunks/app/[^\"']*?layout-[a-f0-9]+\.js")
ANY_LAYOUT_RE = re.compile(r"/[^\"']*layout-[a-f0-9]+\.js")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(am|pm)?", re.IGNORECASE)

#: Branch ids used by the public API.  The names are stable across releases;
#: keeping them locally means the cinema picker still works during an outage.
_FALLBACK_BRANCHES = (
    Branch("1", "Nile Cinema", "premiere"),
    Branch("2", "Premiere Plaza", "premiere"),
    Branch("3", "Galaxy elManial", "premiere"),
    Branch("4", "Premiere Point90", "premiere"),
    Branch("5", "Cima Arkan", "premiere"),
)

#: Re-reading the listing is cheap, but discovery asks every branch in one
#: pass.  Within this window a forced read still shares the first response.
_LISTING_FORCE_MIN_AGE = 90.0


def normalize_time(raw: object) -> str | None:
    """Return ``HH:MM`` for ``15:30`` / ``3:30 PM``; ``None`` if unreadable."""

    match = _TIME_RE.search(str(raw or ""))
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = (match.group(3) or "").lower()
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _iso_day(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text[:10]
    try:
        return date_cls.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return None


def _show_dates(record: dict[str, Any]) -> list[str]:
    raw = record.get("show_dates")
    if isinstance(raw, str):
        values: Iterable[Any] = raw.split(",")
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        return []
    days = {_iso_day(value) for value in values}
    return sorted(day for day in days if day)


def _branch_ids(record: dict[str, Any]) -> set[str]:
    raw = record.get("schdeuled_cinema_list")
    if isinstance(raw, str):
        values: Iterable[Any] = raw.split(",")
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def _records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    records = payload.get("Records")
    if isinstance(records, dict):
        records = records.get("data") or records.get("records") or []
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def _first_text(values: Any) -> str | None:
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                text = _clean(item.get("rating") or item.get("trailer_link") or item.get("url"))
            else:
                text = _clean(item)
            if text:
                return text
    text = _clean(values)
    return text or None


def _poster_url(record: dict[str, Any]) -> str | None:
    # Premiere artwork is intentionally ignored: posters come from TMDB only.
    return None


def _movie_from_record(record: dict[str, Any]) -> Movie | None:
    movie_id = _clean(record.get("movie_unique_identifier") or record.get("movie_id"))
    if not movie_id:
        return None
    title = _clean(record.get("movie_title")) or movie_id
    runtime = record.get("movie_runtime")
    try:
        duration = int(runtime) if runtime not in (None, "") else None
    except (TypeError, ValueError):
        duration = None
    return Movie(
        id=movie_id,
        name=title,
        slug=movie_id,
        provider="premiere",
        poster_url=_poster_url(record),
        duration_minutes=duration,
        rating=_first_text(record.get("ratings")),
        language=_clean(record.get("lang_name")) or None,
        synopsis=_clean(record.get("movie_plot")) or None,
        trailer_url=_first_text(record.get("trailer_links")),
        release_date=None,
    )


def parse_movies(records: Iterable[dict[str, Any]]) -> list[Movie]:
    """Collapse repeated listing rows into one ``Movie`` per picture."""

    found: dict[str, Movie] = {}
    for record in records:
        movie = _movie_from_record(record)
        if movie is not None:
            found.setdefault(movie.id, movie)
    return list(found.values())


def parse_coming_soon(records: Iterable[dict[str, Any]], today: str) -> list[Movie]:
    """Titles whose first playable day is after *today*.

    The listing mixes current releases (dates start today or earlier) with
    advance bookings (Hadoota, Avengers, Dune 3...).  The first ``show_date``
    is the release day the picker must start from, not the marketing
    ``movie_release_date``.
    """

    found: dict[str, Movie] = {}
    for record in records:
        movie = _movie_from_record(record)
        if movie is None:
            continue
        dates = [day for day in _show_dates(record) if day >= today]
        if not dates or dates[0] <= today:
            continue
        found.setdefault(movie.id, replace(movie, release_date=dates[0]))
    return sorted(found.values(), key=lambda movie: (movie.release_date or "", movie.name))


def parse_showtimes(payload: Any) -> list[Showtime]:
    """Flatten every branch's sessions from one movie/day response."""

    found: dict[tuple[str, str], Showtime] = {}
    for cinema in _records(payload):
        branch_id = str(cinema.get("cinema_id") or "").strip()
        branch_name = _clean(cinema.get("cinema_name"))
        groups = cinema.get("cinemaShowTimes")
        if not isinstance(groups, list):
            groups = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            items = group.get("movieDetailsData")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                branch = str(item.get("cinema_id") or branch_id).strip()
                if not branch:
                    continue
                time_value = normalize_time(item.get("ss_start_time"))
                if not time_value:
                    continue
                actual_day = (
                    _iso_day(item.get("ss_actual_start_date"))
                    or _iso_day(item.get("ss_start_date"))
                    or ""
                )
                if not actual_day:
                    continue
                experience = _clean(item.get("movie_experience")) or "Standard"
                screen_format = _clean(item.get("mf_name"))
                hall = experience
                if screen_format.upper().startswith("3D") and "3D" not in hall.upper():
                    hall = f"{hall} 3D"
                showtime_id = _clean(item.get("ss_id")) or (
                    f"{branch}:{actual_day}:{time_value}:{hall}:{_clean(item.get('screen_name'))}"
                )
                key = (branch, showtime_id)
                found.setdefault(
                    key,
                    Showtime(
                        provider="premiere",
                        branch_id=branch,
                        date=actual_day,
                        movie_id=_clean(
                            item.get("movie_unique_identifier") or item.get("movie_id")
                        ),
                        movie_name=_clean(item.get("movie_title")) or branch_name,
                        time=time_value,
                        hall_type=hall,
                        status=AVAILABLE,
                        seats_available=None,
                        booking_url=None,
                        showtime_id=showtime_id,
                    ),
                )
    return sorted(found.values(), key=lambda s: (s.date, s.time, s.hall_type))


def _merge_showtimes(showtimes: Iterable[Showtime]) -> list[Showtime]:
    found: dict[tuple[str, str], Showtime] = {}
    for showtime in showtimes:
        key = (
            showtime.branch_id,
            showtime.showtime_id or f"{showtime.date}:{showtime.time}:{showtime.hall_type}",
        )
        found.setdefault(key, showtime)
    return sorted(found.values(), key=lambda s: (s.date, s.time, s.hall_type))


class PremiereProvider(CinemaProvider):
    name = "premiere"
    showtimes_per_movie = True

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
        self.base_url = settings.premiere_base_url.rstrip("/")
        self.api_url = settings.premiere_api_url.rstrip("/")
        self._encrypted = False
        self._token_lock = asyncio.Lock()

    async def get_movie_poster(self, movie: Movie) -> str | None:
        if self.posters is None:
            return None
        return await self.posters.url(movie.name)

    async def _official_poster(self, movie: Movie) -> Movie:
        return replace(movie, poster_url=await self.get_movie_poster(movie))

    # ------------------------------------------------------------------ public
    async def get_branches(self, force_refresh: bool = False) -> list[Branch]:
        key = branches_key(self.name)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_static_ttl)
            if cached:
                return [Branch(**item) for item in cached]
        branches = list(_FALLBACK_BRANCHES)
        await self.cache.put_json(
            key, [branch.__dict__ for branch in branches], self.settings.cache_static_ttl
        )
        return branches

    async def get_dates(self, branch_id: str, force_refresh: bool = False) -> list[str]:
        key = dates_key(self.name, branch_id)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return list(cached)
        try:
            records = await self._listing(force_refresh=force_refresh)
        except UpstreamError:
            if force_refresh:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            return list(stale) if stale else []
        except Exception:
            logger.exception("Could not read Premiere dates for %s", branch_id)
            stale = await self.cache.get_json(key, allow_stale=True)
            return list(stale) if stale else []
        today = today_iso(self.settings.timezone)
        dates: set[str] = set()
        for record in records:
            if branch_id not in _branch_ids(record):
                continue
            dates.update(day for day in _show_dates(record) if day >= today)
        values = sorted(dates)
        await self.cache.put_json(key, values, self.settings.cache_listings_ttl)
        return values

    async def get_movies(
        self, branch_id: str, date: str, force_refresh: bool = False
    ) -> list[Movie]:
        key = movies_key(self.name, branch_id, date)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return [Movie(**item) for item in cached]
        try:
            records = await self._listing(force_refresh=force_refresh)
        except UpstreamError:
            if force_refresh:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            return [Movie(**item) for item in stale] if stale else []
        except Exception:
            logger.exception("Could not read Premiere movies for %s %s", branch_id, date)
            stale = await self.cache.get_json(key, allow_stale=True)
            return [Movie(**item) for item in stale] if stale else []
        movies = parse_movies(
            record
            for record in records
            if branch_id in _branch_ids(record) and date in _show_dates(record)
        )
        await self.cache.put_json(
            key, [movie.__dict__ for movie in movies], self.settings.cache_listings_ttl
        )
        return movies

    async def get_showtimes(
        self,
        branch_id: str,
        date: str,
        movie_id: str | None = None,
        force_refresh: bool = False,
        ttl: float | None = None,
    ) -> list[Showtime]:
        if not movie_id:
            # A whole-day request would need one call per movie.  Every caller
            # in the bot passes a movie for this provider; returning nothing is
            # safer than firing twenty upstream requests.
            logger.debug("Premiere showtimes need a movie id (%s %s)", branch_id, date)
            return []
        resolved = await self._resolve_movie_id(movie_id)
        showtimes = await self._fetch_movie_showtimes(
            resolved, date, force_refresh=force_refresh, ttl=ttl
        )
        if branch_id:
            showtimes = [item for item in showtimes if item.branch_id == branch_id]
        return showtimes

    async def get_branch_overview(
        self, branch_id: str, force_refresh: bool = False
    ) -> BranchOverview:
        key = overview_key(self.name, branch_id)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.premiere_snapshot_ttl)
            if cached:
                return self._overview_from_dict(cached)
        branches = await self.get_branches()
        branch = next(
            (item for item in branches if item.id == branch_id),
            Branch(branch_id, branch_id, self.name),
        )
        try:
            dates = await self.get_dates(branch_id, force_refresh=force_refresh)
        except UpstreamError:
            if force_refresh:
                raise
            cached = await self.cache.get_json(key, allow_stale=True)
            if cached:
                return self._overview_from_dict(cached)
            return BranchOverview(branch=branch)
        primary = dates[0] if dates else None
        movies: list[Movie] = []
        showtimes: list[Showtime] = []
        if primary:
            try:
                movies = await self.get_movies(branch_id, primary)
                snapshot = await self._day_snapshot(primary)
                showtimes = [item for item in snapshot if item.branch_id == branch_id]
            except UpstreamError:
                if force_refresh:
                    raise
                cached = await self.cache.get_json(key, allow_stale=True)
                if cached:
                    return self._overview_from_dict(cached)
                return BranchOverview(branch=branch, dates=tuple(dates), fetched_date=primary)
        overview = BranchOverview(
            branch=branch,
            dates=tuple(dates),
            movies=tuple(movies),
            showtimes=tuple(showtimes),
            fetched_date=primary,
        )
        await self.cache.put_json(
            key, self._overview_to_dict(overview), self.settings.premiere_snapshot_ttl
        )
        return overview

    async def get_coming_soon(self, force_refresh: bool = False) -> list[Movie]:
        key = coming_soon_key(self.name)
        ttl = self.settings.cache_coming_soon_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached is not None:
                return [Movie(**item) for item in cached]
        try:
            records = await self._listing(force_refresh=force_refresh)
        except Exception:
            logger.exception("Could not fetch Premiere coming soon")
            stale = await self.cache.get_json(key, allow_stale=True)
            return [Movie(**item) for item in stale] if stale else []
        movies = parse_coming_soon(records, today_iso(self.settings.timezone))
        await self.cache.put_json(key, [movie.__dict__ for movie in movies], ttl)
        return movies

    async def get_movie_details(self, movie: Movie, force_refresh: bool = False) -> Movie:
        key = movie_details_key(self.name, movie.slug or movie.id)
        ttl = self.settings.cache_movie_details_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached:
                merged = {**movie.__dict__}
                merged.update(
                    {name: value for name, value in cached.items() if value not in (None, "")}
                )
                return await self._official_poster(Movie(**merged))
        try:
            records = await self._listing()
            record = next(
                (
                    item
                    for item in records
                    if _clean(item.get("movie_unique_identifier") or item.get("movie_id"))
                    in {movie.id, movie.slug}
                ),
                None,
            )
            if record is None:
                return await self._official_poster(movie)
            details = _movie_from_record(record)
            if details is None:
                return await self._official_poster(movie)
            details = replace(
                details,
                name=movie.name or details.name,
                id=movie.id or details.id,
                slug=movie.slug or details.slug,
            )
        except Exception:
            logger.warning("Could not fetch Premiere movie details for %s", movie.id)
            return await self._official_poster(movie)
        details = await self._official_poster(details)
        await self.cache.put_json(
            key,
            {
                "duration_minutes": details.duration_minutes,
                "rating": details.rating,
                "language": details.language,
                "synopsis": details.synopsis,
                "trailer_url": details.trailer_url,
            },
            ttl,
        )
        return details

    # --------------------------------------------------------------- upstream
    async def _token(self, force_refresh: bool = False) -> str:
        key = f"{self.name}:token"
        ttl = self.settings.premiere_token_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached:
                return str(cached)
        # Discovery builds a whole-day snapshot with one request per movie.  A
        # lock keeps those parallel calls from each re-reading the bundle.
        async with self._token_lock:
            if not force_refresh:
                cached = await self.cache.get_json(key, ttl=ttl)
                if cached:
                    return str(cached)
            token = await self._download_token(force_refresh, ttl)
            await self.cache.put_json(key, token, ttl)
            return token

    async def _download_token(self, force_refresh: bool, ttl: float) -> str:
        home_url = f"{self.base_url}/"
        token_key = f"{self.name}:token"
        try:
            home = await self.http.get(
                home_url,
                f"{self.name}:token-home",
                ttl,
                force_refresh=force_refresh,
                target_key=token_key,
                allow_stale=not force_refresh,
                # Premiere's edge tarpits the shared client's browser-shaped
                # Accept header (it contains application/xml + */*); a plain
                # text/html request is served normally.
                headers={"Accept": "text/html"},
            )
            html = home.text or ""
            paths = LAYOUT_RE.findall(html) or ANY_LAYOUT_RE.findall(html)
            if not paths:
                raise ValueError("layout bundle not found")
            layout_url = urljoin(self.base_url, paths[-1])
            bundle = await self.http.get(
                layout_url,
                f"{self.name}:token-bundle",
                ttl,
                force_refresh=force_refresh,
                target_key=token_key,
                allow_stale=not force_refresh,
                headers={"Accept": "*/*"},
            )
            match = JWT_RE.search(bundle.text or "")
            if not match:
                raise ValueError("bearer token not found in layout bundle")
        except UpstreamError:
            # The HTTP layer already recorded this failure against
            # ``premiere:token``, so the admin alert names Premiere correctly.
            raise
        except Exception as exc:
            logger.exception("Could not read the Premiere bearer token")
            await self.http.report_failure("parse", token_key, home_url)
            raise UpstreamError(
                f"Premiere token unavailable: {exc}", reason="parse", url=home_url
            ) from exc
        return match.group(0)

    async def _api_json(
        self,
        path: str,
        *,
        ttl: float,
        force_refresh: bool = False,
        target_key: str | None = None,
    ) -> dict[str, Any]:
        if self._encrypted:
            raise UpstreamError(
                "Premiere API encrypted its responses; provider is stopped",
                reason="parse",
                url=f"{self.api_url}{path}",
            )
        url = f"{self.api_url}{path}"
        token = await self._token()
        try:
            payload = await self._api_once(
                url,
                path,
                token,
                ttl=ttl,
                force_refresh=force_refresh,
                target_key=target_key,
            )
        except UpstreamError as exc:
            if exc.status_code not in {401, 403}:
                raise
            token = await self._token(force_refresh=True)
            payload = await self._api_once(
                url,
                path,
                token,
                ttl=ttl,
                force_refresh=True,
                target_key=target_key,
            )
        return payload

    async def _api_once(
        self,
        url: str,
        path: str,
        token: str,
        *,
        ttl: float,
        force_refresh: bool,
        target_key: str | None,
    ) -> dict[str, Any]:
        result = await self.http.get(
            url,
            f"{self.name}:api:{path}",
            ttl,
            force_refresh=force_refresh,
            target_key=target_key,
            allow_stale=not force_refresh,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
            },
        )
        text = result.text or ""
        if not text:
            await self.http.report_failure("empty", target_key, url)
            raise UpstreamError("Empty Premiere response", reason="parse", url=url)
        try:
            payload = json.loads(text)
        except (TypeError, ValueError) as exc:
            await self.http.report_failure("parse", target_key, url)
            raise UpstreamError(
                "Premiere returned a non-JSON response", reason="parse", url=url
            ) from exc
        if not isinstance(payload, dict):
            await self.http.report_failure("parse", target_key, url)
            raise UpstreamError("Unexpected Premiere payload", reason="parse", url=url)
        if "encryptedData" in payload:
            if not self._encrypted:
                self._encrypted = True
                logger.error(
                    "Premiere switched to encrypted responses; stopping the provider "
                    "instead of reporting empty showtimes"
                )
                await self.http.report_failure("parse", target_key, url)
            raise UpstreamError(
                "Premiere API encrypted its responses; provider is stopped",
                reason="parse",
                url=url,
            )
        if payload.get("status") is False:
            message = _clean(payload.get("message") or payload.get("error"))
            if not payload.get("Records") and (
                "no " in message.lower() or "not found" in message.lower()
            ):
                return payload
            await self.http.report_failure("parse", target_key, url)
            raise UpstreamError(
                f"Premiere API error: {message or 'unknown'}", reason="parse", url=url
            )
        return payload

    async def _listing(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        key = f"{self.name}:listing"
        ttl = self.settings.cache_listings_ttl
        entry = await self.cache.get(key, allow_stale=True)
        if (
            entry is not None
            and entry.age() < ttl
            and (not force_refresh or entry.age() < _LISTING_FORCE_MIN_AGE)
        ):
            try:
                return _records(entry.json())
            except (TypeError, ValueError):
                pass
        payload = await self._api_json(
            "/api/v1/hybrid/get-now-showing-movies?lang_id=1",
            ttl=ttl,
            force_refresh=force_refresh,
            target_key=f"{self.name}:listing",
        )
        return _records(payload)

    async def _resolve_movie_id(self, movie_id: str) -> str:
        """Accept the numeric ``movie_id`` of older watches as well."""

        value = str(movie_id or "").strip()
        if not value or not value.isdigit():
            return value
        try:
            records = await self._listing()
        except Exception:
            return value
        for record in records:
            if str(record.get("movie_id") or "") == value:
                unique = _clean(record.get("movie_unique_identifier"))
                if unique:
                    return unique
        return value

    async def _fetch_movie_showtimes(
        self,
        movie_id: str,
        date: str,
        *,
        force_refresh: bool = False,
        ttl: float | None = None,
    ) -> list[Showtime]:
        key = movie_showtimes_key(self.name, date, movie_id)
        cache_ttl = self.settings.premiere_showtimes_ttl if ttl is None else ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=cache_ttl)
            if cached is not None:
                return [Showtime.from_dict(item) for item in cached]
        path = (
            f"/api/v1/hybrid/get-movie-show-times/{quote(movie_id, safe='.-_~')}"
            f"?fromDate={quote(date, safe='-')}&lang_id=1"
        )
        try:
            payload = await self._api_json(
                path,
                ttl=cache_ttl,
                force_refresh=force_refresh,
                target_key=f"{self.name}:{date}:{movie_id}",
            )
            showtimes = parse_showtimes(payload)
        except UpstreamError:
            # An encrypted response is a contract change, not a transient
            # failure: never hide it behind stale/empty data.
            if force_refresh or self._encrypted:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            return [Showtime.from_dict(item) for item in stale] if stale else []
        except Exception as exc:
            logger.exception("Could not parse Premiere showtimes for %s %s", movie_id, date)
            if force_refresh:
                await self.http.report_failure("parse", f"{self.name}:{date}:{movie_id}")
                raise UpstreamError(
                    f"Parse error: {exc}", reason="parse", url=f"{self.api_url}{path}"
                ) from exc
            stale = await self.cache.get_json(key, allow_stale=True)
            return [Showtime.from_dict(item) for item in stale] if stale else []
        await self.cache.put_json(key, [item.to_dict() for item in showtimes], cache_ttl)
        return showtimes

    async def _day_snapshot(self, date: str) -> list[Showtime]:
        """Every movie's sessions on *date*, all branches, shared by discovery.

        The response for one movie already covers all five branches, so five
        branch overviews cost one batch instead of five.  A partial batch is
        treated as an error: committing half a day would look like sessions
        disappeared and later trigger false alerts.
        """

        key = day_snapshot_key(self.name, date)
        cached = await self.cache.get_json(key, ttl=self.settings.premiere_snapshot_ttl)
        if cached is not None:
            return [Showtime.from_dict(item) for item in cached]
        records = await self._listing()
        movie_ids: list[str] = []
        for record in records:
            if date not in _show_dates(record):
                continue
            movie_id = _clean(record.get("movie_unique_identifier"))
            if movie_id and movie_id not in movie_ids:
                movie_ids.append(movie_id)
        if not movie_ids:
            await self.cache.put_json(key, [], self.settings.premiere_snapshot_ttl)
            return []
        results = await asyncio.gather(
            *(self._fetch_movie_showtimes(movie_id, date) for movie_id in movie_ids),
            return_exceptions=True,
        )
        collected: list[Showtime] = []
        for movie_id, result in zip(movie_ids, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Premiere snapshot failed for %s %s", movie_id, date)
                if isinstance(result, UpstreamError):
                    raise result
                raise UpstreamError(
                    f"Snapshot failed for {movie_id}: {result}",
                    reason="parse",
                    url=f"{self.api_url}/api/v1/hybrid/get-movie-show-times/{movie_id}",
                ) from result
            collected.extend(result)
        showtimes = _merge_showtimes(collected)
        await self.cache.put_json(
            key, [item.to_dict() for item in showtimes], self.settings.premiere_snapshot_ttl
        )
        return showtimes

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _overview_to_dict(overview: BranchOverview) -> dict[str, Any]:
        return {
            "branch": overview.branch.__dict__,
            "dates": list(overview.dates),
            "movies": [movie.__dict__ for movie in overview.movies],
            "showtimes": [item.to_dict() for item in overview.showtimes],
            "fetched_date": overview.fetched_date,
        }

    @staticmethod
    def _overview_from_dict(data: dict[str, Any]) -> BranchOverview:
        return BranchOverview(
            branch=Branch(**data["branch"]),
            dates=tuple(data.get("dates", ())),
            movies=tuple(Movie(**item) for item in data.get("movies", ())),
            showtimes=tuple(Showtime.from_dict(item) for item in data.get("showtimes", ())),
            fetched_date=data.get("fetched_date"),
        )


__all__ = [
    "PremiereProvider",
    "normalize_time",
    "parse_coming_soon",
    "parse_movies",
    "parse_showtimes",
]
