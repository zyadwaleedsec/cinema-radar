"""Small helpers shared by routers."""

from __future__ import annotations

import contextlib
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

import strings
from ui import Screen, render
from utils import json_list

__all__ = [
    "answer",
    "edit",
    "int_part",
    "is_admin",
    "json_list",
    "loading",
    "send",
    "split_cb",
    "toast",
]


async def edit(
    callback: CallbackQuery,
    text: str,
    keyboard: Any = None,
    photo_url: str | None = None,
) -> None:
    """Edit the current screen, ignoring "message is not modified"."""

    await render.edit_screen(
        callback,
        Screen(text=text, keyboard=keyboard, photo_url=photo_url, is_rtl=strings.RTL),
    )


async def send(
    message: Message,
    text: str,
    keyboard: Any = None,
    photo_url: str | None = None,
) -> Any:
    """Send a screen as a new message."""

    return await render.send_screen(
        message,
        Screen(text=text, keyboard=keyboard, photo_url=photo_url, is_rtl=strings.RTL),
    )


async def answer(callback: CallbackQuery, text: str = "", alert: bool = False) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await callback.answer(text=text, show_alert=alert)


async def toast(callback: CallbackQuery, text: str) -> None:
    """A non-blocking confirmation shown above the keyboard."""

    await answer(callback, text)


async def loading(callback: CallbackQuery) -> None:
    """Show a typing indicator while a slow step runs."""

    with contextlib.suppress(Exception):
        await callback.bot.send_chat_action(chat_id=callback.from_user.id, action="typing")


def split_cb(data: str | None, parts: int | None = None) -> list[str]:
    values = (data or "").split(":")
    if parts is not None:
        while len(values) < parts:
            values.append("")
        return values[:parts]
    return values


def int_part(data: str | None, index: int, parts: int | None = None) -> int | None:
    """Parse one integer callback segment, returning ``None`` when invalid."""

    values = split_cb(data, parts)
    try:
        return int(values[index])
    except (IndexError, TypeError, ValueError):
        return None


def is_admin(user_id: int, admin_id: int) -> bool:
    return bool(admin_id) and user_id == admin_id
