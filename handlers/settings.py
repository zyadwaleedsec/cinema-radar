"""Notification preferences: quiet hours, branches, event types and halls."""

from __future__ import annotations

import re
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import i18n
import strings
from cache import branches_key
from config import Settings
from db import Database
from handlers.utils import answer, edit, int_part, json_list, send, split_cb
from keyboards import (
    branches_filter_keyboard,
    event_types_keyboard,
    hall_keyboard,
    quiet_custom_keyboard,
    quiet_keyboard,
    settings_keyboard,
)
from models import CANONICAL_FORMATS, format_key

router = Router(name="settings")

ALL_EVENT_TYPES = [
    "NEW_MOVIE",
    "NEW_DATE_OPENED",
    "NEW_SHOWTIMES",
    "UPCOMING_MOVIE",
]

_EVENT_TYPE_CALLBACK = re.compile(
    rf"^ft:({'|'.join(re.escape(event) for event in ALL_EVENT_TYPES)})$"
)


class SettingsFlow(StatesGroup):
    filters = State()
    quiet = State()


async def _user_and_sub(
    db: Database, telegram_id: int, settings: Settings
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    user = await db.get_or_create_user(telegram_id, watch_limit=settings.free_watch_limit)
    sub = await db.get_subscription(int(user["id"]))
    return user, sub


def _subscription_values(sub: dict[str, Any] | None, **overrides: Any) -> dict[str, Any]:
    """Reuse the existing subscription, applying only the changed fields."""

    values = {
        "branch_ids": json_list(sub.get("branch_ids")) if sub else [],
        "event_types": (json_list(sub.get("event_types")) if sub else list(ALL_EVENT_TYPES)),
        "hall_type": sub.get("hall_type") if sub else None,
        "active": True,
    }
    values.update(overrides)
    return values


def _quiet_bounds(user: dict[str, Any], settings: Settings) -> tuple[int, int]:
    """Per-user override, falling back to the configured global quiet hours."""

    start = user.get("quiet_start")
    end = user.get("quiet_end")
    return (
        settings.quiet_start if start is None else int(start),
        settings.quiet_end if end is None else int(end),
    )


async def _render(
    callback: CallbackQuery, user: dict[str, Any], sub: dict[str, Any] | None, settings: Settings
) -> None:
    text, keyboard = _settings_view(user, sub, settings)
    await edit(callback, text, keyboard)


def _settings_view(
    user: dict[str, Any], sub: dict[str, Any] | None, settings: Settings
) -> tuple[str, Any]:
    branches = json_list(sub.get("branch_ids")) if sub else []
    types = json_list(sub.get("event_types")) if sub else ALL_EVENT_TYPES
    quiet_start, quiet_end = _quiet_bounds(user, settings)
    text = strings.settings_text(
        bool(user.get("notify_cancellations", 1)),
        quiet_start,
        quiet_end,
        bool(sub and sub.get("active")),
        len(branches),
        types or ALL_EVENT_TYPES,
        sub.get("hall_type") if sub else None,
        bool(user.get("quiet_watches", 1)),
        i18n.get_language(),
    )
    return text, settings_keyboard(user, sub)


@router.message(Command("settings"))
async def settings_cmd(
    message: Message, db: Database, settings: Settings, state: FSMContext
) -> None:
    await state.clear()
    user, sub = await _user_and_sub(db, message.from_user.id, settings)
    text, keyboard = _settings_view(user, sub, settings)
    await send(message, text, keyboard)


@router.callback_query(F.data == "menu:settings")
async def open_settings(
    callback: CallbackQuery, db: Database, settings: Settings, state: FSMContext
) -> None:
    await answer(callback)
    await state.clear()
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)


@router.callback_query(F.data == "set:cancel")
async def toggle_cancel(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await db.update_user_settings(
        int(user["id"]), notify_cancellations=0 if user.get("notify_cancellations") else 1
    )
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.setting_saved())


