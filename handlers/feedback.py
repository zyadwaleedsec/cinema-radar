"""User feedback questionnaire and forwarding to the support chat."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import strings
from handlers.utils import answer, edit, send, split_cb
from keyboards import (
    feedback_categories_keyboard,
    feedback_waiting_keyboard,
    main_menu_keyboard,
)

router = Router(name="feedback")

FEEDBACK_CATEGORIES = {"idea", "bug", "movie", "other"}


class FeedbackFlow(StatesGroup):
    category = State()
    waiting = State()


@router.callback_query(F.data == "menu:feedback")
async def feedback_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FeedbackFlow.category)
    await edit(
        callback,
        strings.feedback_categories_text(),
        feedback_categories_keyboard(),
    )
    await answer(callback)


@router.callback_query(FeedbackFlow.category, F.data.startswith("fc:"))
async def feedback_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = split_cb(callback.data, 2)[1]
    if category not in FEEDBACK_CATEGORIES:
        await answer(callback, strings.error_generic(), alert=True)
        return
    await state.set_state(FeedbackFlow.waiting)
    await state.update_data(category=category)
    await edit(
        callback,
        strings.feedback_text(category),
        feedback_waiting_keyboard(),
    )
    await answer(callback)


@router.message(FeedbackFlow.waiting, F.text)
async def feedback_received(message: Message, state: FSMContext, feedback) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(strings.error_generic())
        return
    data = await state.get_data()
    category = strings.feedback_category_label(str(data.get("category") or "other"))
    ok = await feedback.submit(
        message.from_user.id,
        message.from_user.username,
        f"[{category}] {text}",
    )
    await state.clear()
    await send(
        message,
        strings.feedback_thanks() if ok else strings.feedback_too_soon(),
        main_menu_keyboard(),
    )
