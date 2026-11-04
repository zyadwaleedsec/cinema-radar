"""Short-lived memory for ``/start`` deep links that arrive before onboarding.

A brand-new user who taps ``?start=b<branch>`` must pick a language first, so
the payload is parked here (in memory, single process, ten minutes) and taken
back by the language handler once onboarding is done.
"""

from __future__ import annotations

import time

_MAX_PENDING = 500
_TTL_SECONDS = 600
_pending: dict[int, tuple[str, float]] = {}


def remember(user_id: int, payload: str) -> None:
    payload = (payload or "").strip()
    if not payload:
        return
    now = time.monotonic()
    if len(_pending) >= _MAX_PENDING:
        _sweep(now, force=True)
    _pending[int(user_id)] = (payload, now)


def take(user_id: int) -> str:
    entry = _pending.pop(int(user_id), None)
    if entry is None:
        return ""
    payload, created = entry
    if time.monotonic() - created > _TTL_SECONDS:
        return ""
    return payload


def clear() -> None:
    _pending.clear()


def _sweep(now: float, force: bool = False) -> None:
    stale = [key for key, (_, created) in _pending.items() if now - created > _TTL_SECONDS]
    for key in stale:
        _pending.pop(key, None)
    if force and len(_pending) >= _MAX_PENDING:
        # Drop the oldest half rather than growing without bound.
        oldest = sorted(_pending.items(), key=lambda item: item[1][1])
        for key, _ in oldest[: len(oldest) // 2 or 1]:
            _pending.pop(key, None)
