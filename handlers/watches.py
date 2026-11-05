"""The guided add-watch flow plus watch list/detail management."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import i18n
import search
import strings
from cache import branches_key, dates_key, movies_key, showtimes_key
from config import Settings
from db import Database, DuplicateWatch, WatchLimitReached
from handlers.utils import answer, edit, int_part, loading, send, split_cb
from keyboards import (
    WATCH_PAGE_SIZE,
    back_home_keyboard,
    branch_keyboard,
    cinema_keyboard,
    confirm_keyboard,
    confirm_window_keyboard,
    date_keyboard,
    movie_info_keyboard,
    movie_keyboard,
    retry_keyboard,
    search_keyboard,
    search_results_keyboard,
    seat_choice_keyboard,
    showtime_keyboard,
    suggestion_keyboard,
    support_keyboard,
    watch_created_keyboard,
    watch_delete_confirm_keyboard,
    watch_detail_keyboard,
    watch_seat_choice_keyboard,
    watches_clear_confirm_keyboard,
    watches_keyboard,
    window_keyboard,
)
from metadata import display_language
from models import Movie, Showtime, TargetKey, format_key
from scheduler import Scheduler, expected_opening_for
from timeutil import day_end_iso, expiry_iso, resolve_timezone, today_iso
from ui.theme import DIVIDER
from watcher import VALID_MODES

router = Router(name="watches")


class AddWatch(StatesGroup):
    cinema = State()
    branch = State()
    date = State()
    movie = State()
    search = State()
    showtime = State()
    seats = State()
    seats_custom = State()
    window_movie = State()
    window = State()


class EditSeats(StatesGroup):
    custom = State()


SEAT_MIN = 1
SEAT_MAX = 10

#: TMDB is only consulted when the query actually contains Arabic letters.
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


async def _cached(cache: Any, key: str, ttl: float) -> Any:
    return await cache.get_json(key, ttl=ttl)


async def _ack(callback: CallbackQuery) -> None:
    """Acknowledge the tap immediately, then show a typing indicator."""

    await answer(callback)
    await loading(callback)


async def _branches(cache: Any, settings: Settings, provider: Any) -> list[dict[str, Any]]:
    # Read through the provider: it serves the cache first and only fetches
    # when the cache is empty/stale, so the menu still opens after a restart.
    provider_name = getattr(provider, "name", None) or settings.provider
    branches = [b.__dict__ for b in await provider.get_branches()]
    if not branches:
        branches = await _cached(cache, branches_key(provider_name), settings.cache_static_ttl)
    return branches


def _provider_names(providers: Any, provider: Any) -> list[str]:
    if providers is not None and hasattr(providers, "names"):
        return list(providers.names())
    return [getattr(provider, "name", None) or "vox"]


def _selected_provider(providers: Any, provider: Any, data: dict[str, Any]) -> Any:
    name = data.get("provider_name")
    if name and providers is not None and hasattr(providers, "get"):
        try:
            return providers.get(name)
        except Exception:
            pass
    return provider


def _window_match(showtime: Showtime, window: str, morning_end_hour: int) -> bool:
    try:
        hour = int((showtime.time or "").split(":", 1)[0])
    except (ValueError, IndexError):
        return False
    return hour < morning_end_hour if window == "morning" else hour >= morning_end_hour


async def _all_cinemas_dates(providers: Any, provider: Any) -> list[str]:
    """Union of every enabled branch's bookable dates."""

    dates: set[str] = set()
    for name in _provider_names(providers, provider):
        selected = _selected_provider(providers, provider, {"provider_name": name})
        try:
            branches = await selected.get_branches()
        except Exception:
            continue
        for branch in branches:
            try:
                dates.update(await selected.get_dates(branch.id))
            except Exception:
                continue
    return sorted(dates)


async def _collect_window_showtimes(
    providers: Any, provider: Any, date: str, query: str
) -> list[dict[str, Any]]:
    """Fetch the matching movie's showtimes on ``date`` across every branch."""

    results: list[dict[str, Any]] = []
    for name in _provider_names(providers, provider):
        selected = _selected_provider(providers, provider, {"provider_name": name})
        try:
            branches = await selected.get_branches()
        except Exception:
            continue
        for branch in branches:
            try:
                shows = await selected.get_showtimes(branch.id, date)
            except Exception:
                continue
            if not shows:
                continue
            hits = search.rank(query, sorted({s.movie_name for s in shows if s.movie_name}))
            if not hits:
                continue
            best_name = hits[0].item
            movie_shows = [s for s in shows if s.movie_name == best_name]
            if not movie_shows:
                continue
            results.append(
                {
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "provider": name,
                    "movie_id": movie_shows[0].movie_id,
                    "movie_name": best_name,
                    "showtimes": movie_shows,
                }
            )
    return results


def _parse_branch_suffix(
    suffix: str, providers: Any, provider: Any, settings: Settings
) -> tuple[str, str]:
    """Split ``?start=b<provider>_<branch>``; legacy ``b<branch>`` defaults to VOX."""

    known = _provider_names(providers, provider)
    for name in known:
        prefix = f"{name}_"
        if suffix.startswith(prefix):
            return name, suffix[len(prefix) :]
    return getattr(provider, "name", None) or settings.provider, suffix


def _has_imax(showtimes: list[Showtime]) -> bool:
    return any(format_key(showtime.hall_type) == "IMAX" for showtime in showtimes)


def _imax_extra(movie: dict[str, Any]) -> str:
    return strings.imax_line(movie.get("imax_status"))


async def _imax_status(
    db: Database, imax: Any, movie: dict[str, Any], showtimes: list[Showtime]
) -> str | None:
    """Resolve the IMAX indicator only when the film has an IMAX screening."""

    if not _has_imax(showtimes):
        return None
    if movie.get("imax_status"):
        return str(movie["imax_status"])
    movie_id = str(movie.get("id") or "")
    if movie_id:
        override = await db.get_imax_override(movie_id)
        if override:
            return override
    if imax is None:
        return None
    try:
        return await imax.lookup(movie.get("name", ""))
    except Exception:
        return None


def _watch_expiry(
    data: dict[str, Any], scope: str, showtime: dict[str, Any], settings: Settings
) -> str | None:
    """When should this watch stop mattering?"""

    date = data.get("date", "")
    if scope == "movie_all_dates":
        dates = sorted(
            value for value in data.get("dates", []) if value >= today_iso(settings.timezone)
        )[: settings.all_dates_max]
        return day_end_iso(dates[-1], settings.timezone) if dates else None
    if scope == "movie":
        showtimes = [Showtime.from_dict(item) for item in data.get("showtimes", [])]
        selected = data.get("format")
        if selected:
            showtimes = [item for item in showtimes if format_key(item.hall_type) == selected]
        latest = max(
            (item.time for item in showtimes if item.time),
            default=showtime.get("time", ""),
        )
        if not latest:
            return day_end_iso(date, settings.timezone)
        return expiry_iso(date, latest, settings.timezone)
    return expiry_iso(date, showtime.get("time", ""), settings.timezone)


