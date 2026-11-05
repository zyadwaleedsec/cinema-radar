"""Telegram delivery: one shared limiter for watch alerts and broadcasts."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import i18n
import strings
from config import Settings
from db import Database
from http_client import TokenBucket
from keyboards import watch_alert_keyboard, watch_expired_keyboard
from metadata import display_language

logger = logging.getLogger(__name__)


class UserBlocked(Exception):
    def __init__(self, chat_id: int | str) -> None:
        super().__init__(f"Bot blocked by {chat_id}")
        self.chat_id = chat_id


def _is_retry_after(exc: Exception) -> bool:
    return exc.__class__.__name__ in {"TelegramRetryAfter", "RetryAfter"}


def _is_forbidden(exc: Exception) -> bool:
    return (
        exc.__class__.__name__
        in {
            "TelegramForbiddenError",
            "TelegramBadRequest",
            "Forbidden",
        }
        and "blocked" in str(exc).lower()
    )


class TelegramSender:
    """Global ~25 msg/s plus 1 msg/s per chat, with RetryAfter handling."""

    def __init__(
        self,
        bot: Any,
        settings: Settings,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self._clock = clock
        self._sleep = sleep
        self._bucket = TokenBucket(
            settings.telegram_rate_per_second,
            # Capacity 1 keeps the *sliding* one-second window at or below the
            # configured rate (a larger burst would allow rate+1 in a window).
            capacity=1.0,
            clock=clock,
            sleep=sleep,
        )
        self._last_chat_send: dict[int | str, float] = {}
        self._last_chat_sweep = self._clock()
        self._chat_lock = asyncio.Lock()
        self.sent = 0

    async def _wait_chat(self, chat_id: int | str) -> None:
        interval = 1.0 / max(self.settings.telegram_per_chat_per_second, 0.01)
        async with self._chat_lock:
            now = self._clock()
            if now - self._last_chat_sweep > 300:
                self._last_chat_sweep = now
                self._last_chat_send = {
                    chat_id: sent_at
                    for chat_id, sent_at in self._last_chat_send.items()
                    if now - sent_at < 60
                }
            last = self._last_chat_send.get(chat_id)
            if last is not None:
                wait = interval - (now - last)
                if wait > 0:
                    await self._sleep(wait)
            self._last_chat_send[chat_id] = self._clock()

    async def send(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: Any | None = None,
        parse_mode: str | None = "HTML",
        disable_web_page_preview: bool = True,
        photo_url: str | None = None,
    ) -> Any:
        await self._bucket.acquire()
        await self._wait_chat(chat_id)
        send_photo = getattr(self.bot, "send_photo", None)
        if photo_url and send_photo is not None:
            try:
                message = await send_photo(
                    chat_id=chat_id,
                    photo=photo_url,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                self.sent += 1
                return message
            except Exception as exc:
                if _is_retry_after(exc):
                    retry_after = float(getattr(exc, "retry_after", 1) or 1)
                    logger.warning("Telegram flood limit: waiting %ss", retry_after)
                    await self._sleep(retry_after)
                elif _is_forbidden(exc):
                    raise UserBlocked(chat_id) from exc
                else:
                    # Telegram may reject a poster URL (expired, blocked, too
                    # large).  The alert text still matters, so fall back.
                    logger.warning("sendPhoto failed (%s); falling back to text", exc)
        attempts = 2
        for attempt in range(attempts):
            try:
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                self.sent += 1
                return message
            except Exception as exc:
                if _is_retry_after(exc):
                    retry_after = float(getattr(exc, "retry_after", 1) or 1)
                    logger.warning("Telegram flood limit: waiting %ss", retry_after)
                    await self._sleep(retry_after)
                    if attempt + 1 < attempts:
                        continue
                if _is_forbidden(exc):
                    raise UserBlocked(chat_id) from exc
                raise


class Notifier:
    def __init__(
        self,
        sender: TelegramSender,
        db: Database,
        settings: Settings,
        metadata: Any | None = None,
    ) -> None:
        self.sender = sender
        self.db = db
        self.settings = settings
        self.metadata = metadata
        self.bot_username = settings.bot_username

    def manage_url(self, watch_id: int) -> str | None:
        if not self.bot_username:
            return None
        return f"https://t.me/{self.bot_username}?start=w{watch_id}"

    async def _localized_title(self, watch: dict[str, Any]) -> str | None:
        """Arabic title for this recipient, or ``None`` to keep the provider's."""

        if self.metadata is None:
            return None
        language = display_language(watch.get("lang"))
        if not language:
            return None
        title = str(watch.get("movie_name") or "").strip()
        if not title:
            return None
        try:
            movie = await self.metadata.localize(title, language=language)
        except Exception:
            return None
        return movie.title if movie is not None else None

    async def send_watch_alert(self, watch: dict[str, Any], event: Any) -> None:
        title = await self._localized_title(watch)
        with i18n.use(watch.get("lang")):
            text, keyboard = self._watch_alert_payload(watch, event, title_override=title)
            brand = strings.cinema_name(watch.get("provider")) if watch.get("provider") else ""
            if brand:
                text = f"🎬 ({brand})\n{text}"
        try:
            await self.sender.send(
                int(watch["telegram_id"]), text, keyboard, photo_url=watch.get("poster_url")
            )
        except UserBlocked:
            await self._deactivate(int(watch["telegram_id"]))
            logger.info("Deactivated blocked user %s", watch["telegram_id"])
            raise

    def _watch_alert_payload(
        self,
        watch: dict[str, Any],
        event: Any,
        title_override: str | None = None,
    ) -> tuple[str, Any]:
        showtime = event.showtime
        movie_title = (
            title_override or showtime.movie_name or watch.get("movie_name") or ""
        ).strip()
        movie_scope = (watch.get("scope") or "showtime") in {"movie", "movie_all_dates"}
        times = list(event.times or ())
        if event.kind == "NEW_DATE_OPENED":
            text = strings.alert_new_date(
                movie_title,
                watch["branch_name"],
                showtime.date,
                times,
                showtime.hall_type,
            )
        elif event.kind == "BOOKING_OPENED":
            if movie_scope and len(times) > 1:
                text = strings.alert_movie_booking_opened(
                    movie_title,
                    watch["branch_name"],
                    showtime.date,
                    times,
                    event.seats_available,
                )
            else:
                text = strings.alert_booking_opened(
                    movie_title,
                    showtime.hall_type,
                    showtime.time,
                    watch["branch_name"],
                    event.seats_available,
                    showtime.date,
                )
        elif event.kind == "SEATS_AVAILABLE":
            if movie_scope and len(times) > 1:
                text = strings.alert_movie_seats_available(
                    movie_title,
                    watch["branch_name"],
                    showtime.date,
                    times,
                    event.seats_available,
                )
            else:
                text = strings.alert_seats_available(
                    movie_title,
                    showtime.hall_type,
                    showtime.time,
                    watch["branch_name"],
                    event.seats_available,
                    showtime.date,
                )
        else:
            text = strings.alert_new_showtimes(
                movie_title,
                watch["branch_name"],
                showtime.date,
                list(event.times or (showtime.time,)),
            )
        facts = strings.movie_facts(
            watch.get("duration_minutes"), watch.get("rating"), watch.get("language")
        )
        if facts:
            text += f"\n\n{facts}"
        imax = strings.imax_line(watch.get("imax_status"))
        if imax:
            text += f"\n\n{imax}"
        text += f"\n\n<i>{strings.alert_footer()}</i>"
        keyboard = watch_alert_keyboard(
            int(watch["id"]),
            showtime.booking_url,
            watch.get("trailer_url"),
            self.manage_url(int(watch["id"])),
        )
        return text, keyboard

    async def send_watch_reminder(self, watch: dict[str, Any]) -> None:
        title = await self._localized_title(watch)
        with i18n.use(watch.get("lang")):
            text = self._watch_reminder_text(watch, title_override=title)
            brand = strings.cinema_name(watch.get("provider")) if watch.get("provider") else ""
            if brand:
                text = f"🎬 ({brand})\n{text}"
            keyboard = watch_alert_keyboard(
                int(watch["id"]),
                watch.get("booking_url"),
                watch.get("trailer_url"),
                self.manage_url(int(watch["id"])),
            )
        try:
            await self.sender.send(
                int(watch["telegram_id"]),
                text,
                keyboard,
                photo_url=watch.get("poster_url"),
            )
        except UserBlocked:
            await self._deactivate(int(watch["telegram_id"]))
            logger.info("Deactivated blocked user %s", watch["telegram_id"])
            raise

    def _watch_reminder_text(self, watch: dict[str, Any], title_override: str | None = None) -> str:
        text = strings.watch_reminder(
            title_override or watch["movie_name"],
            watch["branch_name"],
            watch["date"],
            watch["showtime"],
            watch["hall_type"],
            watch.get("last_status") or "UNKNOWN",
            watch.get("last_seats"),
            watch.get("scope"),
        )
        facts = strings.movie_facts(
            watch.get("duration_minutes"), watch.get("rating"), watch.get("language")
        )
        if facts:
            text += f"\n\n{facts}"
        imax = strings.imax_line(watch.get("imax_status"))
        if imax:
            text += f"\n\n{imax}"
        return text

    async def send_watch_expired(self, telegram_id: int, watches: list[dict[str, Any]]) -> None:
        """One grouped cleanup notice per user, no matter how many watches ended."""

        lang = watches[0].get("lang") if watches else None
        if not lang:
            user = await self.db.get_user(telegram_id)
            lang = (user or {}).get("lang")
        with i18n.use(lang):
            rows = [
                strings.watch_expired_row(
                    watch["movie_name"],
                    watch["branch_name"],
                    str(watch.get("date") or ""),
                    str(watch.get("showtime") or ""),
                )
                for watch in watches[:15]
            ]
            text = strings.watch_expired_summary(rows, more=max(0, len(watches) - 15))
            keyboard = watch_expired_keyboard()
        try:
            await self.sender.send(telegram_id, text, keyboard)
        except UserBlocked:
            await self._deactivate(telegram_id)
            logger.info("Deactivated blocked user %s", telegram_id)
            raise

    async def send_admin(self, text: str | Callable[[], str]) -> None:
        """Send an operator message in the admin's own language.

        A callable is preferred: it is evaluated here so the text is built under
        the admin's catalog even when the caller runs in a background task.
        """

        if not self.settings.admin_id:
            return
        with i18n.use(i18n.admin_language()):
            body = text() if callable(text) else text
        try:
            await self.sender.send(self.settings.admin_id, body)
        except Exception:
            logger.exception("Could not send admin message")

    async def _deactivate(self, telegram_id: int) -> None:
        await self.db.deactivate_watches_for_telegram(telegram_id)
        await self.db.deactivate_subscription_for_telegram(telegram_id)
