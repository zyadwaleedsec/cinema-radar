"""Watcher: turn due targets into at most one upstream request each, diff the
result against the last snapshot, confirm changes, and fire alerts."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls
from typing import Any

from cache import Cache, alert_key, snapshot_key
from config import Settings
from db import Database
from http_client import CircuitOpenError, HttpClient, UpstreamError
from models import (
    AVAILABLE,
    NOT_AVAILABLE,
    SOLD_OUT,
    UNKNOWN,
    Showtime,
    TargetKey,
    WatchEvent,
    format_key,
    showtime_map,
)
from notifier import UserBlocked
from providers.base import ProviderRegistry
from scheduler import ScheduledTarget, Scheduler
from timeutil import day_end_iso, expiry_iso, is_quiet_time, local_date, today_iso

logger = logging.getLogger(__name__)

BOOKING_OPENED = "BOOKING_OPENED"
SEATS_AVAILABLE = "SEATS_AVAILABLE"
NEW_SHOWTIMES = "NEW_SHOWTIMES"
NEW_DATE_OPENED = "NEW_DATE_OPENED"

# Per-watch notification modes.
MODE_ALL = "all"
MODE_SEATS = "seats"
MODE_OPENING = "opening"
VALID_MODES = frozenset({MODE_ALL, MODE_SEATS, MODE_OPENING})


def alert_allowed(mode: str | None, kind: str) -> bool:
    """Return True when *kind* should be sent for this watch's alert mode."""

    if mode == MODE_OPENING:
        return kind in {BOOKING_OPENED, NEW_DATE_OPENED}
    if mode == MODE_SEATS:
        return kind == SEATS_AVAILABLE
    return True


def in_quiet_hours(
    watch: dict[str, Any], event: WatchEvent, now: float, settings: Settings
) -> bool:
    """Quiet hours apply to watch alerts too, unless the user opted out.

    Screenings today or tomorrow always bypass quiet hours: a seat that frees
    up at 02:00 is useless if the alert arrives at 08:00.
    """

    if not int(watch.get("quiet_watches", 1) or 0):
        return False
    start = watch.get("quiet_start")
    end = watch.get("quiet_end")
    start = settings.quiet_start if start is None else int(start)
    end = settings.quiet_end if end is None else int(end)
    if not is_quiet_time(now, start, end, settings.timezone):
        return False
    try:
        event_date = date_cls.fromisoformat(event.showtime.date)
    except (TypeError, ValueError):
        return True
    return (event_date - local_date(now, settings.timezone)).days > 1


def _is_snoozed(watch: dict[str, Any], now: float) -> bool:
    raw = watch.get("snoozed_until")
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return now < until.timestamp()