async def _begin_add(
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    search_first: bool = False,
) -> list[dict[str, Any]]:
    await state.clear()
    branches = await _branches(cache, settings, provider)
    if not branches:
        return []
    await state.set_state(AddWatch.branch)
    await state.update_data(branches=branches, search_first=search_first)
    return branches


@router.callback_query(F.data == "menu:add")
async def add_start(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    await _ack(callback)
    if len(_provider_names(providers, provider)) <= 1:
        await edit(callback, strings.loading_branches(), back_home_keyboard())
        branches = await _begin_add(state, cache, settings, provider)
        if not branches:
            await edit(callback, strings.no_data(), retry_keyboard("menu:add"))
            return
        await edit(callback, strings.choose_branch(), branch_keyboard(branches))
        return
    await state.clear()
    await state.set_state(AddWatch.cinema)
    await state.update_data(search_first=False, pending_query="")
    await edit(
        callback, strings.choose_cinema(), cinema_keyboard(_provider_names(providers, provider))
    )


@router.message(Command("search"))
async def search_cmd(
    message: Message,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    parts = (message.text or "").split(maxsplit=1)
    query = search.clean_query(parts[1]) if len(parts) > 1 else ""
    if len(_provider_names(providers, provider)) <= 1:
        branches = await _begin_add(state, cache, settings, provider, search_first=True)
        if not branches:
            await message.answer(strings.no_data(), reply_markup=retry_keyboard("menu:search"))
            return
        if query:
            await state.update_data(pending_query=query)
        await message.answer(
            strings.search_choose_branch(query), reply_markup=branch_keyboard(branches)
        )
        return
    await state.clear()
    await state.set_state(AddWatch.cinema)
    await state.update_data(search_first=True, pending_query=query)
    await message.answer(
        strings.choose_cinema(), reply_markup=cinema_keyboard(_provider_names(providers, provider))
    )


@router.message(Command("add"))
async def add_cmd(
    message: Message,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    if len(_provider_names(providers, provider)) <= 1:
        branches = await _begin_add(state, cache, settings, provider)
        if not branches:
            await send(message, strings.no_data(), retry_keyboard("menu:add"))
            return
        await send(message, strings.choose_branch(), branch_keyboard(branches))
        return
    await state.clear()
    await state.set_state(AddWatch.cinema)
    await state.update_data(search_first=False, pending_query="")
    await send(
        message, strings.choose_cinema(), cinema_keyboard(_provider_names(providers, provider))
    )


@router.callback_query(F.data == "menu:search")
async def search_menu(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    await _ack(callback)
    if len(_provider_names(providers, provider)) <= 1:
        await edit(callback, strings.loading_branches(), back_home_keyboard())
        branches = await _begin_add(state, cache, settings, provider, search_first=True)
        if not branches:
            await edit(callback, strings.no_data(), retry_keyboard("menu:search"))
            return
        await edit(callback, strings.search_choose_branch(), branch_keyboard(branches))
        return
    await state.clear()
    await state.set_state(AddWatch.cinema)
    await state.update_data(search_first=True, pending_query="")
    await edit(
        callback, strings.choose_cinema(), cinema_keyboard(_provider_names(providers, provider))
    )


@router.callback_query(AddWatch.cinema, F.data.startswith("pr:"))
async def cinema_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    name = split_cb(callback.data, 2)[1]
    if name == "all":
        await _all_cinemas_chosen(callback, state, settings, provider, providers)
        return
    if name not in _provider_names(providers, provider):
        await answer(callback, strings.error_expired(), alert=True)
        return
    selected = _selected_provider(providers, provider, {"provider_name": name})
    await _ack(callback)
    await edit(callback, strings.loading_branches(), back_home_keyboard())
    data = await state.get_data()
    search_first = data.get("search_first", False)
    pending_query = data.get("pending_query", "")
    branches = await _branches(cache, settings, selected)
    if not branches:
        await edit(callback, strings.no_data(), retry_keyboard("menu:add"))
        return
    await state.update_data(provider_name=name, branches=branches)
    await state.set_state(AddWatch.branch)
    text = strings.search_choose_branch(pending_query) if search_first else strings.choose_branch()
    await edit(callback, text, branch_keyboard(branches, back_cb="ab:cinema"))


async def _all_cinemas_chosen(
    callback: CallbackQuery, state: FSMContext, settings: Settings, provider: Any, providers: Any
) -> None:
    await _ack(callback)
    data = await state.get_data()
    query = search.clean_query(data.get("pending_query") or "")
    await state.update_data(all_cinemas=True)
    if len(search.normalize(query)) >= 2:
        await _all_cinemas_show_date(callback, state, provider, providers)
        return
    await state.set_state(AddWatch.window_movie)
    await edit(callback, strings.window_movie_prompt(), back_home_keyboard())


async def _all_cinemas_show_date(
    callback: CallbackQuery, state: FSMContext, provider: Any, providers: Any
) -> None:
    await edit(callback, strings.loading_branches(), back_home_keyboard())
    dates = await _all_cinemas_dates(providers, provider)
    if not dates:
        await edit(callback, strings.no_dates(), retry_keyboard("menu:add"))
        return
    await state.update_data(dates=dates)
    await state.set_state(AddWatch.date)
    await edit(
        callback, strings.choose_date_all_cinemas(), date_keyboard(dates, back_cb="ab:cinema")
    )


@router.message(AddWatch.window_movie)
async def window_movie_query(
    message: Message, state: FSMContext, provider: Any, providers: Any = None
) -> None:
    title = search.clean_query(message.text or "")
    if len(search.normalize(title)) < 2:
        await send(message, strings.search_too_short(), back_home_keyboard())
        return
    await state.update_data(pending_query=title)
    dates = await _all_cinemas_dates(providers, provider)
    if not dates:
        await send(message, strings.no_dates(), retry_keyboard("menu:add"))
        return
    await state.update_data(dates=dates)
    await state.set_state(AddWatch.date)
    await send(
        message, strings.choose_date_all_cinemas(), date_keyboard(dates, back_cb="ab:cinema")
    )


@router.callback_query(AddWatch.window, F.data.startswith("win:"))
async def window_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    window = split_cb(callback.data, 2)[1]
    if window not in {"morning", "evening"}:
        await answer(callback, strings.error_expired(), alert=True)
        return
    data = await state.get_data()
    await state.update_data(window=window)
    await _show_seat_picker(callback, state, data)
    await answer(callback)


@router.callback_query(AddWatch.window, F.data == "add:confirm_window")
async def confirm_window_watch(
    callback: CallbackQuery, state: FSMContext, db: Database, settings: Settings
) -> None:
    await _ack(callback)
    data = await state.get_data()
    window = data.get("window")
    date = data.get("date", "")
    movie_name = data.get("movie_name", data.get("pending_query", ""))
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    required_seats = _required_seats(data.get("required_seats")) or 1
    group_id = secrets.token_urlsafe(16)
    entries: list[dict[str, Any]] = []
    for br in data.get("window_branches", []):
        shows = [s for s in br["showtimes"] if _window_match(s, window, settings.morning_end_hour)]
        if not shows:
            continue
        entries.append(
            {
                "provider": br["provider"],
                "branch_id": br["branch_id"],
                "branch_name": br["branch_name"],
                "date": date,
                "movie_id": br["movie_id"],
                "movie_name": br["movie_name"],
                # A sentinel that keeps morning/evening distinct in the UNIQUE
                # index (showtime is ignored by the movie-scope renderer).
                "showtime": window,
                "hall_type": "*",
                "scope": "movie",
                "group_id": group_id,
                "time_window": window,
                "required_seats": required_seats,
                "expires_at": day_end_iso(date, settings.timezone),
            }
        )
    if not entries:
        await edit(callback, strings.no_showtimes_window(movie_name, date), back_home_keyboard())
        await state.clear()
        return
    try:
        ids = await db.add_watch_group(int(user["id"]), int(user["watch_limit"]), entries)
    except WatchLimitReached:
        await edit(
            callback,
            strings.watch_limit_reached(
                int(user["watch_limit"]),
                settings.supporter_watch_limit,
                settings.donation_min_amount,
                bool(user.get("is_supporter")),
            ),
            support_keyboard() if not bool(user.get("is_supporter")) else back_home_keyboard(),
        )
        await state.clear()
        return
    except DuplicateWatch:
        await edit(callback, strings.duplicate_watch())
        await state.clear()
        return
    await state.clear()
    await edit(
        callback,
        strings.watch_created_window(
            movie_name, date, window, len(entries), settings.morning_end_hour
        ),
        watch_created_keyboard(ids[0]),
    )


@router.callback_query(AddWatch.branch, F.data.startswith("br_p:"))
async def branches_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    branches = data.get("branches", [])
    page = int_part(callback.data, 1, 2) or 0
    text = (
        strings.search_choose_branch(data.get("pending_query", ""))
        if data.get("search_first")
        else strings.choose_branch()
    )
    await edit(callback, text, branch_keyboard(branches, page))
    await answer(callback)


@router.callback_query(AddWatch.branch, F.data.startswith("br:"))
async def branch_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
) -> None:
    await _ack(callback)
    data = await state.get_data()
    provider = _selected_provider(providers, provider, data)
    branches = data.get("branches", [])
    index = int_part(callback.data, 1, 2) or 0
    if not (0 <= index < len(branches)):
        await answer(callback, strings.error_expired(), alert=True)
        return
    branch = branches[index]
    provider_name = getattr(provider, "name", None) or settings.provider
    dates = await provider.get_dates(branch["id"])
    if not dates:
        dates = await _cached(
            cache, dates_key(provider_name, branch["id"]), settings.cache_listings_ttl
        )
    if not dates:
        await edit(callback, strings.no_dates(), retry_keyboard(f"br:{index}"))
        return
    await state.update_data(branch=branch, dates=dates)
    await state.set_state(AddWatch.date)
    await edit(callback, strings.choose_date(branch["name"]), date_keyboard(dates))


@router.callback_query(AddWatch.date, F.data.startswith("dt_p:"))
async def dates_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    dates = data.get("dates", [])
    branch = data.get("branch", {})
    page = int_part(callback.data, 1, 2) or 0
    if data.get("all_cinemas"):
        await edit(
            callback,
            strings.choose_date_all_cinemas(),
            date_keyboard(dates, page, back_cb="ab:cinema"),
        )
    else:
        await edit(
            callback,
            strings.choose_date(branch.get("name", "")),
            date_keyboard(dates, page),
        )
    await answer(callback)


async def _all_cinemas_date_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    provider: Any,
    providers: Any,
    data: dict[str, Any],
) -> None:
    dates = data.get("dates", [])
    index = int_part(callback.data, 1, 2) or 0
    if not (0 <= index < len(dates)):
        await answer(callback, strings.error_expired(), alert=True)
        return
    chosen = dates[index]
    query = search.clean_query(data.get("pending_query") or "")
    await edit(callback, strings.loading_showtimes(), back_home_keyboard())
    grouped = await _collect_window_showtimes(providers, provider, chosen, query)
    if not grouped:
        await edit(
            callback,
            strings.no_showtimes_window(query, chosen),
            retry_keyboard(f"dt:{index}"),
        )
        return
    movie_name = grouped[0]["movie_name"]
    morning = sum(
        1
        for br in grouped
        for s in br["showtimes"]
        if _window_match(s, "morning", settings.morning_end_hour)
    )
    evening = sum(
        1
        for br in grouped
        for s in br["showtimes"]
        if _window_match(s, "evening", settings.morning_end_hour)
    )
    await state.update_data(date=chosen, movie_name=movie_name, window_branches=grouped)
    await state.set_state(AddWatch.window)
    await edit(
        callback,
        strings.choose_window(movie_name, chosen, settings.morning_end_hour),
        window_keyboard(morning, evening),
    )


@router.callback_query(AddWatch.date, F.data.startswith("dt:"))
async def date_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    providers: Any = None,
    metadata: Any = None,
) -> None:
    await _ack(callback)
    data = await state.get_data()
    if data.get("all_cinemas"):
        await _all_cinemas_date_chosen(callback, state, settings, provider, providers, data)
        return
    provider = _selected_provider(providers, provider, data)
    dates = data.get("dates", [])
    branch = data.get("branch", {})
    index = int_part(callback.data, 1, 2) or 0
    if not (0 <= index < len(dates)):
        await answer(callback, strings.error_expired(), alert=True)
        return
    chosen = dates[index]
    provider_name = getattr(provider, "name", None) or settings.provider
    # The day the user picked may never have been fetched before (discovery
    # only reads the default day).  Fetch it once, on demand, through the
    # shared rate-limited client, then cache it like any other page.
    movies = [m.__dict__ for m in await provider.get_movies(branch["id"], chosen)]
    if not movies:
        movies = await _cached(
            cache,
            movies_key(provider_name, branch["id"], chosen),
            settings.cache_listings_ttl,
        )
    if not movies:
        await edit(callback, strings.no_movies(), retry_keyboard(f"dt:{index}", "dt_p:0"))
        return
    await state.update_data(
        date=chosen,
        movies=movies,
        movie_view=None,
        search_query="",
        movies_total=len(movies),
    )
    if data.get("search_first"):
        await state.set_state(AddWatch.search)
        pending = (data.get("pending_query") or "").strip()
        if pending:
            text, keyboard = await _search_movies(pending, state, metadata)
            await edit(callback, text, keyboard)
        else:
            await edit(
                callback,
                strings.search_prompt(branch.get("name", ""), chosen),
                search_keyboard(),
            )
    else:
        await state.set_state(AddWatch.movie)
        await edit(
            callback,
            strings.choose_movie(branch.get("name", ""), chosen),
            movie_keyboard(movies),
        )


@router.callback_query(AddWatch.movie, F.data.startswith("mv_p:"))
async def movies_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    view = data.get("movie_view")
    movies = view if view is not None else data.get("movies", [])
    branch = data.get("branch", {})
    date = data.get("date", "")
    page = int_part(callback.data, 1, 2) or 0
    keyboard = (
        search_results_keyboard(movies, page) if view is not None else movie_keyboard(movies, page)
    )
    text = (
        strings.search_results(
            data.get("search_query", ""),
            len(movies),
            data.get("movies_total", len(movies)),
        )
        if view is not None
        else strings.choose_movie(branch.get("name", ""), date)
    )
    await edit(callback, text, keyboard)
    await answer(callback)


@router.callback_query(AddWatch.movie, F.data == "mv_search")
@router.callback_query(AddWatch.search, F.data == "mv_search")
async def movie_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    branch = data.get("branch", {})
    date = data.get("date", "")
    await state.set_state(AddWatch.search)
    await edit(
        callback,
        strings.search_prompt(branch.get("name", ""), date),
        search_keyboard(),
    )
    await answer(callback)


@router.callback_query(AddWatch.movie, F.data == "mv_all")
@router.callback_query(AddWatch.search, F.data == "mv_all")
async def show_all_movies(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    movies = data.get("movies", [])
    branch = data.get("branch", {})
    date = data.get("date", "")
    await state.set_state(AddWatch.movie)
    await state.update_data(movie_view=None, search_query="", movies_total=len(movies))
    await edit(
        callback,
        strings.choose_movie(branch.get("name", ""), date),
        movie_keyboard(movies),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("ab:"))
async def add_back(
    callback: CallbackQuery,
    state: FSMContext,
    provider: Any = None,
    providers: Any = None,
) -> None:
    """Move one step back without making a new upstream request."""

    await answer(callback)
    target = split_cb(callback.data, 2)[1]
    data = await state.get_data()
    branches = data.get("branches", [])
    branch = data.get("branch", {})
    date = data.get("date", "")
    dates = data.get("dates", [])
    movies = data.get("movies", [])
    movie = data.get("movie", {})
    if target == "cinema":
        await state.set_state(AddWatch.cinema)
        await edit(
            callback,
            strings.choose_cinema(),
            cinema_keyboard(_provider_names(providers, provider)),
        )
        return
    if target == "branch" and branches:
        await state.set_state(AddWatch.branch)
        text = (
            strings.search_choose_branch(data.get("pending_query", ""))
            if data.get("search_first")
            else strings.choose_branch()
        )
        back_cb = "ab:cinema" if data.get("provider_name") else None
        await edit(callback, text, branch_keyboard(branches, back_cb=back_cb))
        return
    if target == "date" and dates and (branch or data.get("all_cinemas")):
        await state.set_state(AddWatch.date)
        if data.get("all_cinemas"):
            await edit(
                callback,
                strings.choose_date_all_cinemas(),
                date_keyboard(dates, back_cb="ab:cinema"),
            )
        else:
            await edit(
                callback,
                strings.choose_date(branch.get("name", "")),
                date_keyboard(dates),
            )
        return
    if target == "movie" and branch and movies:
        await state.set_state(AddWatch.movie)
        view = data.get("movie_view")
        if view is not None:
            text = strings.search_results(
                data.get("search_query", ""),
                len(view),
                data.get("movies_total", len(movies)),
            )
            await edit(callback, text, search_results_keyboard(view))
        else:
            await edit(
                callback,
                strings.choose_movie(branch.get("name", ""), date),
                movie_keyboard(movies),
            )
        return
    if target == "search":
        await state.set_state(AddWatch.search)
        await edit(
            callback,
            strings.search_prompt(branch.get("name", ""), date),
            search_keyboard(),
        )
        return
    if target == "showtime" and movie:
        all_showtimes = [Showtime.from_dict(item) for item in data.get("showtimes", [])]
        visible = _visible_showtimes(data)
        if not visible:
            await edit(callback, strings.error_expired(), back_home_keyboard())
            return
        await state.set_state(AddWatch.showtime)
        await edit(
            callback,
            strings.choose_showtime(movie.get("name", ""), date, extra=_imax_extra(movie)),
            showtime_keyboard(
                visible,
                formats=_format_counts(all_showtimes),
                current_format=data.get("format"),
                date_count=len(dates),
            ),
        )
        return
    await edit(callback, strings.error_expired(), back_home_keyboard())


async def _arabic_alias_matches(
    query: str, movies: list[dict[str, Any]], metadata: Any
) -> list[dict[str, Any]]:
    """Provider movies whose English title is behind an Arabic query.

    TMDB returns the original English title for the Arabic search; we rank
    those titles against the real listing instead of trusting the first TMDB
    hit, so a loose translation simply produces no match.
    """

    try:
        aliases = await metadata.aliases(query)
    except Exception:
        return []
    if not aliases:
        return []
    key = lambda movie: movie.get("name", "")  # noqa: E731 - tiny local helper
    matched: set[str] = set()
    for alias in aliases:
        for hit in search.rank(alias, movies, key=key, limit=20):
            matched.add(str(hit.item.get("id") or hit.item.get("name") or ""))
    if not matched:
        return []
    return [movie for movie in movies if str(movie.get("id") or movie.get("name") or "") in matched]


async def _search_movies(query: str, state: FSMContext, metadata: Any = None) -> tuple[str, Any]:
    """Search the current day's movies and return the reply text and keyboard."""

    query = search.clean_query(query)
    data = await state.get_data()
    movies = data.get("movies", [])
    if len(search.normalize(query)) < 2:
        return strings.search_too_short(), search_keyboard()

    key = lambda movie: movie.get("name", "")  # noqa: E731 - tiny local helper
    hits = search.rank(query, movies, key=key, limit=20)
    view = [hit.item for hit in hits]
    if metadata is not None and _ARABIC_RE.search(query):
        for movie in await _arabic_alias_matches(query, movies, metadata):
            if movie not in view:
                view.append(movie)
    if view:
        await state.update_data(
            movie_view=view,
            search_query=query,
            movies_total=len(movies),
            pending_query="",
        )
        await state.set_state(AddWatch.movie)
        return (
            strings.search_results(query, len(view), len(movies)),
            search_results_keyboard(view),
        )

    suggestions = search.suggest(query, movies, key=key, limit=3)
    items = [hit.item for hit in suggestions]
    names = [item.get("name", "") for item in items]
    await state.update_data(
        movie_view=items or None,
        search_query=query,
        movies_total=len(movies),
        pending_query="",
    )
    if items:
        await state.set_state(AddWatch.movie)
        return strings.search_no_results(query, names), suggestion_keyboard(items)
    # Keep the current state so the user can simply type another query.
    return strings.search_no_results(query), search_keyboard()


async def _localized_movie(metadata: Any, title: str) -> Any:
    """Localised TMDB metadata for the current interface language, if any.

    English keeps the provider copy (and avoids a TMDB call); Arabic asks for
    the Arabic title and overview and silently falls back on failure.
    """

    language = display_language(i18n.get_language())
    if metadata is None or not language or not title:
        return None
    try:
        movie = await metadata.localize(title, language=language)
    except Exception:
        return None
    return movie


async def _search_and_reply(message: Message, state: FSMContext, metadata: Any = None) -> None:
    text, keyboard = await _search_movies((message.text or "").strip(), state, metadata)
    await message.answer(text, reply_markup=keyboard)


@router.message(AddWatch.search)
async def movie_search_query(message: Message, state: FSMContext, metadata: Any = None) -> None:
    await _search_and_reply(message, state, metadata)


@router.message(AddWatch.movie)
async def movie_list_text_search(message: Message, state: FSMContext, metadata: Any = None) -> None:
    """Typing a name on the movie list is treated as a search, no button needed."""

    await _search_and_reply(message, state, metadata)


@router.callback_query(AddWatch.movie, F.data.startswith("mv:"))
async def movie_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    db: Database,
    imax: Any = None,
    providers: Any = None,
) -> None:
    await _ack(callback)
    data = await state.get_data()
    provider = _selected_provider(providers, provider, data)
    view = data.get("movie_view")
    movies = view if view is not None else data.get("movies", [])
    branch = data.get("branch", {})
    date = data.get("date", "")
    index = int_part(callback.data, 1, 2) or 0
    if not (0 <= index < len(movies)):
        await answer(callback, strings.error_expired(), alert=True)
        return
    movie = movies[index]
    provider_name = getattr(provider, "name", None) or settings.provider
    showtimes = list(await provider.get_showtimes(branch["id"], date, movie_id=movie["id"]))
    if not showtimes:
        raw = await _cached(
            cache,
            showtimes_key(provider_name, branch["id"], date),
            settings.cache_showtimes_ttl,
        )
        fallback = [Showtime.from_dict(item) for item in (raw or [])]
        showtimes = [s for s in fallback if s.movie_id == movie["id"]]
    showtimes.sort(key=lambda s: (s.time, s.hall_type))
    if not showtimes:
        await edit(
            callback,
            strings.no_showtimes(),
            retry_keyboard(f"mv:{index}", "mv_all"),
        )
        return
    movie = dict(movie)
    if hasattr(provider, "get_movie_poster"):
        try:
            poster_movie = Movie(**{name: movie.get(name) for name in Movie.__dataclass_fields__})
            poster = await provider.get_movie_poster(poster_movie)
        except Exception:
            poster = None
        movie["poster_url"] = poster
    status = await _imax_status(db, imax, movie, showtimes) if provider_name == "vox" else None
    if status:
        movie["imax_status"] = status
    await state.update_data(
        movie=movie,
        showtimes=[s.to_dict() for s in showtimes],
        format=None,
    )
    await state.set_state(AddWatch.showtime)
    await edit(
        callback,
        strings.choose_showtime(
            movie["name"], date, extra=strings.imax_line(movie.get("imax_status"))
        ),
        showtime_keyboard(
            showtimes,
            formats=_format_counts(showtimes),
            date_count=len(data.get("dates", [])),
        ),
    )


def _format_counts(showtimes: list[Showtime]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for showtime in showtimes:
        key = format_key(showtime.hall_type)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _visible_showtimes(data: dict[str, Any]) -> list[Showtime]:
    showtimes = [Showtime.from_dict(s) for s in data.get("showtimes", [])]
    selected = data.get("format")
    if not selected:
        return showtimes
    return [s for s in showtimes if format_key(s.hall_type) == selected]


def _required_seats(value: Any) -> int | None:
    """Parse a seat count from a button or typed message, enforcing 1–10."""

    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if SEAT_MIN <= number <= SEAT_MAX else None


def _seat_context(data: dict[str, Any]) -> str:
    movie = (data.get("movie") or {}).get("name") or data.get("movie_name")
    return str(movie or data.get("pending_query") or "")


def _confirm_payload(
    data: dict[str, Any], settings: Settings, required_seats: int
) -> tuple[str, Any]:
    """Rebuild the confirmation screen from the stored flow data."""

    branch = data.get("branch", {})
    movie = data.get("movie", {})
    date = data.get("date", "")
    showtime = data.get("showtime", {})
    scope = data.get("scope", "showtime")
    window = data.get("window")
    selected_format = data.get("format")
    if window:
        movie_name = data.get("movie_name", data.get("pending_query", ""))
        branch_count = sum(
            1
            for br in data.get("window_branches", [])
            if any(_window_match(s, window, settings.morning_end_hour) for s in br["showtimes"])
        )
        text = strings.confirm_window(
            movie_name,
            date,
            window,
            branch_count,
            settings.morning_end_hour,
            required_seats,
        )
        return text, confirm_window_keyboard()
    format_label = strings.format_label(selected_format) if selected_format else None
    if scope == "movie_all_dates":
        text = strings.confirm_all_dates(
            branch.get("name", ""),
            movie.get("name", ""),
            int(data.get("date_count") or 0),
            format_label,
            required_seats,
        )
    elif scope == "movie":
        shows = _visible_showtimes(data)
        text = strings.confirm_movie_watch(
            branch.get("name", ""),
            date,
            movie.get("name", ""),
            int(data.get("showtime_count") or len(shows)),
            [s.status for s in shows],
            format_label,
            required_seats,
        )
    else:
        text = strings.confirm_watch(
            branch.get("name", ""),
            date,
            movie.get("name", ""),
            showtime.get("time", ""),
            showtime.get("hall_type", ""),
            showtime.get("status", ""),
            required_seats,
        )
    return text, confirm_keyboard()


def _confirm_poster(data: dict[str, Any]) -> str | None:
    return (data.get("movie") or {}).get("poster_url")


async def _show_seat_picker(
    callback: CallbackQuery, state: FSMContext, data: dict[str, Any]
) -> None:
    await state.set_state(AddWatch.seats)
    await edit(
        callback,
        strings.choose_seats(_seat_context(data)),
        seat_choice_keyboard(),
    )


async def _show_confirm(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    seats = _required_seats(data.get("required_seats")) or 1
    await state.set_state(AddWatch.window if data.get("window") else AddWatch.showtime)
    text, keyboard = _confirm_payload(data, settings, seats)
    poster = _confirm_poster(data)
    await edit(
        callback,
        strings.truncate(text, 1000) if poster else text,
        keyboard,
        photo_url=poster,
    )


@router.callback_query(AddWatch.showtime, F.data.startswith("fm:"))
async def showtime_format(callback: CallbackQuery, state: FSMContext) -> None:
    value = split_cb(callback.data, 2)[1]
    data = await state.get_data()
    showtimes = [Showtime.from_dict(s) for s in data.get("showtimes", [])]
    counts = _format_counts(showtimes)
    selected = None if value == "all" else value
    if selected is not None and selected not in counts:
        await answer(callback, strings.format_not_found(), alert=True)
        return
    await state.update_data(format=selected)
    movie = data.get("movie", {})
    date = data.get("date", "")
    visible = [s for s in showtimes if selected is None or format_key(s.hall_type) == selected]
    await edit(
        callback,
        strings.choose_showtime(movie.get("name", ""), date, extra=_imax_extra(movie)),
        showtime_keyboard(
            visible,
            formats=counts,
            current_format=selected,
            date_count=len(data.get("dates", [])),
        ),
    )
    await answer(
        callback,
        strings.format_filtered(strings.format_label(selected))
        if selected
        else strings.format_filtered(None),
    )


@router.callback_query(AddWatch.showtime, F.data == "mv:info")
async def show_movie_info(
    callback: CallbackQuery,
    state: FSMContext,
    provider: Any,
    db: Database,
    imax: Any = None,
    providers: Any = None,
    metadata: Any = None,
) -> None:
    await _ack(callback)
    data = await state.get_data()
    provider = _selected_provider(providers, provider, data)
    provider_name = getattr(provider, "name", None) or "vox"
    movie_data = data.get("movie", {})
    movie = Movie(**{name: movie_data.get(name) for name in Movie.__dataclass_fields__})
    details = movie
    if hasattr(provider, "get_movie_details"):
        try:
            details = await provider.get_movie_details(movie)
        except Exception:
            details = movie
    name = details.name
    synopsis = details.synopsis
    localized = await _localized_movie(metadata, name)
    if localized is not None:
        name = localized.title or name
        synopsis = localized.overview or synopsis
    facts = strings.movie_facts(details.duration_minutes, details.rating, details.language)
    showtimes = [Showtime.from_dict(item) for item in data.get("showtimes", [])]
    status = movie_data.get("imax_status")
    if not status and provider_name == "vox":
        status = await _imax_status(db, imax, movie_data, showtimes)
    text = strings.movie_info(
        name,
        synopsis,
        facts,
        extra=strings.imax_line(status),
    )
    photo_url = details.poster_url or movie_data.get("poster_url")
    await edit(
        callback,
        strings.truncate(text, 1000) if photo_url else text,
        movie_info_keyboard(details.trailer_url),
        photo_url=photo_url,
    )


@router.callback_query(AddWatch.showtime, F.data == "info:back")
async def movie_info_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    all_showtimes = [Showtime.from_dict(s) for s in data.get("showtimes", [])]
    visible = _visible_showtimes(data)
    movie = data.get("movie", {})
    date = data.get("date", "")
    await edit(
        callback,
        strings.choose_showtime(movie.get("name", ""), date, extra=_imax_extra(movie)),
        showtime_keyboard(
            visible,
            formats=_format_counts(all_showtimes),
            current_format=data.get("format"),
            date_count=len(data.get("dates", [])),
        ),
    )
    await answer(callback)


@router.callback_query(AddWatch.showtime, F.data.startswith("st_p:"))
async def showtimes_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    all_showtimes = [Showtime.from_dict(s) for s in data.get("showtimes", [])]
    visible = _visible_showtimes(data)
    movie = data.get("movie", {})
    date = data.get("date", "")
    page = int_part(callback.data, 1, 2) or 0
    await edit(
        callback,
        strings.choose_showtime(movie.get("name", ""), date, extra=_imax_extra(movie)),
        showtime_keyboard(
            visible,
            page,
            formats=_format_counts(all_showtimes),
            current_format=data.get("format"),
            date_count=len(data.get("dates", [])),
        ),
    )
    await answer(callback)


@router.callback_query(AddWatch.showtime, F.data.regexp(r"^st:\d+$"))
async def showtime_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    showtimes = _visible_showtimes(data)
    index = int_part(callback.data, 1, 2) or 0
    if not (0 <= index < len(showtimes)):
        await answer(callback, strings.error_expired(), alert=True)
        return
    showtime = showtimes[index].to_dict()
    await state.update_data(showtime=showtime, scope="showtime")
    data = await state.get_data()
    await _show_seat_picker(callback, state, data)
    await answer(callback)


@router.callback_query(AddWatch.showtime, F.data == "st:all")
async def showtime_all_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    showtimes = _visible_showtimes(data)
    if not showtimes:
        await answer(callback, strings.error_generic(), alert=True)
        return
    first = sorted(showtimes, key=lambda s: (s.time, s.hall_type))[0]
    await state.update_data(scope="movie", showtime=first.to_dict(), showtime_count=len(showtimes))
    data = await state.get_data()
    await _show_seat_picker(callback, state, data)
    await answer(callback)


@router.callback_query(AddWatch.showtime, F.data == "st:alldays")
async def showtime_all_dates(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    data = await state.get_data()
    dates = sorted(
        value for value in data.get("dates", []) if value >= today_iso(settings.timezone)
    )[: settings.all_dates_max]
    if not dates:
        await answer(callback, strings.all_dates_unavailable(), alert=True)
        return
    await state.update_data(scope="movie_all_dates", date_count=len(dates))
    data = await state.get_data()
    await _show_seat_picker(callback, state, data)
    await answer(callback)


@router.callback_query(AddWatch.seats, F.data.startswith("add:seats:"))
async def seats_chosen(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    seats = _required_seats(int_part(callback.data, 2, 3))
    if seats is None:
        await answer(callback, strings.seats_custom_invalid(), alert=True)
        return
    await state.update_data(required_seats=seats)
    await _show_confirm(callback, state, settings)
    await answer(callback)


@router.callback_query(AddWatch.seats, F.data == "add:seats_custom")
async def seats_custom_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddWatch.seats_custom)
    await edit(callback, strings.seats_custom_prompt(), back_home_keyboard())
    await answer(callback)


@router.message(AddWatch.seats_custom)
async def seats_custom_value(message: Message, state: FSMContext, settings: Settings) -> None:
    seats = _required_seats(message.text)
    if seats is None:
        await send(message, strings.seats_custom_invalid())
        return
    await state.update_data(required_seats=seats)
    data = await state.get_data()
    await state.set_state(AddWatch.window if data.get("window") else AddWatch.showtime)
    text, keyboard = _confirm_payload(data, settings, seats)
    poster = _confirm_poster(data)
    await send(
        message,
        strings.truncate(text, 1000) if poster else text,
        keyboard,
        photo_url=poster,
    )


@router.callback_query(F.data.startswith("add:seats"))
async def seats_expired(callback: CallbackQuery) -> None:
    await answer(callback, strings.error_expired(), alert=True)


@router.callback_query(AddWatch.showtime, F.data == "add:confirm")
async def confirm_add(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    scheduler: Scheduler,
    provider: Any,
    imax: Any = None,
) -> None:
    await _ack(callback)
    data = await state.get_data()
    branch = data.get("branch", {})
    movie = data.get("movie", {})
    date = data.get("date", "")
    showtime = data.get("showtime", {})
    scope = data.get("scope", "showtime")
    movie_scope = scope in {"movie", "movie_all_dates"}
    all_dates = scope == "movie_all_dates"
    required_seats = _required_seats(data.get("required_seats")) or 1
    selected_format = data.get("format")
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    details = movie
    if hasattr(provider, "get_movie_details"):
        try:
            details = (await provider.get_movie_details(Movie(**movie))).__dict__
        except Exception:
            details = movie
    stored_showtimes = [Showtime.from_dict(item) for item in data.get("showtimes", [])]
    imax_status = movie.get("imax_status") or await _imax_status(db, imax, movie, stored_showtimes)
    expires_at = _watch_expiry(data, scope, showtime, settings)
    try:
        watch_id = await db.add_watch(
            user_id=int(user["id"]),
            provider=settings.provider,
            branch_id=branch.get("id", ""),
            branch_name=branch.get("name", ""),
            date="*" if all_dates else date,
            movie_id=movie.get("id", ""),
            movie_name=movie.get("name", ""),
            showtime="*" if movie_scope else showtime.get("time", ""),
            hall_type=(selected_format or "*") if movie_scope else showtime.get("hall_type", ""),
            watch_limit=int(user["watch_limit"]),
            booking_url=None if all_dates else showtime.get("booking_url"),
            scope=scope,
            poster_url=details.get("poster_url"),
            duration_minutes=details.get("duration_minutes"),
            rating=details.get("rating"),
            language=details.get("language"),
            synopsis=details.get("synopsis"),
            trailer_url=details.get("trailer_url"),
            imax_status=imax_status or details.get("imax_status"),
            expires_at=expires_at,
            required_seats=required_seats,
        )
    except WatchLimitReached:
        await edit(
            callback,
            strings.watch_limit_reached(
                int(user["watch_limit"]),
                settings.supporter_watch_limit,
                settings.donation_min_amount,
                bool(user.get("is_supporter")),
            ),
            support_keyboard() if not bool(user.get("is_supporter")) else back_home_keyboard(),
        )
        await state.clear()
        return
    except DuplicateWatch:
        await edit(callback, strings.duplicate_watch())
        await state.clear()
        return

    target = TargetKey(
        provider=settings.provider,
        branch_id=branch.get("id", ""),
        date=date,
        movie_id=movie.get("id", ""),
    )
    if not all_dates:
        scheduler.add(
            target, status=showtime.get("status"), expected_open_at=expected_opening_for(date)
        )
    await state.clear()
    if all_dates:
        text = strings.watch_created_all_dates(
            branch.get("name", ""),
            movie.get("name", ""),
            int(data.get("date_count") or 0),
            strings.format_label(selected_format) if selected_format else None,
        )
    elif movie_scope:
        text = strings.watch_created_movie(
            branch.get("name", ""),
            date,
            movie.get("name", ""),
            int(data.get("showtime_count") or 0),
            strings.format_label(selected_format) if selected_format else None,
        )
    else:
        text = strings.watch_created(
            branch.get("name", ""),
            date,
            movie.get("name", ""),
            showtime.get("time", ""),
            showtime.get("hall_type", ""),
        )
    await edit(
        callback,
        text,
        watch_created_keyboard(watch_id),
        photo_url=details.get("poster_url"),
    )


# ------------------------------------------------------------------ my watches


def _watches_view(
    watches: list[dict[str, Any]], settings: Settings, page: int = 0
) -> tuple[str, Any]:
    pages = max(1, (len(watches) + WATCH_PAGE_SIZE - 1) // WATCH_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    if not watches:
        return strings.no_watches(), watches_keyboard([])
    start = page * WATCH_PAGE_SIZE
    visible = watches[start : start + WATCH_PAGE_SIZE]
    lines = [strings.watches_page_title(len(watches)), DIVIDER]
    current_group = None
    for index, watch in enumerate(visible):
        group = strings.watches_group(str(watch.get("date") or ""))
        if index:
            lines += ["", DIVIDER]
        if group != current_group:
            lines += ["", group]
            current_group = group
        branch_label = watch["branch_name"]
        if watch.get("time_window"):
            branch_label += (
                f" · {strings.window_label(watch['time_window'], settings.morning_end_hour)}"
            )
        lines.append(
            strings.watch_row(
                branch_label,
                watch["date"],
                watch["movie_name"],
                watch["showtime"],
                watch["hall_type"],
                watch.get("last_status") or "UNKNOWN",
                watch.get("last_seats"),
                watch.get("alert_mode"),
                watch.get("snoozed_until"),
                watch.get("scope"),
                watch.get("provider"),
                watch.get("required_seats") or 1,
            )
        )
    lines += ["", strings.watches_retention_note(settings.watch_retention_days)]
    return "\n".join(lines), watches_keyboard(watches, page)


async def _render_watches(
    callback: CallbackQuery,
    db: Database,
    user: dict[str, Any],
    settings: Settings,
    page: int = 0,
) -> None:
    watches = await db.list_watches(int(user["id"]))
    text, keyboard = _watches_view(watches, settings, page)
    await edit(callback, text, keyboard)


@router.callback_query(F.data == "menu:watches")
async def my_watches(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    await answer(callback)
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await _render_watches(callback, db, user, settings)


@router.callback_query(F.data.startswith("wp:"))
async def watches_page(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    await answer(callback)
    page = int_part(callback.data, 1, 2) or 0
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await _render_watches(callback, db, user, settings, page)


@router.message(Command("watches"))
async def watches_cmd(message: Message, db: Database, settings: Settings) -> None:
    user = await db.get_or_create_user(message.from_user.id, watch_limit=settings.free_watch_limit)
    watches = await db.list_watches(int(user["id"]))
    text, keyboard = _watches_view(watches, settings)
    await send(message, text, keyboard)


async def _owned_watch(
    callback: CallbackQuery, db: Database, settings: Settings, watch_id: int
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    watch = await db.get_watch(watch_id)
    if not watch or int(watch["user_id"]) != int(user["id"]) or not watch.get("active"):
        return None, user
    return watch, user


def _snooze_clock(value: str | None, settings: Settings) -> str | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(resolve_timezone(settings.timezone))
    return strings.format_time(local.strftime("%H:%M"))


async def _watch_detail_payload(
    watch: dict[str, Any],
    settings: Settings,
    metadata: Any = None,
) -> tuple[str, Any]:
    title = watch["movie_name"]
    localized = await _localized_movie(metadata, title)
    if localized is not None:
        title = localized.title or title
    return (
        strings.watch_detail(
            watch["branch_name"],
            watch["date"],
            title,
            watch["showtime"],
            watch["hall_type"],
            watch.get("alert_mode"),
            _snooze_clock(watch.get("snoozed_until"), settings),
            watch.get("scope"),
            watch.get("provider"),
            watch.get("required_seats") or 1,
        ),
        watch_detail_keyboard(watch),
    )


async def _render_watch_detail(
    callback: CallbackQuery,
    watch: dict[str, Any],
    settings: Settings,
    metadata: Any = None,
) -> None:
    text, keyboard = await _watch_detail_payload(watch, settings, metadata)
    await edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("w:cfg:"))
async def watch_settings(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    metadata: Any = None,
) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await state.clear()
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await _render_watches(callback, db, user, settings)
        await answer(callback, strings.error_generic(), alert=True)
        return
    await _render_watch_detail(callback, watch, settings, metadata)
    await answer(callback)


@router.callback_query(F.data.startswith("w:mode:"))
async def watch_alert_mode(
    callback: CallbackQuery, db: Database, settings: Settings, metadata: Any = None
) -> None:
    watch_id = int_part(callback.data, 2, 4)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    mode = split_cb(callback.data, 4)[3]
    if mode not in VALID_MODES:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await db.set_watch_alert_mode(watch_id, int(user["id"]), mode)
    watch = await db.get_watch(watch_id)
    if watch is not None:
        await _render_watch_detail(callback, watch, settings, metadata)
    await answer(callback, strings.watch_mode_set(mode))


@router.callback_query(F.data.startswith("w:seats:"))
async def watch_seats(
    callback: CallbackQuery, state: FSMContext, db: Database, settings: Settings
) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await state.clear()
    watch, _ = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await edit(
        callback,
        strings.choose_seats(watch["movie_name"]),
        watch_seat_choice_keyboard(watch_id),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("ws:"))
async def watch_seats_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    metadata: Any = None,
) -> None:
    watch_id = int_part(callback.data, 1, 3)
    value = split_cb(callback.data, 3)[2]
    await state.clear()
    watch, user = (
        await _owned_watch(callback, db, settings, watch_id) if watch_id is not None else (None, {})
    )
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    if value == "custom":
        await state.set_state(EditSeats.custom)
        await state.update_data(edit_seats_watch_id=watch_id)
        await edit(callback, strings.seats_custom_prompt(), watch_seat_choice_keyboard(watch_id))
        await answer(callback)
        return
    seats = _required_seats(value)
    if seats is None:
        await answer(callback, strings.seats_custom_invalid(), alert=True)
        return
    await db.set_watch_required_seats(watch_id, int(user["id"]), seats)
    watch = await db.get_watch(watch_id)
    if watch is not None:
        await _render_watch_detail(callback, watch, settings, metadata)
    await answer(callback, strings.seats_updated(seats))


@router.message(EditSeats.custom)
async def watch_seats_custom_value(
    message: Message, state: FSMContext, db: Database, settings: Settings, metadata: Any = None
) -> None:
    seats = _required_seats(message.text)
    if seats is None:
        await send(message, strings.seats_custom_invalid())
        return
    data = await state.get_data()
    try:
        watch_id = int(data.get("edit_seats_watch_id"))
    except (TypeError, ValueError):
        await state.clear()
        await send(message, strings.error_expired(), back_home_keyboard())
        return
    user = await db.get_or_create_user(message.from_user.id, watch_limit=settings.free_watch_limit)
    watch = await db.get_watch(watch_id)
    if not watch or int(watch["user_id"]) != int(user["id"]) or not watch.get("active"):
        await state.clear()
        await send(message, strings.error_generic(), back_home_keyboard())
        return
    await db.set_watch_required_seats(watch_id, int(user["id"]), seats)
    await state.clear()
    watch = await db.get_watch(watch_id)
    if watch is not None:
        text, keyboard = await _watch_detail_payload(watch, settings, metadata)
        await send(message, text, keyboard)


@router.callback_query(F.data.startswith("w:snz:"))
async def watch_snooze(
    callback: CallbackQuery, db: Database, settings: Settings, metadata: Any = None
) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    until = datetime.now(UTC) + timedelta(hours=1)
    await db.snooze_watch(watch_id, int(user["id"]), until.isoformat(timespec="seconds"))
    watch = await db.get_watch(watch_id)
    if watch is not None:
        await _render_watch_detail(callback, watch, settings, metadata)
    await answer(
        callback,
        strings.watch_snoozed(_snooze_clock(until.isoformat(), settings) or ""),
    )


@router.callback_query(F.data.startswith("w:snz0:"))
async def watch_unsnooze(
    callback: CallbackQuery, db: Database, settings: Settings, metadata: Any = None
) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, _ = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await db.clear_watch_snooze(watch_id)
    watch = await db.get_watch(watch_id)
    if watch is not None:
        await _render_watch_detail(callback, watch, settings, metadata)
    await answer(callback, strings.watch_unsnoozed())


@router.callback_query(F.data.startswith("wa:snz:"))
async def alert_snooze(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    until = datetime.now(UTC) + timedelta(hours=1)
    await db.snooze_watch(watch_id, int(user["id"]), until.isoformat(timespec="seconds"))
    await answer(
        callback,
        strings.watch_snoozed(_snooze_clock(until.isoformat(), settings) or ""),
    )


@router.callback_query(F.data.startswith("wa:del:"))
async def alert_remove_watch(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await db.deactivate_watch(watch_id, user_id=int(user["id"]))
    await edit(callback, strings.watch_removed_from_alert())
    await answer(callback, strings.watch_removed())


@router.callback_query(F.data.startswith("w:del:"))
async def delete_watch(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, _ = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    when = strings.relative_date(watch["date"])
    if watch.get("scope") not in {"movie", "movie_all_dates"} and watch.get("showtime") not in {
        "",
        "*",
    }:
        when = f"{when} — {strings.format_time(watch['showtime'])}"
    await edit(
        callback,
        strings.confirm_remove_watch(watch["movie_name"], when),
        watch_delete_confirm_keyboard(watch_id),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("w:dely:"))
async def confirm_delete_watch(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    watch_id = int_part(callback.data, 2, 3)
    if watch_id is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    watch, user = await _owned_watch(callback, db, settings, watch_id)
    if watch is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await db.deactivate_watch(watch_id, user_id=int(user["id"]))
    await _render_watches(callback, db, user, settings)
    await answer(callback, strings.watch_removed())


@router.callback_query(F.data == "w:all")
async def delete_all_watches(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    watches = await db.list_watches(int(user["id"]))
    if not watches:
        await _render_watches(callback, db, user, settings)
        await answer(callback)
        return
    await edit(
        callback,
        strings.confirm_delete_all(len(watches)),
        watches_clear_confirm_keyboard(),
    )
    await answer(callback)


@router.callback_query(F.data == "w:ally")
async def confirm_delete_all_watches(
    callback: CallbackQuery, db: Database, settings: Settings
) -> None:
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await db.deactivate_all_watches(int(user["id"]))
    await _render_watches(callback, db, user, settings)
    await answer(callback, strings.all_watches_removed())


# -------------------------------------------------------------------- deep links
async def send_watch_detail_message(
    message: Message,
    db: Database,
    settings: Settings,
    watch_id: int,
    telegram_id: int | None = None,
    metadata: Any = None,
) -> None:
    """Open one watch from ``t.me/<bot>?start=w<id>`` after checking ownership."""

    tid = telegram_id or message.from_user.id
    user = await db.get_or_create_user(tid, watch_limit=settings.free_watch_limit)
    watch = await db.get_watch(watch_id)
    if not watch or int(watch["user_id"]) != int(user["id"]) or not watch.get("active"):
        await send(message, strings.error_expired(), back_home_keyboard())
        return
    text, keyboard = await _watch_detail_payload(watch, settings, metadata)
    await send(message, text, keyboard)


async def start_branch_deeplink(
    message: Message,
    state: FSMContext,
    cache: Any,
    settings: Settings,
    provider: Any,
    suffix: str,
    telegram_id: int | None = None,
    providers: Any = None,
) -> bool:
    """Jump straight to the date step of ``?start=b<provider>_<branch>``.

    Legacy links carry a bare ``?start=b<branch>`` and default to VOX.
    """

    provider_name, branch_id = _parse_branch_suffix(suffix, providers, provider, settings)
    selected = _selected_provider(providers, provider, {"provider_name": provider_name})
    branches = await _branches(cache, settings, selected)
    branch = next((item for item in branches if str(item.get("id")) == branch_id), None)
    if branch is None:
        return False
    dates = await selected.get_dates(branch["id"])
    if not dates:
        dates = await _cached(
            cache, dates_key(provider_name, branch["id"]), settings.cache_listings_ttl
        )
    if not dates:
        await state.clear()
        await send(message, strings.no_dates(), back_home_keyboard())
        return True
    await state.update_data(branch=branch, dates=dates, provider_name=provider_name)
    await state.set_state(AddWatch.date)
    await send(
        message,
        strings.choose_date(branch.get("name", "")),
        date_keyboard(dates),
    )
    return True
