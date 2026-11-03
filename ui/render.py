"""Send and edit screens, preferring rich messages with a safe fallback."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import replace
from typing import Any

from aiogram.exceptions import TelegramBadRequest

from ui import classic, rich
from ui.screen import Screen

logger = logging.getLogger(__name__)

# ``None`` means "not known yet".  Once Telegram rejects a rich message we
# stop trying in ``auto`` mode until the next process restart; ``rich`` mode
# still tries because the operator asked for it explicitly.
_rich_works: bool | None = None

_RICH_REJECTION_HINTS = ("rich", "unsupported", "unknown method", "not supported")

# A short "last updated" / outage note appended to text screens by the health
# loop.  Keeping it here avoids threading the HTTP client through every handler.
_freshness_note = ""


def set_freshness_note(note: str) -> None:
    global _freshness_note
    _freshness_note = note or ""


def _decorate(screen: Screen) -> Screen:
    if not _freshness_note or screen.photo_url:
        return screen
    return replace(screen, text=screen.text + _freshness_note)


def reset_capability() -> None:
    """Test hook: forget what we learned about rich-message support."""

    global _rich_works
    _rich_works = None


def rich_supported() -> bool:
    return _rich_works is not False


def _mode(settings: Any = None) -> str:
    if settings is not None and getattr(settings, "ui_renderer", None):
        value = str(settings.ui_renderer).lower()
    else:
        try:
            from config import settings as default_settings

            value = str(getattr(default_settings, "ui_renderer", "auto")).lower()
        except Exception:  # pragma: no cover - config is always importable in prod
            value = "auto"
    return value if value in {"auto", "rich", "classic"} else "auto"


def _use_rich(settings: Any = None) -> bool:
    mode = _mode(settings)
    if mode == "classic":
        return False
    if mode == "rich":
        return True
    return rich_supported()


def _detail(exc: Exception) -> str:
    return str(exc).lower()


def _is_not_modified(exc: Exception) -> bool:
    return "message is not modified" in _detail(exc)


def _is_rich_rejection(exc: Exception) -> bool:
    text = _detail(exc)
    return any(hint in text for hint in _RICH_REJECTION_HINTS)


def _mark_rich_failed() -> None:
    global _rich_works
    _rich_works = False


def _mark_rich_ok() -> None:
    global _rich_works
    _rich_works = True


async def send_screen(message: Any, screen: Screen, settings: Any = None) -> Any:
    """Send a screen as a new message, choosing the best available renderer."""

    screen = _decorate(screen)
    if screen.photo_url:
        try:
            return await message.answer_photo(**classic.photo_payload(screen))
        except Exception as exc:  # poster rejected: the text still matters
            logger.warning("Photo card failed (%s); falling back to text", exc)

    if _use_rich(settings):
        built = rich.build(screen)
        send_rich = getattr(getattr(message, "bot", None), "send_rich_message", None)
        if built is not None and send_rich is not None:
            try:
                result = await send_rich(
                    chat_id=message.chat.id,
                    rich_message=built,
                    reply_markup=screen.keyboard,
                )
                _mark_rich_ok()
                return result
            except TelegramBadRequest as exc:
                if _is_rich_rejection(exc):
                    _mark_rich_failed()
                logger.info("Rich message rejected (%s); using classic HTML", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.info("Rich message unavailable (%s); using classic HTML", exc)

    return await message.answer(**classic.text_payload(screen))


async def edit_screen(callback: Any, screen: Screen, settings: Any = None) -> None:
    """Edit the message behind a callback, falling back only when necessary."""

    screen = _decorate(screen)
    message = getattr(callback, "message", None)
    if message is None:
        with contextlib.suppress(TelegramBadRequest):
            await callback.answer()
        return

    # Photo cards cannot be edited into text (and vice versa).  Delete the old
    # card and send the new screen so the chat stays a single clean message.
    if screen.photo_url and getattr(message, "photo", None):
        try:
            await message.edit_caption(
                caption=screen.text,
                reply_markup=screen.keyboard,
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest as exc:
            if _is_not_modified(exc):
                return
        except Exception as exc:  # pragma: no cover - defensive
            logger.info("Could not edit photo caption (%s)", exc)
        with contextlib.suppress(Exception):
            await message.delete()
        await send_screen(message, screen, settings)
        return

    if screen.photo_url or getattr(message, "photo", None):
        with contextlib.suppress(Exception):
            await message.delete()
        await send_screen(message, screen, settings)
        return

    if _use_rich(settings):
        built = rich.build(screen)
        if built is not None:
            try:
                await message.edit_text(rich_message=built, reply_markup=screen.keyboard)
                _mark_rich_ok()
                return
            except TelegramBadRequest as exc:
                if _is_not_modified(exc):
                    return
                if _is_rich_rejection(exc):
                    _mark_rich_failed()
                logger.info("Rich edit rejected (%s); using classic HTML", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.info("Rich edit unavailable (%s); using classic HTML", exc)

    try:
        await message.edit_text(**classic.text_payload(screen))
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return
        # A photo caption, an inaccessible message or a dead inline message
        # cannot be edited.  Sending the screen once is the only recovery.
        logger.info("Edit failed (%s); sending a replacement message", exc)
        with contextlib.suppress(Exception):
            await message.answer(**classic.text_payload(screen))
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("Edit failed (%s); sending a replacement message", exc)
        with contextlib.suppress(Exception):
            await message.answer(**classic.text_payload(screen))
