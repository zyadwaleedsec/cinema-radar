"""Manual support: proof upload and the admin's approve/reject decision."""

from __future__ import annotations

import contextlib

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import strings
from config import Settings
from handlers.utils import answer, edit, is_admin, send, split_cb
from keyboards import (
    back_home_keyboard,
    donation_amount_keyboard,
    main_menu_keyboard,
    manual_payment_keyboard,
    proof_cancel_keyboard,
    support_keyboard,
)

router = Router(name="support")


class SupportFlow(StatesGroup):
    waiting_amount = State()
    waiting_proof = State()


@router.callback_query(F.data == "menu:support")
async def support_menu(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    user_row: dict | None = None,
) -> None:
    await answer(callback)
    await state.clear()
    is_supporter = bool(user_row and int(user_row.get("is_supporter") or 0))
    current_limit = int((user_row or {}).get("watch_limit") or settings.free_watch_limit)
    await edit(
        callback,
        strings.support_text(
            settings.supporter_watch_limit,
            settings.donation_min_amount,
            is_supporter=is_supporter,
            current_limit=current_limit,
        ),
        support_keyboard(),
    )


@router.callback_query(F.data.in_({"sup:vodafone_cash", "sup:instapay"}))
async def manual(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    method = split_cb(callback.data, 2)[1]
    account = settings.donation_account(method)
    if not account:
        await edit(callback, strings.support_not_configured(), back_home_keyboard())
        await answer(callback)
        return
    await edit(
        callback,
        strings.support_manual_text(
            method,
            account,
            settings.donation_min_amount,
            settings.supporter_watch_limit,
        ),
        manual_payment_keyboard(method, account),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("sup:paid:"))
async def paid(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    method = split_cb(callback.data, 3)[2]
    if method not in {"vodafone_cash", "instapay"}:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await state.set_state(SupportFlow.waiting_amount)
    await state.update_data(method=method, amount=None)
    await edit(
        callback,
        strings.support_ask_amount(settings.donation_min_amount),
        donation_amount_keyboard(settings.donation_min_amount),
    )
    await answer(callback)


@router.callback_query(F.data.startswith("sup:amt:"))
async def amount_preset(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        amount = int(split_cb(callback.data, 3)[2])
    except (IndexError, ValueError):
        await answer(callback, strings.support_amount_invalid(), alert=True)
        return
    await state.update_data(amount=amount)
    await state.set_state(SupportFlow.waiting_proof)
    await edit(callback, strings.support_ask_proof(_method(await state.get_data())))
    await answer(callback)


@router.callback_query(F.data == "sup:amtc")
async def amount_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportFlow.waiting_amount)
    await edit(
        callback,
        strings.support_custom_amount_prompt(),
        proof_cancel_keyboard(),
    )
    await answer(callback)


def _method(data: dict) -> str:
    value = str(data.get("method") or "vodafone_cash")
    return value if value in {"vodafone_cash", "instapay"} else "vodafone_cash"


@router.message(SupportFlow.waiting_amount, F.text, ~F.text.startswith("/"))
async def amount_typed(message: Message, state: FSMContext, settings: Settings) -> None:
    digits = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not digits:
        await send(message, strings.support_amount_invalid(), proof_cancel_keyboard())
        return
    amount = int(digits)
    await state.update_data(amount=amount)
    await state.set_state(SupportFlow.waiting_proof)
    data = await state.get_data()
    warning = ""
    if amount < settings.donation_min_amount:
        warning = "\n\n" + strings.support_below_minimum_warning()
    await send(
        message,
        strings.support_ask_proof(_method(data)) + warning,
        proof_cancel_keyboard(),
    )


@router.message(
    SupportFlow.waiting_proof, F.photo | F.document | (F.text & ~F.text.startswith("/"))
)
async def proof_received(message: Message, state: FSMContext, support, settings: Settings) -> None:
    data = await state.get_data()
    method = _method(data)
    amount = data.get("amount")
    file_id = None
    file_type = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        # Screenshots are often sent uncompressed as a file; accept both.
        file_id = message.document.file_id
        file_type = "document"
    note = (message.caption or message.text or "").strip()
    if not file_id and not note:
        await send(message, strings.error_generic())
        return
    await support.create_manual(
        telegram_id=message.from_user.id,
        method=method,
        note=note,
        file_id=file_id,
        amount=float(amount) if amount else None,
        file_type=file_type,
    )
    await state.clear()
    await send(message, strings.support_proof_received(), main_menu_keyboard())


@router.callback_query(F.data.startswith("dn:"))
async def donation_decision(callback: CallbackQuery, support, settings: Settings) -> None:
    parts = split_cb(callback.data, 3)
    action, raw_id = parts[1], parts[2]
    if not is_admin(callback.from_user.id, settings.admin_id):
        await answer(callback, strings.admin_only(), alert=True)
        return
    try:
        donation_id = int(raw_id)
    except ValueError:
        await answer(callback, strings.error_generic(), alert=True)
        return

    if action == "a":
        changed, _ = await support.approve(donation_id, callback.from_user.id)
        approved = True
    elif action == "r":
        changed, _ = await support.reject(donation_id, callback.from_user.id)
        approved = False
    else:
        await answer(callback, strings.error_generic(), alert=True)
        return

    if not changed:
        await answer(callback, strings.support_already_handled(), alert=True)
        return
    with contextlib.suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    await answer(callback, strings.support_admin_decided(donation_id, approved), alert=True)
