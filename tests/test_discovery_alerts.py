"""Discovery alerts: poster, cinema brand and a readable card layout."""

from __future__ import annotations

import json

import i18n
import strings
from broadcaster import MAX_DIGEST_LINES, Broadcaster, _event_text
from links import cinema_page_url, movie_page_url
from models import Branch, DiscoveryEvent, Movie


class _Posters:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def url(self, title: str, year: int | None = None) -> str:
        self.calls.append(title)
        return f"https://image.tmdb.org/t/p/w500/{title}.jpg"


class _Sender:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, chat_id, text, reply_markup=None, photo_url=None) -> None:
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "keyboard": reply_markup,
                "photo_url": photo_url,
            }
        )


def test_showtimes_card_names_the_cinema_brand_and_branch():
    i18n.set_language("ar")
    text = strings.discovery_new_showtimes(
        "ولا كان عبال", "Madinaty", "2026-11-05", ["21:30", "23:45"], "vox"
    )

    assert "حفلات جديدة نزلت" in text
    assert "ولا كان عبال" in text
    assert "فوكس" in text and "Madinaty" in text
    assert "9:30 م" in text and "11:45 م" in text
    assert "<b>" in text and "<i>" in text


def test_cards_leave_a_blank_line_between_blocks():
    i18n.set_language("ar")
    text = strings.discovery_new_showtimes(
        "ولا كان عبال", "Madinaty", "2026-11-05", ["21:30"], "vox"
    )

    assert "\n\n" in text
    assert text.splitlines()[1] == ""


def test_arabic_cards_are_explicitly_rtl_and_isolate_latin_branches():
    i18n.set_language("ar")
    text = strings.discovery_new_showtimes(
        "ولا كان عبال", "Madinaty", "2026-11-05", ["21:30"], "vox"
    )

    # Every Arabic line starts with RLM, and the Latin branch sits inside an
    # LTR isolate so it cannot flip the surrounding Arabic punctuation.
    assert text.startswith("\u200f")
    assert "\u2066Madinaty\u2069" in text


def test_alert_uses_the_renaissance_brand():
    i18n.set_language("ar")
    text = strings.discovery_new_movie("Dune", "City Stars", None, None, "renaissance")

    assert "رينيسانس" in text
    assert "City Stars" in text


def test_digest_escapes_the_branch_and_keeps_the_brand():
    i18n.set_language("ar")
    text = strings.discovery_digest("<b>Madinaty</b>", 2, ["a", "b"], "vox")

    assert "&lt;b&gt;Madinaty&lt;/b&gt;" in text
    assert "فوكس" in text
    assert "تحديثين جديدين" in text


def test_english_card_uses_the_same_structure():
    i18n.set_language("en")
    text = strings.discovery_new_showtimes("Dune", "Madinaty", "2026-11-05", ["21:30"], "vox")

    assert "New showtimes just dropped" in text
    assert "VOX" in text and "Madinaty" in text
    assert "9:30 PM" in text
    i18n.set_language("ar")


def test_event_text_uses_the_branch_provider():
    i18n.set_language("ar")
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("city-stars", "City Stars", "renaissance"),
        movie=Movie("m1", "Dune", "dune"),
        date="2026-11-05",
        times=("21:30",),
    )

    assert "رينيسانس" in _event_text(event)


async def test_one_broken_subscriber_does_not_block_the_rest(db, test_settings):
    for telegram_id in (961, 962):
        user = await db.get_or_create_user(telegram_id, watch_limit=test_settings.free_watch_limit)
        await db.set_user_language(telegram_id, "ar")
        await db.upsert_subscription(int(user["id"]), [], ["NEW_SHOWTIMES"], None, True)

    sender = _Sender()
    broadcaster = Broadcaster(test_settings, db, sender)
    original = broadcaster._build_message

    async def flaky(telegram_id, events, titles=None):
        if telegram_id == 961:
            raise RuntimeError("broken preference row")
        return await original(telegram_id, events, titles=titles)

    broadcaster._build_message = flaky
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune"),
        date="2026-12-16",
        times=("21:30",),
        event_key="NEW_SHOWTIMES:madina:m1:2026-12-16",
    )

    sent = await broadcaster.process([event])

    assert sent == 1
    assert len(sender.sent) == 1
    assert sender.sent[0]["chat_id"] == 962


