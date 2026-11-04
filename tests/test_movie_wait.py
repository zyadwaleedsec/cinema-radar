"""Movie waits: "tell me when this title is bookable anywhere"."""

from __future__ import annotations

import pytest

import search
from broadcaster import Broadcaster
from handlers.watches import _create_movie_wait
from keyboards import search_keyboard
from notifier import TelegramSender


class _FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return None


def _now_showing_candidate(title: str = "Avengers: Doomsday") -> dict:
    return {
        "title": title,
        "movie_id": "avengers-doomsday",
        "provider": "renaissance",
        "branch_id": "madinty",
        "branch_name": "Madinaty",
        "date": "2026-12-16",
        "booking_url": "https://rnscinemas.com/en/booking/x",
    }


@pytest.mark.asyncio
async def test_movie_wait_limit_is_enforced(db, test_settings):
    user = await db.get_or_create_user(100, watch_limit=2)
    await _create_movie_wait(db, test_settings, 100, "Avengers")
    await _create_movie_wait(db, test_settings, 100, "Dune")
    assert await db.count_active_movie_waits(int(user["id"])) == 2

    await _create_movie_wait(db, test_settings, 100, "Godzilla")
    assert await db.count_active_movie_waits(int(user["id"])) == 2


@pytest.mark.asyncio
async def test_movie_wait_duplicate_is_ignored(db, test_settings):
    await db.get_or_create_user(101, watch_limit=2)
    await _create_movie_wait(db, test_settings, 101, "Avengers")
    await _create_movie_wait(db, test_settings, 101, "avengers")
    assert await db.count_active_movie_waits(1) == 1


@pytest.mark.asyncio
async def test_movie_wait_alert_is_sent_once(db, test_settings, clock):
    user = await db.get_or_create_user(102)
    await db.add_movie_wait(
        int(user["id"]), "Avengers: Doomsday", search.compact("Avengers: Doomsday")
    )
    bot = _FakeBot()
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)
    broadcaster = Broadcaster(test_settings, db, sender, clock=clock)

    sent = await broadcaster.notify_movie_waits([_now_showing_candidate()], now=clock())
    assert sent == 1
    assert len(bot.messages) == 1
    assert "Avengers: Doomsday" in bot.messages[0]["text"]

    # One-shot: the same wait must not fire again.
    assert await broadcaster.notify_movie_waits([_now_showing_candidate()], now=clock()) == 0
    assert len(bot.messages) == 1


@pytest.mark.asyncio
async def test_movie_wait_matches_arabic_transliteration(db, test_settings, clock):
    user = await db.get_or_create_user(103)
    await db.add_movie_wait(int(user["id"]), "افنجرز", search.compact("افنجرز"))
    bot = _FakeBot()
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)
    broadcaster = Broadcaster(test_settings, db, sender, clock=clock)

    sent = await broadcaster.notify_movie_waits([_now_showing_candidate()], now=clock())
    assert sent == 1


@pytest.mark.asyncio
async def test_movie_wait_prebook_candidate_does_not_need_branch(db, test_settings, clock):
    user = await db.get_or_create_user(104)
    await db.add_movie_wait(
        int(user["id"]), "Avengers: Doomsday", search.compact("Avengers: Doomsday")
    )
    bot = _FakeBot()
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)
    broadcaster = Broadcaster(test_settings, db, sender, clock=clock)

    candidate = {
        "title": "Avengers: Doomsday",
        "movie_id": "avengers-doomsday",
        "provider": "renaissance",
        "dates": ["2026-12-16", "2026-12-23"],
    }
    sent = await broadcaster.notify_movie_waits([candidate], now=clock())
    assert sent == 1
    assert "Avengers: Doomsday" in bot.messages[0]["text"]


def test_search_keyboard_offers_movie_wait():
    callbacks = {
        button.callback_data for row in search_keyboard().inline_keyboard for button in row
    }
    assert "mw:add" in callbacks
