"""The language gate: the first screen a user ever sees, plus the switcher."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import consent
import i18n
import strings
from config import Settings
from db import Database
from handlers.utils import answer, edit, send
from keyboards import consent_keyboard, language_keyboard, onboarding_keyboard

router = Router(name="language")


@router.message(Command("language"))
async def language_cmd(
    message: Message, state: FSMContext, db: Database, settings: Settings
) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    source = "s" if user and user.get("lang") else ""
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
) -> None:
    parts = (callback.data or "").split(":")
    code = i18n.normalize(parts[2] if len(parts) > 2 else "")
    source = parts[3] if len(parts) > 3 else ""

    user = await db.get_user(callback.from_user.id)
    if user is None or not consent.has_consent(user):
        # Nothing may be written before explicit consent: hold the choice in
        # memory and ask for it now.  Existing pre-consent rows are left as they
        # are until the user agrees to the current notice.
        consent.remember_pending_language(callback.from_user.id, code)
        i18n.set_language(code)
        if settings.admin_id and callback.from_user.id == settings.admin_id:
            i18n.set_admin_language(code)
        await answer(callback, strings.language_saved())
        await edit(callback, strings.consent_text(), consent_keyboard())
        return

    await db.set_user_language(callback.from_user.id, code)
    i18n.set_language(code)
    if settings.admin_id and callback.from_user.id == settings.admin_id:
        i18n.set_admin_language(code)

    await answer(callback, strings.language_saved())

    if source == "s" and int(user.get("onboarded") or 0):
        from handlers.settings import _settings_view

        sub = await db.get_subscription(int(user["id"]))
        text, keyboard = _settings_view(user, sub, settings)
        await edit(callback, text, keyboard)
        return

    # Picker flow: always follow the choice with the three welcome screens in
    # the new language.  Any deep link parked by the gate stays in ``deeplinks``
    # and is resumed when onboarding finishes.
    await state.clear()
    name = (callback.from_user.first_name or "") if callback.from_user else ""
    await edit(
        callback,
        f"{strings.onboard_progress(0)}\n\n{strings.onboard_intro(name)}",
        onboarding_keyboard(0),
    )
