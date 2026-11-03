"""UX polish: onboarding, clickable suggestions and actionable empty states."""

from __future__ import annotations

import strings
from keyboards import (
    onboarding_keyboard,
    retry_keyboard,
    showtime_keyboard,
    suggestion_keyboard,
)


def _callbacks(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def _texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


async def test_new_user_is_not_onboarded_until_marked(db):
    user = await db.get_or_create_user(960)
    assert user["onboarded"] == 0

    await db.mark_user_onboarded(960)
    refreshed = await db.get_user(960)
    assert refreshed is not None and refreshed["onboarded"] == 1


def test_onboarding_has_three_screens_with_skip():
    first = _texts(onboarding_keyboard(0))
    assert strings.BTN_ONBOARD_NEXT in first
    assert strings.BTN_ONBOARD_SKIP in first

    last = _texts(onboarding_keyboard(2))
    assert strings.BTN_ONBOARD_START in last
    assert strings.BTN_ONBOARD_SKIP in last

    assert "ob:1" in _callbacks(onboarding_keyboard(0))
    assert "ob:done" in _callbacks(onboarding_keyboard(2))


def test_suggestions_are_clickable_movie_buttons():
    markup = suggestion_keyboard([{"id": "m1", "name": "Dune"}, {"id": "m2", "name": "Dune 2"}])
    assert _texts(markup)[:2] == ["Dune", "Dune 2"]
    callbacks = _callbacks(markup)
    assert "mv:0" in callbacks and "mv:1" in callbacks
    assert "mv_search" in callbacks and "mv_all" in callbacks


def test_empty_state_keyboard_offers_retry_and_back():
    callbacks = _callbacks(retry_keyboard("dt:1", "dt_p:0"))
    assert callbacks == ["dt:1", "dt_p:0"]


def test_no_results_text_uses_buttons_instead_of_repeating_names():
    with_buttons = strings.search_no_results("dun", ["Dune"])
    assert "Dune" not in with_buttons
    assert "اضغط عليها" in with_buttons

    without = strings.search_no_results("zzz")
    assert "اضغط عليها" not in without


def test_all_dates_button_is_hidden_when_only_one_day_is_available():
    showtimes = [{"time": "18:00", "hall_type": "MAX", "status": "AVAILABLE"}]
    one_day = _callbacks(showtime_keyboard(showtimes, date_count=1))
    two_days = _callbacks(showtime_keyboard(showtimes, date_count=2))
    assert "st:alldays" not in one_day
    assert "st:alldays" in two_days
    assert "st:all" in two_days
