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

    assert "🔴" in sold_out
    assert "⚪" in not_open
    assert "🟢" in available


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


def test_feedback_admin_prefers_the_sender_name():
    ar = strings.catalog("ar")
    assert "@zyad" in ar.feedback_admin(42, "zyad", "hi", "Zeyad")
    named = ar.feedback_admin(42, None, "hi", "Zeyad")
    assert "Zeyad" in named
    assert "<code>42</code>" in named
    anonymous = ar.feedback_admin(42, None, "hi")
    assert "<code>42</code>" in anonymous
    assert "ID:" not in anonymous


def test_admin_usage_escapes_placeholder_tags():
    # Telegram's HTML parser treats "<telegram_id>" as an unknown tag and
    # rejects the whole message, so usage lines must escape the angle brackets.
    for lang in ("ar", "en"):
        catalog = strings.catalog(lang)
        usage = catalog.admin_usage("grant")
        assert "<telegram_id>" not in usage
        assert "&lt;telegram_id&gt;" in usage
        imax = catalog.imax_override_usage()
        assert "<movie_id>" not in imax
        assert "<status>" not in imax


def test_seat_requirement_appears_on_the_confirmation():
    text = strings.confirm_watch(
        "City Centre Almaza",
        "2026-12-16",
        "Avengers: Doomsday",
        "10:45",
        "MAX",
        SOLD_OUT,
        required_seats=3,
    )
    assert "3 كراسي" in text
    assert "محتاج" in text


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
