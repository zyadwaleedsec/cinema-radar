"""Watch creation from a discovery alert: every update, then a movie chooser."""

from __future__ import annotations

import json
from unittest.mock import patch

from aiogram.types import User

import i18n
import strings
from broadcaster import Broadcaster, _watch_choices
from handlers import discovery as discovery_handler
from keyboards import discovery_movie_keyboard
from models import Branch, DiscoveryEvent, Movie, Showtime


def _showtime(
    movie_id: str = "m1",
    movie_name: str = "Dune",
    time: str = "21:30",
    hall: str = "MAX",
) -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="madina",
        date="2026-12-16",
        movie_id=movie_id,
        movie_name=movie_name,
        time=time,
        hall_type=hall,
        status="AVAILABLE",
        booking_url="https://example/booking",
    )


def _movie(movie_id: str = "m1", name: str = "Dune") -> Movie:
    return Movie(
        movie_id,
        name,
        name.lower(),
        poster_url="https://image/movie.jpg",
        duration_minutes=155,
        rating="PG-13",
        language="English",
        synopsis="A desert epic.",
        trailer_url="https://video/trailer",
        imax_status="IMAX",
    )


def _event(
    kind: str = "NEW_SHOWTIMES",
    movie: Movie | None = None,
    time: str = "21:30",
    times: tuple[str, ...] = (),
) -> DiscoveryEvent:
    movie = movie or _movie()
    showtime = _showtime(movie.id, movie.name, time)
    return DiscoveryEvent(
        kind=kind,
        branch=Branch("madina", "Madinaty", "vox"),
        movie=movie,
        date="2026-12-16",
        showtime=showtime,
        booking_url="https://example/booking",
        times=times or (time,),
        event_key=f"{kind}:madina:{movie.id}:2026-12-16",
    )


class _FakeCallback:
    def __init__(self, user_id: int, data: str) -> None:
        self.data = data
        self.message = object()
        self.from_user = User(id=user_id, is_bot=False, first_name="Tester")


class _FakeScheduler:
    def __init__(self) -> None:
        self.targets = []

    def add(self, target, status=None, expected_open_at=None) -> None:
        self.targets.append(target)


class _Sender:
    async def send(self, chat_id, text, reply_markup=None, photo_url=None) -> None:
        pass


def test_digest_lists_every_update_without_a_more_line():
    i18n.set_language("ar")
    lines = [f"تحديث رقم {number}" for number in range(9)]

    text = strings.discovery_digest("Masrya Plaza - Zagazig", 9, lines, "renaissance")

    for line in lines:
        assert line in text
    assert "وكمان" not in text
    assert "9 تحديثات جديدة" in text


def test_watch_choices_dedupe_and_keep_the_event_data():
    events = [
        _event(time="21:30"),
        _event(time="23:45"),  # same movie: one chooser row only
        _event(movie=_movie("m2", "Inside Out 2"), time="18:00"),
    ]

    choices = _watch_choices(events, {"Dune": "الكثيب"})

    assert [choice["movie_id"] for choice in choices] == ["m1", "m2"]
    first = choices[0]
    assert first["title"] == "الكثيب"
    assert first["movie_name"] == "Dune"
    assert first["branch_name"] == "Madinaty"
    assert first["showtime"] == "21:30"
    assert first["hall_type"] == "MAX"
    assert first["booking_url"] == "https://example/booking"
    assert first["poster_url"] == "https://image/movie.jpg"
    assert first["duration_minutes"] == 155
    assert first["imax_status"] == "IMAX"
    assert first["line"].startswith("🕐")


def test_movie_keyboard_offers_one_button_per_update_line():
    choices = [
        {"movie_id": "m1", "title": "Dune", "line": "🕐 New showtimes: Dune — 9:30 PM"},
        {"movie_id": "m2", "title": "Inside Out 2", "line": "🆕 New movie: Inside Out 2"},
    ]

    markup = discovery_movie_keyboard("tok", choices)
    rows = markup.inline_keyboard

    assert [row[0].callback_data for row in rows] == ["dwm:tok:0", "dwm:tok:1"]
    assert rows[0][0].text.startswith("🕐")
    assert rows[1][0].text.startswith("🆕")


def test_choices_read_the_payload_and_fall_back_to_the_row():
    payload = json.dumps([{"movie_id": "m1", "title": "Dune"}])
    action = {"payload": payload, "movie_id": "m9", "movie_name": "Old"}

    assert discovery_handler._choices(action)[0]["movie_id"] == "m1"

    legacy = {"payload": None, "movie_id": "m9", "movie_name": "Old"}
    assert discovery_handler._choices(legacy)[0]["movie_name"] == "Old"


