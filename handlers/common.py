"""Start, help, dashboard, deep links and account deletion."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import deeplinks
import strings
from config import Settings
from db import Database
from handlers.utils import edit, send
from keyboards import (
    back_home_keyboard,
    delete_me_keyboard,
    main_menu_keyboard,
    onboarding_keyboard,
)

router = Router(name="common")

# Resolve the copy at call time so onboarding follows the chosen language.
ONBOARD_SCREENS = ("onboard_intro", "onboard_alerts", "onboard_safety")


async def dashboard_text(
    db: Database, user: dict[str, Any], settings: Settings, name: str = ""
) -> str:
    watches = await db.list_watches(int(user["id"]))
    next_line = None
    if watches:
        watch = next((item for item in watches if item.get("date") != "*"), watches[0])
        next_line = strings.dashboard_next(
            watch["movie_name"],
            watch["branch_name"],
            str(watch.get("date") or ""),
            str(watch.get("showtime") or ""),
            watch.get("scope"),
        )
    return strings.dashboard(
        name=name,
        active_watches=len(watches),
        next_watch=next_line,
        limit=int(user.get("watch_limit") or settings.free_watch_limit),
    )


async def show_home(message: Message, db: Database, settings: Settings) -> None:
    user = await db.get_or_create_user(message.from_user.id, watch_limit=settings.free_watch_limit)
    name = (message.from_user.first_name or "") if message.from_user else ""
    await send(message, await dashboard_text(db, user, settings, name), main_menu_keyboard())


async def handle_deep_link(
    message: Message,
    payload: str,
    state: FSMContext,
    db: Database,
    settings: Settings,
    cache: Any,
    provider: Any,
    telegram_id: int | None = None,
    providers: Any = None,
    metadata: Any = None,
) -> bool:
    payload = payload.strip()
    if payload.startswith("w") and payload[1:].isdigit():
        from handlers.watches import send_watch_detail_message

        await send_watch_detail_message(
            message, db, settings, int(payload[1:]), telegram_id=telegram_id, metadata=metadata
        )
        return True
    if payload.startswith("b") and len(payload) > 1:
        from handlers.watches import start_branch_deeplink

        return await start_branch_deeplink(
            message,
            state,
            cache,
            settings,
            provider,
            payload[1:],
            telegram_id=telegram_id,
            providers=providers,
        )
    return False


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
    cache: Any = None,
    provider: Any = None,
    providers: Any = None,
    metadata: Any = None,
) -> None:
    await state.clear()
    user = await db.get_or_create_user(message.from_user.id, watch_limit=settings.free_watch_limit)
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    if payload and int(user.get("onboarded") or 0):
        handled = await handle_deep_link(
            message,
            payload,
            state,
            db,
            settings,
            cache,
            provider,
            providers=providers,
            metadata=metadata,
        )
        if handled:
            return
    if int(user.get("onboarded") or 0):
        await send(
            message,
            await dashboard_text(db, user, settings, _telegram_name(message)),
            main_menu_keyboard(),
        )
        return
    if payload:
        # The gate parks links for users without a language; this covers the
        # gap where a language was already chosen but onboarding is unfinished.
        deeplinks.remember(message.from_user.id, payload)
    await send(
        message,
        f"{strings.onboard_progress(0)}\n\n{strings.onboard_intro(_telegram_name(message))}",
        onboarding_keyboard(0),
    )


def _telegram_name(message: Message) -> str:
    return (message.from_user.first_name or "") if message.from_user else ""


@router.callback_query(F.data.startswith("ob:"))
async def onboarding_step(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    cache: Any = None,
    provider: Any = None,
    providers: Any = None,
    metadata: Any = None,
) -> None:
    step = (callback.data or "").split(":", 1)[1]
    if step == "done":
        await db.mark_user_onboarded(callback.from_user.id)
        await state.clear()
        user = await db.get_or_create_user(
            callback.from_user.id, watch_limit=settings.free_watch_limit
        )
        payload = deeplinks.take(callback.from_user.id)
        if (
            payload
            and callback.message is not None
            and await handle_deep_link(
                callback.message,
                payload,
                state,
                db,
                settings,
                cache,
                provider,
                telegram_id=callback.from_user.id,
                providers=providers,
                metadata=metadata,
            )
        ):
            await callback.answer()
            return
        await edit(
            callback,
            await dashboard_text(db, user, settings, _telegram_name_callback(callback)),
            main_menu_keyboard(),
        )
        await callback.answer()
        return
    if not step.isdigit() or not (0 <= int(step) < len(ONBOARD_SCREENS)):
        await callback.answer(strings.error_expired(), show_alert=True)
        return
    index = int(step)
    screen = getattr(strings, ONBOARD_SCREENS[index])
    text = screen(_telegram_name_callback(callback)) if index == 0 else screen()
    await edit(
        callback,
        f"{strings.onboard_progress(index)}\n\n{text}",
        onboarding_keyboard(index),
    )
    await callback.answer()


def _telegram_name_callback(callback: CallbackQuery) -> str:
    return (callback.from_user.first_name or "") if callback.from_user else ""


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await send(message, strings.help_text())


@router.message(Command("privacy"))
async def privacy_cmd(message: Message) -> None:
    await send(message, strings.privacy_text())


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send(message, strings.cancelled(), main_menu_keyboard())


@router.message(Command("delete_me"))
async def delete_me_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send(message, strings.delete_me_confirm(), delete_me_keyboard())


@router.callback_query(F.data == "menu:home")
async def menu_home(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    await state.clear()
    await callback.answer()
    user = await db.get_or_create_user(callback.from_user.id, watch_limit=settings.free_watch_limit)
    await edit(
        callback,
        await dashboard_text(db, user, settings, _telegram_name_callback(callback)),
        main_menu_keyboard(),
    )


@router.callback_query(F.data == "del:ask")
async def delete_me_ask(callback: CallbackQuery) -> None:
    await edit(callback, strings.delete_me_confirm(), delete_me_keyboard())
    await callback.answer()


@router.callback_query(F.data == "del:yes")
async def delete_me_yes(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await db.delete_user(callback.from_user.id)
    await edit(callback, strings.delete_me_done(), back_home_keyboard())
    await callback.answer()
