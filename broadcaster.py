"""Rate-limited fan-out for discovery alerts and the optional public channel."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import time
from collections.abc import Callable, Iterable
from datetime import date as date_cls
from typing import Any

import i18n
import strings
from config import Settings
from db import Database
from metadata import display_language
from models import DiscoveryEvent, format_key
from notifier import TelegramSender, UserBlocked
from timeutil import is_quiet_time, local_date, today_iso
from utils import json_list

logger = logging.getLogger(__name__)


class Broadcaster:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        sender: TelegramSender,
        stats: Any | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[], Any] | None = None,
        posters: Any | None = None,
        metadata: Any | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.sender = sender
        self.stats = stats
        self.posters = posters
        self.metadata = metadata
        self._clock = clock
        self._queue: asyncio.Queue[list[DiscoveryEvent]] = asyncio.Queue()
        self._worker: asyncio.Task[Any] | None = None
        self.sent = 0

    async def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="broadcaster")

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def enqueue_events(self, events: Iterable[DiscoveryEvent]) -> None:
        batch = list(events)
        if not batch:
            return
        await self._queue.put(batch)

    @property
    def queue_length(self) -> int:
        return self._queue.qsize()

    async def _run(self) -> None:
        while True:
            batch = await self._queue.get()
            try:
                # Group everything already queued in this cycle.
                while True:
                    try:
                        batch.extend(self._queue.get_nowait())
                        self._queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                await self.process(batch)
            except Exception:
                logger.exception("Broadcaster batch failed")
            finally:
                self._queue.task_done()

    async def process(self, events: list[DiscoveryEvent], now: float | None = None) -> int:
        now = self._clock() if now is None else now
        if not events:
            return 0
        await self._post_to_channel(events)

        subscriptions = await self.db.list_active_subscriptions()
        sent = 0
        for sub in subscriptions:
            matching = self._filter_events(sub, events)
            if not matching:
                continue
            if self._is_quiet(sub, matching, now):
                continue
            day = self._local_day(now)
            count = await self.db.get_discovery_count(int(sub["user_id"]), day)
            if count >= self.settings.discovery_daily_cap:
                continue
            by_branch: dict[str, list[DiscoveryEvent]] = {}
            for event in matching:
                by_branch.setdefault(event.branch.id, []).append(event)
            for branch_events in by_branch.values():
                if count >= self.settings.discovery_daily_cap:
                    break
                titles = await self._localized_titles(branch_events, sub.get("lang"))
                with i18n.use(sub.get("lang")):
                    text, keyboard = await self._build_message(
                        int(sub["telegram_id"]), branch_events, titles=titles
                    )
                # The overview strips cinema-scraped artwork, so every alert
                # resolves official artwork from TMDB (cached for a month).
                photo = await self._poster(branch_events[0].movie)
                try:
                    await self.sender.send(int(sub["telegram_id"]), text, keyboard, photo_url=photo)
                except UserBlocked:
                    await self.db.deactivate_subscription_for_telegram(int(sub["telegram_id"]))
                    logger.info("Deactivated blocked subscriber %s", sub["telegram_id"])
                    break
                except Exception:
                    logger.exception("Broadcast failed for %s", sub["telegram_id"])
                    continue
                await self.db.increment_discovery_count(int(sub["user_id"]), day)
                count += 1
                sent += 1
                self.sent += 1
                if self.stats is not None:
                    self.stats.note_broadcast()
        return sent

    def _filter_events(
        self, sub: dict[str, Any], events: list[DiscoveryEvent]
    ) -> list[DiscoveryEvent]:
        branch_ids = set(json_list(sub.get("branch_ids")))
        event_types = json_list(sub.get("event_types"))
        hall = format_key(sub.get("hall_type")) if sub.get("hall_type") else "*"
        result = []
        for event in events:
            candidates = {event.branch.id, f"{event.branch.provider}:{event.branch.id}"}
            if branch_ids and not (branch_ids & candidates):
                continue
            if event_types and event.kind not in event_types:
                continue
            if hall != "*":
                if event.showtime is None:
                    continue
                if format_key(event.showtime.hall_type) != hall:
                    continue
            result.append(event)
        return result

    def _is_quiet(self, sub: dict[str, Any], events: list[DiscoveryEvent], now: float) -> bool:
        start = int(
            sub.get("quiet_start")
            if sub.get("quiet_start") is not None
            else self.settings.quiet_start
        )
        end = int(
            sub.get("quiet_end") if sub.get("quiet_end") is not None else self.settings.quiet_end
        )
        if not is_quiet_time(now, start, end, self.settings.timezone):
            return False
        today = local_date(now, self.settings.timezone)
        for event in events:
            if not event.date:
                continue
            try:
                event_date = date_cls.fromisoformat(event.date)
            except (TypeError, ValueError):
                continue
            if 0 <= (event_date - today).days <= 1:
                return False
        return True

    def _local_day(self, now: float) -> str:
        return local_date(now, self.settings.timezone).isoformat()

    async def _poster(self, movie: Any) -> str | None:
        """Return official artwork for a discovery event, if we can find it."""

        existing = getattr(movie, "poster_url", None)
        if existing:
            return existing
        if self.posters is None:
            return None
        try:
            return await self.posters.url(getattr(movie, "name", "") or "")
        except Exception:
            logger.warning("Could not resolve a discovery poster")
            return None

    async def _localized_titles(self, events: list[DiscoveryEvent], lang: object) -> dict[str, str]:
        """Arabic titles keyed by the provider's English title."""

        language = display_language(i18n.normalize(lang))
        if self.metadata is None or not language:
            return {}
        titles: dict[str, str] = {}
        for event in events:
            name = event.movie.name
            if not name or name in titles:
                continue
            try:
                movie = await self.metadata.localize(name, language=language)
            except Exception:
                continue
            if movie is not None:
                titles[name] = movie.title
        return titles

    async def _build_message(
        self,
        telegram_id: int,
        events: list[DiscoveryEvent],
        titles: dict[str, str] | None = None,
    ) -> tuple[str, Any]:
        from keyboards import discovery_keyboard

        titles = titles or {}
        first = events[0]
        branch_name = first.branch.name
        first_title = titles.get(first.movie.name) or first.movie.name
        if len(events) == 1:
            text = _event_text(first, first_title)
        else:
            lines = [_event_line(e, titles.get(e.movie.name)) for e in events]
            text = strings.discovery_digest(branch_name, len(events), lines, first.branch.provider)

        token = secrets.token_urlsafe(16)
        await self.db.add_discovery_action(
            token,
            telegram_id,
            first.branch.id,
            first.branch.name,
            first.date or today_iso(self.settings.timezone),
            first.movie.id,
            first.movie.name,
            first.branch.provider,
            payload=json.dumps(
                _watch_choices(events, titles), ensure_ascii=False, separators=(",", ":")
            ),
        )
        keyboard = discovery_keyboard(
            token=token,
            booking_url=first.booking_url
            or (first.showtime.booking_url if first.showtime else None),
        )
        return text, keyboard

    async def _post_to_channel(self, events: list[DiscoveryEvent]) -> None:
        channel = self.settings.channel_chat_id
        if not channel:
            return
        titles = await self._localized_titles(events, i18n.DEFAULT_LANGUAGE)
        for event in events:
            with i18n.use(i18n.DEFAULT_LANGUAGE):
                text = strings.discovery_channel(_event_text(event, titles.get(event.movie.name)))
            photo = await self._poster(event.movie)
            try:
                await self.sender.send(channel, text, photo_url=photo)
            except Exception:
                logger.exception("Could not post to public channel")


