"""New-movie / new-booking discovery.

One low-frequency job per branch.  It reuses the provider's whole-branch page,
compares it with the last known state, confirms changes, and publishes each
event exactly once through the broadcaster.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any

import i18n
import strings
from cache import Cache
from config import Settings
from db import Database
from http_client import HttpClient
from models import Branch, BranchOverview, DiscoveryEvent, Movie, Showtime
from providers.base import ProviderRegistry

logger = logging.getLogger(__name__)

NEW_MOVIE = "NEW_MOVIE"
NEW_DATE_OPENED = "NEW_DATE_OPENED"
NEW_SHOWTIMES = "NEW_SHOWTIMES"
UPCOMING_MOVIE = "UPCOMING_MOVIE"

# ``known_state`` row used for the Coming Soon list; it is not a real branch.
COMING_SOON_STATE = "__comingsoon__"


@dataclass
class _State:
    movies: set[str]
    dates: set[str]
    pairs: set[str]
    showtimes: set[str]
    flap: dict[str, float]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> _State:
        return cls(
            movies=set(payload.get("movies", [])),
            dates=set(payload.get("dates", [])),
            pairs=set(payload.get("pairs", [])),
            showtimes=set(payload.get("showtimes", [])),
            flap={str(k): float(v) for k, v in payload.get("flap", {}).items()},
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "movies": sorted(self.movies),
            "dates": sorted(self.dates),
            "pairs": sorted(self.pairs),
            "showtimes": sorted(self.showtimes),
            "flap": {k: v for k, v in sorted(self.flap.items())},
        }


def _pair(movie_id: str, date: str) -> str:
    return f"{movie_id}|{date}"


@dataclass
class _UpcomingState:
    movies: dict[str, dict[str, Any]]
    released: set[str]
    baseline: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> _UpcomingState:
        raw = payload.get("movies", {})
        if isinstance(raw, list):  # early/simple payload
            raw = {str(item): {"id": str(item)} for item in raw}
        movies = {str(key): dict(value) for key, value in raw.items() if isinstance(value, dict)}
        return cls(
            movies=movies,
            released={str(item) for item in payload.get("released", [])},
        )

    def to_payload(self) -> dict[str, Any]:
        return {"movies": self.movies, "released": sorted(self.released)}


def _movie_payload(movie: Movie) -> dict[str, Any]:
    return {
        "id": movie.id,
        "name": movie.name,
        "slug": movie.slug,
        "provider": movie.provider,
        "poster_url": movie.poster_url,
        "duration_minutes": movie.duration_minutes,
        "rating": movie.rating,
        "language": movie.language,
    }


def _movie_from_payload(payload: dict[str, Any], current: Movie | None = None) -> Movie:
    values: dict[str, Any] = {field: payload.get(field) for field in Movie.__dataclass_fields__}
    if current is not None:
        values |= {
            field: value for field, value in current.__dict__.items() if value not in (None, "")
        }
    values["id"] = values.get("id") or (current.id if current else "")
    values["name"] = values.get("name") or values["id"]
    values["slug"] = values.get("slug") or values["id"]
    values["provider"] = values.get("provider") or "vox"
    return Movie(**values)


def upcoming_release_events(
    overview: BranchOverview, upcoming: _UpcomingState | None
) -> list[DiscoveryEvent]:
    """Turn a known Coming Soon title into an "it is out now" event."""

    if upcoming is None or upcoming.baseline:
        return []
    events: list[DiscoveryEvent] = []
    for movie in overview.movies:
        keys = [key for key in (movie.id, movie.slug) if key in upcoming.movies]
        if not keys or any(key in upcoming.released for key in keys):
            continue
        shows = [s for s in overview.showtimes if s.movie_id == movie.id]
        if not shows:
            continue
        first = min(shows, key=lambda s: (s.date, s.time, s.hall_type))
        events.append(
            DiscoveryEvent(
                kind=UPCOMING_MOVIE,
                branch=overview.branch,
                movie=_movie_from_payload(upcoming.movies[keys[0]], movie),
                date=first.date,
                showtime=first,
                booking_url=first.booking_url,
                event_key=f"{UPCOMING_MOVIE}:{keys[0]}",
                released=True,
            )
        )
    return events


def _showtime_key(movie_id: str, date: str, showtime: Showtime) -> str:
    return f"{movie_id}|{date}|{showtime.time}|{showtime.hall_type}"


def build_state(overview: BranchOverview) -> _State:
    movies = {m.id for m in overview.movies}
    dates = set(overview.dates)
    pairs: set[str] = set()
    showtimes: set[str] = set()
    for showtime in overview.showtimes:
        pairs.add(_pair(showtime.movie_id, showtime.date))
        showtimes.add(_showtime_key(showtime.movie_id, showtime.date, showtime))
    return _State(movies=movies, dates=dates, pairs=pairs, showtimes=showtimes, flap={})


def diff_states(
    previous: _State,
    current: _State,
    overview: BranchOverview,
    now: float,
    flap_window: float,
    upcoming_ids: set[str] | None = None,
) -> tuple[list[DiscoveryEvent], _State]:
    """Return events and the next state (with flap bookkeeping)."""

    movie_by_id: dict[str, Movie] = {m.id: m for m in overview.movies}
    showtimes_by_movie: dict[str, list[Showtime]] = {}
    for showtime in overview.showtimes:
        showtimes_by_movie.setdefault(showtime.movie_id, []).append(showtime)

    events: list[DiscoveryEvent] = []
    new_movies = current.movies - previous.movies
    for movie_id in sorted(new_movies):
        if upcoming_ids and movie_id in upcoming_ids:
            # A Coming Soon release is reported as UPCOMING_MOVIE instead, so
            # subscribers do not get two near-identical messages.
            continue
        movie = movie_by_id.get(movie_id) or Movie(movie_id, movie_id, movie_id)
        showtimes = showtimes_by_movie.get(movie_id, [])
        first = min(showtimes, key=lambda s: (s.date, s.time), default=None)
        events.append(
            DiscoveryEvent(
                kind=NEW_MOVIE,
                branch=overview.branch,
                movie=movie,
                date=first.date if first else overview.fetched_date,
                showtime=first,
                booking_url=first.booking_url if first else None,
                event_key=f"{NEW_MOVIE}:{overview.branch.id}:{movie_id}",
            )
        )

    # A new date for a known movie (pairs only exist when showtimes exist).
    new_pairs = current.pairs - previous.pairs
    grouped_pairs: dict[tuple[str, str], list[Showtime]] = {}
    for showtime in overview.showtimes:
        pair = _pair(showtime.movie_id, showtime.date)
        if pair in new_pairs and showtime.movie_id not in new_movies:
            grouped_pairs.setdefault((showtime.movie_id, showtime.date), []).append(showtime)
    for (movie_id, date), showtimes in sorted(grouped_pairs.items()):
        movie = movie_by_id.get(movie_id) or Movie(movie_id, movie_id, movie_id)
        first = min(showtimes, key=lambda s: (s.time, s.hall_type))
        events.append(
            DiscoveryEvent(
                kind=NEW_DATE_OPENED,
                branch=overview.branch,
                movie=movie,
                date=date,
                showtime=first,
                booking_url=first.booking_url,
                event_key=f"{NEW_DATE_OPENED}:{overview.branch.id}:{movie_id}:{date}",
            )
        )

    new_showtimes = current.showtimes - previous.showtimes
    grouped_showtimes: dict[tuple[str, str], list[Showtime]] = {}
    for showtime in overview.showtimes:
        key = _showtime_key(showtime.movie_id, showtime.date, showtime)
        if (
            key in new_showtimes
            and showtime.movie_id not in new_movies
            and _pair(showtime.movie_id, showtime.date) not in new_pairs
        ):
            grouped_showtimes.setdefault((showtime.movie_id, showtime.date), []).append(showtime)
    for (movie_id, date), showtimes in sorted(grouped_showtimes.items()):
        movie = movie_by_id.get(movie_id) or Movie(movie_id, movie_id, movie_id)
        first = min(showtimes, key=lambda s: (s.time, s.hall_type))
        events.append(
            DiscoveryEvent(
                kind=NEW_SHOWTIMES,
                branch=overview.branch,
                movie=movie,
                date=date,
                showtime=first,
                booking_url=first.booking_url,
                event_key=(
                    f"{NEW_SHOWTIMES}:{overview.branch.id}:{movie_id}:{date}:"
                    + ",".join(sorted({s.time for s in showtimes}))
                ),
                times=tuple(sorted({s.time for s in showtimes})),
            )
        )

    # Ignore items that flap back within the configured window.  Ignored items
    # must not be committed as "known", otherwise they would look like old
    # news once the flap window expires.
    flap = dict(current.flap or previous.flap)
    confirmed: list[DiscoveryEvent] = []
    for event in events:
        last_gone = flap.get(event.event_key)
        if last_gone is not None and now - last_gone < flap_window:
            logger.info("Ignoring flapping discovery event %s", event.event_key)
            _forget_event(current, event, previous)
            continue
        flap.pop(event.event_key, None)
        confirmed.append(event)

    next_state = current
    next_state.flap = flap
    return confirmed, next_state


def _forget_event(state: _State, event: DiscoveryEvent, previous: _State) -> None:
    """Remove an unconfirmed item from the candidate state.

    The item stays visible upstream and will be reported again on a later
    pass, at which point it either confirms or enters the flap window.
    """

    if event.kind == NEW_MOVIE:
        state.movies.discard(event.movie.id)
        return
    if event.kind == NEW_DATE_OPENED:
        if event.date:
            state.pairs.discard(_pair(event.movie.id, event.date))
        return
    if event.date:
        prefix = f"{event.movie.id}|{event.date}|"
        state.showtimes = {
            key
            for key in state.showtimes
            if not (key.startswith(prefix) and key not in previous.showtimes)
        }


class DiscoveryJob:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        cache: Cache,
        providers: ProviderRegistry,
        broadcaster: Any | None = None,
        http: HttpClient | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
        on_admin_message: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.cache = cache
        self.providers = providers
        self.broadcaster = broadcaster
        self.http = http
        self._clock = clock
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._on_admin_message = on_admin_message
        self._next_allowed: dict[str, float] = {}
        self._next_coming_soon: dict[str, float] = {}
        self.last_run: dict[str, float] = {}
        self.events_today = 0
        self.last_error: str | None = None
        self.provider_last_run: dict[str, float] = {}
        self.provider_last_error: dict[str, str] = {}
        self.provider_events: dict[str, int] = {}
        self._now_showing: list[dict[str, Any]] = []

    async def run_once(
        self, now: float | None = None, branch_ids: Iterable[str] | None = None
    ) -> int:
        now = self._clock() if now is None else now
        wanted = set(branch_ids) if branch_ids is not None else None
        queued = 0
        self._now_showing = []
        wait_candidates: list[dict[str, Any]] = []
        for provider_name in self.providers.names():
            provider = self.providers.get(provider_name)
            self.provider_last_run[provider_name] = now
            try:
                branches = await provider.get_branches()
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.provider_last_error[provider_name] = self.last_error
                logger.exception("Discovery could not list branches for %s", provider_name)
                with i18n.use(i18n.admin_language()):
                    alert = strings.admin_discovery_branches_failed(exc)
                await self._admin(alert)
                continue
            self.provider_last_error.pop(provider_name, None)
            upcoming = await self._upcoming_state(provider, now)
            if hasattr(provider, "get_prebook_movies"):
                wait_candidates.extend(
                    {
                        "title": item.get("title") or item.get("slug") or "",
                        "movie_id": item.get("slug") or "",
                        "provider": provider_name,
                        "dates": list(item.get("dates") or []),
                        "branch_id": None,
                        "branch_name": None,
                        "date": None,
                        "booking_url": None,
                    }
                    for item in await provider.get_prebook_movies()
                )
            for branch in branches:
                if wanted is not None and branch.id not in wanted:
                    continue
                if not self._due(branch.id, now):
                    continue
                self._mark_run(branch.id, now)
                try:
                    queued += await self._process_branch(branch, provider, now, upcoming)
                except Exception as exc:
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    self.provider_last_error[provider_name] = self.last_error
                    logger.exception("Discovery failed for %s", branch.id)
                    with i18n.use(i18n.admin_language()):
                        alert = strings.admin_discovery_branch_failed(branch.name, exc)
                    await self._admin(alert)
            self.provider_events[provider_name] = self.provider_events.get(provider_name, 0)
            if upcoming is not None:
                await self._save_upcoming(upcoming, now, provider)
        await self._flush_movie_waits(wait_candidates, now)
        return queued

    async def _flush_movie_waits(self, candidates: list[dict[str, Any]], now: float) -> None:
        """Alert users waiting for a movie that is now bookable.

        ``candidates`` combines the currently-showing movies collected while
        scanning branch overviews with the bookable Coming Soon titles from the
        pre-book scan.  The broadcaster matches them against active waits.
        """

        candidates.extend(self._now_showing)
        self._now_showing = []
        if not candidates or self.broadcaster is None:
            return
        if not hasattr(self.broadcaster, "notify_movie_waits"):
            return
        try:
            await self.broadcaster.notify_movie_waits(candidates, now)
        except Exception:
            logger.exception("Movie-wait notification failed")

    def _due(self, branch_id: str, now: float) -> bool:
        return now >= self._next_allowed.get(branch_id, 0.0)

    def _mark_run(self, branch_id: str, now: float) -> None:
        jitter = 1.0 + self._rng.uniform(
            -self.settings.discovery_jitter, self.settings.discovery_jitter
        )
        self._next_allowed[branch_id] = now + self.settings.discovery_interval * jitter
        self.last_run[branch_id] = now

    async def _upcoming_state(self, provider: Any, now: float) -> _UpcomingState | None:
        if not hasattr(provider, "get_coming_soon"):
            return None
        state_key = f"{COMING_SOON_STATE}:{provider.name}"
        row = await self.db.get_known_state(state_key)
        state = _UpcomingState.from_payload(json.loads(row["payload"])) if row is not None else None
        if state is not None and now < self._next_coming_soon.get(provider.name, 0.0):
            return state
        self._next_coming_soon[provider.name] = now + self.settings.coming_soon_interval
        baseline = state is None
        try:
            movies = await provider.get_coming_soon(force_refresh=True)
        except Exception:
            logger.exception("Discovery could not fetch Coming Soon")
            # Retry on the next discovery pass instead of waiting a full hour
            # with no baseline.
            self._next_coming_soon[provider.name] = 0.0
            return state
        if hasattr(provider, "refresh_prebook_dates"):
            try:
                await provider.refresh_prebook_dates()
            except Exception:
                logger.exception("Discovery could not refresh pre-book dates")
        if baseline:
            state = _UpcomingState(
                movies={
                    (movie.id or movie.slug): _movie_payload(movie)
                    for movie in movies
                    if (movie.id or movie.slug)
                },
                released=set(),
                baseline=True,
            )
            logger.info("Coming Soon baseline stored: %s movies", len(state.movies))
            return state
        assert state is not None
        for movie in movies:
            key = movie.id or movie.slug
            if not key:
                continue
            payload = state.movies.setdefault(key, _movie_payload(movie))
            for field, value in _movie_payload(movie).items():
                if value not in (None, ""):
                    payload[field] = value
        return state

    async def _save_upcoming(self, state: _UpcomingState, now: float, provider: Any) -> None:
        state_key = f"{COMING_SOON_STATE}:{provider.name}"
        await self.db.set_known_state(state_key, json.dumps(state.to_payload()), now)

    async def _enrich(self, provider: Any, events: list[DiscoveryEvent]) -> list[DiscoveryEvent]:
        if not events or not hasattr(provider, "get_movie_details"):
            return events
        details: dict[str, Movie] = {}
        enriched: list[DiscoveryEvent] = []
        for event in events:
            key = event.movie.slug or event.movie.id
            if key not in details:
                try:
                    details[key] = await provider.get_movie_details(event.movie)
                except Exception:
                    logger.warning("Could not enrich movie details for %s", event.movie.name)
                    details[key] = event.movie
            enriched.append(replace(event, movie=details[key]))
        return enriched

    def _collect_now_showing(self, overview: BranchOverview, provider: Any, branch: Branch) -> None:
        """Remember every movie currently on sale at a branch so waits for a
        title that is already showing can fire too (not only brand-new ones)."""

        for movie in overview.movies:
            showtime = next((s for s in overview.showtimes if s.movie_id == movie.id), None)
            self._now_showing.append(
                {
                    "title": movie.name,
                    "movie_id": movie.id or movie.slug,
                    "provider": provider.name,
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "date": overview.fetched_date
                    or (overview.dates[0] if overview.dates else None),
                    "booking_url": showtime.booking_url if showtime else None,
                }
            )

    async def _process_branch(
        self,
        branch: Branch,
        provider: Any,
        now: float,
        upcoming: _UpcomingState | None = None,
    ) -> int:
        overview = await provider.get_branch_overview(branch.id, force_refresh=True)
        self._collect_now_showing(overview, provider, branch)
        if upcoming is not None and upcoming.baseline:
            # Anything already on sale while the Coming Soon baseline is being
            # taken is not a new release; never alert for it later.
            for movie in overview.movies:
                for key in (movie.id, movie.slug):
                    if key in upcoming.movies:
                        upcoming.released.add(key)
        current = build_state(overview)
        upcoming_ids = None
        if upcoming is not None:
            upcoming_ids = set(upcoming.movies)
            # The Coming Soon listing sometimes only exposes a slug while the
            # day page uses the HO identifier; map both directions.
            for movie in overview.movies:
                if movie.id in upcoming.movies or movie.slug in upcoming.movies:
                    upcoming_ids.add(movie.id)
        row = await self.db.get_known_state(state_key := f"{provider.name}:{branch.id}")
        if row is None:
            current.flap = {}
            await self._save_state(state_key, current, now)
            logger.info("Discovery baseline stored for %s", branch.name)
            return 0

        previous = _State.from_payload(json.loads(row["payload"]))
        current.flap = dict(previous.flap)
        diff_events, next_state = diff_states(
            previous,
            current,
            overview,
            now,
            self.settings.discovery_flap_window,
            upcoming_ids=upcoming_ids,
        )
        release_events = upcoming_release_events(overview, upcoming)
        events = diff_events + release_events
        if not events:
            await self._save_state(state_key, next_state, now)
            return 0

        # Confirm with a second read.  By default this re-reads the provider
        # cache (no extra upstream request); DISCOVERY_CONFIRM_NETWORK=true
        # enables a real second request.
        await self._sleep(self.settings.discovery_confirm_delay)
        try:
            if self.settings.discovery_confirm_network:
                confirmed_overview = await provider.get_branch_overview(
                    branch.id, force_refresh=True
                )
            else:
                confirmed_overview = await provider.get_branch_overview(
                    branch.id, force_refresh=False
                )
        except Exception:
            logger.warning("Discovery confirmation failed for %s", branch.id)
            await self._save_state(state_key, next_state, now)
            return 0

        confirmed_state = build_state(confirmed_overview)
        confirmed_state.flap = dict(next_state.flap)
        confirmed_diff, final_state = diff_states(
            previous,
            confirmed_state,
            confirmed_overview,
            now,
            self.settings.discovery_flap_window,
            upcoming_ids=upcoming_ids,
        )
        confirmed_events = confirmed_diff + upcoming_release_events(confirmed_overview, upcoming)
        confirmed_keys = {e.event_key for e in confirmed_events}
        kept = [e for e in events if e.event_key in confirmed_keys]
        dropped = [e for e in events if e.event_key not in confirmed_keys]
        for event in dropped:
            final_state.flap[event.event_key] = now

        # Merge flap entries from the first pass, keeping the newer timestamps
        # recorded for events that were dropped by confirmation.
        merged_flap = dict(next_state.flap)
        merged_flap.update(final_state.flap)
        final_state.flap = merged_flap

        published: list[DiscoveryEvent] = []
        for event in kept:
            if event.kind == UPCOMING_MOVIE and upcoming is not None:
                if event.movie.id:
                    upcoming.released.add(event.movie.id)
                if event.movie.slug:
                    upcoming.released.add(event.movie.slug)
            # Mark before enqueueing: exactly-once is more important than
            # retrying after a process crash.
            if not await self.db.mark_broadcast(event.event_key):
                continue
            published.append(event)

        published = await self._enrich(provider, published)
        if published and self.broadcaster is not None:
            await self.broadcaster.enqueue_events(published)
        self.events_today += len(published)
        self.provider_events[provider.name] = self.provider_events.get(provider.name, 0) + len(
            published
        )
        await self._save_state(state_key, final_state, now)
        logger.info(
            "Discovery %s: %s events, %s published, %s dropped",
            branch.name,
            len(events),
            len(published),
            len(dropped),
        )
        return len(published)

    async def _save_state(self, branch_id: str, state: _State, now: float) -> None:
        await self.db.set_known_state(branch_id, json.dumps(state.to_payload()), now)

    async def _admin(self, text: str) -> None:
        if self._on_admin_message:
            try:
                await self._on_admin_message(text)
            except Exception:  # pragma: no cover
                logger.exception("Could not notify admin")
