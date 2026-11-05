"""Format normalisation, format buttons and canonical filtering."""

from __future__ import annotations

from broadcaster import Broadcaster
from keyboards import hall_keyboard, showtime_keyboard
from models import (
    AVAILABLE,
    CANONICAL_FORMATS,
    Branch,
    DiscoveryEvent,
    Movie,
    Showtime,
    format_key,
    format_label,
)
from providers.base import PROVIDER_FORMATS, available_formats


def _showtime(hall: str, time: str = "10:45") -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="almaza",
        date="2026-12-20",
        movie_id="HO1",
        movie_name="Avengers",
        time=time,
        hall_type=hall,
        status=AVAILABLE,
        seats_available=4,
    )


def test_format_key_matches_the_most_specific_label_first():
    assert format_key("IMAX") == "IMAX"
    assert format_key("IMAX Laser") == "IMAX"
    assert format_key("MAX") == "MAX"
    assert format_key("4DX") == "4DX"
    assert format_key("3D") == "3D"
    assert format_key("Standard") == "STANDARD"
    assert format_key(" standard ") == "STANDARD"
    assert format_key("*") == "*"
    assert format_key(None) == "*"


def test_unknown_formats_keep_their_uppercased_name():
    assert format_key("Drive-In") == "DRIVE-IN"
    assert format_label("Drive-In") == "Drive-In"


def test_format_labels_are_arabic_for_known_formats():
    assert format_label("IMAX") == "آيماكس IMAX"
    assert format_label("standard") == "Standard"
    assert format_label("*") == "كل الفورمات"


def _callback_data(keyboard) -> list[str]:
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_showtime_keyboard_offers_one_button_per_present_format():
    keyboard = showtime_keyboard(
        [_showtime("IMAX"), _showtime("MAX"), _showtime("MAX", "15:00")],
        formats={"IMAX": 1, "MAX": 2},
    )
    callbacks = _callback_data(keyboard)
    assert "fm:IMAX" in callbacks
    assert "fm:MAX" in callbacks
    assert "fm:all" not in callbacks

    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "آيماكس IMAX (1)" in labels
    assert "MAX (2)" in labels


def test_selected_format_is_marked_and_can_be_cleared():
    keyboard = showtime_keyboard(
        [_showtime("IMAX")],
        formats={"IMAX": 1, "MAX": 2},
        current_format="IMAX",
    )
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "✅ آيماكس IMAX (1)" in labels
    assert "fm:all" in _callback_data(keyboard)


def test_subscription_hall_filter_is_canonical():
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("almaza", "Almaza"),
        movie=Movie("HO1", "Avengers", "avengers"),
        showtime=_showtime("Standard"),
    )
    sub = {"branch_ids": "[]", "event_types": "[]", "hall_type": "standard"}
    assert Broadcaster._filter_events(None, sub, [event]) == [event]

    sub["hall_type"] = "IMAX"
    assert Broadcaster._filter_events(None, sub, [event]) == []

    sub["hall_type"] = "*"
    assert Broadcaster._filter_events(None, sub, [event]) == [event]


def test_available_formats_unions_only_the_selected_cinemas():
    renaissance = available_formats(["renaissance:citystars"], ["vox", "renaissance"])
    assert "STANDARD" in renaissance
    assert "DBOX" in renaissance
    assert "IMAX" not in renaissance
    assert "4DX" not in renaissance

    vox = available_formats(["vox:almaza"], ["vox", "renaissance"])
    assert "IMAX" in vox
    assert "DBOX" not in vox

    both = available_formats(["vox:almaza", "renaissance:citystars"], ["vox", "renaissance"])
    assert "IMAX" in both and "DBOX" in both
    assert both == tuple(key for key in CANONICAL_FORMATS if key in both)


def test_available_formats_falls_back_to_every_enabled_cinema():
    expected = set(PROVIDER_FORMATS["vox"]) | set(PROVIDER_FORMATS["renaissance"])
    assert available_formats([], ["vox", "renaissance"]) == tuple(
        key for key in CANONICAL_FORMATS if key in expected
    )
    # A branch prefix that is not enabled is ignored, keeping the result non-empty.
    assert available_formats(["vox:almaza"], ["renaissance"]) == available_formats(
        [], ["renaissance"]
    )


def test_hall_keyboard_only_offers_available_formats():
    keyboard = hall_keyboard(None, ("IMAX", "STANDARD"))
    callbacks = _callback_data(keyboard)
    assert "fh:all" in callbacks
    assert "fh:IMAX" in callbacks
    assert "fh:STANDARD" in callbacks
    assert "fh:DBOX" not in callbacks

    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(text.startswith("✅") for text in labels)


def test_hall_keyboard_marks_the_current_format():
    keyboard = hall_keyboard("IMAX", ("IMAX", "STANDARD"))
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "✅ آيماكس IMAX" in labels
    assert not any("✅ " in text and "كل الفورمات" in text for text in labels)