async def test_broadcast_action_belongs_to_the_telegram_user(db, test_settings):
    user = await db.get_or_create_user(949)
    await db.set_user_language(949, "ar")
    await db.upsert_subscription(int(user["id"]), [], ["NEW_SHOWTIMES"], None, True)

    broadcaster = Broadcaster(test_settings, db, _Sender())
    await broadcaster.process([_event()])

    action = await db.fetchone("SELECT user_id, payload FROM discovery_actions LIMIT 1")

    # The callback only knows the Telegram id, so the action must store that
    # id (not the internal users.id) or every watch button rejects its owner.
    assert action is not None and action["user_id"] == 949
    choices = json.loads(action["payload"])
    assert choices[0]["movie_id"] == "m1"
    assert choices[0]["booking_url"] == "https://example/booking"


async def test_watch_button_opens_the_movie_chooser(db):
    await db.get_or_create_user(950)
    payload = json.dumps(
        _watch_choices([_event(), _event(movie=_movie("m2", "Inside Out 2"), time="18:00")], {}),
        ensure_ascii=False,
    )
    await db.add_discovery_action(
        "tok",
        950,
        "madina",
        "Madinaty",
        "2026-12-16",
        "m1",
        "Dune",
        "vox",
        payload=payload,
    )

    sent: list[tuple[str, object]] = []

    async def fake_answer(callback, text="", alert=False):
        pass

    async def fake_send(message, text, keyboard=None, photo_url=None):
        sent.append((text, keyboard))

    with (
        patch.object(discovery_handler, "answer", fake_answer),
        patch.object(discovery_handler, "send", fake_send),
    ):
        await discovery_handler.watch_from_discovery(_FakeCallback(950, "dw:tok"), db)

    assert sent and "تحب تراقب أنهي فيلم؟" in sent[0][0]
    callbacks = [button.callback_data for row in sent[0][1].inline_keyboard for button in row]
    assert callbacks == ["dwm:tok:0", "dwm:tok:1"]


async def test_legacy_action_is_owned_by_the_internal_user_id(db):
    user = await db.get_or_create_user(952)
    payload = json.dumps(_watch_choices([_event()], {}), ensure_ascii=False)
    # 2.8.1 and earlier stored users.id instead of the Telegram id.
    await db.add_discovery_action(
        "old",
        int(user["id"]),
        "madina",
        "Madinaty",
        "2026-12-16",
        "m1",
        "Dune",
        "vox",
        payload=payload,
    )
    sent: list[object] = []

    async def fake_answer(callback, text="", alert=False):
        pass

    async def fake_send(message, text, keyboard=None, photo_url=None):
        sent.append(keyboard)

    with (
        patch.object(discovery_handler, "answer", fake_answer),
        patch.object(discovery_handler, "send", fake_send),
    ):
        await discovery_handler.watch_from_discovery(_FakeCallback(952, "dw:old"), db)

    assert sent


async def test_choosing_a_movie_creates_the_watch_from_the_payload(db, test_settings):
    user = await db.get_or_create_user(951)
    payload = json.dumps(_watch_choices([_event()], {"Dune": "الكثيب"}), ensure_ascii=False)
    await db.add_discovery_action(
        "tok",
        951,
        "madina",
        "Madinaty",
        "2026-12-16",
        "m1",
        "Dune",
        "vox",
        payload=payload,
    )
    scheduler = _FakeScheduler()
    edits: list[str] = []

    async def fake_answer(callback, text="", alert=False):
        pass

    async def fake_edit(callback, text, keyboard=None, photo_url=None):
        edits.append(text)

    with (
        patch.object(discovery_handler, "answer", fake_answer),
        patch.object(discovery_handler, "edit", fake_edit),
    ):
        await discovery_handler.watch_movie_chosen(
            _FakeCallback(951, "dwm:tok:0"), db, test_settings, scheduler
        )

    watches = await db.list_watches(int(user["id"]))
    assert len(watches) == 1
    watch = watches[0]
    assert watch["movie_id"] == "m1"
    assert watch["branch_name"] == "Madinaty"
    assert watch["showtime"] == "21:30"
    assert watch["hall_type"] == "MAX"
    assert watch["poster_url"] == "https://image/movie.jpg"
    assert watch["duration_minutes"] == 155
    assert scheduler.targets and scheduler.targets[0].movie_id == "m1"
    assert edits and "الكثيب" in edits[0]