def _watch_choices(events: list[DiscoveryEvent], titles: dict[str, str]) -> list[dict[str, Any]]:
    """One row per movie in this digest, with everything a watch needs.

    The callback used to fetch showtimes again, which could fail upstream and
    broke the button.  Storing the event payload makes the follow-up purely
    local: the user picks a movie and the watch is created from this data.
    """

    choices: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        key = (event.branch.provider, event.branch.id, event.movie.id)
        if key in seen:
            continue
        seen.add(key)
        showtime = event.showtime
        movie = event.movie
        choices.append(
            {
                "provider": event.branch.provider,
                "branch_id": event.branch.id,
                "branch_name": event.branch.name,
                "date": event.date or "",
                "movie_id": movie.id,
                "movie_name": movie.name,
                "title": titles.get(movie.name) or movie.name,
                "line": _event_line(event, titles.get(movie.name)),
                "showtime": showtime.time if showtime else "",
                "hall_type": showtime.hall_type if showtime else "",
                "booking_url": event.booking_url
                or (showtime.booking_url if showtime else None)
                or "",
                "poster_url": movie.poster_url or "",
                "duration_minutes": movie.duration_minutes,
                "rating": movie.rating,
                "language": movie.language,
                "synopsis": movie.synopsis,
                "trailer_url": movie.trailer_url,
                "imax_status": movie.imax_status,
            }
        )
    return choices


def _event_text(event: DiscoveryEvent, title_override: str | None = None) -> str:
    provider = event.branch.provider
    movie_name = (title_override or event.movie.name or "").strip()
    if event.kind == "UPCOMING_MOVIE":
        hall = event.showtime.hall_type if event.showtime else None
        text = strings.discovery_upcoming_released(
            movie_name, event.branch.name, event.date, hall, provider
        )
    elif event.kind == "NEW_MOVIE":
        hall = event.showtime.hall_type if event.showtime else None
        text = strings.discovery_new_movie(
            movie_name, event.branch.name, event.date, hall, provider
        )
    elif event.kind == "NEW_DATE_OPENED":
        text = strings.discovery_new_date(movie_name, event.branch.name, event.date or "", provider)
    else:
        text = strings.discovery_new_showtimes(
            movie_name,
            event.branch.name,
            event.date or "",
            list(event.times or ((event.showtime.time,) if event.showtime else ())),
            provider,
        )
    facts = strings.movie_facts(
        event.movie.duration_minutes, event.movie.rating, event.movie.language
    )
    if facts:
        text += f"\n\n{facts}"
    return text


def _event_line(event: DiscoveryEvent, title_override: str | None = None) -> str:
    name = title_override or event.movie.name
    if event.kind == "UPCOMING_MOVIE":
        return strings.discovery_line_upcoming(name)
    if event.kind == "NEW_MOVIE":
        return strings.discovery_line_new_movie(name)
    if event.kind == "NEW_DATE_OPENED":
        return strings.discovery_line_new_date(name, event.date or "")
    return strings.discovery_line_new_showtimes(name, event.times or ())
