"""Timezone helpers with a safe fallback when tzdata is unavailable."""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as date_cls
from datetime import time as time_cls
from zoneinfo import ZoneInfo


def resolve_timezone(name: str):
    """Return a ZoneInfo for *name*, or UTC if the host lacks tzdata."""

    try:
        return ZoneInfo(name)
    except Exception:  # tzdata may be missing in minimal containers
        return UTC


def local_now(name: str) -> datetime:
    return datetime.now(resolve_timezone(name))


def local_date(epoch: float, name: str) -> date_cls:
    return datetime.fromtimestamp(epoch, tz=resolve_timezone(name)).date()


def today_iso(name: str) -> str:
    return local_now(name).date().isoformat()


def local_moment(date_str: str, time_str: str, name: str) -> datetime | None:
    """Combine a local ``YYYY-MM-DD`` and ``HH:MM`` into an aware datetime.

    Returns ``None`` for values the provider might leave malformed so callers
    can fall back instead of crashing a scan.
    """

    try:
        day = date_cls.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    try:
        hour_text, minute_text = str(time_str).strip().split(":", 1)
        moment = time_cls(int(hour_text), int(minute_text[:2]))
    except (TypeError, ValueError):
        return None
    return datetime.combine(day, moment, tzinfo=resolve_timezone(name))


def expiry_iso(date_str: str, time_str: str, name: str) -> str | None:
    """UTC timestamp for the moment a screening starts, or ``None``."""

    moment = local_moment(date_str, time_str, name)
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def day_end_iso(date_str: str, name: str) -> str | None:
    """UTC timestamp for 23:59 local time on *date_str*, or ``None``."""

    return expiry_iso(date_str, "23:59", name)


def is_quiet_time(epoch: float, start: int, end: int, name: str) -> bool:
    """True when *epoch* falls inside the quiet window ``start → end``.

    Hours are local to *name*.  ``start == end`` disables quiet hours; a window
    that wraps midnight (for example ``23 → 8``) is supported.
    """

    if start == end:
        return False
    hour = datetime.fromtimestamp(epoch, tz=resolve_timezone(name)).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end
