"""Keyboard builders must work with both cached dicts and model objects."""

from __future__ import annotations

from keyboards import (
    branch_keyboard,
    branches_filter_keyboard,
    event_types_keyboard,
    main_menu_keyboard,
    movie_keyboard,
    search_keyboard,
    search_results_keyboard,
    showtime_keyboard,
    watch_alert_keyboard,
    watch_created_keyboard,
    watch_detail_keyboard,
    watches_keyboard,
)
from models import Branch, Movie, Showtime


def _texts(markup) -> list[str]:
    return [row[0].text for row in markup.inline_keyboard]


def _all_texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def test_branch_keyboard_accepts_cached_dicts():
    branches = [{"id": "city-centre-almaza", "name": "سيتي سنتر الماظة"}]
    assert _texts(branch_keyboard(branches))[0] == "سيتي سنتر الماظة"


def test_branch_keyboard_accepts_models():
    branches = [Branch("mall-of-egypt", "مول مصر")]
    assert _texts(branch_keyboard(branches))[0] == "مول مصر"


def test_movie_keyboard_accepts_cached_dicts():
    movies = [{"id": "m1", "name": "فيلم تجريبي"}]
    assert _texts(movie_keyboard(movies))[0] == "فيلم تجريبي"


def test_movie_keyboard_accepts_models():
    movies = [Movie("m1", "فيلم تجريبي", "demo")]
    assert _texts(movie_keyboard(movies))[0] == "فيلم تجريبي"


def test_branches_filter_keyboard_marks_selected_dict():
    branches = [{"id": "a", "name": "فرع أ"}]
    assert _texts(branches_filter_keyboard(branches, ["vox:a"]))[0].startswith("✅")


def test_showtime_keyboard_accepts_dicts_and_models():
    as_dict = {
        "time": "18:00",
        "hall_type": "MAX",
        "status": "AVAILABLE",
        "seats_available": 3,
    }
    as_model = Showtime(
        provider="vox",
        branch_id="a",
        date="2026-11-02",
        movie_id="m1",
        movie_name="Film",
        time="18:00",
        hall_type="MAX",
        status="AVAILABLE",
        seats_available=3,
    )
    assert _texts(showtime_keyboard([as_dict]))[0] == _texts(showtime_keyboard([as_model]))[0]


def test_showtime_keyboard_offers_watching_the_whole_day():
    callbacks = {
        button.callback_data
        for row in showtime_keyboard(
            [{"time": "18:00", "hall_type": "MAX", "status": "AVAILABLE"}]
        ).inline_keyboard
        for button in row
    }
    assert "st:all" in callbacks


def test_watches_keyboard_labels_movie_scope_without_sentinel_time():
    rows = watches_keyboard(
        [
            {
                "id": 12,
                "date": "2026-12-16",
                "showtime": "*",
                "hall_type": "*",
                "movie_name": "Avengers",
                "scope": "movie",
            }
        ]
    )
    text = rows.inline_keyboard[0][0].text
    assert "كل الحفلات" in text
    assert "*" not in text


def test_movie_keyboard_offers_name_search():
    texts = _all_texts(movie_keyboard([{"id": "m1", "name": "فيلم"}]))
    assert any("دوّر بالاسم" in text for text in texts)


def test_search_results_keyboard_offers_again_and_all():
    texts = _all_texts(search_results_keyboard([{"id": "m1", "name": "فيلم"}]))
    assert any("بحث تاني" in text for text in texts)
    assert any("كل الأفلام" in text for text in texts)


def test_main_menu_has_search_entry():
    texts = _all_texts(main_menu_keyboard())
    assert any("دوّر على فيلم" in text for text in texts)


def test_search_prompt_keyboard_can_skip_to_all_movies():
    texts = _all_texts(search_keyboard())
    assert any("كل الأفلام" in text for text in texts)


def test_alert_has_booking_snooze_and_remove_buttons():
    markup = watch_alert_keyboard(5, "https://example/booking/5")
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert any(button.url == "https://example/booking/5" for button in buttons)
    callbacks = {button.callback_data for button in buttons}
    assert "wa:snz:5" in callbacks
    assert "wa:del:5" in callbacks


def test_alert_omits_booking_button_without_url():
    callbacks = {
        button.callback_data
        for row in watch_alert_keyboard(5, None).inline_keyboard
        for button in row
    }
    assert callbacks == {"wa:snz:5", "wa:del:5"}


def test_watch_detail_keyboard_marks_mode_and_snooze():
    watch = {"id": 7, "alert_mode": "seats", "snoozed_until": None}
    buttons = [button for row in watch_detail_keyboard(watch).inline_keyboard for button in row]
    callbacks = {button.callback_data for button in buttons}
    assert {"w:mode:7:seats", "w:mode:7:opening", "w:mode:7:all"} <= callbacks
    assert "w:snz:7" in callbacks
    assert "w:del:7" in callbacks
    assert any(button.text.startswith("✅") and "كراسي" in button.text for button in buttons)


def test_watch_detail_offers_unsnooze_when_snoozed():
    watch = {"id": 7, "alert_mode": "all", "snoozed_until": "2026-01-01T10:00:00+00:00"}
    callbacks = {
        button.callback_data
        for row in watch_detail_keyboard(watch).inline_keyboard
        for button in row
    }
    assert "w:snz0:7" in callbacks
    assert "w:snz:7" not in callbacks


def test_watches_list_opens_settings():
    rows = watches_keyboard(
        [
            {
                "id": 11,
                "date": "2026-12-16",
                "showtime": "10:45",
                "movie_name": "Avengers",
            }
        ]
    )
    callbacks = {button.callback_data for row in rows.inline_keyboard for button in row}
    assert "w:cfg:11" in callbacks


def test_created_watch_offers_settings_button():
    callbacks = {
        button.callback_data for row in watch_created_keyboard(9).inline_keyboard for button in row
    }
    assert "w:cfg:9" in callbacks


def test_event_types_keyboard_includes_coming_soon_release():
    callbacks = {
        button.callback_data for row in event_types_keyboard([]).inline_keyboard for button in row
    }
    assert "ft:UPCOMING_MOVIE" in callbacks
