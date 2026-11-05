"""Explicit first-run consent before any user data is persisted."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

import consent
import i18n
import strings
from config import Settings
from db import Database
from handlers.utils import answer, edit
from keyboards import (
    consent_declined_keyboard,
    consent_keyboard,
    main_menu_keyboard,
    onboarding_keyboard,
)

router = Router(name="consent")


def _name(callback: CallbackQuery) -> str:
    return (callback.from_user.first_name or "") if callback.from_user else ""


@router.callback_query(F.data == "consent:yes")
async def consent_accepted(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    telegram_id = callback.from_user.id
    row = await db.get_user(telegram_id)
    # The pending choice is newer than anything stored before consent, so it
    # wins for users upgrading from an older release.
    lang = consent.pending_language(telegram_id) or (row or {}).get("lang") or i18n.DEFAULT_LANGUAGE
    user = await db.record_user_consent(
        telegram_id,
        lang=lang,
        watch_limit=settings.free_watch_limit,
        version=consent.CONSENT_VERSION,
    )
    consent.clear_pending_language(telegram_id)
    i18n.set_language(lang)

    await answer(callback, strings.language_saved())
    if int(user.get("onboarded") or 0):
        from handlers.common import dashboard_text

        await edit(
            callback,
            await dashboard_text(db, user, settings, _name(callback)),
            main_menu_keyboard(),
        )
        return

    await edit(
        callback,
        f"{strings.onboard_progress(0)}\n\n{strings.onboard_intro(_name(callback))}",
        onboarding_keyboard(0),
    )


@router.callback_query(F.data == "consent:no")
async def consent_declined(callback: CallbackQuery) -> None:
    # Keep the in-memory language so the "review" button can re-open consent.
    # No database row is created by declining.
    await answer(callback)
    await edit(callback, strings.consent_declined(), consent_declined_keyboard())


@router.callback_query(F.data == "consent:ask")
async def consent_review(callback: CallbackQuery) -> None:
    await answer(callback)
    await edit(callback, strings.consent_text(), consent_keyboard())
