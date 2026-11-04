"""The language gate: the first screen a user ever sees, plus the switcher."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import deeplinks
import i18n
import strings
from config import Settings
from db import Database
from handlers.utils import answer, edit, send
from keyboards import language_keyboard, main_menu_keyboard, onboarding_keyboard

router = Router(name="language")


@router.message(Command("language"))
async def language_cmd(
    message: Message, state: FSMContext, db: Database, settings: Settings
) -> None:
    await state.clear()
    user = await db.get_or_create_user(message.from_user.id, watch_limit=settings.free_watch_limit)
    source = "s" if user.get("lang") else ""
    await send(message, strings.language_screen(), language_keyboard(source))


@router.callback_query(F.data == "set:lang")
async def change_language(callback: CallbackQuery) -> None:
    await edit(callback, strings.language_screen(), language_keyboard("s"))
    await answer(callback)


@router.callback_query(F.data.startswith("lang:set:"))
async def language_chosen(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    cache: Any = None,
    provider: Any = None,
) -> None:
    parts = (callback.data or "").split(":")
    code = i18n.normalize(parts[2] if len(parts) > 2 else "")
    source = parts[3] if len(parts) > 3 else ""

    await db.set_user_language(callback.from_user.id, code)
    i18n.set_language(code)
    if settings.admin_id and callback.from_user.id == settings.admin_id:
        i18n.set_admin_language(code)
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)

    await answer(callback, strings.language_saved())

    if source == "s" and int(user.get("onboarded") or 0):
        from handlers.settings import _settings_view

        sub = await db.get_subscription(int(user["id"]))
        text, keyboard = _settings_view(user, sub, settings)
        await edit(callback, text, keyboard)
        return

    if int(user.get("onboarded") or 0):
        payload = deeplinks.take(callback.from_user.id)
        if payload and await _resume_deeplink(
            callback, payload, state, db, settings, cache, provider
        ):
            return
        from handlers.common import dashboard_text

        name = (callback.from_user.first_name or "") if callback.from_user else ""
        await edit(callback, await dashboard_text(db, user, settings, name), main_menu_keyboard())
        return

    # First run: continue with the intro in the chosen language.  Any parked
    # deep link stays in ``deeplinks`` and is resumed when onboarding finishes.
    await state.clear()
    name = (callback.from_user.first_name or "") if callback.from_user else ""
    await edit(
        callback,
        f"{strings.onboard_progress(0)}\n\n{strings.onboard_intro(name)}",
        onboarding_keyboard(0),
    )


async def _resume_deeplink(
    callback: CallbackQuery,
    payload: str,
    state: FSMContext,
    db: Database,
    settings: Settings,
    cache: Any,
    provider: Any,
) -> bool:
    from handlers.common import handle_deep_link

    message = callback.message
    if message is None:
        return False
    return await handle_deep_link(
        message,
        payload,
        state,
        db,
        settings,
        cache,
        provider,
        telegram_id=callback.from_user.id,
    )
