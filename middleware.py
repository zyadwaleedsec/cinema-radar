"""Per-user sliding-window rate limiter for messages and callbacks."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import strings
from config import Settings


class RateLimitMiddleware(BaseMiddleware):
    """Max N bot actions per user per minute, with a polite refusal."""

    def __init__(self, settings: Settings, clock: Callable[[], float] | None = None) -> None:
        import time

        self.settings = settings
        self._clock = clock or time.monotonic
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._last_sweep = self._clock()

    def _sweep(self, now: float) -> None:
        """Drop buckets that have been idle for more than one window."""

        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        stale = [
            user_id for user_id, bucket in self._hits.items() if not bucket or now - bucket[-1] > 60
        ]
        for user_id in stale:
            self._hits.pop(user_id, None)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        now = self._clock()
        self._sweep(now)
        bucket = self._hits[user.id]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.settings.user_rate_limit_per_minute:
            text = strings.rate_limited()
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer(text, show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(text)
            except Exception:
                pass
            return None
        bucket.append(now)
        return await handler(event, data)