class RequestCoalescer:
    """One in-flight fetch per key; every caller awaits the same future."""

    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future[Any]] = {}

    async def run(self, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
        existing = self._futures.get(key)
        if existing is not None:
            return await asyncio.shield(existing)
        future: asyncio.Future[Any] = asyncio.ensure_future(factory())
        self._futures[key] = future
        try:
            return await asyncio.shield(future)
        finally:
            if self._futures.get(key) is future:
                self._futures.pop(key, None)


def _in_window(showtime: Showtime, window: str | None, morning_end_hour: int) -> bool:
    """True when ``showtime`` falls inside the requested morning/evening window."""

    if not window:
        return True
    try:
        hour = int(str(showtime.time or "").split(":", 1)[0])
    except (ValueError, IndexError):
        return False
    return hour < morning_end_hour if window == "morning" else hour >= morning_end_hour


def _required_seats(watch: dict[str, Any]) -> int:
    """Seats the user asked for; older rows and ``None`` mean one seat."""

    try:
        value = int(watch.get("required_seats") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, value)


def _seat_alertable(prev: Showtime | None, curr: Showtime, watch: dict[str, Any]) -> bool:
    """True when this poll just crossed the watch's seat requirement.

    ``prev`` and ``curr`` are the same showtime on consecutive polls.  An
    unknown current count fails open, and a count that was already enough does
    not alert again until it drops below the requirement.
    """

    required = _required_seats(watch)
    if curr.seats_available is None:
        return True
    if curr.seats_available < required:
        return False
    return prev is None or prev.seats_available is None or prev.seats_available < required


def compute_watch_events(
    previous: Iterable[Showtime],
    current: Iterable[Showtime],
    watches: Iterable[dict[str, Any]],
    morning_end_hour: int = 17,
) -> list[tuple[dict[str, Any], WatchEvent]]:
    """Pure diff logic, easy to unit-test with mocked provider responses."""

    previous_map = showtime_map(previous)
    current_map = showtime_map(current)
    watches = list(watches)
    events: list[tuple[dict[str, Any], WatchEvent]] = []

    def scan(prev_map: dict[str, Showtime], curr_map: dict[str, Showtime]):
        new_by_movie: dict[str, list[Showtime]] = {}
        opened_by_movie: dict[str, list[Showtime]] = {}
        seats_by_movie: dict[str, list[Showtime]] = {}
        for key, curr in curr_map.items():
            prev = prev_map.get(key)
            if prev is None:
                new_by_movie.setdefault(curr.movie_id, []).append(curr)
                continue
            if prev.status in {NOT_AVAILABLE, UNKNOWN} and curr.status == AVAILABLE:
                opened_by_movie.setdefault(curr.movie_id, []).append(curr)
            elif (prev.status == SOLD_OUT and curr.status == AVAILABLE) or (
                prev.status == AVAILABLE
                and curr.status == AVAILABLE
                and prev.seats_available is not None
                and curr.seats_available is not None
                and curr.seats_available > prev.seats_available
            ):
                seats_by_movie.setdefault(curr.movie_id, []).append(curr)
        return new_by_movie, opened_by_movie, seats_by_movie

    def aggregated(watch: dict[str, Any], shows: list[Showtime], kind: str):
        ordered = sorted(shows, key=lambda s: (s.time, s.hall_type))
        seats = [s.seats_available for s in ordered]
        total = None if any(value is None for value in seats) else sum(seats)
        return (
            watch,
            WatchEvent(
                kind=kind,
                showtime=ordered[0],
                seats_available=total,
                times=tuple(sorted({s.time for s in ordered})),
            ),
        )

    for watch in watches:
        if (watch.get("scope") or "showtime") in {"movie", "movie_all_dates"}:
            hall = format_key(watch.get("hall_type"))
            window = watch.get("time_window")
            if hall == "*":
                prev_map, curr_map = previous_map, current_map
            else:
                prev_map = {
                    k: v for k, v in previous_map.items() if format_key(v.hall_type) == hall
                }
                curr_map = {k: v for k, v in current_map.items() if format_key(v.hall_type) == hall}
            if window:
                prev_map = {
                    k: v for k, v in prev_map.items() if _in_window(v, window, morning_end_hour)
                }
                curr_map = {
                    k: v for k, v in curr_map.items() if _in_window(v, window, morning_end_hour)
                }
            new_by_movie, opened_by_movie, seats_by_movie = scan(prev_map, curr_map)
            movie_id = watch["movie_id"]
            if movie_id in opened_by_movie:
                events.append(aggregated(watch, opened_by_movie[movie_id], BOOKING_OPENED))
            if movie_id in seats_by_movie:
                eligible = [
                    show
                    for show in seats_by_movie[movie_id]
                    if _seat_alertable(prev_map.get(f"{show.time}|{show.hall_type}"), show, watch)
                ]
                if eligible:
                    events.append(aggregated(watch, eligible, SEATS_AVAILABLE))
            if movie_id in new_by_movie:
                events.append(aggregated(watch, new_by_movie[movie_id], NEW_SHOWTIMES))
            continue

        key = f"{watch['showtime']}|{watch['hall_type']}"
        prev = previous_map.get(key)
        curr = current_map.get(key)
        if prev is None and curr is None:
            continue
        if prev is None and curr is not None:
            # Covered by the grouped NEW_SHOWTIMES event below.
            continue
        assert prev is not None
        if curr is None:
            continue

        prev_status = prev.status
        if prev_status in {NOT_AVAILABLE, UNKNOWN} and curr.status == AVAILABLE:
            events.append(
                (
                    watch,
                    WatchEvent(
                        kind=BOOKING_OPENED,
                        showtime=curr,
                        previous_status=prev_status,
                        previous_seats=prev.seats_available,
                        seats_available=curr.seats_available,
                    ),
                )
            )
        seat_event = (prev_status == SOLD_OUT and curr.status == AVAILABLE) or (
            prev_status == AVAILABLE
            and curr.status == AVAILABLE
            and prev.seats_available is not None
            and curr.seats_available is not None
            and curr.seats_available > prev.seats_available
        )
        if seat_event and _seat_alertable(prev, curr, watch):
            events.append(
                (
                    watch,
                    WatchEvent(
                        kind=SEATS_AVAILABLE,
                        showtime=curr,
                        previous_status=prev_status,
                        previous_seats=prev.seats_available,
                        seats_available=curr.seats_available,
                    ),
                )
            )

    # Group newly appeared showtimes per movie.  A watch only cares about the
    # movie it targets, so attach the group to watches of that movie.
    new_by_movie, _, _ = scan(previous_map, current_map)
    for movie_id, showtimes in new_by_movie.items():
        times = tuple(sorted({s.time for s in showtimes}))
        for watch in watches:
            if (watch.get("scope") or "showtime") in {"movie", "movie_all_dates"}:
                continue
            if watch["movie_id"] != movie_id:
                continue
            first = min(showtimes, key=lambda s: (s.time, s.hall_type))
            events.append(
                (
                    watch,
                    WatchEvent(
                        kind=NEW_SHOWTIMES,
                        showtime=first,
                        seats_available=first.seats_available,
                        is_new=True,
                        times=times,
                    ),
                )
            )
    return events


class Watcher:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        cache: Cache,
        scheduler: Scheduler,
        providers: ProviderRegistry,
        http: HttpClient,
        notifier: Any | None = None,
        stats: Any | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_admin_message: Callable[[str], Awaitable[None]] | None = None,
        concurrency: int = 4,
    ) -> None:
        self.settings = settings
        self.db = db
        self.cache = cache
        self.scheduler = scheduler
        self.providers = providers
        self.http = http
        self.notifier = notifier
        self.stats = stats
        self._clock = clock
        self._sleep = sleep
        self._on_admin_message = on_admin_message
        self._coalescer = RequestCoalescer()
        self._semaphore = asyncio.Semaphore(max(concurrency, 1))
        self._dates_cache: dict[str, tuple[float, list[str]]] = {}
        self.last_run: float | None = None
        self.last_error: str | None = None

    # ---------------------------------------------------------------- lifecycle
    async def sync_targets(self) -> int:
        today = today_iso(self.settings.timezone)
        now = self._clock()
        now_iso = _iso(now)
        await self._backfill_watch_expiries()
        await self._expire_finished_watches(now_iso)
        # Legacy rows without an expiry are closed by date as a final safety
        # net; the normal path uses ``expires_at`` so the user gets one notice.
        await self.db.close_past_date_watches(today, now_iso)
        await self.db.prune_watch_baselines(today)
        await self._delete_old_watches(now)
        rows = await self.db.active_watch_targets()
        active_keys: set[str] = set()
        supported = getattr(self.providers, "names", None)
        supported = supported() if callable(supported) else None
        for row in rows:
            if supported is not None and row["provider"] not in supported:
                # A database can outlive a provider switch; keep the old rows
                # stored but do not schedule work the current process cannot do.
                continue
            target = TargetKey(
                provider=row["provider"],
                branch_id=row["branch_id"],
                date=row["date"],
                movie_id=row["movie_id"],
            )
            active_keys.add(target.key)
            if target.key not in self.scheduler:
                # Check newly discovered targets on the next tick rather than
                # waiting a full (possibly 15 minute) far-date interval.
                self.scheduler.add(target, status=None, interval=0.0, now=self._clock())
        await self._expand_all_dates(today, active_keys)
        removed = self.scheduler.remove_missing(active_keys)
        return len(rows) + removed

    async def _backfill_watch_expiries(self) -> None:
        """Give older date-specific watches an expiry without a migration step."""

        rows = await self.db.active_watches_missing_expiry()
        for watch in rows:
            expires = self._fallback_expiry(watch)
            if expires:
                await self.db.set_watch_expires_at(int(watch["id"]), expires)

    def _fallback_expiry(self, watch: dict[str, Any]) -> str | None:
        date = str(watch.get("date") or "")
        if not date or date == "*":
            return None
        if (watch.get("scope") or "showtime") in {"movie", "movie_all_dates"}:
            return day_end_iso(date, self.settings.timezone)
        return expiry_iso(date, str(watch.get("showtime") or ""), self.settings.timezone)

    async def _expire_finished_watches(self, now_iso: str) -> int:
        """Close due watches, then send one grouped message per affected user."""

        rows = await self.db.active_expired_watches(now_iso)
        if not rows:
            return 0
        for watch in rows:
            await self.db.expire_watch(int(watch["id"]), now_iso)

        pending = [watch for watch in rows if not int(watch.get("expiry_notified") or 0)]
        if not pending:
            return 0
        if self.notifier is None or not hasattr(self.notifier, "send_watch_expired"):
            for watch in pending:
                await self.db.mark_watch_expiry_notified(int(watch["id"]))
            return 0

        grouped: dict[int, list[dict[str, Any]]] = {}
        for watch in pending:
            grouped.setdefault(int(watch["user_id"]), []).append(watch)

        sent = 0
        for watches in grouped.values():
            telegram_id = int(watches[0]["telegram_id"])
            try:
                await self.notifier.send_watch_expired(telegram_id, watches)
            except UserBlocked:
                logger.info("User %s blocked the bot; expiry notice skipped", telegram_id)
            except Exception:
                logger.exception("Failed to send expiry notice to %s", telegram_id)
                continue
            else:
                sent += 1
            for watch in watches:
                await self.db.mark_watch_expiry_notified(int(watch["id"]))
        return sent

    async def _delete_old_watches(self, now: float) -> None:
        cutoff = datetime.fromtimestamp(now, tz=UTC) - timedelta(
            days=self.settings.watch_retention_days
        )
        await self.db.delete_inactive_watches(cutoff.isoformat(timespec="seconds"))

    async def _expand_all_dates(self, today: str, active_keys: set[str]) -> None:
        """Turn "all available days" watches into one target per branch/day."""

        watches = await self.db.active_all_dates_watches()
        if not watches:
            return
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for watch in watches:
            grouped.setdefault((watch["provider"], watch["branch_id"]), []).append(watch)
        for (provider, branch_id), group in grouped.items():
            dates = await self._branch_dates(provider, branch_id)
            dates = [value for value in dates if value >= today][: self.settings.all_dates_max]
            expires = day_end_iso(dates[-1], self.settings.timezone) if dates else None
            for watch in group:
                watch_id = int(watch["id"])
                if expires and watch.get("expires_at") != expires:
                    await self.db.set_watch_expires_at(watch_id, expires)
                elif not dates and int(watch.get("baseline_done") or 0):
                    # The branch has no future bookable day left.  A watch
                    # that already completed its baseline can close tonight.
                    fallback = day_end_iso(today, self.settings.timezone)
                    if fallback and watch.get("expires_at") != fallback:
                        await self.db.set_watch_expires_at(watch_id, fallback)
                if not int(watch.get("baseline_done") or 0):
                    baselined = await self.db.count_watch_baselines(watch_id)
                    # Only finish the silent baseline once every expanded day
                    # has been seen, so a transient fetch failure cannot turn
                    # an existing day into a false "new date" alert.
                    if dates and baselined >= len(dates):
                        await self.db.mark_watch_baseline_done(watch_id)
                for date in dates:
                    target = TargetKey(
                        provider=provider,
                        branch_id=branch_id,
                        date=date,
                        movie_id=watch["movie_id"],
                    )
                    active_keys.add(target.key)
                    if target.key not in self.scheduler:
                        self.scheduler.add(target, status=None, interval=0.0, now=self._clock())

    async def _branch_dates(self, provider_name: str, branch_id: str) -> list[str]:
        now = self._clock()
        cached = self._dates_cache.get(branch_id)
        if cached is not None and now - cached[0] < self.settings.all_dates_refresh:
            return cached[1]
        try:
            provider = self.providers.get(provider_name)
            dates = sorted(set(await provider.get_dates(branch_id)))
        except Exception:
            logger.warning("Could not refresh dates for %s", branch_id)
            return cached[1] if cached is not None else []
        self._dates_cache[branch_id] = (now, dates)
        return dates

    async def run_once(self, now: float | None = None) -> int:
        now = self._clock() if now is None else now
        self.http.affected_hint = len(self.scheduler)
        await self._send_due_reminders(now)
        await self.sync_targets()
        due = self.scheduler.pop_due(now)
        if not due:
            return 0
        results = await asyncio.gather(
            *(self._process_with_semaphore(item, now) for item in due),
            return_exceptions=True,
        )
        sent = 0
        for result in results:
            if isinstance(result, Exception):
                logger.exception("Watcher target failed: %s", result)
            else:
                sent += int(result or 0)
        self.last_run = now
        return sent

    async def _process_with_semaphore(self, item: ScheduledTarget, now: float) -> int:
        async with self._semaphore:
            return await self._process_target(item, now)

    # ------------------------------------------------------------------ target
    async def _process_target(self, item: ScheduledTarget, now: float) -> int:
        target = item.target
        try:
            return await self._process_target_inner(target, now)
        except Exception as exc:  # keep the target alive even on bugs
            logger.exception("Watcher error for %s", target.key)
            self.last_error = f"{type(exc).__name__}: {exc}"
            await self.http.report_failure("unknown", target.key)
            self.scheduler.schedule(
                target,
                status=item.status or UNKNOWN,
                slowdown=self.http.slowdown_factor * self.http.target_multiplier(target.key),
                now=now,
            )
            return 0

    async def _process_target_inner(self, target: TargetKey, now: float) -> int:
        watches = await self.db.active_watches_for_target(
            target.provider, target.branch_id, target.date, target.movie_id
        )
        if not watches:
            self.scheduler.remove(target.key)
            return 0
        if target.date < today_iso(self.settings.timezone):
            self.scheduler.remove(target.key)
            return 0

        provider = self.providers.get(target.provider)
        try:
            showtimes = await self._coalescer.run(
                target.fetch_key,
                lambda: provider.get_showtimes(target.branch_id, target.date, force_refresh=True),
            )
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Fetch failed for %s: %s", target.key, exc)
            if not isinstance(exc, (UpstreamError, CircuitOpenError)):
                await self.http.report_failure("unknown", target.key)
            self.scheduler.schedule(
                target,
                status=watches[0].get("last_status") or UNKNOWN,
                slowdown=self.http.slowdown_factor * self.http.target_multiplier(target.key),
                now=now,
            )
            return 0

        movie_showtimes = [s for s in showtimes if s.movie_id == target.movie_id]
        current_map = showtime_map(movie_showtimes)
        normal_watches = [w for w in watches if (w.get("date") or "") != "*"]
        all_dates_watches = [w for w in watches if (w.get("date") or "") == "*"]
        previous_raw = await self.cache.get_json(
            snapshot_key(target.provider, target.branch_id, target.date, target.movie_id),
            allow_stale=True,
        )
        previous = [Showtime.from_dict(item) for item in previous_raw] if previous_raw else []

        if previous_raw is None:
            # Baseline: never flood users because the bot just started.
            events, updates = await self._all_dates_candidates(
                all_dates_watches, [], movie_showtimes, target
            )
            sent, deferred = await self._dispatch(events, now)
            await self._commit_baselines(updates, deferred)
            await self._store_snapshot(target, movie_showtimes)
            await self._update_watch_states(normal_watches, current_map, target.date)
            self._reschedule(target, movie_showtimes, now)
            return sent

        normal_events = compute_watch_events(
            previous, movie_showtimes, normal_watches, self.settings.morning_end_hour
        )
        all_events, updates = await self._all_dates_candidates(
            all_dates_watches, previous, movie_showtimes, target
        )
        events = normal_events + all_events
        if events:
            confirmed = await self._confirm_showtimes(target)
            if confirmed is None:
                # Upstream changed again or failed: keep the old snapshot and
                # try next cycle; no half-confirmed alert.
                self._reschedule(target, movie_showtimes, now)
                return 0
            movie_showtimes = confirmed
            normal_events = compute_watch_events(
                previous, movie_showtimes, normal_watches, self.settings.morning_end_hour
            )
            all_events, updates = await self._all_dates_candidates(
                all_dates_watches, previous, movie_showtimes, target
            )
            events = normal_events + all_events

        sent, deferred = await self._dispatch(events, now)
        await self._commit_baselines(updates, deferred)
        await self._store_snapshot(target, movie_showtimes)
        await self._update_watch_states(normal_watches, showtime_map(movie_showtimes), target.date)
        self._reschedule(target, movie_showtimes, now)
        return sent

    async def _all_dates_candidates(
        self,
        watches: list[dict[str, Any]],
        previous: list[Showtime],
        current: list[Showtime],
        target: TargetKey,
    ) -> tuple[list[tuple[dict[str, Any], WatchEvent]], list[tuple[int, str, str | None]]]:
        """Diff all-days watches against their own per-date baseline.

        A watch's first full scan is silent.  Afterwards a date that starts
        showing the movie (or a brand new date on sale) produces one
        ``NEW_DATE_OPENED`` alert instead of a generic "new showtimes" one.
        """

        events: list[tuple[dict[str, Any], WatchEvent]] = []
        updates: list[tuple[int, str, str | None]] = []
        for watch in watches:
            watch_id = int(watch["id"])
            hall = format_key(watch.get("hall_type"))
            if hall == "*":
                previous_shows, current_shows = previous, current
            else:
                previous_shows = [s for s in previous if format_key(s.hall_type) == hall]
                current_shows = [s for s in current if format_key(s.hall_type) == hall]
            status = aggregate_status(current_shows) if current_shows else None
            baseline = await self.db.get_watch_baseline(watch_id, target.date)
            updates.append((watch_id, target.date, status))
            if baseline is None:
                if int(watch.get("baseline_done") or 0) and current_shows:
                    events.append((watch, self._new_date_event(current_shows)))
                continue
            previous_status = baseline.get("status")
            if previous_status in {None, "", UNKNOWN} and current_shows:
                events.append((watch, self._new_date_event(current_shows)))
                continue
            events.extend(
                compute_watch_events(
                    previous_shows, current_shows, [watch], self.settings.morning_end_hour
                )
            )
        return events, updates

    @staticmethod
    def _new_date_event(showtimes: list[Showtime]) -> WatchEvent:
        ordered = sorted(showtimes, key=lambda s: (s.time, s.hall_type))
        return WatchEvent(
            kind=NEW_DATE_OPENED,
            showtime=ordered[0],
            seats_available=ordered[0].seats_available,
            times=tuple(sorted({s.time for s in ordered})),
        )

    async def _commit_baselines(
        self,
        updates: list[tuple[int, str, str | None]],
        deferred: set[tuple[int, str]] | None = None,
    ) -> None:
        for watch_id, date, status in updates:
            if deferred and (watch_id, date) in deferred:
                continue
            await self.db.set_watch_baseline(watch_id, date, status)

    async def _confirm_showtimes(self, target: TargetKey) -> list[Showtime] | None:
        await self._sleep(self.settings.watch_confirm_delay)
        provider = self.providers.get(target.provider)
        try:
            showtimes = await provider.get_showtimes(
                target.branch_id, target.date, force_refresh=True
            )
        except Exception:
            logger.warning("Confirmation fetch failed for %s", target.key)
            return None
        return [s for s in showtimes if s.movie_id == target.movie_id]

    # ------------------------------------------------------------------ output
    async def _send_due_reminders(self, now: float) -> int:
        if self.notifier is None:
            return 0
        rows = await self.db.list_due_snoozes(_iso(now))
        sent = 0
        for watch in rows:
            try:
                await self.notifier.send_watch_reminder(watch)
                sent += 1
            except UserBlocked:
                logger.info("User %s blocked the bot; reminder skipped", watch.get("telegram_id"))
            except Exception:
                logger.exception("Failed to send reminder to %s", watch.get("telegram_id"))
            finally:
                await self.db.clear_watch_snooze(int(watch["id"]))
        return sent

    async def _dispatch(
        self, events: list[tuple[dict[str, Any], WatchEvent]], now: float
    ) -> tuple[int, set[tuple[int, str]]]:
        sent = 0
        deferred: set[tuple[int, str]] = set()
        for watch, event in events:
            watch_key = (int(watch["id"]), event.showtime.date)
            if not alert_allowed(watch.get("alert_mode"), event.kind):
                continue
            if event.kind == SEATS_AVAILABLE and not int(watch.get("notify_cancellations", 1) or 0):
                continue
            if _is_snoozed(watch, now):
                deferred.add(watch_key)
                continue
            if in_quiet_hours(watch, event, now, self.settings):
                logger.debug(
                    "Quiet hours: skipping %s alert for watch %s", event.kind, watch.get("id")
                )
                deferred.add(watch_key)
                continue
            if self._on_cooldown(watch, now):
                deferred.add(watch_key)
                continue
            dedupe = alert_key(
                f"{watch['provider']}:{watch['branch_id']}:{watch['date']}:"
                f"{watch['movie_id']}:{event.showtime.branch_id}:{event.showtime.date}",
                event.kind,
                event.showtime.key,
            )
            if await self.cache.get(dedupe) is not None:
                continue
            try:
                if self.notifier is not None:
                    await self.notifier.send_watch_alert(watch, event)
            except UserBlocked:
                # The notifier already deactivated this user's watches and
                # subscription.  Skip the rest of their events quietly.
                logger.info(
                    "User %s blocked the bot; watch alert skipped", watch.get("telegram_id")
                )
                continue
            except Exception:
                logger.exception("Failed to send watch alert to %s", watch.get("telegram_id"))
                deferred.add(watch_key)
                continue
            await self.cache.put(dedupe, "1", ttl=self.settings.watch_alert_cooldown)
            await self.db.mark_watch_alert(int(watch["id"]), _iso(now))
            await self.db.increment_alerts_sent(_local_date(now, self.settings.timezone))
            if self.stats is not None:
                self.stats.note_alert()
            sent += 1
        return sent, deferred

    def _on_cooldown(self, watch: dict[str, Any], now: float) -> bool:
        raw = watch.get("last_alert_at")
        if not raw:
            return False
        try:
            last = datetime.fromisoformat(raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            return (now - last.timestamp()) < self.settings.watch_alert_cooldown
        except (TypeError, ValueError):
            return False

    async def _store_snapshot(self, target: TargetKey, showtimes: list[Showtime]) -> None:
        await self.cache.put_json(
            snapshot_key(target.provider, target.branch_id, target.date, target.movie_id),
            [s.to_dict() for s in showtimes],
            ttl=self.settings.cache_stale_ttl,
        )

    async def _update_watch_states(
        self, watches: list[dict[str, Any]], current: dict[str, Showtime], date: str
    ) -> None:
        for watch in watches:
            if (watch.get("date") or "") == "*":
                continue
            if (watch.get("scope") or "showtime") in {"movie", "movie_all_dates"}:
                shows = list(current.values())
                hall = format_key(watch.get("hall_type"))
                if hall != "*":
                    shows = [show for show in shows if format_key(show.hall_type) == hall]
                status = aggregate_status(shows) if shows else None
                seats = [
                    showtime.seats_available
                    for showtime in shows
                    if showtime.seats_available is not None
                ]
                await self.db.update_watch_state(
                    int(watch["id"]), status, sum(seats) if seats else None
                )
                latest = max((show.time for show in shows if show.time), default=None)
                if latest:
                    expires = expiry_iso(date, latest, self.settings.timezone)
                    if expires and expires != watch.get("expires_at"):
                        await self.db.set_watch_expires_at(int(watch["id"]), expires)
                continue
            showtime = current.get(f"{watch['showtime']}|{watch['hall_type']}")
            await self.db.update_watch_state(
                int(watch["id"]),
                showtime.status if showtime else None,
                showtime.seats_available if showtime else None,
            )

    def _reschedule(self, target: TargetKey, showtimes: list[Showtime], now: float) -> None:
        status = aggregate_status(showtimes)
        slowdown = self.http.slowdown_factor * self.http.target_multiplier(target.key)
        self.scheduler.schedule(target, status=status, slowdown=slowdown, now=now)


def aggregate_status(showtimes: Iterable[Showtime]) -> str:
    statuses = {s.status for s in showtimes}
    if AVAILABLE in statuses:
        return AVAILABLE
    if SOLD_OUT in statuses:
        return SOLD_OUT
    if NOT_AVAILABLE in statuses:
        return NOT_AVAILABLE
    return UNKNOWN


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat(timespec="seconds")


def _local_date(epoch: float, timezone_name: str) -> str:
    return local_date(epoch, timezone_name).isoformat()