async def test_broadcast_resolves_and_sends_the_tmdb_poster(db, test_settings):
    user = await db.get_or_create_user(950, watch_limit=test_settings.free_watch_limit)
    await db.set_user_language(950, "ar")
    await db.upsert_subscription(int(user["id"]), [], ["NEW_SHOWTIMES"], None, True)

    sender = _Sender()
    posters = _Posters()
    broadcaster = Broadcaster(test_settings, db, sender, posters=posters)
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune"),
        date="2026-12-16",
        times=("21:30",),
        event_key="NEW_SHOWTIMES:madina:m1:2026-12-16",
    )

    sent = await broadcaster.process([event])

    assert sent == 1
    assert posters.calls == ["Dune"]
    assert sender.sent[0]["photo_url"] == "https://image.tmdb.org/t/p/w500/Dune.jpg"
    assert "فوكس" in str(sender.sent[0]["text"])
    assert "Madinaty" in str(sender.sent[0]["text"])


def _urls(keyboard) -> list[str]:
    return [button.url for row in keyboard.inline_keyboard for button in row if button.url]


def _callbacks(keyboard) -> list[str]:
    return [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_movie_page_urls_follow_each_provider():
    assert (
        movie_page_url(Movie("m1", "Dune", "dune", "vox"))
        == "https://egy.voxcinemas.com/movies/dune"
    )
    assert (
        movie_page_url(Movie("dune", "Dune", "dune", "renaissance"))
        == "https://rnscinemas.com/en/movie/dune"
    )
    assert (
        movie_page_url(Movie("dune", "Dune", "dune", "renaissance"), "ar")
        == "https://rnscinemas.com/ar/movie/dune"
    )
    assert (
        movie_page_url(Movie("7651.499", "Ramayana", "7651.499", "premiere"), "ar")
        == "https://www.premiere-cinemas.com/ar/movie-details/7651.499"
    )


def test_cinema_page_falls_back_to_the_provider_listing():
    branch = Branch("5", "Cima Arkan", "premiere")
    assert cinema_page_url(branch, "ar") == ("https://www.premiere-cinemas.com/ar/now-showing")
    vox = Branch("madina", "Madinaty", "vox", "https://egy.voxcinemas.com/cinemas/madina")
    assert cinema_page_url(vox) == "https://egy.voxcinemas.com/cinemas/madina"


def test_stored_renaissance_branch_urls_are_localized():
    branch = Branch(
        "city-stars",
        "City Stars",
        "renaissance",
        "https://rnscinemas.com/en/cinemas/city-stars",
    )

    assert cinema_page_url(branch, "ar") == "https://rnscinemas.com/ar/cinemas/city-stars"
    assert cinema_page_url(branch, "en") == "https://rnscinemas.com/en/cinemas/city-stars"


async def test_single_event_alert_links_to_the_movie_page(db, test_settings):
    i18n.set_language("ar")
    broadcaster = Broadcaster(test_settings, db, _Sender())
    event = DiscoveryEvent(
        kind="NEW_MOVIE",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune", "vox"),
        date="2026-12-16",
    )

    _, keyboard = await broadcaster._build_message(12345, [event])

    assert "https://egy.voxcinemas.com/movies/dune" in _urls(keyboard)
    assert any(callback.startswith("dw:") for callback in _callbacks(keyboard))
    assert "ds:stop" in _callbacks(keyboard)


async def test_digest_alert_links_to_the_cinema_page(db, test_settings):
    i18n.set_language("ar")
    broadcaster = Broadcaster(test_settings, db, _Sender())
    branch = Branch("madina", "Madinaty", "vox", "https://egy.voxcinemas.com/cinemas/madina")
    events = [
        DiscoveryEvent(
            kind="NEW_MOVIE",
            branch=branch,
            movie=Movie("m1", "Dune", "dune", "vox"),
            date="2026-12-16",
        ),
        DiscoveryEvent(
            kind="NEW_MOVIE",
            branch=branch,
            movie=Movie("m2", "Arrival", "arrival", "vox"),
            date="2026-12-16",
        ),
    ]

    _, keyboard = await broadcaster._build_message(12345, events)

    assert "https://egy.voxcinemas.com/cinemas/madina" in _urls(keyboard)
    assert "https://egy.voxcinemas.com/movies/dune" not in _urls(keyboard)


async def _subscribe(db, test_settings, telegram_id: int, kinds: list[str]) -> dict:
    user = await db.get_or_create_user(telegram_id, watch_limit=test_settings.free_watch_limit)
    await db.set_user_language(telegram_id, "ar")
    await db.upsert_subscription(int(user["id"]), [], kinds, None, True)
    return user


async def test_active_watch_suppresses_the_duplicate_discovery_card(db, test_settings):
    user = await _subscribe(db, test_settings, 971, ["NEW_SHOWTIMES"])
    await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="madina",
        branch_name="Madinaty",
        date="2026-12-16",
        movie_id="m1",
        movie_name="Dune",
        showtime="*",
        hall_type="*",
        watch_limit=10,
        scope="movie",
    )
    broadcaster = Broadcaster(test_settings, db, _Sender())
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune", "vox"),
        date="2026-12-16",
        times=("21:30",),
    )

    assert await broadcaster.process([event]) == 0


