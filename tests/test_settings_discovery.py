"""Discovery must stay opt-in, and the feature must be discoverable."""

from __future__ import annotations

import i18n
import strings
from handlers.settings import _subscription_values


def test_filter_edits_never_activate_alerts():
    # No row yet, or a row the user switched off: editing filters must not
    # silently opt them back in.
    assert _subscription_values(None)["active"] is False
    assert (
        _subscription_values({"active": 0, "branch_ids": "[]", "event_types": '["NEW_MOVIE"]'})[
            "active"
        ]
        is False
    )


def test_activation_happens_only_through_the_explicit_toggle():
    assert _subscription_values({"active": 0}, active=True)["active"] is True
    assert _subscription_values({"active": 1}, active=False)["active"] is False


def test_filters_chosen_while_off_are_remembered():
    values = _subscription_values(
        {"active": 0, "branch_ids": '["vox:madina"]', "event_types": '["NEW_MOVIE"]'}
    )

    assert values["active"] is False
    assert values["branch_ids"] == ["vox:madina"]
    assert values["event_types"] == ["NEW_MOVIE"]


def test_settings_explains_how_to_turn_alerts_on():
    i18n.set_language("ar")
    try:
        off = strings.settings_text(True, 0, 0, False, 0, [], None)
        on = strings.settings_text(True, 0, 0, True, 0, [], None)

        assert "فعّل تنبيهات الأفلام والمواعيد" in off
        assert "فعّل تنبيهات الأفلام والمواعيد" not in on
        assert "الأفلام والمواعيد الجديدة: مقفولة" in off
    finally:
        i18n.set_language("ar")


def test_help_and_onboarding_mention_discovery_alerts():
    i18n.set_language("ar")
    try:
        assert "تنبيهات الأفلام والمواعيد" in strings.help_text()
        assert "تنبيهات الأفلام والمواعيد" in strings.onboard_alerts()
        assert "المواعيد" in strings.BTN_DISCOVERY_ALERTS
    finally:
        i18n.set_language("ar")


def test_english_copy_uses_the_same_wording():
    i18n.set_language("en")
    try:
        assert "Movie and showtime alerts" in strings.help_text()
        assert "Movie and showtime alerts" in strings.onboard_alerts()
        assert "showtime" in strings.BTN_DISCOVERY_ALERTS.lower()
        assert "New movies and showtimes" in strings.settings_text(
            True, 0, 0, True, 0, [], None, True, "en"
        )
    finally:
        i18n.set_language("ar")
