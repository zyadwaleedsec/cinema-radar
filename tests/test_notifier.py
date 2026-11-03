"""Poster delivery and its text fallback."""

from __future__ import annotations

import pytest

from notifier import TelegramSender


class PhotoBot:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.photos: list[dict] = []
        self.messages: list[dict] = []

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)
        if self.fail:
            raise RuntimeError("Telegram rejected the poster")
        return {"photo": True}

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"message": True}


class TextOnlyBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"message": True}


@pytest.mark.asyncio
async def test_sender_uses_send_photo_for_movie_poster(test_settings, clock):
    bot = PhotoBot()
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)

    await sender.send(1, "alert text", photo_url="https://assets.voxcinemas.com/poster.jpg")

    assert len(bot.photos) == 1
    assert bot.photos[0]["photo"] == "https://assets.voxcinemas.com/poster.jpg"
    assert bot.photos[0]["caption"] == "alert text"
    assert bot.messages == []
    assert sender.sent == 1


@pytest.mark.asyncio
async def test_sender_falls_back_to_text_when_poster_is_rejected(test_settings, clock):
    bot = PhotoBot(fail=True)
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)

    await sender.send(1, "alert text", photo_url="https://assets/poster.jpg")

    assert len(bot.photos) == 1
    assert len(bot.messages) == 1
    assert bot.messages[0]["text"] == "alert text"
    assert sender.sent == 1


@pytest.mark.asyncio
async def test_sender_without_photo_support_still_delivers_text(test_settings, clock):
    bot = TextOnlyBot()
    sender = TelegramSender(bot, test_settings, clock=clock, sleep=clock.sleep)

    await sender.send(1, "alert text", photo_url="https://assets/poster.jpg")

    assert len(bot.messages) == 1
    assert bot.messages[0]["text"] == "alert text"
