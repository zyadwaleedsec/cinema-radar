"""Admin-only commands: dashboard, grants and revocations."""

from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import strings
from config import Settings
from handlers.utils import is_admin
from imax import IMAX_CATEGORIES, UNKNOWN

router = Router(name="admin")


def _admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user) and is_admin(message.from_user.id, settings.admin_id)


def _target_id(message: Message) -> int | None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return None
    return int(parts[1])


@router.message(Command("admin"))
async def admin_dashboard(message: Message, stats, settings: Settings) -> None:
    if not _admin(message, settings):
        await message.answer(strings.admin_only())
        return
    await message.answer(await stats.admin_text(), disable_web_page_preview=True)


@router.message(Command("status"))
async def upstream_status(
    message: Message,
    http,
    scheduler,
    settings: Settings,
    providers=None,
    discovery=None,
) -> None:
    if not _admin(message, settings):
        await message.answer(strings.admin_only())
        return
    names = (
        list(providers.names())
        if providers is not None and hasattr(providers, "names")
        else [settings.provider]
    )
    sections = []
    for name in names:
        last_run = discovery.provider_last_run.get(name) if discovery is not None else None
        last_error = discovery.provider_last_error.get(name) if discovery is not None else None
        events = discovery.provider_events.get(name, 0) if discovery is not None else 0
        sections.append(
            {
                "cinema": strings.cinema_name(name),
                "last_success": (
                    datetime.fromtimestamp(last_run).strftime("%Y-%m-%d %H:%M") if last_run else "—"
                ),
                "last_error": str(last_error) if last_error else "—",
                "events": events,
            }
        )
    await message.answer(
        strings.admin_status_multi(
            {
                "sections": sections,
                "breaker": http.circuit_state,
                "targets": len(scheduler),
                "affected": http.affected_hint,
            }
        ),
        disable_web_page_preview=True,
    )


@router.message(Command("grant"))
async def grant(message: Message, support, settings: Settings) -> None:
    if not _admin(message, settings):
        await message.answer(strings.admin_only())
        return
    telegram_id = _target_id(message)
    if telegram_id is None:
        await message.answer(strings.admin_usage("grant"))
        return
    ok = await support.grant(telegram_id)
    await message.answer(
        strings.grant_done(telegram_id, settings.supporter_watch_limit)
        if ok
        else strings.user_not_found()
    )


@router.message(Command("imax"))
async def imax_override(message: Message, db, settings: Settings, imax=None) -> None:
    if not _admin(message, settings):
        await message.answer(strings.admin_only())
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer(strings.imax_override_usage())
        return
    movie_id, status = parts[1], parts[2].upper()
    if status not in {*IMAX_CATEGORIES, UNKNOWN}:
        await message.answer(strings.imax_override_usage())
        return
    names = await db.movie_names_for_id(movie_id)
    if imax is not None:
        for name in names:
            imax.remember(name, status)
    await db.set_imax_override(movie_id, status)
    updated = await db.set_movie_imax_status(movie_id, status)
    await message.answer(strings.imax_override_done(movie_id, status, updated))


@router.message(Command("revoke"))
async def revoke(message: Message, support, settings: Settings) -> None:
    if not _admin(message, settings):
        await message.answer(strings.admin_only())
        return
    telegram_id = _target_id(message)
    if telegram_id is None:
        await message.answer(strings.admin_usage("revoke"))
        return
    ok = await support.revoke(telegram_id)
    await message.answer(
        strings.revoke_done(telegram_id, settings.free_watch_limit)
        if ok
        else strings.user_not_found()
    )
