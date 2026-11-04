"""Per-user sliding-window rate limiter for messages and callbacks."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import deeplinks
import i18n
import strings
from config import Settings
from db import Database
from keyboards import language_keyboard


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


class LanguageMiddleware(BaseMiddleware):
    """Load the user's language and block the app until they choose one.

    Runs before the rate limiter so even the "slow down" message is localized.
    A user with ``users.lang IS NULL`` (everyone on first run, including people
    who onboarded before English existed) only sees the bilingual picker until
    they tap a language.  The operator sees the same picker on ``/start``; only
    the hidden admin commands and donation decisions stay available before the
    choice, defaulting to Arabic.
    """

    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        row = await self.db.get_or_create_user(user.id, watch_limit=self.settings.free_watch_limit)
        data["user_row"] = row
        lang = row.get("lang")
        is_admin = bool(self.settings.admin_id) and user.id == self.settings.admin_id

        if not lang and is_admin and _is_admin_surface(event):
            lang = i18n.DEFAULT_LANGUAGE

        if not lang and not _is_language_choice(event):
            if isinstance(event, Message):
                _remember_deeplink(event)
            await _show_language_picker(event, getattr(user, "language_code", None))
            return None

        # The picker callback runs in the new language; its handler sets the
        # catalog before answering.
        if lang:
            i18n.set_language(lang)
        data["lang"] = i18n.get_language()
        return await handler(event, data)


def _is_language_choice(event: TelegramObject) -> bool:
    return isinstance(event, CallbackQuery) and (event.data or "").startswith("lang:set:")


# Surfaces that must keep working for the operator before a language is stored.
# ``/start`` deliberately stays out so the admin sees the same first-run flow
# as everyone else.
_ADMIN_COMMANDS = {"/admin", "/status", "/grant", "/revoke", "/imax"}


def _is_admin_surface(event: TelegramObject) -> bool:
    if isinstance(event, Message):
        head = (event.text or "").strip().split(maxsplit=1)[0].split("@", 1)[0].lower()
        return head in _ADMIN_COMMANDS
    if isinstance(event, CallbackQuery):
        return (event.data or "").startswith("dn:")
    return False


def _remember_deeplink(message: Message) -> None:
    text = (message.text or "").strip()
    if not text.startswith("/start"):
        return
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        deeplinks.remember(message.from_user.id, parts[1])


async def _show_language_picker(event: TelegramObject, language_code: str | None = None) -> None:
    # Lead with the language of their Telegram app when we can guess it.
    catalog = i18n.for_language(language_code or i18n.DEFAULT_LANGUAGE)
    text = catalog.language_screen()
    keyboard = language_keyboard()
    if isinstance(event, CallbackQuery):
        from handlers.utils import answer

        await answer(event)
        if event.message is not None:
            try:
                await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