@router.callback_query(F.data == "set:quiet")
async def quiet_menu(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user, _ = await _user_and_sub(db, callback.from_user.id, settings)
    start, end = _quiet_bounds(user, settings)
    quiet_watches = bool(user.get("quiet_watches", 1))
    await edit(
        callback,
        strings.quiet_hours_text(start, end, quiet_watches),
        quiet_keyboard(start, end, quiet_watches),
    )
    await answer(callback)


@router.callback_query(F.data == "q:watch")
async def toggle_quiet_watches(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user, _ = await _user_and_sub(db, callback.from_user.id, settings)
    value = 0 if user.get("quiet_watches", 1) else 1
    await db.update_user_settings(int(user["id"]), quiet_watches=value)
    user, _ = await _user_and_sub(db, callback.from_user.id, settings)
    start, end = _quiet_bounds(user, settings)
    quiet_watches = bool(user.get("quiet_watches", 1))
    await edit(
        callback,
        strings.quiet_hours_text(start, end, quiet_watches),
        quiet_keyboard(start, end, quiet_watches),
    )
    await answer(callback, strings.setting_saved())


@router.callback_query(F.data.regexp(r"^q:\d{1,2}:\d{1,2}$"))
async def set_quiet(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    start = int_part(callback.data, 1, 3)
    end = int_part(callback.data, 2, 3)
    if start is None or end is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    if not (0 <= start <= 23 and 0 <= end <= 23):
        await answer(callback, strings.error_generic(), alert=True)
        return
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await db.update_user_settings(int(user["id"]), quiet_start=start, quiet_end=end)
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.quiet_hours_set(start, end))


@router.callback_query(F.data == "q:cust")
async def quiet_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFlow.quiet)
    await edit(callback, strings.quiet_custom_prompt(), quiet_custom_keyboard())
    await answer(callback)


_QUIET_CUSTOM = re.compile(r"^\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*$")


def parse_quiet_range(value: str) -> tuple[int, int] | None:
    """Parse ``23-8`` into ``(23, 8)``; reject hours outside 0–23."""

    match = _QUIET_CUSTOM.match(value or "")
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if not (0 <= start <= 23 and 0 <= end <= 23):
        return None
    return start, end


@router.message(SettingsFlow.quiet, F.text)
async def quiet_custom_received(
    message: Message, state: FSMContext, db: Database, settings: Settings
) -> None:
    parsed = parse_quiet_range(message.text or "")
    if parsed is None:
        await message.answer(strings.quiet_custom_invalid(), reply_markup=quiet_custom_keyboard())
        return
    start, end = parsed
    user, sub = await _user_and_sub(db, message.from_user.id, settings)
    await db.update_user_settings(int(user["id"]), quiet_start=start, quiet_end=end)
    await state.clear()
    user, sub = await _user_and_sub(db, message.from_user.id, settings)
    text, keyboard = _settings_view(user, sub, settings)
    await send(message, text, keyboard)


@router.callback_query(F.data == "set:disc")
async def toggle_discovery(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    if sub and sub.get("active"):
        await db.set_subscription_active(int(user["id"]), False)
    else:
        await db.upsert_subscription(int(user["id"]), **_subscription_values(sub))
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.setting_saved())


@router.callback_query(F.data == "set:branches")
async def branches_menu(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    cache: Any,
    state: FSMContext,
) -> None:
    branches = await cache.get_json(branches_key(settings.provider), ttl=settings.cache_static_ttl)
    if not branches:
        await edit(callback, strings.no_data())
        await answer(callback)
        return
    _, sub = await _user_and_sub(db, callback.from_user.id, settings)
    selected = json_list(sub.get("branch_ids")) if sub else []
    await state.set_state(SettingsFlow.filters)
    await state.update_data(
        branches=branches, selected_branches=selected, selected_types=[], mode="branches"
    )
    await edit(
        callback,
        strings.choose_branches_text(),
        branches_filter_keyboard(branches, selected),
    )
    await answer(callback)


@router.callback_query(SettingsFlow.filters, F.data.startswith("fb_p:"))
async def branches_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    page = int_part(callback.data, 1, 2) or 0
    await edit(
        callback,
        strings.choose_branches_text(),
        branches_filter_keyboard(data.get("branches", []), data.get("selected_branches", []), page),
    )
    await answer(callback)


@router.callback_query(SettingsFlow.filters, F.data.regexp(r"^fb:\d+$"))
async def toggle_branch(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    branches = data.get("branches", [])
    selected = list(data.get("selected_branches", []))
    index = int_part(callback.data, 1, 2)
    if index is None:
        await answer(callback, strings.error_generic(), alert=True)
        return
    if not (0 <= index < len(branches)):
        await answer(callback, strings.error_generic(), alert=True)
        return
    branch_id = branches[index]["id"]
    if branch_id in selected:
        selected.remove(branch_id)
    else:
        selected.append(branch_id)
    await state.update_data(selected_branches=selected)
    await edit(
        callback,
        strings.choose_branches_text(),
        branches_filter_keyboard(branches, selected),
    )
    await answer(callback)


@router.callback_query(F.data == "fb:done")
async def save_branches(
    callback: CallbackQuery, db: Database, settings: Settings, state: FSMContext
) -> None:
    data = await state.get_data()
    selected = list(data.get("selected_branches", []))
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await db.upsert_subscription(int(user["id"]), **_subscription_values(sub, branch_ids=selected))
    await state.clear()
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.setting_saved())


@router.callback_query(F.data == "set:types")
async def types_menu(
    callback: CallbackQuery, db: Database, settings: Settings, state: FSMContext
) -> None:
    _, sub = await _user_and_sub(db, callback.from_user.id, settings)
    selected = json_list(sub.get("event_types")) if sub else ALL_EVENT_TYPES
    await state.set_state(SettingsFlow.filters)
    await state.update_data(selected_types=selected, mode="types")
    await edit(callback, strings.choose_event_types_text(), event_types_keyboard(selected))
    await answer(callback)


@router.callback_query(
    SettingsFlow.filters,
    F.data.regexp(_EVENT_TYPE_CALLBACK),
)
async def toggle_type(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = list(data.get("selected_types", []))
    value = split_cb(callback.data, 2)[1]
    if value in ALL_EVENT_TYPES:
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(selected_types=selected)
    await edit(callback, strings.choose_event_types_text(), event_types_keyboard(selected))
    await answer(callback)


@router.callback_query(F.data == "ft:done")
async def save_types(
    callback: CallbackQuery, db: Database, settings: Settings, state: FSMContext
) -> None:
    data = await state.get_data()
    selected = list(data.get("selected_types", ALL_EVENT_TYPES)) or ALL_EVENT_TYPES
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await db.upsert_subscription(int(user["id"]), **_subscription_values(sub, event_types=selected))
    await state.clear()
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.setting_saved())


@router.callback_query(F.data == "set:hall")
async def hall_menu(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    _, sub = await _user_and_sub(db, callback.from_user.id, settings)
    current = sub.get("hall_type") if sub else None
    await edit(callback, strings.choose_hall_text(), hall_keyboard(current))
    await answer(callback)


@router.callback_query(F.data.startswith("fh:"))
async def set_hall(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    value = split_cb(callback.data, 2)[1]
    hall = None if value == "all" else format_key(value)
    if hall is not None and hall not in CANONICAL_FORMATS:
        await answer(callback, strings.error_generic(), alert=True)
        return
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await db.upsert_subscription(int(user["id"]), **_subscription_values(sub, hall_type=hall))
    user, sub = await _user_and_sub(db, callback.from_user.id, settings)
    await _render(callback, user, sub, settings)
    await answer(callback, strings.setting_saved())
