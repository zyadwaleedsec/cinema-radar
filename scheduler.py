"""Per-target priority queue scheduler.

There is no global polling cycle: each (provider, branch, date, movie) target
has its own next_run in a heap.  Intervals are adaptive and jittered so requests
spread evenly instead of arriving in a burst.
"""

from __future__ import annotations

import heapq
import itertools
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls

from config import Settings
from models import AVAILABLE, NOT_AVAILABLE, SOLD_OUT, UNKNOWN, TargetKey
from timeutil import today_iso


@dataclass
class ScheduledTarget:
    target: TargetKey
    next_run: float
    interval: float
    status: str | None = None
    expected_open_at: datetime | None = None
    seq: int = 0


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Scheduler:
    def __init__(
        self,
        settings: Settings,
        clock: Callable[[], float],
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock
        self._rng = rng or random.Random()
        self._heap: list[tuple[float, int, str]] = []
        self._targets: dict[str, ScheduledTarget] = {}
        self._counter = itertools.count()

    def __len__(self) -> int:
        return len(self._targets)

    def __contains__(self, key: str) -> bool:
        return key in self._targets

    @property
    def keys(self) -> set[str]:
        return set(self._targets)

    def get(self, key: str) -> ScheduledTarget | None:
        return self._targets.get(key)

    def add(
        self,
        target: TargetKey,
        status: str | None = None,
        expected_open_at: datetime | None = None,
        interval: float | None = None,
        now: float | None = None,
    ) -> ScheduledTarget:
        now = self._clock() if now is None else now
        if interval is None:
            interval = self.compute_interval(
                target=target,
                status=status,
                now=now,
                expected_open_at=expected_open_at,
            )
        seq = next(self._counter)
        item = ScheduledTarget(
            target=target,
            next_run=now + interval,
            interval=interval,
            status=status,
            expected_open_at=expected_open_at,
            seq=seq,
        )
        self._targets[target.key] = item
        heapq.heappush(self._heap, (item.next_run, seq, target.key))
        return item

    def schedule(
        self,
        target: TargetKey,
        status: str | None,
        slowdown: float = 1.0,
        expected_open_at: datetime | None = None,
        interval: float | None = None,
        now: float | None = None,
    ) -> ScheduledTarget:
        now = self._clock() if now is None else now
        if interval is None:
            interval = self.compute_interval(
                target=target,
                status=status,
                now=now,
                slowdown=slowdown,
                expected_open_at=expected_open_at,
            )
        return self.add(
            target,
            status=status,
            expected_open_at=expected_open_at,
            interval=interval,
            now=now,
        )

    def remove(self, key: str) -> bool:
        return self._targets.pop(key, None) is not None

    def remove_missing(self, active_keys: Iterable[str]) -> int:
        active = set(active_keys)
        stale = [key for key in self._targets if key not in active]
        for key in stale:
            self.remove(key)
        return len(stale)

    def pop_due(self, now: float | None = None) -> list[ScheduledTarget]:
        now = self._clock() if now is None else now
        due: list[ScheduledTarget] = []
        while self._heap and self._heap[0][0] <= now:
            _, seq, key = heapq.heappop(self._heap)
            item = self._targets.get(key)
            if item is None or item.seq != seq:
                continue
            due.append(item)
            # Remove until the watcher explicitly reschedules it; this keeps
            # one in-flight copy per target even if processing overlaps.
            self._targets.pop(key, None)
        return due

    def next_run(self) -> float | None:
        while self._heap:
            next_at, seq, key = self._heap[0]
            item = self._targets.get(key)
            if item is not None and item.seq == seq:
                return next_at
            heapq.heappop(self._heap)
        return None

    # ------------------------------------------------------------- interval math
    def compute_interval(
        self,
        target: TargetKey,
        status: str | None,
        now: float | None = None,
        slowdown: float = 1.0,
        expected_open_at: datetime | None = None,
    ) -> float:
        s = self.settings
        now = self._clock() if now is None else now
        try:
            target_date = date_cls.fromisoformat(target.date)
            days_away = (target_date - date_cls.fromisoformat(today_iso(s.timezone))).days
        except (TypeError, ValueError):
            days_away = 0

        if days_away > s.far_date_days:
            base = self._rng.uniform(s.poll_far_min, s.poll_far_max)
        elif status == AVAILABLE:
            base = float(s.poll_open_with_seats)
        elif status == SOLD_OUT:
            base = float(s.poll_sold_out)
        elif status in {NOT_AVAILABLE, UNKNOWN, None}:
            base = float(s.poll_waiting_for_open)
            if expected_open_at is not None:
                now_dt = datetime.fromtimestamp(now, tz=UTC)
                expected = _as_aware(expected_open_at)
                window = timedelta(minutes=s.poll_opening_window_minutes)
                if expected - window <= now_dt <= expected + window:
                    base = float(s.poll_burst)
        else:
            base = float(s.poll_waiting_for_open)

        jitter = 1.0 + self._rng.uniform(-s.poll_jitter, s.poll_jitter)
        interval = base * max(slowdown, 1.0) * jitter
        return max(5.0, interval)


def expected_opening_for(date_str: str, hour: int = 0) -> datetime:
    """Rough opening time used for the burst window (midnight local date)."""

    try:
        d = date_cls.fromisoformat(date_str)
    except (TypeError, ValueError):
        d = date_cls.today()
    return datetime(d.year, d.month, d.day, hour, tzinfo=UTC)
