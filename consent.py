"""Explicit first-run consent and the tiny pending-language buffer.

Nothing is written to the database until the user taps **I agree**.  The chosen
language is held in memory only while the consent screen is open, so a decline
leaves no row behind.
"""

from __future__ import annotations

import time
from typing import Any

#: Bump this when the privacy notice changes materially.  Users whose stored
#: version is lower see the consent screen again before the bot stores anything.
CONSENT_VERSION = 1

_PENDING_TTL = 24 * 3600
_PENDING_LIMIT = 5000
_pending: dict[int, tuple[str, float]] = {}


def remember_pending_language(telegram_id: int, lang: str) -> None:
    now = time.monotonic()
    if len(_pending) >= _PENDING_LIMIT:
        cutoff = now - _PENDING_TTL
        for key in [key for key, (_, sent) in _pending.items() if sent < cutoff]:
            _pending.pop(key, None)
        if len(_pending) >= _PENDING_LIMIT:
            _pending.clear()
    _pending[int(telegram_id)] = (lang, now)


def pending_language(telegram_id: int) -> str | None:
    value = _pending.get(int(telegram_id))
    if value is None:
        return None
    lang, sent = value
    if time.monotonic() - sent > _PENDING_TTL:
        _pending.pop(int(telegram_id), None)
        return None
    return lang


def clear_pending_language(telegram_id: int) -> None:
    _pending.pop(int(telegram_id), None)


def clear_all() -> None:
    """Test helper: forget every pending choice."""

    _pending.clear()


def has_consent(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    try:
        return int(row.get("consent_version") or 0) >= CONSENT_VERSION
    except (TypeError, ValueError):
        return False
