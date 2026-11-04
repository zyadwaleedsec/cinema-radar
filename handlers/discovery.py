"""One-tap watch creation from a discovery alert."""

from __future__ import annotations

import contextlib
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery

import strings
from cache import showtimes_key
from config import Settings
from db import Database, DuplicateWatch, WatchLimitReached
from handlers.utils import answer, loading, send
from models import Movie, Showtime, TargetKey
from scheduler import Scheduler, expected_opening_for

router = Router(name="discovery")


@router.callback_query(F.data.startswith("dw:"))
async def watch_from_discovery(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    cache,
    scheduler: Scheduler,
    provider: Any,
    providers: Any = None,
) -> None:
    token = (callback.data or "").split(":", 1)[1]
    await loading(callback)
    action = await db.get_discovery_action(token)
    if not action or int(action.get("user_id") or 0) != callback.from_user.id:
        await answer(callback, strings.error_generic(), alert=True)
        return
    selected = provider
    if providers is not None and hasattr(providers, "get"):
        with contextlib.suppress(Exception):
            selected = providers.get(action.get("provider") or settings.provider)
    provider_name = getattr(selected, "name", None) or action.get("provider") or settings.provider
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    showtimes = list(
        await selected.get_showtimes(
            action["branch_id"], action["date"], movie_id=action["movie_id"]
        )
    )
    if not showtimes:
        raw = await cache.get_json(
            showtimes_key(provider_name, action["branch_id"], action["date"]),
            ttl=settings.cache_showtimes_ttl,
        )
        fallback = [Showtime.from_dict(item) for item in (raw or [])]
        showtimes = [s for s in fallback if s.movie_id == action["movie_id"]]
    showtimes.sort(key=lambda s: (s.time, s.hall_type))
    showtime = showtimes[0] if showtimes else None

    # The discovery event carries the full movie payload, but the action row
    # only stores id/name.  Recover the slug from the day's listing when we can
    # so the 7-day detail cache is keyed the same way as normal watches.
    movie = Movie(action["movie_id"], action["movie_name"], action["movie_id"])
    try:
        listing = await selected.get_movies(action["branch_id"], action["date"])
    except Exception:
        listing = []
    match = next((m for m in listing if m.id == action["movie_id"]), None)
    if match is not None:
        movie = match
    if hasattr(selected, "get_movie_details"):
        with contextlib.suppress(Exception):
            movie = await selected.get_movie_details(movie)
    try:
        await db.add_watch(
            user_id=int(user["id"]),
            provider=provider_name,
            branch_id=action["branch_id"],
            branch_name=action["branch_name"],
            date=action["date"],
            movie_id=action["movie_id"],
            movie_name=action["movie_name"],
            showtime=showtime.time if showtime else "",
            hall_type=showtime.hall_type if showtime else "",
            watch_limit=int(user["watch_limit"]),
            booking_url=showtime.booking_url if showtime else None,
            poster_url=movie.poster_url,
            duration_minutes=movie.duration_minutes,
            rating=movie.rating,
            language=movie.language,
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
    target = TargetKey(
        provider=provider_name,
        branch_id=action["branch_id"],
        date=action["date"],
        movie_id=action["movie_id"],
    )
    scheduler.add(
        target,
        status=showtime.status if showtime else None,
        expected_open_at=expected_opening_for(action["date"]),
    )
    await answer(callback, strings.setting_saved(), alert=False)
    await send(
        callback.message,
        strings.watch_created(
            action["branch_name"],
            action["date"],
            action["movie_name"],
            showtime.time if showtime else "—",
            showtime.hall_type if showtime else "—",
        ),
    )


@router.callback_query(F.data == "ds:stop")
async def stop_discovery(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await db.set_subscription_active(int(user["id"]), False)
    await answer(callback, strings.setting_saved(), alert=False)