async def test_a_seats_only_watch_does_not_hide_new_movie_news(db, test_settings):
    user = await _subscribe(db, test_settings, 972, ["NEW_SHOWTIMES"])
    await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="madina",
        branch_name="Madinaty",
        date="2026-12-16",
        movie_id="m1",
        movie_name="Dune",
        showtime="*",
        hall_type="*",
        watch_limit=10,
        scope="movie",
        alert_mode="seats",
    )
    broadcaster = Broadcaster(test_settings, db, _Sender())
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune", "vox"),
        date="2026-12-16",
        times=("21:30",),
    )

    assert await broadcaster.process([event]) == 1


async def test_a_watch_for_another_date_does_not_suppress_the_card(db, test_settings):
    user = await _subscribe(db, test_settings, 973, ["NEW_SHOWTIMES"])
    await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="madina",
        branch_name="Madinaty",
        date="2026-12-17",
        movie_id="m1",
        movie_name="Dune",
        showtime="*",
        hall_type="*",
        watch_limit=10,
        scope="movie",
    )
    broadcaster = Broadcaster(test_settings, db, _Sender())
    event = DiscoveryEvent(
        kind="NEW_SHOWTIMES",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune", "vox"),
        date="2026-12-16",
        times=("21:30",),
    )

    assert await broadcaster.process([event]) == 1


async def test_all_dates_watch_covers_any_discovery_date(db, test_settings):
    user = await _subscribe(db, test_settings, 974, ["NEW_DATE_OPENED"])
    await db.add_watch(
        user_id=int(user["id"]),
        provider="vox",
        branch_id="madina",
        branch_name="Madinaty",
        date="*",
        movie_id="m1",
        movie_name="Dune",
        showtime="*",
        hall_type="*",
        watch_limit=10,
        scope="movie_all_dates",
    )
    broadcaster = Broadcaster(test_settings, db, _Sender())
    event = DiscoveryEvent(
        kind="NEW_DATE_OPENED",
        branch=Branch("madina", "Madinaty", "vox"),
        movie=Movie("m1", "Dune", "dune", "vox"),
        date="2026-12-20",
    )

    assert await broadcaster.process([event]) == 0


async def test_digest_caps_lines_and_summarises_the_rest(db, test_settings):
    i18n.set_language("ar")
    broadcaster = Broadcaster(test_settings, db, _Sender())
    branch = Branch("madina", "Madinaty", "vox")
    events = [
        DiscoveryEvent(
            kind="NEW_MOVIE",
            branch=branch,
            movie=Movie(f"m{index}", f"Movie {index}", f"m{index}", "vox"),
            date="2026-12-16",
        )
        for index in range(15)
    ]

    text, keyboard = await broadcaster._build_message(12345, events)

    assert len([line for line in text.splitlines() if "• " in line]) == MAX_DIGEST_LINES
    assert "3 تحديثات جديدة" in text
    token = next(cb for cb in _callbacks(keyboard) if cb.startswith("dw:")).split(":", 1)[1]
    action = await db.get_discovery_action(token)
    assert action is not None
    assert len(json.loads(action["payload"])) == MAX_DIGEST_LINES


def test_showtime_lines_cap_the_visible_times():
    i18n.set_language("ar")
    line = strings.discovery_line_new_showtimes(
        "Dune", tuple(f"{hour:02d}:00" for hour in range(9, 18))
    )

    assert "وغيرها" in line
    assert line.count("—") == 1
