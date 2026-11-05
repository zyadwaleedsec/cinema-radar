"""Renaissance Cinemas Egypt provider.

The site is server-rendered HTML.  The useful pages are:

* ``/en/cinemas``                          -> branch list
* ``/en/cinemas/<slug>``                   -> ten-day date strip + first day
* ``/en/cinemas/<slug>/DD-MM-YYYY``        -> every movie/session for one day
* ``/en/movie/<slug>``                     -> poster, duration, rating, trailer
* ``/en/coming-soon``                      -> announced releases

The day page is the whole-branch+day endpoint we prefer.  Every session is an
``<a>`` carrying ``data-booking-url`` when it can be booked online, or the
``disabled`` class when online booking is closed (the site then tells the user
to buy at the cinema).  We never open booking or seat-map pages; availability
comes from the public showtimes markup.  Renaissance does not expose seat
counts, so ``seats_available`` stays ``None``.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import replace
from datetime import date as date_cls
from datetime import datetime, timedelta
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
    prebook_dates_key,
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
from timeutil import today_iso

logger = logging.getLogger(__name__)

BASE_URL = "https://rnscinemas.com"
_DATE_IN_HREF = re.compile(r"/(\d{2})-(\d{2})-(\d{4})(?:[/?#]|$)")
_MOVIE_IN_HREF = re.compile(r"/movie/([^/?#]+)")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(am|pm)?", re.IGNORECASE)
_RATING_RE = re.compile(r"Rated\s+([^\s•]+)", re.IGNORECASE)
_DURATION_RE = re.compile(r"(\d+)\s*Mins?", re.IGNORECASE)
_ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")

_FALLBACK_BRANCHES = (
    Branch("san_stephano", "San Stephano", "renaissance"),
    Branch("madinty", "Madinaty", "renaissance"),
    Branch("downtown", "DownTown", "renaissance"),
    Branch("al_rehab", "Al Rehab", "renaissance"),
    Branch("dandy_mall", "Dandy Mall", "renaissance"),
    Branch("semoha", "Semoha", "renaissance"),
    Branch("banha", "Nile View Banha", "renaissance"),
    Branch("al-masrya-plaza-agazig", "Al Masrya Plaza - Zagazig", "renaissance"),
)


def to_rns_date(iso_date: str) -> str:
    try:
        return date_cls.fromisoformat(iso_date).strftime("%d-%m-%Y")
    except (TypeError, ValueError):
        return iso_date


def from_rns_date(raw: str) -> str:
    try:
        return datetime.strptime(raw, "%d-%m-%Y").date().isoformat()
    except (TypeError, ValueError):
        return raw


def _merge_dates(strip: list[str], extra: list[str]) -> list[str]:
    """Union of the branch date strip and bookable pre-book dates, sorted."""

    merged = {d for d in strip if d}
    merged.update(d for d in extra if d)
    return sorted(merged)


def normalize_time(raw: str) -> str | None:
    match = _TIME_RE.search(raw or "")
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


def _raw_key(key: str) -> str:
    return f"raw:{key}"


def _url_part(value: str) -> str:
    return quote(value or "", safe="-_.~")


def _movie_slug(node: Any) -> str:
    href = str(node.get("href") or "") if node is not None else ""
    match = _MOVIE_IN_HREF.search(href)
    return match.group(1) if match else ""


def _without_scraped_posters(movies: Iterable[Movie]) -> list[Movie]:
    """Drop cinema-hosted artwork; official posters come from TMDB only."""

    return [replace(movie, poster_url=None) for movie in movies]


def _poster(node: Any) -> str | None:
    image = node.select_one("img[src]") if node is not None else None
    if image is None:
        return None
    source = str(image.get("src") or "").strip()
    return urljoin(BASE_URL, source) if source else None


def _format_label(heading: Any) -> str:
    """Map a Renaissance experience heading to one canonical label.

    A heading can list several formats (``Regular • Premium • Special``); the
    sessions below it do not say which one applies, so the first label is the
    safest default.  A ``vip`` class on a session overrides it later.
    """

    labels = []
    if heading is not None:
        for item in heading.select(".bullitsdivitem"):
            label = _clean(item.get_text(" "))
            if label and label not in labels:
                labels.append(label)
    if not labels:
        return "Standard"
    first = labels[0].lower()
    if "vip" in first:
        return "VIP"
    if "dbox" in first:
        return "DBOX"
    if "balcone" in first:
        return "Balcone"
    if "premium" in first:
        return "Premium"
    if "special" in first:
        return "Special"
    if "regular" in first or "standard" in first:
        return "Standard"
    return labels[0]


def _is_3d(anchor: Any, text: str) -> bool:
    return str(anchor.get("data-is-3d") or "") == "1" or "(3D)" in text.upper()


_HALL_RANK = {
    "VIP": 6,
    "DBOX": 5,
    "PREMIUM": 4,
    "SPECIAL": 3,
    "BALCONE": 2,
    "STANDARD": 1,
}


def _hall_rank(value: str) -> int:
    head = value.split(" ", 1)[0].upper()
    return _HALL_RANK.get(head, 0)


def parse_branches(html: str) -> list[Branch]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Branch] = {}
    for anchor in soup.select("a.venulink[href]"):
        slug = _clean(str(anchor.get("href") or "").rstrip("/").rsplit("/", 1)[-1])
        if not slug:
            continue
        name_node = anchor.select_one(".venuename")
        name = _clean(name_node.get_text(" ")) if name_node else slug.replace("_", " ").title()
        found.setdefault(
            slug,
            Branch(slug, name or slug, "renaissance", urljoin(BASE_URL, anchor["href"])),
        )
    return list(found.values())


def parse_dates(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    dates: set[str] = set()
    for anchor in soup.select(".eventsDays a[href]"):
        match = _DATE_IN_HREF.search(anchor["href"])
        if match:
            dates.add(from_rns_date(f"{match.group(1)}-{match.group(2)}-{match.group(3)}"))
    return sorted(dates)


def _movie_blocks(soup: BeautifulSoup) -> list[Any]:
    # ``div.showtimes_data`` also wraps the whole row, so anchor on the
    # per-movie wrapper and take its inner data block.
    return soup.select("div.showtimes_location")


def _movie_identity(block: Any) -> tuple[str, str, str | None]:
    data = block.select_one("div.showtimes_data") or block
    link = data.select_one('a[href*="/movie/"]')
    slug = _movie_slug(link)
    name_node = data.select_one(".venuename")
    name = _clean(name_node.get_text(" ")) if name_node else ""
    # The showtime anchors carry the English title explicitly; prefer it over
    # the visible wordmark, which can be Arabic on the English page.
    title_node = data.select_one("a[data-movie-name-en]")
    if title_node is not None:
        name = _clean(title_node.get("data-movie-name-en")) or name
    return slug, name or slug.replace("-", " ").title(), _poster(data)


def parse_movies(html: str) -> list[Movie]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Movie] = {}
    for block in _movie_blocks(soup):
        slug, name, poster = _movie_identity(block)
        if not slug:
            continue
        found.setdefault(slug, Movie(slug, name, slug, "renaissance", poster))
    return list(found.values())


def parse_showtimes(html: str, branch_id: str, date: str) -> list[Showtime]:
    soup = BeautifulSoup(html, "lxml")
    sessions: dict[str, Showtime] = {}
    for block in _movie_blocks(soup):
        data = block.select_one("div.showtimes_data") or block
        slug, movie_name, _ = _movie_identity(block)
        if not slug:
            continue
        for times in data.select("div.show_time_dates"):
            heading = times.find_previous("div", class_="venuenameseats")
            if heading is not None and data not in heading.parents:
                heading = None
            hall = _format_label(heading)
            for item in times.select("ul li"):
                anchor = item.find("a")
                if anchor is None:
                    continue
                text = _clean(anchor.get_text(" "))
                time_value = normalize_time(str(anchor.get("data-event-time") or text))
                if not time_value:
                    continue
                booking = str(anchor.get("data-booking-url") or "").strip()
                classes = anchor.get("class") or []
                disabled = "disabled" in classes or booking.startswith("javascript")
                if disabled:
                    status = SOLD_OUT
                    booking = ""
                elif booking:
                    status = AVAILABLE
                else:
                    status = NOT_AVAILABLE
                suffix = " 3D" if _is_3d(anchor, text) else ""
                session_hall = "VIP" if "vip" in classes else hall
                show_date = date
                if str(anchor.get("data-after-midnight") or "") == "1" and time_value < "12:00":
                    try:
                        show_date = (date_cls.fromisoformat(date) + timedelta(days=1)).isoformat()
                    except (TypeError, ValueError):
                        show_date = date
                showtime_id = booking.rstrip("/").rsplit("/", 1)[-1] if booking else ""
                showtime = Showtime(
                    provider="renaissance",
                    branch_id=branch_id,
                    date=show_date,
                    movie_id=slug,
                    movie_name=_clean(anchor.get("data-movie-name-en")) or movie_name,
                    time=time_value,
                    hall_type=f"{session_hall}{suffix}",
                    status=status,
                    seats_available=None,
                    booking_url=booking or None,
                    showtime_id=showtime_id or f"{slug}:{time_value}:{session_hall}",
                )
                # The site can repeat the same session under several format
                # headings; the booking id is the reliable identity.  Prefer
                # the more specific hall (VIP over Standard) when merging.
                key = booking or f"{slug}|{showtime.key}"
                previous = sessions.get(key)
                if (
                    previous is None
                    or (previous.status != AVAILABLE and status == AVAILABLE)
                    or (
                        previous.status == status
                        and _hall_rank(session_hall) > _hall_rank(previous.hall_type)
                    )
                ):
                    sessions[key] = showtime
    return sorted(sessions.values(), key=lambda s: (s.movie_name, s.time, s.hall_type))


def parse_movie_details(html: str, fallback: Movie) -> Movie:
    soup = BeautifulSoup(html, "lxml")
    data: dict[str, Any] = {}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        items = payload.get("@graph", [payload]) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Movie":
                data = item
                break
        if data:
            break

    extra = soup.select_one(".movie_extra")
    extra_text = _clean(extra.get_text(" ")) if extra else ""
    rating_match = _RATING_RE.search(extra_text)
    duration_match = _DURATION_RE.search(extra_text)
    iso_duration = _ISO_DURATION_RE.fullmatch(str(data.get("duration") or ""))
    duration = None
    if iso_duration:
        duration = int(iso_duration.group(1) or 0) * 60 + int(iso_duration.group(2) or 0)
    elif duration_match:
        duration = int(duration_match.group(1))

    trailer = None
    if extra is not None:
        trailer_node = extra.select_one("a[data-src], a[href^='http']")
        if trailer_node is not None:
            raw_trailer = str(
                trailer_node.get("data-src") or trailer_node.get("href") or ""
            ).strip()
            if raw_trailer.startswith(("http://", "https://")):
                trailer = raw_trailer.replace("/embed/", "/watch?v=")

    poster = data.get("image") or fallback.poster_url
    if isinstance(poster, str) and poster:
        poster = urljoin(BASE_URL, poster)

    return Movie(
        id=fallback.id,
        name=fallback.name or _clean(data.get("name")),
        slug=fallback.slug or fallback.id,
        provider="renaissance",
        poster_url=poster if isinstance(poster, str) else fallback.poster_url,
        duration_minutes=duration or fallback.duration_minutes,
        rating=_clean(rating_match.group(1)) if rating_match else fallback.rating,
        language=fallback.language,
        synopsis=_clean(data.get("description")) or fallback.synopsis,
        trailer_url=trailer or fallback.trailer_url,
        imax_status=fallback.imax_status,
    )


def parse_coming_soon(html: str) -> list[Movie]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Movie] = {}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        items = payload.get("@graph", [payload]) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("@type") != "ItemList":
                continue
            for entry in item.get("itemListElement") or []:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "")
                match = _MOVIE_IN_HREF.search(url)
                if not match:
                    continue
                slug = match.group(1)
                found.setdefault(
                    slug,
                    Movie(
                        slug,
                        _clean(entry.get("name")) or slug.replace("-", " ").title(),
                        slug,
                        "renaissance",
                        str(entry.get("image") or "") or None,
                        synopsis=_clean(entry.get("description")) or None,
                    ),
                )
    return list(found.values())


class RenaissanceProvider(CinemaProvider):
    name = "renaissance"

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
        self.base_url = settings.renaissance_base_url.rstrip("/")

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
                f"{self.base_url}/en/cinemas",
                _raw_key(key),
                self.settings.cache_static_ttl,
                force_refresh,
            )
            branches = parse_branches(html)
        except Exception:
            logger.exception("Could not fetch Renaissance branches; using fallback list")
            stale = await self.cache.get_json(key, allow_stale=True)
            branches = [Branch(**item) for item in stale] if stale else list(_FALLBACK_BRANCHES)
        if not branches:
            branches = list(_FALLBACK_BRANCHES)
        await self.cache.put_json(
            key, [b.__dict__ for b in branches], self.settings.cache_static_ttl
        )
        return branches

    async def get_dates(self, branch_id: str, force_refresh: bool = False) -> list[str]:
        key = dates_key(self.name, branch_id)
        extra = await self._prebook_dates()
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return _merge_dates(cached, extra)
        url = f"{self.base_url}/en/cinemas/{_url_part(branch_id)}"
        try:
            html = await self._fetch(
                url, _raw_key(key), self.settings.cache_listings_ttl, force_refresh
            )
            dates = parse_dates(html)
        except UpstreamError:
            if force_refresh:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            dates = list(stale) if stale else []
        except Exception:
            logger.exception("Could not parse Renaissance dates for %s", branch_id)
            dates = []
        if dates:
            await self.cache.put_json(key, dates, self.settings.cache_listings_ttl)
        return _merge_dates(dates, extra)

    async def _prebook_dates(self) -> list[str]:
        """The cached union of bookable Coming Soon dates (see
        :meth:`refresh_prebook_dates`)."""

        cached = await self.cache.get_json(
            prebook_dates_key(self.name), ttl=self.settings.prebook_dates_ttl
        )
        return list(cached) if cached is not None else []

    async def refresh_prebook_dates(self, force_refresh: bool = False) -> None:
        """Rebuild the bookable Coming Soon dates from the movie pages.

        The branch page only exposes a ten-day strip, but pre-book titles keep
        their bookable dates on their own ``/en/movie/<slug>`` page (sometimes
        months ahead).  This scans those pages once per ``prebook_dates_ttl``
        and caches the union so ``get_dates`` can offer them in the picker.
        """

        key = prebook_dates_key(self.name)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.prebook_dates_ttl)
            if cached is not None:
                return
        movies = await self.get_coming_soon()
        today = today_iso(self.settings.timezone)
        try:
            horizon = (
                date_cls.fromisoformat(today) + timedelta(days=self.settings.prebook_dates_max_days)
            ).isoformat()
        except ValueError:
            horizon = today
        extra: set[str] = set()
        for movie in movies:
            slug = (movie.slug or movie.id or "").strip()
            if not slug:
                continue
            raw_key = _raw_key(f"{key}:{slug}")
            try:
                html = await self._fetch(
                    f"{self.base_url}/en/movie/{_url_part(slug)}",
                    raw_key,
                    self.settings.prebook_dates_ttl,
                    force_refresh,
                )
            except Exception:
                logger.debug("Could not read movie page for pre-book dates: %s", slug)
                continue
            # A Coming Soon card can show a date strip even when the movie has
            # no bookable sessions yet ("No Showings Available").  Only count
            # the dates of movies that can actually be booked.
            if "data-booking-url" not in html:
                continue
            for iso in parse_dates(html):
                if today <= iso <= horizon:
                    extra.add(iso)
        await self.cache.put_json(key, sorted(extra), self.settings.prebook_dates_ttl)

    async def get_movies(
        self, branch_id: str, date: str, force_refresh: bool = False
    ) -> list[Movie]:
        key = movies_key(self.name, branch_id, date)
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=self.settings.cache_listings_ttl)
            if cached is not None:
                return _without_scraped_posters([Movie(**item) for item in cached])
        url = f"{self.base_url}/en/cinemas/{_url_part(branch_id)}/{to_rns_date(date)}"
        try:
            html = await self._fetch(
                url, _raw_key(key), self.settings.cache_listings_ttl, force_refresh
            )
            movies = parse_movies(html)
        except UpstreamError:
            if force_refresh:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            movies = [Movie(**item) for item in stale] if stale else []
        except Exception:
            logger.exception("Could not parse Renaissance movies for %s %s", branch_id, date)
            movies = []
        movies = _without_scraped_posters(movies)
        if movies:
            await self.cache.put_json(
                key, [m.__dict__ for m in movies], self.settings.cache_listings_ttl
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
        key = showtimes_key(self.name, branch_id, date)
        ttl = self.settings.cache_showtimes_ttl if ttl is None else ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached is not None:
                showtimes = [Showtime.from_dict(item) for item in cached]
                return self._filter(showtimes, movie_id)
        url = f"{self.base_url}/en/cinemas/{_url_part(branch_id)}/{to_rns_date(date)}"
        try:
            html = await self._fetch(
                url,
                _raw_key(key),
                ttl,
                force_refresh,
                strict=force_refresh,
                target_key=f"{self.name}:{branch_id}:{date}",
            )
            showtimes = parse_showtimes(html, branch_id, date)
        except UpstreamError:
            if force_refresh:
                raise
            stale = await self.cache.get_json(key, allow_stale=True)
            showtimes = [Showtime.from_dict(item) for item in stale] if stale else []
        except Exception as exc:
            logger.exception("Could not parse Renaissance showtimes for %s %s", branch_id, date)
            if force_refresh:
                await self.http.report_failure("parse", f"{self.name}:{branch_id}:{date}")
                raise UpstreamError(
                    f"Parse error: {exc}",
                    reason="parse",
                    url=url,
                ) from exc
            stale = await self.cache.get_json(key, allow_stale=True)
            showtimes = [Showtime.from_dict(item) for item in stale] if stale else []
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
        url = f"{self.base_url}/en/cinemas/{_url_part(branch_id)}"
        try:
            html = await self._fetch(
                url,
                _raw_key(key),
                self.settings.cache_listings_ttl,
                force_refresh,
                strict=force_refresh,
                target_key=f"{self.name}:{branch_id}",
            )
        except UpstreamError:
            if force_refresh:
                raise
            cached = await self.cache.get_json(key, allow_stale=True)
            if cached:
                return self._overview_from_dict(cached)
            branches = await self.get_branches()
            branch = next(
                (b for b in branches if b.id == branch_id), Branch(branch_id, branch_id, self.name)
            )
            return BranchOverview(branch=branch)
        except Exception as exc:
            logger.exception("Could not parse Renaissance overview for %s", branch_id)
            if force_refresh:
                await self.http.report_failure("parse", f"{self.name}:{branch_id}")
                raise UpstreamError(f"Parse error: {exc}", reason="parse", url=url) from exc
            cached = await self.cache.get_json(key, allow_stale=True)
            if cached:
                return self._overview_from_dict(cached)
            branches = await self.get_branches()
            branch = next(
                (b for b in branches if b.id == branch_id), Branch(branch_id, branch_id, self.name)
            )
            return BranchOverview(branch=branch)

        branches = await self.get_branches()
        branch = next(
            (b for b in branches if b.id == branch_id), Branch(branch_id, branch_id, self.name)
        )
        dates = parse_dates(html)
        movies = _without_scraped_posters(parse_movies(html))
        primary = dates[0] if dates else date_cls.today().isoformat()
        showtimes = parse_showtimes(html, branch_id, primary)
        overview = BranchOverview(
            branch=branch,
            dates=tuple(dates),
            movies=tuple(movies),
            showtimes=tuple(showtimes),
            fetched_date=primary,
        )
        if showtimes:
            await self.cache.put_json(
                showtimes_key(self.name, branch_id, primary),
                [s.to_dict() for s in showtimes],
                self.settings.cache_showtimes_ttl,
            )
        await self.cache.put_json(
            key, self._overview_to_dict(overview), self.settings.cache_listings_ttl
        )
        return overview

    async def get_coming_soon(self, force_refresh: bool = False) -> list[Movie]:
        key = coming_soon_key(self.name)
        ttl = self.settings.cache_coming_soon_ttl
        if not force_refresh:
            cached = await self.cache.get_json(key, ttl=ttl)
            if cached is not None:
                return _without_scraped_posters([Movie(**item) for item in cached])
        try:
            html = await self._fetch(
                f"{self.base_url}/en/coming-soon", _raw_key(key), ttl, force_refresh
            )
            movies = parse_coming_soon(html)
        except Exception:
            logger.exception("Could not fetch Renaissance coming soon")
            stale = await self.cache.get_json(key, allow_stale=True)
            return _without_scraped_posters([Movie(**item) for item in stale]) if stale else []
        movies = _without_scraped_posters(movies)
        if movies:
            await self.cache.put_json(key, [m.__dict__ for m in movies], ttl)
        return movies

    async def get_movie_details(self, movie: Movie, force_refresh: bool = False) -> Movie:
        slug = (movie.slug or movie.id or "").strip()
        if not slug:
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
                f"{self.base_url}/en/movie/{_url_part(slug)}",
                _raw_key(key),
                ttl,
                force_refresh,
            )
            details = parse_movie_details(html, movie)
        except Exception:
            logger.warning("Could not fetch Renaissance movie details for %s", slug)
            return await self._official_poster(movie)
        details = await self._official_poster(details)
        await self.cache.put_json(
            key,
            {
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

    @staticmethod
    def _filter(showtimes: list[Showtime], movie_id: str | None) -> list[Showtime]:
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
