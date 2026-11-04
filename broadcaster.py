"""Rate-limited fan-out for discovery alerts and the optional public channel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import time
from collections.abc import Callable, Iterable
from datetime import date as date_cls
from typing import Any

import i18n
import search
import strings
from config import Settings
from db import Database
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
    ) -> None:
        self.settings = settings
        self.db = db
        self.sender = sender
        self.stats = stats
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
                with i18n.use(sub.get("lang")):
                    text, keyboard = await self._build_message(int(sub["user_id"]), branch_events)
                photo = branch_events[0].movie.poster_url if len(branch_events) == 1 else None
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

    async def notify_movie_waits(
        self, candidates: list[dict[str, Any]], now: float | None = None
    ) -> int:
        """Alert users waiting for a movie that has become bookable.

        ``candidates`` describe movies that are on sale right now (with a
        ``branch_id``/``date``) or opening pre-book (``dates`` only).  Each
        active wait is alerted once and then deactivated.
        """

        if not candidates:
            return 0
        waits = await self.db.list_active_movie_waits()
        if not waits:
            return 0
        now = self._clock() if now is None else now
        day = self._local_day(now)

        # Keep one candidate per title; the first (now-showing, with a branch)
        # is preferred over pre-book-only candidates.
        unique: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for candidate in candidates:
            key = search.normalize(candidate.get("title") or "")
            if not key or key in seen_titles:
                continue
            seen_titles.add(key)
            unique.append(candidate)

        sent = 0
        notified: set[int] = set()
        for candidate in unique:
            title = candidate.get("title") or ""
            for wait in waits:
                if wait["id"] in notified:
                    continue
                if search.score(wait["title"], title) < 0.90:
                    continue
                if self._wait_is_quiet(wait, candidate, now):
                    continue
                user_id = int(wait["user_id"])
                count = await self.db.get_discovery_count(user_id, day)
                if count >= self.settings.discovery_daily_cap:
                    continue
                with i18n.use(wait.get("lang")):
                    text, keyboard = await self._movie_wait_message(wait, candidate, user_id)
                try:
                    await self.sender.send(int(wait["telegram_id"]), text, keyboard)
                except UserBlocked:
                    logger.info("Deactivated blocked movie-wait user %s", wait["telegram_id"])
                    await self.db.mark_movie_wait_notified(wait["id"])
                    notified.add(wait["id"])
                    continue
                except Exception:
                    logger.exception("Movie-wait alert failed for %s", wait["telegram_id"])
                    continue
                await self.db.mark_movie_wait_notified(wait["id"])
                notified.add(wait["id"])
                await self.db.increment_discovery_count(user_id, day)
                sent += 1
                self.sent += 1
                if self.stats is not None:
                    self.stats.note_broadcast()
        return sent

    def _wait_is_quiet(self, wait: dict[str, Any], candidate: dict[str, Any], now: float) -> bool:
        start = int(
            wait.get("quiet_start")
            if wait.get("quiet_start") is not None
            else self.settings.quiet_start
        )
        end = int(
            wait.get("quiet_end") if wait.get("quiet_end") is not None else self.settings.quiet_end
        )
        if not is_quiet_time(now, start, end, self.settings.timezone):
            return False
        dates = candidate.get("dates") or []
        date_text = candidate.get("date") or (dates[0] if dates else None)
        if not date_text:
            return True
        try:
            event_date = date_cls.fromisoformat(date_text)
        except (TypeError, ValueError):
            return True
        return not (0 <= (event_date - local_date(now, self.settings.timezone)).days <= 1)

    async def _movie_wait_message(
        self, wait: dict[str, Any], candidate: dict[str, Any], user_id: int
    ) -> tuple[str, Any]:
        from keyboards import movie_wait_keyboard, movie_wait_watch_keyboard

        title = candidate.get("title") or ""
        provider = candidate.get("provider") or "vox"
        branch_name = candidate.get("branch_name")
        date_text = candidate.get("date")

        if branch_name and date_text:
            token = secrets.token_urlsafe(16)
            await self.db.add_discovery_action(
                token,
                user_id,
                candidate["branch_id"],
                branch_name,
                date_text,
                candidate["movie_id"],
                title,
                provider,
            )
            text = strings.movie_wait_alert(
                title,
                strings.cinema_name(provider),
                branch_name,
                date_text,
            )
            keyboard = movie_wait_watch_keyboard(
                token=token, booking_url=candidate.get("booking_url")
            )
            return text, keyboard

        dates = candidate.get("dates") or []
        first_date = dates[0] if dates else ""
        last_date = dates[-1] if dates else ""
        text = strings.movie_wait_prebook(
            title, strings.cinema_name(provider), first_date, last_date
        )
        return text, movie_wait_keyboard()

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

    async def _build_message(self, user_id: int, events: list[DiscoveryEvent]) -> tuple[str, Any]:
        from keyboards import discovery_keyboard

        branch_name = events[0].branch.name
        if len(events) == 1:
            text = _event_text(events[0])
        else:
            lines = [_event_line(e) for e in events]
            text = strings.discovery_digest(branch_name, len(events), lines)

        first = events[0]
        token = secrets.token_urlsafe(16)
        await self.db.add_discovery_action(
            token,
            user_id,
            first.branch.id,
            first.branch.name,
            first.date or today_iso(self.settings.timezone),
            first.movie.id,
            first.movie.name,
            first.branch.provider,
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
        for event in events:
            with i18n.use(i18n.DEFAULT_LANGUAGE):
                text = strings.discovery_channel(_event_text(event))
            try:
                await self.sender.send(channel, text, photo_url=event.movie.poster_url)
            except Exception:
                logger.exception("Could not post to public channel")


def _event_text(event: DiscoveryEvent) -> str:
    if event.kind == "UPCOMING_MOVIE":
        hall = event.showtime.hall_type if event.showtime else None
        text = strings.discovery_upcoming_released(
            event.movie.name, event.branch.name, event.date, hall
        )
    elif event.kind == "NEW_MOVIE":
        hall = event.showtime.hall_type if event.showtime else None
        text = strings.discovery_new_movie(event.movie.name, event.branch.name, event.date, hall)
    elif event.kind == "NEW_DATE_OPENED":
        text = strings.discovery_new_date(event.movie.name, event.branch.name, event.date or "")
    else:
        text = strings.discovery_new_showtimes(
            event.movie.name,
            event.branch.name,
            event.date or "",
            list(event.times or ((event.showtime.time,) if event.showtime else ())),
        )
    facts = strings.movie_facts(
        event.movie.duration_minutes, event.movie.rating, event.movie.language
    )
    if facts:
        text += f"\n\n{facts}"
    return text


def _event_line(event: DiscoveryEvent) -> str:
    if event.kind == "UPCOMING_MOVIE":
        return strings.discovery_line_upcoming(event.movie.name)
    if event.kind == "NEW_MOVIE":
        return strings.discovery_line_new_movie(event.movie.name)
    if event.kind == "NEW_DATE_OPENED":
        return strings.discovery_line_new_date(event.movie.name, event.date or "")
    return strings.discovery_line_new_showtimes(event.movie.name, event.times or ())
