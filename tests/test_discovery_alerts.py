"""Discovery alerts: poster, cinema brand and a readable card layout."""

from __future__ import annotations

import i18n
import strings
from broadcaster import Broadcaster, _event_text
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
