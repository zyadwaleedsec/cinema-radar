"""The cinema chosen in the add-watch flow must be the one stored.

The handler used to save ``settings.provider`` (the default cinema) for every
manual watch, so a Premiere or Renaissance pick became a VOX watch.  The
watcher then asked VOX about foreign branch ids and got HTTP 404s.
"""

from __future__ import annotations

import pytest

import i18n
from handlers import watches as watch_flow
from handlers.watches import confirm_add


class FakeProvider:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeProviders:
    def __init__(self, providers: list[FakeProvider]) -> None:
        self._items = {provider.name: provider for provider in providers}

    def get(self, name: str) -> FakeProvider | None:
        return self._items.get(name)

    def names(self) -> list[str]:
        return list(self._items)


class FakeState:
    def __init__(self, data: dict) -> None:
        self.data = dict(data)
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()


class FakeScheduler:
    def __init__(self) -> None:
        self.added: list[tuple[object, dict]] = []

    def add(self, target, **kwargs) -> None:
        self.added.append((target, kwargs))


class FakeDB:
    def __init__(self) -> None:
        self.saved: dict | None = None

    async def get_or_create_user(self, telegram_id: int, watch_limit: int | None = None) -> dict:
        return {"id": 1, "watch_limit": 2, "is_supporter": 0}

    async def add_watch(self, **fields) -> int:
        self.saved = fields
        return 77


class FakeUser:
    id = 12345


class FakeCallback:
    def __init__(self) -> None:
        self.from_user = FakeUser()


def _state_data(provider_name: str, branch_id: str, branch_name: str) -> dict:
    return {
        "provider_name": provider_name,
        "branch": {"id": branch_id, "name": branch_name},
        "movie": {
            "id": "5180.855",
            "name": "Avengers: Doomsday",
            "poster_url": None,
            "duration_minutes": 120,
            "rating": None,
            "language": None,
            "synopsis": None,
            "trailer_url": None,
        },
        "date": "2026-12-17",
        "showtime": {
            "time": "18:15",
            "hall_type": "2D",
            "booking_url": "https://example.test/book",
            "status": "open",
        },
        "scope": "showtime",
        "required_seats": 1,
        "showtimes": [],
        "date_count": 1,
        "showtime_count": 1,
    }


@pytest.mark.asyncio
async def test_manual_watch_keeps_the_selected_cinema(monkeypatch, test_settings):
    async def noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(watch_flow, "_ack", noop)
    monkeypatch.setattr(watch_flow, "edit", noop)

    db = FakeDB()
    scheduler = FakeScheduler()
    state = FakeState(_state_data("premiere", "2", "Premiere Plaza"))

    i18n.set_language("en")
    try:
        await confirm_add(
            callback=FakeCallback(),
            state=state,
            db=db,
            settings=test_settings,
            scheduler=scheduler,
            provider=FakeProvider("vox"),
            providers=FakeProviders([FakeProvider("vox"), FakeProvider("premiere")]),
        )
    finally:
        i18n.set_language("ar")

    assert db.saved is not None
    assert db.saved["provider"] == "premiere"
    assert db.saved["branch_id"] == "2"
    assert scheduler.added[0][0].provider == "premiere"
    assert state.cleared is True
