"""Renderer, navigation and 2026 UX contracts."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest

import keyboards
import strings
from handlers.watches import _watches_view
from ui import Screen, render, rich


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []
        self.rich_sent: list[dict] = []
        self.rich_error: Exception | None = None

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))

    async def send_rich_message(self, **kwargs):
        if self.rich_error is not None:
            raise self.rich_error
        self.rich_sent.append(kwargs)
        return {"ok": True}


class FakeMessage:
    def __init__(self, photo: bool = False) -> None:
        self.chat = SimpleNamespace(id=1)
        self.photo = object() if photo else None
        self.bot = FakeBot()
        self.edited: list[dict] = []
        self.answered: list[dict] = []
        self.captions: list[dict] = []
        self.deleted = False
        self.edit_error: Exception | None = None
        self.rich_error: Exception | None = None

    async def edit_text(self, **kwargs):
        if "rich_message" in kwargs and self.rich_error is not None:
            raise self.rich_error
        if self.edit_error is not None:
            raise self.edit_error
        self.edited.append(kwargs)
        return {"ok": True}

    async def edit_caption(self, **kwargs):
        if self.edit_error is not None:
            raise self.edit_error
        self.captions.append(kwargs)
        return {"ok": True}

    async def answer(self, **kwargs):
        self.answered.append(kwargs)
        return {"ok": True}

    async def answer_photo(self, **kwargs):
        self.answered.append({"photo": True, **kwargs})
        return {"ok": True}

    async def delete(self):
        self.deleted = True


class FakeCallback:
    def __init__(self, message: FakeMessage | None = None) -> None:
        self.from_user = SimpleNamespace(id=7, first_name="Test")
        self.message = message
        self.bot = message.bot if message else FakeBot()
        self.answers: list[dict] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=object(), message=message)


def _callbacks(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


def _all_buttons(markup) -> list:
    return [button for row in markup.inline_keyboard for button in row]


@pytest.fixture(autouse=True)
def _reset_renderer() -> None:
    render.reset_capability()
    render.set_freshness_note("")


async def test_classic_mode_edits_the_same_message():
    message = FakeMessage()
    callback = FakeCallback(message)
    await render.edit_screen(
        callback,
        Screen(text="<b>hello</b>", keyboard=None),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert message.edited[0]["text"] == "<b>hello</b>"
    assert message.answered == []


async def test_not_modified_does_not_send_a_duplicate_message():
    message = FakeMessage()
    message.edit_error = _bad_request("Bad Request: message is not modified")
    callback = FakeCallback(message)

    await render.edit_screen(
        callback,
        Screen(text="same"),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert message.answered == []


async def test_rich_rejection_falls_back_to_classic_and_remembers():
    message = FakeMessage()
    message.rich_error = _bad_request("Bad Request: rich messages are not supported")
    callback = FakeCallback(message)

    await render.edit_screen(
        callback,
        Screen(text="hello"),
        SimpleNamespace(ui_renderer="auto"),
    )
    assert len(message.edited) == 1
    assert message.edited[0]["text"] == "hello"
    assert render.rich_supported() is False


async def test_auto_mode_uses_rich_when_available():
    message = FakeMessage()
    callback = FakeCallback(message)

    await render.edit_screen(
        callback,
        Screen(text="hello"),
        SimpleNamespace(ui_renderer="auto"),
    )
    assert "rich_message" in message.edited[0]
    assert render.rich_supported() is True


def test_rich_messages_keep_paragraph_breaks():
    built = rich.build(Screen(text="one\ntwo\n\nthree"))
    if built is None:
        pytest.skip("rich messages are unavailable")
    assert built.html == "one<br>two<br><br>three"


async def test_photo_card_edits_caption_in_place():
    message = FakeMessage(photo=True)
    callback = FakeCallback(message)

    await render.edit_screen(
        callback,
        Screen(text="caption", photo_url="https://poster", keyboard=None),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert message.captions[0]["caption"] == "caption"
    assert message.deleted is False


def test_main_menu_is_two_columns_with_primary_action():
    rows = keyboards.main_menu_keyboard().inline_keyboard
    assert all(len(row) == 2 for row in rows)
    assert rows[0][0].callback_data == "menu:add"
    assert rows[0][0].style == "primary"


def test_visual_system_tokens_render_consistently():
    from ui.theme import DIVIDER, progress

    assert progress(1, 5) == "▰▱▱▱▱ 1/5"
    assert progress(4, 5) == "▰▰▰▰▱ 4/5"

    ar = strings.catalog("ar")
    en = strings.catalog("en")
    assert DIVIDER in ar.step_header(2, 5, "الفرع")
    assert DIVIDER in en.step_header(2, 5, "Branch")
    assert ar.page_label(0, 2) == "صفحة 1 / 2"
    assert en.page_label(0, 2) == "Page 1 / 2"
    assert "🎬 Cinema Radar · v" in ar.version_line()
    assert "🎬 Cinema Radar · v" in en.version_line()

    labels = [
        button.text for row in keyboards.language_keyboard().inline_keyboard for button in row
    ]
    assert "🇪🇬 العربية" in labels
    assert "🇺🇸 English" in labels


def test_add_flow_has_back_on_every_step():
    dates = keyboards.date_keyboard(["2026-11-03"])
    movies = keyboards.movie_keyboard([{"id": "m1", "name": "Film"}])
    showtimes = keyboards.showtime_keyboard(
        [{"time": "18:00", "hall_type": "MAX", "status": "AVAILABLE"}]
    )
    assert "ab:branch" in _callbacks(dates)
    assert "ab:date" in _callbacks(movies)
    assert "ab:movie" in _callbacks(showtimes)
    assert "ab:showtime" in _callbacks(keyboards.confirm_keyboard())
    assert "menu:home" in _callbacks(dates)


def test_destructive_actions_need_confirmation():
    assert "w:ally" in _callbacks(keyboards.watches_clear_confirm_keyboard())
    assert "w:dely:9" in _callbacks(keyboards.watch_delete_confirm_keyboard(9))
    assert "w:del:9" in _callbacks(keyboards.watch_detail_keyboard({"id": 9}))


def test_settings_has_delete_data_and_custom_quiet_time():
    settings = keyboards.settings_keyboard({"notify_cancellations": 1}, {"active": True})
    assert "del:ask" in _callbacks(settings)
    assert "q:cust" in _callbacks(keyboards.quiet_keyboard(23, 8))


def test_manual_payment_has_copy_button():
    markup = keyboards.manual_payment_keyboard("vodafone_cash", "01000000000")
    copies = [button for button in _all_buttons(markup) if getattr(button, "copy_text", None)]
    assert len(copies) == 1
    assert copies[0].copy_text.text == "01000000000"


def test_alert_can_deep_link_to_watch_management():
    markup = keyboards.watch_alert_keyboard(
        5,
        "https://booking",
        manage_url="https://t.me/cinemaradar_bot?start=w5",
    )
    urls = {button.url for button in _all_buttons(markup) if getattr(button, "url", None)}
    assert "https://t.me/cinemaradar_bot?start=w5" in urls


def test_weekday_labels_for_other_days():
    today = date(2026, 11, 3)
    assert strings.relative_date("2026-11-03", today) == "النهاردة"
    assert strings.relative_date("2026-11-04", today) == "بكرة"
    assert strings.relative_date("2026-11-06", today) == "الجمعة 6/11"


def test_dashboard_shows_active_count_and_next_watch():
    text = strings.dashboard(
        "زينب",
        3,
        strings.dashboard_next("Dune", "الماظة", "2026-11-04", "19:30", "showtime"),
        limit=10,
    )
    assert "3" in text
    assert "Dune" in text
    assert "الماظة" in text


def test_watch_list_is_grouped_and_paged():
    watches = [
        {
            "id": index,
            "branch_name": "الماظة",
            "date": "2026-11-03" if index < 4 else "2026-11-04",
            "movie_name": f"Film {index}",
            "showtime": "18:00",
            "hall_type": "MAX",
            "scope": "showtime",
        }
        for index in range(8)
    ]
    from config import Settings

    _text, markup = _watches_view(watches, Settings(), page=0)
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "صفحة 1 / 2" in labels
    page_button = next(
        button for row in markup.inline_keyboard for button in row if button.text == "صفحة 1 / 2"
    )
    assert page_button.disabled is not None
    assert page_button.callback_data is None
    assert "wp:1" in _callbacks(markup)
    text_two, _ = _watches_view(watches, Settings(), page=1)
    assert "Film 7" in text_two


def test_command_scopes_keep_admin_commands_private():
    public = {name for name, _ in strings.PUBLIC_COMMANDS}
    admin = {name for name, _ in strings.ADMIN_COMMANDS}
    assert {"start", "add", "search", "watches", "settings"} <= public
    assert public.isdisjoint(admin)
    assert {"admin", "grant", "revoke", "imax"} <= admin


def test_custom_quiet_range_parsing():
    from handlers.settings import parse_quiet_range

    assert parse_quiet_range("23-8") == (23, 8)
    assert parse_quiet_range(" 0 – 7 ") == (0, 7)
    assert parse_quiet_range("24-8") is None
    assert parse_quiet_range("23:30-8:30") is None
    assert parse_quiet_range("night") is None


def test_truncate_does_not_split_html_tags_or_entities():
    tagged = "a" * 10 + "<b>" + "b" * 20 + "</b>"
    cut = strings.truncate(tagged, 13)
    assert cut == "a" * 10 + "…"

    entity = "x" * 5 + "&amp;" + "y" * 10
    assert strings.truncate(entity, 8) == "x" * 5 + "…"


async def test_send_falls_back_to_classic_when_rich_send_is_rejected():
    message = FakeMessage()
    message.bot.rich_error = _bad_request("Bad Request: unknown method sendRichMessage")
    await render.send_screen(
        message,
        Screen(text="<b>hello</b>", keyboard=None),
        SimpleNamespace(ui_renderer="auto"),
    )
    assert message.answered[0]["text"] == "<b>hello</b>"
    assert render.rich_supported() is False


async def test_loading_helper_sends_typing_action():
    from handlers.utils import loading

    message = FakeMessage()
    callback = FakeCallback(message)
    await loading(callback)
    assert message.bot.actions == [(7, "typing")]


async def test_not_modified_in_auto_mode_does_not_disable_rich():
    message = FakeMessage()
    message.rich_error = _bad_request("Bad Request: message is not modified")
    callback = FakeCallback(message)
    await render.edit_screen(
        callback,
        Screen(text="same"),
        SimpleNamespace(ui_renderer="auto"),
    )
    assert render.rich_supported() is True
    assert message.answered == []


async def test_back_from_photo_card_deletes_and_resends_text():
    message = FakeMessage(photo=True)
    callback = FakeCallback(message)
    await render.edit_screen(
        callback,
        Screen(text="showtimes", keyboard=None),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert message.deleted is True
    assert message.answered[0]["text"] == "showtimes"


async def test_freshness_note_is_appended_to_text_screens_only():
    render.set_freshness_note(strings.stale_notice(15, True))

    message = FakeMessage()
    await render.send_screen(
        message,
        Screen(text="<b>menu</b>", keyboard=None),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert "آخر تحديث" in message.answered[0]["text"]
    assert "البيانات ممكن تكون قديمة" in message.answered[0]["text"]

    photo = FakeMessage(photo=True)
    await render.send_screen(
        photo,
        Screen(text="poster", photo_url="https://poster", keyboard=None),
        SimpleNamespace(ui_renderer="classic"),
    )
    assert photo.answered[0]["caption"] == "poster"
    assert "آخر تحديث" not in photo.answered[0]["caption"]


def test_stale_notice_is_quiet_while_fresh():
    assert strings.stale_notice(0, False) == ""
    assert strings.stale_notice(5, False) == ""
    assert "من 12 دقيقة" in strings.stale_notice(12, False)
    assert "مش متاح" in strings.stale_notice(1, True)


def test_reason_label_maps_upstream_failures():
    assert "403" in strings.reason_label("http_403")
    assert "429" in strings.reason_label("http_429")
    assert "مهلة" in strings.reason_label("timeout")
    assert strings.reason_label("not-a-real-reason") == strings.reason_label("unknown")
