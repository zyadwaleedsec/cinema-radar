"""Watch creation from a discovery alert.

The alert can list several movies, so the watch button is a chooser: the user
picks the movie they care about and the watch is built from the event data that
was sent with the alert.  Nothing is fetched again at callback time, so an
upstream hiccup can no longer break the button.
"""

from __future__ import annotations

import json
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery

import strings
from config import Settings
from db import Database, DuplicateWatch, WatchLimitReached
from handlers.utils import answer, edit, send
from keyboards import discovery_movie_keyboard
from models import TargetKey
from scheduler import Scheduler, expected_opening_for
from timeutil import today_iso

router = Router(name="discovery")


async def _owned_action(db: Database, callback: CallbackQuery, token: str) -> dict[str, Any] | None:
    """Load an alert only when it belongs to the person tapping it.

    Newer rows store the Telegram id; rows sent before 2.8.2 stored the internal
    ``users.id``, so accept either until they age out of the seven-day window.
    """

    action = await db.get_discovery_action(token)
    if not action:
        return None
    owner = int(action.get("user_id") or 0)
    if owner == callback.from_user.id:
        return action
    user = await db.get_user(callback.from_user.id)
    if user is not None and owner == int(user["id"]):
        return action
    return None


def _choices(action: dict[str, Any]) -> list[dict[str, Any]]:
    """Movies carried by a discovery alert, newest payload shape first."""

    raw = action.get("payload")
    if raw:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            payload = payload.get("movies")
        if isinstance(payload, list):
            choices = [item for item in payload if isinstance(item, dict) and item.get("movie_id")]
            if choices:
                return choices
    # Actions created before the payload column existed still open a chooser
    # with the single movie stored on the row.
    return [
        {
            "provider": action.get("provider") or "vox",
            "branch_id": action.get("branch_id") or "",
            "branch_name": action.get("branch_name") or "",
            "date": action.get("date") or "",
            "movie_id": action.get("movie_id") or "",
            "movie_name": action.get("movie_name") or "",
            "title": action.get("movie_name") or "",
            "line": action.get("movie_name") or "",
            "showtime": "",
            "hall_type": "",
        }
    ]


@router.callback_query(F.data.startswith("dw:"))
async def watch_from_discovery(callback: CallbackQuery, db: Database) -> None:
    token = (callback.data or "").split(":", 1)[1]
    action = await _owned_action(db, callback, token)
    if not action:
        await answer(callback, strings.error_generic(), alert=True)
        return
    choices = _choices(action)
    await send(
        callback.message,
        strings.discovery_watch_prompt(),
        discovery_movie_keyboard(token, choices),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("dwm:"))
async def watch_movie_chosen(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    scheduler: Scheduler,
) -> None:
    parts = (callback.data or "").split(":")
    token = parts[1] if len(parts) > 1 else ""
    try:
        index = int(parts[2]) if len(parts) > 2 else -1
    except ValueError:
        index = -1
    action = await _owned_action(db, callback, token)
    if not action:
        await answer(callback, strings.error_generic(), alert=True)
        return
    choices = _choices(action)
    if not 0 <= index < len(choices):
        await answer(callback, strings.error_expired(), alert=True)
        return
    choice = choices[index]

    provider_name = str(choice.get("provider") or action.get("provider") or settings.provider)
    branch_id = str(choice.get("branch_id") or action.get("branch_id") or "")
    branch_name = str(choice.get("branch_name") or action.get("branch_name") or "")
    movie_id = str(choice.get("movie_id") or action.get("movie_id") or "")
    movie_name = str(choice.get("movie_name") or action.get("movie_name") or "")
    title = str(choice.get("title") or movie_name)
    date = str(choice.get("date") or action.get("date") or today_iso(settings.timezone))
    showtime = str(choice.get("showtime") or "")
    hall = str(choice.get("hall_type") or "")
    if not (branch_id and movie_id):
        await answer(callback, strings.error_expired(), alert=True)
        return

    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    try:
        await db.add_watch(
            user_id=int(user["id"]),
            provider=provider_name,
            branch_id=branch_id,
            branch_name=branch_name,
            date=date,
            movie_id=movie_id,
            movie_name=movie_name,
            showtime=showtime,
            hall_type=hall,
            watch_limit=int(user["watch_limit"]),
            booking_url=str(choice.get("booking_url") or "") or None,
            poster_url=str(choice.get("poster_url") or "") or None,
            duration_minutes=choice.get("duration_minutes"),
            rating=str(choice.get("rating") or "") or None,
            language=str(choice.get("language") or "") or None,
            synopsis=str(choice.get("synopsis") or "") or None,
            trailer_url=str(choice.get("trailer_url") or "") or None,
            imax_status=str(choice.get("imax_status") or "") or None,
        )
    except WatchLimitReached:
        await answer(
            callback,
            strings.watch_limit_reached(
                int(user["watch_limit"]),
                settings.supporter_watch_limit,
                settings.donation_min_amount,
                bool(user.get("is_supporter")),
            ),
            alert=True,
        )
        return
    except DuplicateWatch:
        await answer(callback, strings.duplicate_watch(), alert=True)
        return

    scheduler.add(
        TargetKey(
            provider=provider_name,
            branch_id=branch_id,
            date=date,
            movie_id=movie_id,
        ),
        status=None,
        expected_open_at=expected_opening_for(date),
    )
    await answer(callback, strings.setting_saved(), alert=False)
    await edit(
        callback,
        strings.watch_created(
            branch_name,
            date,
            title,
            showtime or "—",
            hall or "—",
        ),
    )


@router.callback_query(F.data == "ds:stop")
async def stop_discovery(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await db.set_subscription_active(int(user["id"]), False)
    await answer(callback, strings.setting_saved(), alert=False)
