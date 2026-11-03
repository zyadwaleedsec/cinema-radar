"""User-facing formatting and status wording."""

from __future__ import annotations

import strings
from models import AVAILABLE, NOT_AVAILABLE, SOLD_OUT


def test_format_time_handles_24_hour_values():
    assert strings.format_time("10:45") == "10:45 ص"
    assert strings.format_time("15:00") == "3:00 م"
    assert strings.format_time("22:00") == "10:00 م"
    assert strings.format_time("00:30") == "12:30 ص"
    assert strings.format_time("12:15") == "12:15 م"


def test_format_time_handles_am_pm_values():
    assert strings.format_time("10:45am") == "10:45 ص"
    assert strings.format_time("3:00pm") == "3:00 م"
    assert strings.format_time("12:15am") == "12:15 ص"
    assert strings.format_time("12:15pm") == "12:15 م"


def test_sold_out_and_not_open_have_different_labels():
    sold_out = strings.showtime_button("10:45", "MAX", SOLD_OUT, None)
    not_open = strings.showtime_button("10:45", "MAX", NOT_AVAILABLE, None)
    available = strings.showtime_button("10:45", "MAX", AVAILABLE, 4)

    assert "الحجز مكتمل" in sold_out
    assert "لسه مفتحش" in not_open
    assert "متاح" in available


def test_confirmation_explains_sold_out_watch():
    text = strings.confirm_watch(
        "City Centre Almaza",
        "2026-12-16",
        "Avengers: Doomsday (Infinity Vision)",
        "10:45",
        "MAX",
        SOLD_OUT,
    )
    assert "حجوزاتها مكتملة" in text
    assert "ترجع كراسي" in text


def test_movie_facts_show_duration_rating_and_language():
    facts = strings.movie_facts(125, "PG-13", "English")
    assert "ساعتين و5 دقيقة" in facts
    assert "PG-13" in facts
    assert "English" in facts


def test_duration_label_handles_short_and_long_films():
    assert strings.duration_label(45) == "45 دقيقة"
    assert strings.duration_label(60) == "ساعة"
    assert strings.duration_label(166) == "ساعتين و46 دقيقة"
    assert strings.movie_facts(None, None, None) == ""
